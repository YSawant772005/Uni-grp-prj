"""Atomic archival, provenance interpretation and protected-data preservation."""
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db.catalogue_reset import digest, execute_reset, plan_reset, snapshot
from app.models import CatalogueArchiveRecord, InstitutionIdentityReview, InstitutionIdentityReviewEvent, InstitutionReview, InstitutionReviewEvent
from app.services import admin
from test_admin import TestInstitutionReview as InstitutionFixture


def _plan(db):
    return plan_reset(db.connection(), operation_id=uuid.uuid4(), backup_path="/private/test-only.dump",
                      backup_sha256="a" * 64, operator="Isolated test", reason="Archive the test catalogue and preserve all original provenance.")


def test_archive_reset_retains_original_associations_and_events(db, make_user, client):
    university, review = InstitutionFixture()._make_institution(db, with_program=True, verified_website=True)
    user = make_user("admin")
    student = make_user("student")
    db.add(InstitutionReviewEvent(review_id=review.id, actor_user_id=user.id, action="defer",
                                 reason="Official evidence requires review.", before_summary={}, after_summary={}))
    claim = university.id
    from app.models import SourceDocument
    document = db.scalar(select(SourceDocument).where(SourceDocument.title == "Institution record"))
    identity = InstitutionIdentityReview(source_id=document.source_id, source_document_id=document.id,
        external_key="reset-source-identity", candidate_payload={"candidate": {"name": university.canonical_name}},
        status="approved", resolved_university_id=university.id)
    db.add(identity)
    db.flush()
    db.add(InstitutionIdentityReviewEvent(review_id=identity.id, actor_user_id=user.id,
        action="approve_link", reason="Official source identity matches.", before_summary={},
        after_summary={"resolved_university_id": str(university.id)}))
    db.commit()
    plan = _plan(db)
    result = execute_reset(db.connection(), plan, confirm=plan["confirmation_sha256"])
    assert result["active_programs"] == result["active_universities"] == 0
    db.expire_all()
    assert db.get(InstitutionReview, review.id).university_id is None
    assert db.get(InstitutionIdentityReview, identity.id).resolved_university_id is None
    assert db.scalar(select(InstitutionReviewEvent.id).where(InstitutionReviewEvent.review_id == review.id))
    assert db.scalar(select(InstitutionIdentityReviewEvent.id).where(InstitutionIdentityReviewEvent.review_id == identity.id))
    original = db.scalar(select(CatalogueArchiveRecord).where(
        CatalogueArchiveRecord.table_name == "institution_identity_reviews",
        CatalogueArchiveRecord.record_key == str(identity.id)))
    assert original.payload["resolved_university_id"] == str(claim)
    assert original.row_sha256 == digest(original.payload)
    assert admin.institution_review_queue(db)["items"] == []
    assert admin.identity_review_queue(db, status="approved")["items"] == []
    assert execute_reset(db.connection(), plan, confirm=plan["confirmation_sha256"])["already_applied"] is True
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("DELETE FROM catalogue_archive_records WHERE record_key=:key"), {"key": str(identity.id)})
    db.commit()
    from app.core.security import create_access_token
    url = f"/api/v1/admin/catalogue-archives/{plan['operation_id']}"
    assert client.get(url).status_code == 401
    student_headers = {"Authorization": "Bearer " + create_access_token(str(student.id), ["student"])}
    assert client.get(url, headers=student_headers).status_code == 403
    headers = {"Authorization": "Bearer " + create_access_token(str(user.id), ["admin"])}
    response = client.get("/api/v1/admin/catalogue-archives", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == plan["operation_id"]
    response = client.get(url, params={"table_name": "institution_identity_reviews"}, headers=headers)
    assert response.status_code == 200 and response.json()["total_items"] == 1
    assert response.json()["items"][0]["payload"]["resolved_university_id"] == str(claim)


def test_wrong_confirmation_or_changed_database_is_refused(db):
    plan = _plan(db)
    before = snapshot(db.connection())
    with pytest.raises(RuntimeError, match="confirmation"):
        execute_reset(db.connection(), plan, confirm="incorrect")
    db.execute(text("UPDATE universities SET canonical_name=canonical_name || ' changed'"))
    with pytest.raises(RuntimeError, match="changed since preflight"):
        execute_reset(db.connection(), plan, confirm=plan["confirmation_sha256"])
    assert db.scalar(text("SELECT count(*) FROM catalogue_reset_operations")) == 0
    assert db.scalar(text("SELECT count(*) FROM universities")) == before["universities"]["count"]


def test_reset_rolls_back_archive_and_deletions_together(db):
    plan = _plan(db)
    before = snapshot(db.connection())
    with pytest.raises(RuntimeError, match="injected"):
        with db.begin_nested():
            execute_reset(db.connection(), plan, confirm=plan["confirmation_sha256"])
            raise RuntimeError("injected failure before commit")
    assert snapshot(db.connection()) == before
    assert db.scalar(text("SELECT count(*) FROM catalogue_archive_records")) == 0


def test_student_catalogue_associations_block_reset(db, make_user):
    from app.models import Program, SavedProgram
    user = make_user()
    program = db.scalar(select(Program))
    db.add(SavedProgram(user_id=user.id, program_id=program.id))
    db.flush()
    with pytest.raises(RuntimeError, match="protected student"):
        _plan(db)
