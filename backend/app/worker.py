import time
from sqlalchemy import select, update
from app.db import Session, engine
from app.db.models import Job, Outbox, Run, Dataset, Message, User, now
from app.services.conversations import process
from app.services.runs import analyze, get_run
from app.services.plans import make_plan
from app.integrations.photon import send

def tick():
    with Session.begin() as db:
        # PostgreSQL advisory lock; SQLite BEGIN IMMEDIATE gives one writer.
        if engine.dialect.name=='postgresql':
            from sqlalchemy import text
            if not db.scalar(text('SELECT pg_try_advisory_xact_lock(748191)')): return
        else:
            from sqlalchemy import text
            db.execute(text('BEGIN IMMEDIATE'))
        for run in db.scalars(select(Run).where(Run.paused==0).with_for_update(skip_locked=True)):
            ds=db.get(Dataset,run.dataset_id)
            # Analyze full prefix, therefore no intervening intervals are skipped at speed.
            run.cursor=min(ds.end,run.cursor+300*run.speed); run.revision+=1
            analyze(db,run)
            if run.cursor>=ds.end: run.paused=1
        job=db.scalar(select(Job).where(Job.status=='pending',Job.next_attempt<=now()).order_by(Job.next_attempt).with_for_update(skip_locked=True).limit(1))
        if job:
            try:
                with db.begin_nested():
                    run=get_run(db,job.payload['run_id'],lock=True)
                    if job.kind=='analyze': analyze(db,run)
                    elif job.kind=='plan': make_plan(db,run,job.payload['system_id'])
                    elif job.kind=='conversation':
                        user=db.get(User,job.payload['user_id']); get_run(db,run.id,user)
                        started=time.monotonic()
                        result=process(db,run,user,job.payload['text'],job.payload['message_id'])
                        job.payload={**job.payload,'trace':result['trace'],'elapsed_ms':round((time.monotonic()-started)*1000)}
                    else: raise ValueError('Unknown job type')
                job.status='done'
            except Exception:
                job.attempts+=1; job.next_attempt=now()+min(300,2**job.attempts)
                if job.attempts>=3: job.status='failed'
        out=db.scalar(select(Outbox).where(Outbox.status=='pending',Outbox.next_attempt<=now()).with_for_update(skip_locked=True).limit(1))
        if out:
            # Mark unknown before external I/O. Never automatically resend ambiguous submissions.
            out.status='unknown'; out.attempts+=1; payload=out.payload; oid=out.id
        else: payload=None
    if payload:
        import httpx
        try: result=send(payload)
        except (httpx.ReadTimeout,httpx.WriteTimeout,httpx.RemoteProtocolError): result={'delivery':'unknown'}
        except (httpx.ConnectError,httpx.ConnectTimeout): result={'delivery':'retry'}
        except Exception: result={'delivery':'failed'}
        with Session.begin() as db:
            out=db.get(Outbox,oid); out.status=result['delivery']
            if out.status=='retry':
                out.status='pending' if out.attempts<3 else 'failed'; out.next_attempt=now()+2**out.attempts
            else: db.add(Message(run_id=payload['run_id'],actor='FieldLink',text=f'[SIMULATION · scenario {payload["scenario_ts"]} UTC epoch] {payload["text"]}',scenario_ts=payload['scenario_ts'],delivery=out.status))

def main():
    print('FieldLink worker: persistent replay, jobs and mock outbox; polling every 2 seconds')
    while True:
        try: tick()
        except Exception as error: print(f'Worker tick failed: {type(error).__name__}',flush=True)
        time.sleep(2)

if __name__=='__main__': main()
