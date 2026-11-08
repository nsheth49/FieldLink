import httpx
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.db.models import Base,Dataset,Run,Outbox,Message,Job
from app import worker

def setup_worker(tmp_path,monkeypatch):
    engine=create_engine(f'sqlite:///{tmp_path / "worker.db"}')
    Base.metadata.create_all(engine);sessions=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(worker,'engine',engine);monkeypatch.setattr(worker,'Session',sessions)
    with sessions.begin() as db:
        db.add(Dataset(id='ds',name='test',network={'systems':[]},ops={},manifest={},start=0,end=600));db.flush()
        db.add(Run(id='r',dataset_id='ds',mode='replay',cursor=300,paused=1,state={}));db.flush()
        db.add(Outbox(key='once',payload={'run_id':'r','text':'simulation','scenario_ts':300}))
        db.add(Job(key='analyze-once',kind='analyze',payload={'run_id':'r'}))
    return sessions,engine

def test_restart_does_not_duplicate_job_or_outbox(tmp_path,monkeypatch):
    sessions,engine=setup_worker(tmp_path,monkeypatch)
    monkeypatch.setattr(worker,'send',lambda payload:{'delivery':'mock'})
    worker.tick();worker.tick()
    with sessions() as db:
        assert db.get(Run,'r').cursor==300
        assert len(db.scalars(select(Message)).all())==1
        assert db.scalar(select(Job)).status=='done'
        assert db.scalar(select(Outbox)).attempts==1
    engine.dispose()

def test_ambiguous_timeout_never_automatically_resends(tmp_path,monkeypatch):
    sessions,engine=setup_worker(tmp_path,monkeypatch);attempts=[]
    def send(payload):attempts.append(1);raise httpx.ReadTimeout('unknown')
    monkeypatch.setattr(worker,'send',send)
    worker.tick();worker.tick()
    with sessions() as db: assert db.scalar(select(Outbox)).status=='unknown'
    assert attempts==[1];engine.dispose()

def test_unsubmitted_connection_failure_can_retry(tmp_path,monkeypatch):
    sessions,engine=setup_worker(tmp_path,monkeypatch)
    def send(payload):raise httpx.ConnectError('not submitted')
    monkeypatch.setattr(worker,'send',send);worker.tick()
    with sessions.begin() as db:
        out=db.scalar(select(Outbox));assert out.status=='pending';out.next_attempt=0
    monkeypatch.setattr(worker,'send',lambda payload:{'delivery':'mock'});worker.tick()
    with sessions() as db:
        out=db.scalar(select(Outbox));assert out.status=='mock' and out.attempts==2
        assert len(db.scalars(select(Message)).all())==1
    engine.dispose()
