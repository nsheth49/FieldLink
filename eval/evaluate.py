"""Isolated practice evaluator. Never import this module into app/ or load keys in runtime."""
import argparse
import json
from datetime import datetime
from pathlib import Path

def epoch(value):
    if value is None:return None
    if isinstance(value,dict):return epoch(value.get('ts_unix',value.get('timestamp')))
    if isinstance(value,(float,int)):return float(value)
    return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

def evaluate(predictions,truth,tolerance=1800):
    if isinstance(truth,dict): truth=truth.get('events',[])
    report={}
    for category in ('pump_failure','pipeline_leak','pump_degradation'):
        actual=[e for e in truth if e['category']==category];pred=[e for e in predictions if e['category']==category and not e.get('provisional',False)]
        matched=set();delays=[];status_correct=0
        for p in pred:
            onset=epoch(p.get('onset_unix',p.get('onset_ts')))
            options=[]
            for i,a in enumerate(actual):
                a_onset=epoch(a.get('onset_unix',a.get('onset_ts',a.get('onset'))))
                a_end=epoch(a.get('end_unix',a.get('end')))
                p_end=epoch(p.get('end_unix',p.get('end_ts')))
                overlap=onset<(a_end if a_end is not None else float('inf')) and a_onset<(p_end if p_end is not None else float('inf'))
                if i not in matched and a.get('asset_id',a.get('asset'))==p['asset_id'] and (abs(onset-a_onset)<=tolerance or overlap):options.append((abs(onset-a_onset),i,a,a_onset))
            if options:
                _,i,a,a_onset=min(options,key=lambda x:x[0]);matched.add(i);delays.append(epoch(p.get('confirmed_unix',p.get('detection_unix',onset)))-a_onset);status_correct+=p['status']==a['status']
        tp=len(matched);report[category]={'predictions':len(pred),'actual':len(actual),'true_positives':tp,'false_alarms':len(pred)-tp,'precision':round(tp/len(pred),4) if pred else None,'recall':round(tp/len(actual),4) if actual else None,'mean_detection_delay_seconds':round(sum(delays)/len(delays),1) if delays else None,'matched_status_accuracy':round(status_correct/tp,4) if tp else None}
    return {'practice_only':True,'matching':'same asset/category; one-to-one closest onset, overlapping episode or onset within tolerance','onset_tolerance_seconds':tolerance,'categories':report}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--predictions',required=True);p.add_argument('--answer-key',required=True);p.add_argument('--output');p.add_argument('--tolerance',type=int,default=1800);a=p.parse_args()
    result=evaluate(json.loads(Path(a.predictions).read_text()),json.loads(Path(a.answer_key).read_text()),a.tolerance)
    content=json.dumps(result,indent=2);print(content)
    if a.output:Path(a.output).write_text(content)
