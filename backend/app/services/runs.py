import hashlib
import json
from sqlalchemy import select, delete
from fastapi import HTTPException
from app.db.models import Dataset, Run, Event, Constraint, Reservation, Job
from app.domain.detector import detect
from app.db.models import Telemetry

def get_run(db, run_id, user=None, lock=False):
    stmt=select(Run).where(Run.id==run_id)
    if lock: stmt=stmt.with_for_update()
    run=db.scalar(stmt)
    if not run: raise HTTPException(404,'Run not found')
    # A restricted identity may see only runs whose entire topology is in scope.
    if user and user.facilities:
        ds=db.get(Dataset,run.dataset_id)
        ids={f['id'] for s in ds.network['systems'] for f in s['facilities']}
        if not ids.issubset(set(user.facilities)): raise HTTPException(403,'Run outside identity scope')
    return run

def analyze(db,run):
    ds=db.get(Dataset,run.dataset_id)
    rows=db.execute(select(Telemetry.ts,Telemetry.asset_id,Telemetry.metric,Telemetry.value).where(Telemetry.dataset_id==ds.id,Telemetry.ts<=run.cursor).order_by(Telemetry.ts)).all()
    state=detect(ds.network,ds.ops,rows,run.cursor)
    run.state=state
    db.execute(delete(Event).where(Event.run_id==run.id))
    for e in state['history']: db.add(Event(id=f'{run.id}:{e["event_id"]}',run_id=run.id,status=e['status'],data=e))
    return state

def fingerprint(db,run):
    constraints=[(c.id,c.truck_id,c.until) for c in db.scalars(select(Constraint).where(Constraint.run_id==run.id)).all()]
    reservations=[(r.id,r.truck_id,r.start,r.end) for r in db.scalars(select(Reservation).where(Reservation.run_id==run.id)).all()]
    data={'cursor':float(run.cursor),'revision':run.revision,'events':run.state.get('events',[]),'constraints':sorted(constraints),'reservations':sorted(reservations)}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def enqueue(db,key,kind,payload):
    if not db.scalar(select(Job).where(Job.key==key)): db.add(Job(key=key,kind=kind,payload=payload))
