from sqlalchemy import select, func
from fastapi import HTTPException
from app.db.models import Dataset, Plan, Constraint, Reservation, Audit, Outbox, now
from app.domain.planner import compare
from app.services.runs import fingerprint, get_run

def make_plan(db,run,system_id):
    ds=db.get(Dataset,run.dataset_id)
    if system_id not in ds.ops['systems']: raise ValueError('Unknown system')
    constraints=[{'truck_id':c.truck_id,'until':c.until} for c in db.scalars(select(Constraint).where(Constraint.run_id==run.id,Constraint.until>run.cursor))]
    reservations=[{'truck_id':r.truck_id,'start':r.start,'end':r.end} for r in db.scalars(select(Reservation).where(Reservation.run_id==run.id))]
    result=compare(ds.network,ds.ops,run.state,system_id,run.cursor,constraints,reservations)
    version=(db.scalar(select(func.max(Plan.version)).where(Plan.run_id==run.id)) or 0)+1
    for old in db.scalars(select(Plan).where(Plan.run_id==run.id,Plan.status=='PENDING_APPROVAL')):
        if old.data['system_id']==system_id: old.status='SUPERSEDED'
    plan=Plan(run_id=run.id,version=version,fingerprint=fingerprint(db,run),data=result)
    db.add(plan); db.flush()
    return plan

def approve(db,plan_id,version,expected,user):
    # SQLite serializes writers with BEGIN IMMEDIATE in route; PostgreSQL locks run first.
    initial=db.get(Plan,plan_id)
    if not initial: raise HTTPException(404,'Plan not found')
    run=get_run(db,initial.run_id,user,lock=True)
    plan=db.scalar(select(Plan).where(Plan.id==plan_id).with_for_update().execution_options(populate_existing=True))
    db.refresh(run)
    if run.mode!='scenario': raise HTTPException(409,'Create an interactive scenario to approve simulated actions')
    if plan.version!=version or plan.fingerprint!=expected or expected!=fingerprint(db,run) or plan.status!='PENDING_APPROVAL' or plan.expires<now():
        raise HTTPException(409,'Plan is stale or expired. Review a newly calculated plan.')
    if not plan.data['incident_count']: raise HTTPException(409,'No confirmed failures in this plan')
    for r in plan.data['recommended']['reservations']:
        overlap=db.scalar(select(Reservation).where(Reservation.run_id==run.id,Reservation.truck_id==r['truck_id'],Reservation.start<r['end'],Reservation.end>r['start']))
        if overlap: raise HTTPException(409,'Truck reservation conflict')
        db.add(Reservation(plan_id=plan.id,run_id=run.id,**r))
    plan.status='SIMULATED_DISPATCHED'; run.revision+=1
    for action in ('APPROVED','SIMULATED_DISPATCHED'):
        db.add(Audit(actor=user.id,action=action,run_id=run.id,plan_id=plan.id,outcome=f'Exact version {plan.version}'))
    db.add(Outbox(key=f'approval:{plan.id}:{version}',payload={'run_id':run.id,'text':f'Plan {plan.id[:8]} v{version}: simulated dispatch recorded. Please acknowledge in FieldLink.','scenario_ts':run.cursor}))
    return plan
