import json,os,secrets,uuid
from pathlib import Path
from sqlalchemy import select
from app.core.config import settings
from app.core.security import hash_password
from app.db.safety import verify_test_target,verify_connected
from app.db.session import SessionLocal
from app.db.seed import run_seed
from app.ingestion.pipeline import RunOptions,run_source
from app.models import FactRecord,InstitutionIdentityReview,Program,Role,StudentProfile,University,User,UserRole
from conftest import _truncate_all
verify_test_target(settings.runtime_database_url)
with SessionLocal() as db:
 verify_connected(db.connection())
 _truncate_all(db)
 run_seed(db)
 identities={}
 for label,role_keys in [('admin',['admin','reviewer']),('student',['student'])]:
  password=secrets.token_urlsafe(24)
  user=User(email=f'browser-{label}-{uuid.uuid4().hex[:8]}@example.com',password_hash=hash_password(password),display_name=f'Isolated {label.title()}')
  db.add(user);db.flush()
  for role_key in role_keys:
   role=db.scalar(select(Role).where(Role.key==role_key));db.add(UserRole(user_id=user.id,role_id=role.id))
  if label=='student':
   db.add(StudentProfile(user_id=user.id,intended_degree_level='masters',academic_degree='bachelors',academic_major='computer science',institution_name='Isolated test profile',grade_system='cgpa',grade_value=8,grade_scale_min=0,grade_scale_max=10,graduation_status='completed',graduation_year=2025,english_test_status='completed',english_test_type='ielts',english_test_overall=7.5,budget_amount=40000,budget_currency='EUR',budget_basis='full_degree_all_in',target_intake_year=2027,target_intake_term='fall',country_mode='open',risk_tolerance='balanced',career_goal='Data science'))
  identities[label]={'email':user.email,'password':password,'id':str(user.id)}
 db.commit()
 ror=run_source('ror',RunOptions(max_records=1,query='Universidad de Almería'),db=db)
 assert ror.status=='succeeded',ror.error
 ual=run_source('ual_masters',RunOptions(max_records=5),db=db)
 assert ual.status=='partial',ual.error
 university=db.scalar(select(University).where(University.external_identifiers['ror'].astext=='003d3xx08'))
 assert university
 identity=db.scalar(select(InstitutionIdentityReview).where(InstitutionIdentityReview.status=='pending',InstitutionIdentityReview.suggested_university_id==university.id))
 assert identity
 website=db.scalar(select(FactRecord).where(FactRecord.entity_id==university.id,FactRecord.fact_key=='official_website_url'))
 demos=list(db.scalars(select(Program.id).where(Program.publication_status=='published').order_by(Program.id).limit(2)))
 identities.update({'university_id':str(university.id),'identity_review_id':str(identity.id),'website_fact_id':str(website.id),'demo_program_ids':list(map(str,demos))})
 out=Path('/private/browser-credentials.json');out.write_text(json.dumps(identities));out.chmod(0o600)
 owner=out.parent.stat();os.chown(out,owner.st_uid,owner.st_gid)
 print('Created isolated admin/reviewer and student accounts; ROR identity and five UAL source candidates await browser review. Credentials stored privately.')
