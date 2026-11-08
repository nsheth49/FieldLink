import re
from sqlalchemy import select
from app.db.models import Message, Constraint, Dataset, Audit, Job
from app.services.runs import enqueue
from app.integrations.nemotron import reply
from app.services.plans import make_plan

def queue(db,run,user,text):
    message=Message(run_id=run.id,actor=user.id,text=text[:3000],scenario_ts=run.cursor)
    db.add(message); db.flush()
    enqueue(db,f'conversation:{message.id}','conversation',{'run_id':run.id,'user_id':user.id,'message_id':message.id,'text':text[:3000]})
    return {'queued':True,'message_id':message.id,'trace':[]}

def process(db,run,user,text,message_id=None):
    if user.role not in ('operator','supervisor'): raise ValueError('Identity no longer authorized')
    message=db.get(Message,message_id) if message_id else Message(run_id=run.id,actor=user.id,text=text[:3000],scenario_ts=run.cursor)
    if not message_id: db.add(message); db.flush()
    # Strict local demo grammar; never infer historical dates from wall-clock language.
    match=re.fullmatch(r'(\w+_TRUCK_\d+) unavailable for (\d+) scenario minutes',text.strip(),re.I)
    known={f'{sid}_TRUCK_{i+1}' for sid,s in db.get(Dataset,run.dataset_id).ops['systems'].items() for i in range(s['emergency_fleet_size'])}
    if not match or match[1].upper() not in known or not 0<int(match[2])<=1440:
        answer='Please use an exact resource and duration, for example: S2_TRUCK_1 unavailable for 60 scenario minutes. Approval requires the authenticated plan page.'
        trace=[]
    else:
        truck=match[1].upper(); duration=int(match[2]); sid=next(s for s in db.get(Dataset,run.dataset_id).ops['systems'] if truck.startswith(s+'_TRUCK_'))
        db.add(Constraint(run_id=run.id,truck_id=truck,until=run.cursor+duration*60,source=user.id,message_id=message.id)); run.revision+=1; db.flush()
        db.add(Audit(actor=user.id,action='constraint',run_id=run.id,plan_id=None,outcome=f'{truck} unavailable for {duration} scenario minutes'))
        cached={}
        def replan():
            if not cached:
                plan=make_plan(db,run,sid); cached.update(version=plan.version,plan_id=plan.id,total_cost=plan.data['recommended']['total_cost'])
            return cached
        response=reply(text,{'get_incident_context':lambda:{'cursor':run.cursor,'events':run.state.get('events',[])},'get_system_resources':lambda:{'truck_ids':sorted(known)},'compare_response_plans':replan})
        replan()
        answer=f'Confirmed {truck} unavailable for {duration} scenario minutes. '+response['text']; trace=response['trace']
    db.add(Message(run_id=run.id,actor='FieldLink',text=f'[SIMULATION · scenario {int(run.cursor)} UTC epoch] {answer}',scenario_ts=run.cursor))
    return {'text':answer,'trace':trace}
