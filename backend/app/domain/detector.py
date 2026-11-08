"""Causal, explainable state machine. All observations are filtered by cursor."""
from collections import deque
from statistics import median
from app.domain.ingest import facilities
from app.domain.forecast import countdown, revenue
from app.config import settings

PARAMETERS = {'version': 'baseline-2', 'leak_ratio': settings.detector_leak_ratio, 'leak_samples': 3, 'degradation_ratio': settings.detector_degradation_ratio, 'degradation_samples': 6, 'missing_after_seconds': 600}

def detect(network, ops, rows, cursor):
    frames = {}
    for ts, asset, metric, value in rows:
        if ts <= cursor: frames.setdefault(ts, {})[(asset,metric)] = value
    all_events, latest, quality = [], {}, []
    for system, f in facilities(network):
        pid, tid, lid = f['pump']['id'], f['tank']['id'], f['pipeline']['id']
        active, counters, starts, running = {}, {}, {}, deque(maxlen=12)
        expected, previous_running, last_ts = False, False, None
        last_good = {}
        for ts, values in sorted(frames.items()):
            keys = [(pid,'status'), (pid,'flow_bpd'), (tid,'level_pct'), (lid,'receive_flow_bpd'), (f['id'],'inflow_bpd')]
            if any(key not in values for key in keys):
                if ts == max(frames): quality.append(f'{f["id"]}: incomplete sensor interval')
                previous_running = False
                counters.clear(); running.clear()
                continue
            if last_ts is not None and ts-last_ts > PARAMETERS['missing_after_seconds']:
                quality.append(f'{f["id"]}: gap of {int(ts-last_ts)} seconds before {int(ts)}')
                counters.clear(); running.clear(); previous_running=False
            last_ts, last_good = ts, values
            status, flow, level, received, inflow = [values[k] for k in keys]
            if level >= f['pump']['start_level_pct']: expected = True
            elif level <= f['pump']['stop_level_pct'] + .5: expected = False
            is_running = status == 1 and flow > f['pump']['max_flow_bpd']*.1
            if is_running: running.append(flow)
            if status == 1 and flow > f['pump']['max_flow_bpd']*.1 and active.get('pump_failure'):
                e = active.pop('pump_failure'); e.update(status='resolved', provisional=False, end_unix=ts)
            if status == 2 and flow > f['pump']['max_flow_bpd']*.5:
                if ts == max(frames): quality.append(f'{pid}: sensor inconsistency, fault with high flow')
            failure = status == 2 or (expected and flow < f['pump']['max_flow_bpd']*.05)
            stable = is_running and previous_running
            pressure=values.get((lid,'pressure_psi'))
            pressure_drop=pressure is None or pressure < system.get('disposal_site',{}).get('pressure_psi',0)+35
            leak = stable and (flow-received)/max(flow,1) > PARAMETERS['leak_ratio'] and pressure_drop
            downward=len(running)>=6 and median(list(running)[-3:]) < median(list(running)[:3])
            degradation = is_running and len(running) >= 6 and median(running) < f['pump']['max_flow_bpd']*PARAMETERS['degradation_ratio'] and downward
            conditions = {'pump_failure': failure, 'pipeline_leak': leak, 'pump_degradation': degradation}
            for category, condition in conditions.items():
                if condition:
                    starts.setdefault(category, ts)
                    counters[category] = counters.get(category,0)+1
                    required = 1 if category == 'pump_failure' and status == 2 else (6 if category == 'pump_degradation' else 3)
                    if category not in active:
                        evidence = [dict(asset_id=a, metric=m, value=v, ts=ts) for (a,m),v in values.items() if a in {pid,tid,lid}]
                        e = dict(event_id=f'{f["id"]}-{category}-{int(starts[category])}', system_id=system['id'], facility_id=f['id'], asset_id=lid if category=='pipeline_leak' else pid, category=category, status='ongoing', onset_unix=starts[category], detection_unix=ts, end_unix=None, provisional=True, confidence=.6, evidence=evidence)
                        active[category] = e; all_events.append(e)
                    if counters[category] >= required:
                        e=active[category]; e.update(provisional=False, confidence=.98 if status==2 and category=='pump_failure' else .85)
                        if 'confirmed_unix' not in e: e['confirmed_unix']=ts
                else:
                    counters[category]=0; starts.pop(category,None)
                    if category != 'pump_failure' and category in active and is_running and ((category=='pipeline_leak' and received >= flow*.985 and (not pressure_drop or pressure is None)) or (category=='pump_degradation' and flow > f['pump']['max_flow_bpd']*.98)):
                        e=active.pop(category); e.update(status='resolved', end_unix=ts)
            previous_running = is_running
        if not last_good: quality.append(f'{f["id"]}: no complete observations'); continue
        if cursor-last_ts > PARAMETERS['missing_after_seconds']: quality.append(f'{f["id"]}: stale observations')
        level=last_good[(tid,'level_pct')]; inflow=last_good[(f['id'],'inflow_bpd')]; flow=last_good[(pid,'flow_bpd')]
        latest[f['id']] = {'facility_id':f['id'], 'system_id':system['id'], 'level_pct':level,'inflow_bpd':inflow,'flow_bpd':flow,'observed_ts':last_ts}
        for e in active.values():
            hours, reason = countdown(level,f['tank']['capacity_bbl'],network['defaults']['tank_limits_pct']['shutdown'],inflow,flow) if e['category']=='pump_failure' else (None,'Field inspection; no shutdown countdown')
            e.update(level_pct=level,hours_to_limit=hours,forecast_reason=reason,revenue_per_hour=sum(revenue(w,ops['prices']) for w in f['wells']),remaining_repair_hours=max(0,ops['expected_repair_hours']['pump_failure']-(cursor-e['onset_unix'])/3600))
    ongoing=[e for e in all_events if e['status']=='ongoing']
    ongoing.sort(key=lambda e:(e['category']!='pump_failure',float('inf') if e.get('hours_to_limit') is None else e['hours_to_limit'],-e.get('revenue_per_hour',0)))
    return {'events':ongoing, 'history':all_events, 'facilities':list(latest.values()),'data_quality':list(dict.fromkeys(quality)),'parameters':PARAMETERS}
