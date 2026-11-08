import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, text, func
from app.config import settings
from app.db import engine
from app.db.models import *
from app.api.auth import database, current_user, supervisor, operator, verify
from app.services.runs import get_run, enqueue
from app.services.plans import approve
from app.services.conversations import queue
from app.domain.ingest import import_files
from app.integrations.photon import status as photon_status

@asynccontextmanager
async def lifespan(app):
    if settings.app_env!='development' and (len(settings.session_secret)<32 or engine.dialect.name=='sqlite'):
        raise RuntimeError('Production requires PostgreSQL and a strong SESSION_SECRET')
    yield

app=FastAPI(title='FieldLink',version='0.1.0',lifespan=lifespan)

@app.middleware('http')
async def security(request:Request,call_next):
    if request.method in {'POST','PUT','DELETE','PATCH'} and request.url.path!='/api/webhooks/photon':
        origin=request.headers.get('origin')
        allowed={settings.app_public_url.rstrip('/')}
        if settings.app_env=='development': allowed.update({'http://localhost:5173','http://127.0.0.1:5173'})
        if origin and origin.rstrip('/') not in allowed:
            return Response('Origin not allowed',403)
        if request.headers.get('x-fieldlink-request')!='1': return Response('Missing request protection',403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    return response

class Strict(BaseModel): model_config=ConfigDict(extra='forbid')
class Login(Strict):
    username:str=Field(max_length=100)
    password:str=Field(max_length=300)
class RunCreate(Strict):
    dataset_id:str
    mode:Literal['snapshot','replay','scenario']='snapshot'
    start_cursor:float|None=None
class Control(Strict):
    action:Literal['pause','resume','speed','seek']
    value:float|None=None
class PlanCreate(Strict): system_id:str
class Approval(Strict):
    version:int
    fingerprint:str
class ConstraintCreate(Strict):
    truck_id:str
    unavailable_minutes:int=Field(gt=0,le=1440)
class TextMessage(Strict): text:str=Field(min_length=1,max_length=3000)

@app.get('/api/health')
def health(db=Depends(database)):
    db.execute(text('SELECT 1'))
    return {'status':'ok','database':'local SQLite fallback' if engine.dialect.name=='sqlite' else 'PostgreSQL (Tiger usage unverified)',
            'ai':{'mode':settings.ai_mode,'ready':bool(settings.nvidia_api_key) if settings.ai_mode!='mock' else True,
                  'configured':bool(settings.nvidia_api_key),'model':settings.nvidia_model,
                  'detail':'Live mode; readiness indicates configuration, not current provider availability' if settings.ai_mode=='live' else 'Local mock; no NVIDIA request'},
            'messaging':photon_status(),'simulation':True}

@app.post('/api/auth/login')
def login(body:Login,response:Response,db=Depends(database)):
    user=db.get(User,body.username)
    if not user or not verify(body.password,user.password_hash): raise HTTPException(401,'Invalid credentials')
    token=secrets.token_urlsafe(32)
    db.add(AuthSession(id=hashlib.sha256(token.encode()).hexdigest(),user_id=user.id,expires=now()+8*3600)); db.commit()
    response.set_cookie('fieldlink_session',token,httponly=True,samesite='strict',secure=settings.app_env!='development',max_age=28800)
    return {'id':user.id,'role':user.role}

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,user=Depends(current_user),db=Depends(database)):
    session=db.get(AuthSession,hashlib.sha256(request.cookies.get('fieldlink_session','').encode()).hexdigest())
    if session: db.delete(session); db.commit()
    response.delete_cookie('fieldlink_session'); return {'ok':True}

@app.get('/api/auth/me')
def me(user=Depends(current_user)): return {'id':user.id,'role':user.role}

@app.get('/api/datasets')
def datasets(user=Depends(current_user),db=Depends(database)):
    return [{'id':d.id,'name':d.name,'start':d.start,'end':d.end,'manifest':d.manifest} for d in db.scalars(select(Dataset))]

@app.post('/api/datasets')
async def upload(files:list[UploadFile]=File(...),user=Depends(supervisor),db=Depends(database)):
    if len(files)!=3 or len({f.filename for f in files})!=3: raise HTTPException(422,'Upload exactly three unique files')
    contents={}
    for f in files:
        if f.filename not in {'network.json','ops.json','telemetry.csv'}: raise HTTPException(422,'Unrecognized file')
        data=await f.read(100*1024*1024+1)
        if len(data)>100*1024*1024: raise HTTPException(413,'File exceeds 100 MB')
        contents[f.filename]=data
    try: did,report=import_files(db,contents,'Uploaded dataset'); db.commit()
    except (ValueError,KeyError,TypeError) as error: db.rollback(); raise HTTPException(422,str(error))
    return {'dataset_id':did,'validation_report':report}

@app.get('/api/runs')
def runs(user=Depends(current_user),db=Depends(database)):
    result=[]
    for r in db.scalars(select(Run)):
        try: get_run(db,r.id,user)
        except HTTPException: continue
        result.append({'id':r.id,'dataset_id':r.dataset_id,'mode':r.mode,'cursor':r.cursor})
    return result

@app.post('/api/runs')
def create_run(body:RunCreate,user=Depends(supervisor),db=Depends(database)):
    ds=db.get(Dataset,body.dataset_id)
    if not ds: raise HTTPException(404,'Dataset not found')
    cursor=ds.end if body.mode in ('snapshot','scenario') else (body.start_cursor if body.start_cursor is not None else ds.start)
    if not ds.start<=cursor<=ds.end: raise HTTPException(422,'Cursor outside dataset')
    run=Run(dataset_id=ds.id,mode=body.mode,cursor=cursor,state={})
    db.add(run); db.flush(); enqueue(db,f'analyze:{run.id}:0','analyze',{'run_id':run.id}); db.commit()
    return {'id':run.id}

@app.post('/api/runs/{rid}/control')
def control(rid:str,body:Control,user=Depends(supervisor),db=Depends(database)):
    run=get_run(db,rid,user,lock=True); ds=db.get(Dataset,run.dataset_id)
    if body.action=='seek':
        if body.value is None or not ds.start<=body.value<=ds.end: raise HTTPException(422,'Invalid cursor')
        fresh=Run(dataset_id=ds.id,mode='replay',cursor=body.value,state={}); db.add(fresh); db.flush()
        enqueue(db,f'analyze:{fresh.id}:0','analyze',{'run_id':fresh.id}); db.commit(); return {'id':fresh.id,'fresh_run':True}
    if body.action=='resume':
        if run.mode!='replay': raise HTTPException(409,'Only historical replay can resume; create a separate replay run')
        run.paused=0
    elif body.action=='pause': run.paused=1
    else:
        if body.value not in (1,2,5,10): raise HTTPException(422,'Speed must be 1, 2, 5 or 10 intervals per tick')
        run.speed=int(body.value)
    run.revision+=1; db.commit(); return {'id':run.id}

@app.get('/api/runs/{rid}/state')
def state(rid:str,user=Depends(current_user),db=Depends(database)):
    run=get_run(db,rid,user); ds=db.get(Dataset,run.dataset_id)
    return {'id':run.id,'dataset_id':run.dataset_id,'mode':run.mode,'cursor':run.cursor,'paused':bool(run.paused),'speed':run.speed,'revision':run.revision,'topology':ds.network,'ops':ds.ops,'analysis_pending':not bool(run.state),**run.state,'providers':{'ai':settings.ai_mode,'messaging':photon_status()},'constraints':[{'id':c.id,'truck_id':c.truck_id,'until':c.until,'source':c.source} for c in db.scalars(select(Constraint).where(Constraint.run_id==rid))],'jobs':[{'kind':j.kind,'status':j.status} for j in db.scalars(select(Job).where(Job.status.in_(['pending','failed'])) ) if j.payload.get('run_id')==rid]}

@app.get('/api/runs/{rid}/series')
def series(rid:str,asset_id:str,metric:str,start:float|None=None,end:float|None=None,user=Depends(current_user),db=Depends(database)):
    run=get_run(db,rid,user); upper=min(end if end is not None else run.cursor,run.cursor); lower=start if start is not None else upper-86400
    # Server-side bucketing caps result size without changing original detector inputs.
    bucket=max(300,int(max(0,upper-lower)/500/300+1)*300)
    stamp=func.floor(Telemetry.ts/bucket)*bucket
    stmt=select(stamp.label('ts'),func.avg(Telemetry.value).label('value')).where(Telemetry.dataset_id==run.dataset_id,Telemetry.asset_id==asset_id,Telemetry.metric==metric,Telemetry.ts>=lower,Telemetry.ts<=upper).group_by(stamp).order_by(stamp)
    return [{'ts':float(r.ts),'value':float(r.value)} for r in db.execute(stmt)]

def plan_json(p): return {'id':p.id,'run_id':p.run_id,'version':p.version,'fingerprint':p.fingerprint,'status':p.status,'expires':p.expires,**p.data}

@app.get('/api/runs/{rid}/plans')
def plans(rid:str,user=Depends(current_user),db=Depends(database)):
    get_run(db,rid,user)
    return [plan_json(p) for p in db.scalars(select(Plan).where(Plan.run_id==rid).order_by(Plan.version.desc()))]

@app.post('/api/runs/{rid}/plans',status_code=202)
def queue_plan(rid:str,body:PlanCreate,user=Depends(operator),db=Depends(database)):
    run=get_run(db,rid,user,lock=True)
    if not run.state: raise HTTPException(409,'Analysis pending')
    if body.system_id not in db.get(Dataset,run.dataset_id).ops['systems']: raise HTTPException(422,'Unknown system')
    enqueue(db,f'plan:{rid}:{run.revision}:{body.system_id}:{secrets.token_hex(4)}','plan',{'run_id':rid,'system_id':body.system_id}); db.commit(); return {'queued':True}

@app.post('/api/plans/{pid}/approve')
def approve_route(pid:str,body:Approval,user=Depends(supervisor),db=Depends(database)):
    if engine.dialect.name=='sqlite': db.execute(text('BEGIN IMMEDIATE'))
    p=approve(db,pid,body.version,body.fingerprint,user); db.commit(); return plan_json(p)

@app.post('/api/plans/{pid}/reject')
def reject(pid:str,user=Depends(supervisor),db=Depends(database)):
    p=db.get(Plan,pid)
    if not p: raise HTTPException(404,'Plan not found')
    get_run(db,p.run_id,user,lock=True)
    if p.status!='PENDING_APPROVAL': raise HTTPException(409,'Plan no longer pending')
    p.status='REJECTED'; db.add(Audit(actor=user.id,action='REJECTED',run_id=p.run_id,plan_id=p.id,outcome='Rejected')); db.commit(); return plan_json(p)

@app.post('/api/plans/{pid}/acknowledge')
def acknowledge(pid:str,user=Depends(operator),db=Depends(database)):
    p=db.get(Plan,pid)
    if not p: raise HTTPException(404,'Plan not found')
    get_run(db,p.run_id,user,lock=True)
    if p.status!='SIMULATED_DISPATCHED': raise HTTPException(409,'Plan is not awaiting acknowledgment')
    p.status='ACKNOWLEDGED'; db.add(Audit(actor=user.id,action='ACKNOWLEDGED',run_id=p.run_id,plan_id=p.id,outcome='Operator acknowledgment')); db.commit(); return plan_json(p)

@app.post('/api/runs/{rid}/constraints')
def constraint(rid:str,body:ConstraintCreate,user=Depends(operator),db=Depends(database)):
    run=get_run(db,rid,user,lock=True)
    text_message=f'{body.truck_id} unavailable for {body.unavailable_minutes} scenario minutes'
    result=queue(db,run,user,text_message); db.commit(); return result

@app.get('/api/runs/{rid}/messages')
def messages(rid:str,user=Depends(current_user),db=Depends(database)):
    get_run(db,rid,user)
    return [{'id':m.id,'actor':m.actor,'text':m.text,'scenario_ts':m.scenario_ts,'wall_ts':m.wall_ts,'delivery':m.delivery} for m in db.scalars(select(Message).where(Message.run_id==rid).order_by(Message.wall_ts))]

@app.post('/api/runs/{rid}/messages')
def message(rid:str,body:TextMessage,user=Depends(operator),db=Depends(database)):
    run=get_run(db,rid,user,lock=True)
    if settings.messaging_mode!='mock': raise HTTPException(503,'Live messages require verified Photon channel identity')
    result=queue(db,run,user,body.text); db.commit(); return result

@app.post('/api/webhooks/photon')
def webhook(): raise HTTPException(503,'Webhook mutations disabled: Photon signing contract unverified')

@app.get('/api/runs/{rid}/activity')
def tool_activity(rid:str,user=Depends(current_user),db=Depends(database)):
    get_run(db,rid,user)
    return [{'job_id':j.id,'status':j.status,'trace':j.payload.get('trace',[]),'elapsed_ms':j.payload.get('elapsed_ms')} for j in db.scalars(select(Job).where(Job.kind=='conversation')) if j.payload.get('run_id')==rid]

@app.get('/api/runs/{rid}/export')
def export(rid:str,user=Depends(current_user),db=Depends(database)):
    run=get_run(db,rid,user); results=[]
    iso=lambda ts: datetime.fromtimestamp(ts,timezone.utc).isoformat().replace('+00:00','Z') if ts is not None else None
    for e in run.state.get('history',[]):
        if e['provisional']: continue
        result={k:e[k] for k in ('event_id','system_id','facility_id','asset_id','category','status','onset_unix','end_unix','confidence')}
        result.update(onset_ts=iso(e['onset_unix']),end_ts=iso(e['end_unix']),evidence=[f'{v["asset_id"]} {v["metric"]}={v["value"]} at {iso(v["ts"])}' for v in e['evidence']],hours_to_limit={'p50':e['hours_to_limit']} if e.get('hours_to_limit') is not None and e['status']=='ongoing' else None,recommended_actions=[{'type':'field_inspection','asset_id':e['asset_id']}] if e['category']!='pump_failure' else [{'type':'none'}])
        results.append(result)
    return results
