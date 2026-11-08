import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.api.auth import database, hash_password
from app.db.models import *
from app.services.runs import fingerprint
from app.services.plans import approve

@pytest.fixture
def environment(tmp_path):
    eng=create_engine(f'sqlite:///{tmp_path / "test.db"}',connect_args={'check_same_thread':False,'timeout':30})
    Base.metadata.create_all(eng); sessions=sessionmaker(eng,expire_on_commit=False)
    with sessions.begin() as db:
        db.add_all([User(id=role,role=role,password_hash=hash_password('test-password')) for role in ('supervisor','operator','judge')])
        ds=Dataset(id='dataset',name='test',network={'systems':[]},ops={'systems':{}},manifest={},start=0,end=3600);db.add(ds);db.flush()
        r=Run(id='run',dataset_id='dataset',mode='scenario',cursor=1800,state={'events':[],'history':[]});db.add(r);db.flush()
        db.add(Telemetry(dataset_id='dataset',ts=2400,asset_id='P',metric='flow_bpd',value=999))
        p=Plan(id='plan',run_id=r.id,version=1,fingerprint=fingerprint(db,r),data={'system_id':'S','incident_count':1,'recommended':{'reservations':[{'truck_id':'T1','start':1800,'end':3600}]}});db.add(p)
    def dependency():
        with sessions() as db: yield db
    app.dependency_overrides[database]=dependency
    with TestClient(app,headers={'X-FieldLink-Request':'1'}) as client: yield client,sessions
    app.dependency_overrides.clear();eng.dispose()

def signin(client,role):
    r=client.post('/api/auth/login',json={'username':role,'password':'test-password'});assert r.status_code==200

def test_auth_role_scope_and_unsigned_webhook(environment):
    client,sessions=environment
    assert client.get('/api/runs/run/state').status_code==401
    signin(client,'operator')
    assert client.post('/api/plans/plan/approve',json={'version':1,'fingerprint':'x'}).status_code==403
    assert client.post('/api/webhooks/photon',json={'text':'approve'}).status_code==503
    assert client.post('/api/auth/login',json={'username':'judge','password':'test-password','role':'supervisor'}).status_code==422
    assert client.post('/api/runs/run/messages',json={'text':'T1 until 10'}).json()['trace']==[]
    with sessions() as db: assert not db.scalars(select(Constraint)).all()

def test_cursor_series_seek_and_read_only(environment):
    client,_=environment;signin(client,'judge')
    assert client.get('/api/runs/run/series?asset_id=P&metric=flow_bpd&end=3000').json()==[]
    assert client.post('/api/runs/run/control',json={'action':'seek','value':600}).status_code==403
    signin(client,'supervisor')
    fresh=client.post('/api/runs/run/control',json={'action':'seek','value':600}).json()['id']
    assert fresh!='run'
    s=client.get(f'/api/runs/{fresh}/state').json()
    assert s['cursor']==600 and not s['constraints']

def test_stale_and_exact_approval_deduplicated(environment):
    client,sessions=environment;signin(client,'supervisor')
    with sessions() as db: token=db.get(Plan,'plan').fingerprint
    assert client.post('/api/plans/plan/approve',json={'version':2,'fingerprint':token}).status_code==409
    result=client.post('/api/plans/plan/approve',json={'version':1,'fingerprint':token})
    assert result.status_code==200,result.text
    assert result.json()['status']=='SIMULATED_DISPATCHED'
    assert client.post('/api/plans/plan/approve',json={'version':1,'fingerprint':token}).status_code==409
    with sessions() as db:
        assert len(db.scalars(select(Reservation)).all())==1
        assert len(db.scalars(select(Outbox)).all())==1

def test_constraint_invalidates_fingerprint(environment):
    client,sessions=environment;signin(client,'supervisor')
    with sessions.begin() as db:
        token=db.get(Plan,'plan').fingerprint
        db.add(Constraint(run_id='run',truck_id='T1',until=3000,source='operator'))
    assert client.post('/api/plans/plan/approve',json={'version':1,'fingerprint':token}).status_code==409

def test_concurrent_approval_only_one_commits(environment):
    _,sessions=environment
    with sessions() as db: token=db.get(Plan,'plan').fingerprint
    def attempt():
        from fastapi import HTTPException
        from sqlalchemy import text
        with sessions() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            try: approve(db,'plan',1,token,db.get(User,'supervisor'));db.commit();return 200
            except HTTPException as e: return e.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: assert sorted(pool.map(lambda _:attempt(),range(2)))==[200,409]

def test_origin_and_header_protection(environment):
    client,_=environment
    assert client.post('/api/auth/login',headers={'Origin':'https://untrusted.example'},json={}).status_code==403
