import itertools
import time
from app.domain.ingest import facilities
from app.domain.simulator import simulate

def compare(network,ops,state,system_id,cursor,constraints=(),reservations=(),budget_seconds=3):
    start=time.monotonic(); limit=network['defaults']['tank_limits_pct']['shutdown']
    system_ops=ops['systems'][system_id]
    trucks=[f'{system_id}_TRUCK_{i+1}' for i in range(system_ops['emergency_fleet_size'])]
    busy={truck:0. for truck in trucks}
    for c in constraints:
        if c['truck_id'] in busy: busy[c['truck_id']]=max(busy[c['truck_id']],(c['until']-cursor)/3600)
    for r in reservations:
        if r['truck_id'] in busy and r['end']>cursor: busy[r['truck_id']]=max(busy[r['truck_id']],(r['end']-cursor)/3600)
    incidents=[e for e in state['events'] if e['system_id']==system_id and e['category']=='pump_failure' and not e['provisional']]
    configs={f['id']:f for s,f in facilities(network)}
    observations={f['facility_id']:f for f in state['facilities']}
    candidates=[]; complete=True
    for incident in incidents:
        f=configs[incident['facility_id']]; horizon=incident['remaining_repair_hours']; travel=system_ops['facilities'][f['id']]
        response=travel['response_min']/60; cycle=travel['cycle_min']/60
        def evaluate(actions,assignments):
            result=simulate(f,ops,incident['level_pct'],limit,horizon,actions,observations[f['id']]['inflow_bpd'])
            return dict(facility_id=f['id'],actions=actions,reservations=assignments,**result)
        options=[evaluate([],[])]
        # Call together at scenario start; no fictional instant transfers between facilities.
        free=[truck for truck in trucks if busy[truck]<=0]
        max_trips=max(0,int((horizon-response-1e-8)//cycle)+1)
        schedules=[([],[])]
        for count in range(1,len(free)+1):
            for assigned in itertools.combinations(free,count):
                for trips in range(1,max_trips+1):
                    actions=[{'type':'truck','truck_id':truck,'at_hours':response+k*cycle,'bbl':ops['emergency_trucking']['truck_capacity_bbl']} for truck in assigned for k in range(trips)]
                    calendar=[{'truck_id':truck,'start':cursor,'end':cursor+(response+trips*cycle)*3600} for truck in assigned]
                    schedules.append((actions,calendar)); options.append(evaluate(actions,calendar))
        for actions, calendar in schedules:
            for size in range(1,len(f['wells'])+1):
                for subset in itertools.combinations(f['wells'],size):
                    # Declared minute grid; retain minimum cost including accepted trips.
                    best=None
                    for minute in range(max(1,int(horizon*60))):
                        if time.monotonic()-start>budget_seconds: complete=False; break
                        shut=[{'type':'shut_in','well_id':w['id'],'at_hours':minute/60} for w in subset]
                        result=evaluate(actions+shut,calendar)
                        if result['feasible'] and (best is None or result['total_cost']<best['total_cost']): best=result
                    if best: options.append(best)
                    if not complete: break
                if not complete: break
            if not complete: break
        feasible=sorted([o for o in options if o['feasible']],key=lambda o:o['total_cost'])
        candidates.append((options[0],feasible))
    baseline=sum(b['total_cost'] for b,_ in candidates)
    solutions=[]
    def search(index, chosen, cost, calendar):
        nonlocal complete
        if time.monotonic()-start>budget_seconds+.5: complete=False; return
        if len(solutions)>=12 and cost>solutions[-1]['total_cost']: return
        if index==len(candidates):
            solutions.append({'total_cost':round(cost,2),'facilities':chosen,'reservations':calendar})
            solutions.sort(key=lambda s:s['total_cost']); del solutions[12:]; return
        for option in candidates[index][1]:
            rs=option['reservations']
            if any(a['truck_id']==b['truck_id'] and a['start']<b['end'] and b['start']<a['end'] for a in rs for b in calendar): continue
            search(index+1,chosen+[option],cost+option['total_cost'],calendar+rs)
    search(0,[],0,[])
    # Always retain baseline even if candidate enumeration exhausts budget.
    baseline_solution={'total_cost':round(baseline,2),'facilities':[b for b,_ in candidates],'reservations':[]}
    if not solutions: solutions=[baseline_solution]
    return {'system_id':system_id,'baseline':baseline_solution,'alternatives':solutions[:4],'recommended':solutions[0],'search_complete':complete,'optimality':'Least cost found; minute-grid shut-ins, bounded search, calls at plan start only','truck_ids':trucks,'synthetic_truck_ids':True,'elapsed_ms':round((time.monotonic()-start)*1000),'incident_count':len(incidents)}
