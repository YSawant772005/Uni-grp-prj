"""Exact programme plans reuse existing identity, evidence and publication gates."""
import json
from urllib.parse import parse_qs,urlsplit

import pytest
from sqlalchemy import func,select,text

from app.ingestion import program_import as bulk
from app.ingestion.http import HttpResult
from app.models import Program,ProgramIdentifier,InstitutionReview,FactEvidence,FactRecord,FactVersion,SourceDocument,University
from test_duo_rio_adapter import _row
from test_monmaster_adapter import _row as french_row


def snapshot(tmp_path,monkeypatch,count,source='duo_rio_masters',rows=None,name='snapshot'):
    import uuid
    values = rows or [_row(offering=str(uuid.UUID(int=i+1)),NAAM_LANG=f'Programme {i}',
        ONDERWIJSAANBIEDERID=f'PROVIDER{i%5}',ONDERWIJSAANBIEDER_NAAM=f'Official Test Institution {i%5}') for i in range(count)]
    class Network:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,**kwargs):
            query=parse_qs(urlsplit(url).query);offset=int(query.get('offset',['0'])[0]);limit=int(query['limit'][0])
            content={'success':True,'result':{'records':values[offset:offset+limit],'total':len(values)}} if source=='duo_rio_masters' else {'results':values[offset:offset+limit],'total_count':len(values)}
            return HttpResult(url=url,status=200,content=json.dumps(content,ensure_ascii=False).encode())
    monkeypatch.setattr(bulk,'Fetcher',Network)
    metadata={'success':True,'result':{'name':'ho_opleidingsoverzicht','license_id':'cc-by','resources':[{'id':'ffffa7ad-e6a2-4ba7-9fc2-a09df4128555','last_modified':'2026-10-21T02:35:16'}]}} if source=='duo_rio_masters' else {'dataset_id':'fr-esr-mon_master','metas':{'default':{'license':'Licence Ouverte v2.0','modified':'2025-12-04T08:00:00+00:00'}}}
    meta=tmp_path/f'{name}-metadata.json';meta.write_text(json.dumps(metadata))
    result=bulk.capture(source,tmp_path/name,meta,limit=max(count,1),pages=100)
    return result['snapshot']


@pytest.mark.parametrize('count',[100,500])
def test_exact_scale_import_repeat_and_visibility(db,client,tmp_path,monkeypatch,count):
    source=snapshot(tmp_path,monkeypatch,count)
    backup=tmp_path/'isolated-fixture.dump';backup.write_bytes(b'test-only backup fixture')
    before=bulk.existing_state(db)
    approved=bulk.plan(db,[source],backup)
    assert approved['expected_programmes']==count and approved['expected_new_institutions']==5
    result=bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    assert result[0]['entity_counts']['programs_created']==count
    assert bulk.existing_state(db,before)==before
    assert db.scalar(select(func.count()).select_from(ProgramIdentifier).where(ProgramIdentifier.source_key=='duo_rio_masters'))==count
    assert db.scalar(select(func.count()).select_from(InstitutionReview).where(InstitutionReview.status=='approved'))==0
    assert client.get('/api/v1/programs').json()['total_items']==9
    from app.services.admin import institution_review_detail
    from sqlalchemy import event
    university=db.scalar(select(University).where(University.canonical_name=='Official Test Institution 0'))
    query_count=[0]
    def count_query(*args):query_count[0]+=1
    event.listen(db.get_bind(),'before_cursor_execute',count_query)
    try: review=institution_review_detail(db,university.id)
    finally:event.remove(db.get_bind(),'before_cursor_execute',count_query)
    assert review['program_count']==count//5 and review['status']=='pending'
    assert query_count[0]<80, 'Institution evidence review must batch programme/fact queries'
    from app.services.admin import institution_review_queue
    query_count[0]=0
    event.listen(db.get_bind(),'before_cursor_execute',count_query)
    try: queue=institution_review_queue(db,page_size=1)
    finally:event.remove(db.get_bind(),'before_cursor_execute',count_query)
    assert queue['total_items']==5 and len(queue['items'])==1
    assert queue['stage_counts']=={'discovery':0,'evidence_collection':5,'ready_for_review':0}
    assert query_count[0]<80, 'Off-page institutions without a website cannot be ready; avoid loading their facts'
    totals=lambda:(db.scalar(select(func.count()).select_from(Program)),db.scalar(select(func.count()).select_from(FactRecord)),db.scalar(select(func.count()).select_from(FactVersion)),db.scalar(select(func.count()).select_from(FactEvidence)))
    original=totals()
    repeat=bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    assert repeat[0]['entity_counts']['programs_created']==0 and totals()==original


def test_tampered_snapshot_or_confirmation_refused_without_writes(db,tmp_path,monkeypatch):
    source=snapshot(tmp_path,monkeypatch,2)
    backup=tmp_path/'backup';backup.write_bytes(b'isolated fixture')
    approved=bulk.plan(db,[source],backup)
    with pytest.raises(ValueError,match='confirmation'):
        bulk.apply(db.get_bind(),approved,'wrong')
    path,manifest=bulk.load(source)
    (path.parent/manifest['requests'][0]['filename']).write_bytes(b'{}')
    with pytest.raises(ValueError,match='checksum'):
        bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    assert db.scalar(select(func.count()).select_from(ProgramIdentifier).where(ProgramIdentifier.source_key=='duo_rio_masters'))==0


def test_any_partial_source_failure_rolls_back_all_planned_additions(db,tmp_path,monkeypatch):
    source=snapshot(tmp_path,monkeypatch,100)
    backup=tmp_path/'backup';backup.write_bytes(b'isolated fixture')
    approved=bulk.plan(db,[source],backup)
    from app.ingestion import persist
    original=persist.upsert_program
    calls=0
    def fail(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==51:raise RuntimeError('injected programme write failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(persist,'upsert_program',fail)
    before=bulk.existing_state(db)
    with pytest.raises(ValueError,match='exact plan'):
        bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    assert bulk.existing_state(db)==before


def test_archived_provider_is_held_without_reconciliation(db,tmp_path,monkeypatch):
    import uuid
    from app.models import CatalogueArchiveRecord,CatalogueResetOperation
    from app.db.catalogue_reset import digest
    operation=CatalogueResetOperation(id=uuid.uuid4(),operator='Test',reason='Historical fixture',original_revision='85b2e4a6c910',backup_path='/fixture',backup_sha256='a'*64,manifest={})
    db.add(operation);db.flush()
    payload={'id':str(uuid.uuid4()),'external_identifiers':{'rio_provider_id':'PROVIDER0'}}
    db.add(CatalogueArchiveRecord(operation_id=operation.id,table_name='universities',record_key=payload['id'],payload=payload,row_sha256=digest(payload)));db.commit()
    source=snapshot(tmp_path,monkeypatch,5)
    selected=bulk.selection(db,source)
    assert len(selected['programmes'])==4 and len(selected['held_institutions'])==1


def test_differing_source_owners_never_use_first_duplicate(db,tmp_path,monkeypatch):
    import uuid
    key=str(uuid.uuid4())
    source=snapshot(tmp_path,monkeypatch,2,rows=[_row(offering=key),_row(offering=key,provider='OTHER')])
    selected=bulk.selection(db,source)
    assert selected['programmes']=={} and len(selected['source_identity_conflicts'])==1


def test_french_campaign_and_multi_award_rows_are_never_misclassified(db,tmp_path,monkeypatch):
    rows=[french_row('valid'),french_row('old',session='2024'),french_row('joint',track='Double diplôme Franco-Italien')]
    source=snapshot(tmp_path,monkeypatch,3,source='fr_monmaster',rows=rows)
    selected=bulk.selection(db,source)
    assert set(selected['programmes'])=={'fr-monmaster:ifc:valid'}
    documents=list(bulk.batches(source))
    assert documents[0].document.academic_period=='2025'
    assert documents[0].document.retrieval_attempt_count==0
    assert documents[0].document.retrieved_at is not None


def test_provider_specific_cache_is_not_shared(monkeypatch,tmp_path):
    from app.ingestion.adapters.duo_rio import DuoRioAdapter
    from app.ingestion.adapters.base import RunContext
    from test_duo_rio_adapter import Fetcher,_payload
    monkeypatch.setenv('INGESTION_CACHE_DIR',str(tmp_path))
    list(DuoRioAdapter().iter_batches(RunContext(fetcher=Fetcher([_payload([_row(provider='PROVIDER_A')])]),max_records=1,query='PROVIDER_A')))
    with pytest.raises(ValueError,match='cache is missing'):
        list(DuoRioAdapter().iter_batches(RunContext(fetcher=Fetcher([]),max_records=1,query='PROVIDER_B',offline=True)))


def test_known_discovery_holdouts_remain_visible_without_rejecting_eligible_additions(db,tmp_path,monkeypatch):
    rows=[_row(),_row(grade='BACHELOR'),_row(SAMENWERKEND_MET='Partner university')]
    source=snapshot(tmp_path,monkeypatch,3,rows=rows)
    backup=tmp_path/'backup';backup.write_bytes(b'isolated fixture')
    approved=bulk.plan(db,[source],backup)
    assert approved['expected_programmes']==1
    result=bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    assert result[0]['entity_counts']['programs_created']==1
    assert result[0]['quality_counts']['skipped']==2
    assert result[0]['status']=='partial' and result[0]['error'] is None


def test_shared_board_subunits_require_identity_review_instead_of_duplicate_universities(db,tmp_path,monkeypatch):
    import uuid
    rows=[_row(offering=str(uuid.uuid4()),provider='FACULTY1',ONDERWIJSAANBIEDER_NAAM='University Faculty One',ONDERWIJSBESTUURID='BOARD1'),
          _row(offering=str(uuid.uuid4()),provider='FACULTY2',ONDERWIJSAANBIEDER_NAAM='University Faculty Two',ONDERWIJSBESTUURID='BOARD1'),
          _row(offering=str(uuid.uuid4()),provider='INDEPENDENT',ONDERWIJSAANBIEDER_NAAM='Independent Institution',ONDERWIJSBESTUURID='BOARD2')]
    source=snapshot(tmp_path,monkeypatch,3,rows=rows)
    selected=bulk.selection(db,source)
    assert len(selected['held_institutions'])==2 and len(selected['programmes'])==1
    assert {i['name'] for i in selected['institutions'].values()}=={'Independent Institution'}


def test_multi_page_dry_run_keeps_new_source_until_outer_rollback(db,tmp_path,monkeypatch):
    from app.ingestion.pipeline import run_source,RunOptions
    from app.ingestion.registry import _ADAPTERS
    source=snapshot(tmp_path,monkeypatch,150)
    old=_ADAPTERS['duo_rio_masters']
    _ADAPTERS['duo_rio_masters']=bulk.SelectedAdapter(source,{f'duo:offering:{__import__("uuid").UUID(int=i+1)}' for i in range(150)})
    before=bulk.existing_state(db)
    try: result=run_source('duo_rio_masters',RunOptions(max_records=100,dry_run=True,offline=True),db=db)
    finally:_ADAPTERS['duo_rio_masters']=old
    assert result.status=='dry_run' and result.counters.programs_created==150
    assert result.counters.http_failures==[]
    assert bulk.existing_state(db)==before


def test_database_source_permission_cannot_be_overwritten_by_registry_defaults(db,tmp_path,monkeypatch):
    from app.ingestion.persist import ensure_source
    from app.ingestion.registry import get_spec
    source=snapshot(tmp_path,monkeypatch,1)
    row=ensure_source(db,get_spec('duo_rio_masters'))
    row.allowed_use_policy='prohibited_automated_fetch';db.commit()
    with pytest.raises(ValueError,match='policy forbids'):
        bulk.selection(db,source)


# --------------------------------------------------------------- mixed national sources

def test_mixed_source_plan_keeps_national_offerings_and_identities_separate(db,tmp_path,monkeypatch):
    import uuid
    dutch=[_row(offering=str(uuid.UUID(int=i+1)),ONDERWIJSAANBIEDERID='NLPROV1',
        ONDERWIJSAANBIEDER_NAAM='Shared Name University',NAAM_LANG=f'Dutch Programme {i}') for i in range(10)]
    french=[french_row(ifc=f'IFC{i}',track=f'Track {i}',mention=f'MENTION {i}',
        eta_uai='0751717J',eta_nom='Shared Name University') for i in range(8)]
    dutch_source=snapshot(tmp_path,monkeypatch,10,rows=dutch,name='dutch')
    french_source=snapshot(tmp_path,monkeypatch,8,source='fr_monmaster',rows=french,name='french')
    backup=tmp_path/'backup';backup.write_bytes(b'isolated fixture')
    approved=bulk.plan(db,[dutch_source,french_source],backup)
    assert approved['expected_programmes']==18
    assert approved['expected_new_institutions']==2
    keys={key for source in approved['sources'] for key in source['programmes']}
    assert sum(key.startswith('duo:offering:') for key in keys)==10
    assert sum(key.startswith('fr-monmaster:ifc:') for key in keys)==8
    # The two national sources use disjoint identifier namespaces.
    namespaces={source['source_key']:{tuple(sorted(i['identifiers'])) for i in source['institutions'].values()}
        for source in approved['sources']}
    assert namespaces['duo_rio_masters']=={('rio_provider_id',)}
    assert namespaces['fr_monmaster']=={('uai',)}
    result=bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    assert [entry['entity_counts']['programs_created'] for entry in result]==[10,8]
    assert db.scalar(select(func.count()).select_from(ProgramIdentifier)
        .where(ProgramIdentifier.source_key=='duo_rio_masters'))==10
    assert db.scalar(select(func.count()).select_from(ProgramIdentifier)
        .where(ProgramIdentifier.source_key=='fr_monmaster'))==8
    # An identical institution name in two countries is not merged into one record.
    names=set(db.execute(select(University.canonical_name,University.country_code)
        .where(University.canonical_name=='Shared Name University')).all())
    assert names=={('Shared Name University','NL'),('Shared Name University','FR')}
    assert db.scalar(select(func.count()).select_from(University)
        .where(University.canonical_name=='Shared Name University'))==2
    # Every imported offering is an unpublished candidate at a pending institution.
    assert db.scalar(select(func.count()).select_from(Program)
        .where(Program.publication_status=='candidate'))==18
    assert db.scalar(select(func.count()).select_from(InstitutionReview)
        .where(InstitutionReview.status=='pending'))==2
    assert db.scalar(select(func.count()).select_from(InstitutionReview)
        .where(InstitutionReview.status=='approved'))==0
    # Replaying the same two-source plan adds nothing.
    repeat=bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    assert [entry['entity_counts']['programs_created'] for entry in repeat]==[0,0]


def test_second_provider_with_an_identical_name_is_held_instead_of_merged(db,tmp_path,monkeypatch):
    import uuid
    first=[_row(offering=str(uuid.UUID(int=i+1)),ONDERWIJSAANBIEDERID='PROVA',
        ONDERWIJSAANBIEDER_NAAM='Shared Name University',NAAM_LANG=f'Programme {i}') for i in range(2)]
    second=[_row(offering=str(uuid.UUID(int=3)),ONDERWIJSAANBIEDERID='PROVB',
        ONDERWIJSAANBIEDER_NAAM='Shared Name University',NAAM_LANG='Programme Two')]
    first_source=snapshot(tmp_path,monkeypatch,2,rows=first,name='first')
    backup=tmp_path/'backup';backup.write_bytes(b'isolated fixture')
    approved=bulk.plan(db,[first_source],backup)
    bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    second_source=snapshot(tmp_path,monkeypatch,1,rows=second,name='second')
    selected=bulk.selection(db,second_source)
    assert selected['programmes']=={}
    assert len(selected['held_institutions'])==1
    assert 'name_country' in selected['held_institutions'][
        'duo:rio-provider:PROVB']['reason']
    # The existing canonical institution is not relabelled or duplicated.
    assert db.scalar(select(func.count()).select_from(University)
        .where(University.canonical_name=='Shared Name University'))==1


# --------------------------------------------------------------- review queue at scale

def test_review_queue_pagination_is_deterministic_and_stage_filtered_at_scale(db,tmp_path,monkeypatch):
    import uuid
    from sqlalchemy import event
    from app.services.admin import institution_review_queue
    rows=[_row(offering=str(uuid.UUID(int=i+1)),ONDERWIJSAANBIEDERID=f'PROV{i%20}',
        ONDERWIJSAANBIEDER_NAAM=f'Institution {i%20}',NAAM_LANG=f'Programme {i}') for i in range(100)]
    source=snapshot(tmp_path,monkeypatch,100,rows=rows)
    backup=tmp_path/'backup';backup.write_bytes(b'isolated fixture')
    approved=bulk.plan(db,[source],backup)
    bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    queue=institution_review_queue(db,page_size=5)
    assert queue['total_items']==20 and queue['total_pages']==4
    assert queue['stage_counts']=={'discovery':0,'evidence_collection':20,'ready_for_review':0}
    seen=[]
    for page in (1,2,3,4):
        chunk=institution_review_queue(db,page=page,page_size=5)
        assert chunk['page']==page and len(chunk['items'])==5
        seen.extend(item['university_id'] for item in chunk['items'])
    assert len(set(seen))==20
    # Ordering is stable, so pagination never repeats or skips an institution.
    first=institution_review_queue(db,page=1,page_size=5)
    assert first==institution_review_queue(db,page=1,page_size=5)
    # Stage filtering happens before pagination.
    assert institution_review_queue(db,stage='ready_for_review')['total_items']==0
    assert institution_review_queue(db,stage='discovery')['total_items']==0
    assert institution_review_queue(db,stage='evidence_collection')['total_items']==20
    # The queue fast path must agree with each institution's own computed stage.
    for item in queue['items']:
        stage=item['workflow_stage']
        assert stage not in ('discovery','ready_for_review')
        assert stage in ('program_evidence_needed','website_evidence_needed','institution_evidence_needed')
    # Institutions without a canonical website are staged without loading their facts.
    queries=[0]
    def count_query(*args):queries[0]+=1
    event.listen(db.get_bind(),'before_cursor_execute',count_query)
    try:institution_review_queue(db,page=1,page_size=5)
    finally:event.remove(db.get_bind(),'before_cursor_execute',count_query)
    assert queries[0]<200,'Off-page institutions must not be serialized as review evidence'


# --------------------------------------------------------------- preservation and resume

def test_existing_catalogue_publication_and_archive_state_survive_the_import(db,client,tmp_path,monkeypatch):
    import uuid
    before_programs={row[0]:(row[1],row[2],row[3]) for row in db.execute(
        select(Program.id,Program.canonical_name,Program.slug,Program.publication_status)).all()}
    before_universities={row[0]:(row[1],row[2]) for row in db.execute(
        select(University.id,University.canonical_name,University.country_code)).all()}
    before_archives=db.scalar(select(func.count()).select_from(
        __import__('app.models',fromlist=['CatalogueArchiveRecord']).CatalogueArchiveRecord))
    rows=[_row(offering=str(uuid.UUID(int=i+1)),ONDERWIJSAANBIEDERID=f'PROV{i%3}',
        ONDERWIJSAANBIEDER_NAAM=f'Institution {i%3}',NAAM_LANG=f'Programme {i}') for i in range(20)]
    source=snapshot(tmp_path,monkeypatch,20,rows=rows)
    backup=tmp_path/'backup';backup.write_bytes(b'isolated fixture')
    approved=bulk.plan(db,[source],backup)
    bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    after_programs={row[0]:(row[1],row[2],row[3]) for row in db.execute(
        select(Program.id,Program.canonical_name,Program.slug,Program.publication_status)).all()}
    for identifier,value in before_programs.items():
        assert after_programs[identifier]==value
    after_universities={row[0]:(row[1],row[2]) for row in db.execute(
        select(University.id,University.canonical_name,University.country_code)).all()}
    for identifier,value in before_universities.items():
        assert after_universities[identifier]==value
    assert db.scalar(select(func.count()).select_from(
        __import__('app.models',fromlist=['CatalogueArchiveRecord']).CatalogueArchiveRecord))==before_archives
    # New candidates never enter the public catalogue and nothing new is published.
    assert client.get('/api/v1/programs').json()['total_items']==len(before_programs)
    new=[row[0] for row in db.execute(select(Program.id)
        .where(~Program.id.in_(list(before_programs)))).all()]
    assert len(new)==20
    assert db.scalar(select(func.count()).select_from(Program)
        .where(Program.publication_status=='published'))==len(before_programs)
    for identifier in new:
        assert client.get(f'/api/v1/programs/{identifier}').status_code==404


def test_interrupted_import_leaves_nothing_behind_and_the_exact_plan_reapplies(db,tmp_path,monkeypatch):
    from app.ingestion import persist
    source=snapshot(tmp_path,monkeypatch,100)
    backup=tmp_path/'backup';backup.write_bytes(b'isolated fixture')
    approved=bulk.plan(db,[source],backup)
    baseline=db.scalar(select(func.count()).select_from(University))
    baseline_documents=db.scalar(select(func.count()).select_from(SourceDocument))
    original=persist.upsert_program
    calls={'n':0,'armed':True}
    def fail(*args,**kwargs):
        calls['n']+=1
        if calls['armed'] and calls['n']==51:
            raise RuntimeError('injected interruption')
        return original(*args,**kwargs)
    monkeypatch.setattr(persist,'upsert_program',fail)
    with pytest.raises(ValueError,match='exact plan'):
        bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    # The interrupted operation left no partial catalogue, fact or evidence state.
    assert db.scalar(select(func.count()).select_from(ProgramIdentifier)
        .where(ProgramIdentifier.source_key=='duo_rio_masters'))==0
    assert db.scalar(select(func.count()).select_from(University))==baseline
    assert db.scalar(select(func.count()).select_from(SourceDocument))==baseline_documents
    assert bulk.existing_state(db,approved['original_rows'])==approved['original_rows']
    # Re-applying the same approved plan completes the exact planned addition.
    calls['armed']=False
    result=bulk.apply(db.get_bind(),approved,approved['confirmation_sha256'])
    assert result[0]['entity_counts']['programs_created']==100
    assert db.scalar(select(func.count()).select_from(ProgramIdentifier)
        .where(ProgramIdentifier.source_key=='duo_rio_masters'))==100
