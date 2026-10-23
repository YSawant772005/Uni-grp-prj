"""Read-only PostgreSQL programme coverage; no estimates or reference inflation."""
import argparse
import json

from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.safety import verify_development_target,verify_recovery_target,verify_test_target
from app.models import Program
from app.services.program_evidence import official_program_page


def report(db):
    def scalar(sql):return db.scalar(text(sql))
    def rows(sql):return [dict(r) for r in db.execute(text(sql)).mappings()]
    real = "JOIN universities u ON u.id=p.university_id WHERE p.degree_level='masters' AND COALESCE(u.external_identifiers->>'demo_fixture','false') <> 'true'"
    pages = db.scalars(select(Program).where(Program.official_program_url.is_not(None))).all()
    return {
        'database':scalar('SELECT current_database()'),
        'revision':scalar('SELECT version_num FROM alembic_version'),
        'ror_reference_rows':scalar('SELECT count(*) FROM directory_institutions'),
        'canonical_active_institutions':scalar('SELECT count(*) FROM universities'),
        'active_institution_reviews':rows("SELECT status,count(*) AS count FROM institution_reviews WHERE university_id IS NOT NULL AND archived_operation_id IS NULL GROUP BY status ORDER BY status"),
        'distinct_real_masters_programme_offerings':scalar('SELECT count(*) FROM programs p '+real),
        'by_country_source':rows('SELECT p.country_code,i.source_key,count(DISTINCT p.id) AS programmes FROM programs p JOIN program_identifiers i ON i.program_id=p.id '+real+' GROUP BY p.country_code,i.source_key ORDER BY p.country_code,i.source_key'),
        'programme_identities':rows('SELECT claim_status,count(*) AS count,count(DISTINCT program_id) AS programmes FROM program_identifiers GROUP BY claim_status'),
        'verified_official_programme_pages':sum(official_program_page(db,p)['status']=='verified' for p in pages),
        'publication':rows('SELECT publication_status,count(*) AS count FROM programs p '+real+' GROUP BY publication_status ORDER BY publication_status'),
        'historical_2025_programmes':scalar("SELECT count(DISTINCT p.id) FROM programs p JOIN program_identifiers i ON i.program_id=p.id JOIN source_documents d ON d.id=i.source_document_id WHERE i.source_key='fr_monmaster' AND d.academic_period='2025'"),
        'duo_validity_as_reported':rows("""SELECT CASE WHEN v.value_json->>'valid_from' IS NULL THEN 'unknown_start'
            WHEN (v.value_json->>'valid_from')::date > CURRENT_DATE THEN 'future_registry_offering'
            WHEN v.value_json->>'valid_to' IS NOT NULL AND (v.value_json->>'valid_to')::date < CURRENT_DATE THEN 'ended_registry_offering'
            ELSE 'unexpired_registry_offering' END AS applicability,count(*) AS count
            FROM fact_records f JOIN fact_versions v ON v.id=f.current_version_id
            WHERE f.entity_type='program' AND f.fact_key='offering_validity_period' GROUP BY 1 ORDER BY 1"""),
        'academic_period_unknown_programmes':scalar("SELECT count(*) FROM programs p WHERE NOT EXISTS (SELECT 1 FROM program_identifiers i JOIN source_documents d ON d.id=i.source_document_id WHERE i.program_id=p.id AND d.academic_period IS NOT NULL)"),
        'missing_academic_values':{
            'tuition':scalar("SELECT count(*) FROM programs p "+real+" AND NOT EXISTS (SELECT 1 FROM program_fees f WHERE f.program_id=p.id AND f.fee_type='tuition' AND f.amount IS NOT NULL)"),
            'admissions':scalar('SELECT count(*) FROM programs p '+real+' AND NOT EXISTS (SELECT 1 FROM admission_requirements r WHERE r.program_id=p.id)'),
            'application_deadlines':scalar('SELECT count(*) FROM programs p '+real+' AND NOT EXISTS (SELECT 1 FROM program_intakes i WHERE i.program_id=p.id AND i.application_deadline IS NOT NULL)'),
            'duration':scalar('SELECT count(*) FROM programs p '+real+' AND p.duration_min_months IS NULL AND p.duration_max_months IS NULL')},
        'conflicted_programme_facts':scalar("SELECT count(*) FROM fact_records WHERE entity_type='program' AND current_status='conflicted'"),
        'duplicate_accepted_programme_identifiers':scalar("SELECT count(*) FROM (SELECT source_key,normalized_external_key FROM program_identifiers WHERE claim_status='accepted' GROUP BY 1,2 HAVING count(*)>1) q"),
        'jobs_by_source_status':rows("SELECT COALESCE(s.metadata->>'adapter_key','manual') AS source,j.status,count(*) AS count FROM ingestion_jobs j LEFT JOIN sources s ON s.id=j.source_id GROUP BY 1,2 ORDER BY 1,2"),
        'archive_records':scalar('SELECT count(*) FROM catalogue_archive_records'),
        'facts':scalar('SELECT count(*) FROM fact_records'),
        'versions':scalar('SELECT count(*) FROM fact_versions'),
        'evidence':scalar('SELECT count(*) FROM fact_evidence'),
        'source_documents':scalar('SELECT count(*) FROM source_documents'),
        'notice':'Counts distinguish source-identified offerings from unique qualification families. Unexpired registry validity is not an open application period; academic-year coverage may be unknown.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',choices=('development','recovery','test'),required=True)
    args=parser.parse_args()
    {'development':verify_development_target,'recovery':verify_recovery_target,'test':verify_test_target}[args.target](settings.database_url)
    engine=create_engine(settings.database_url)
    with Session(engine) as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        print(json.dumps(report(db),ensure_ascii=False,default=str,indent=2))


if __name__=='__main__':main()
