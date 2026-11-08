"""Event-based integration with exact threshold crossings and no revenue duplication."""
from app.domain.forecast import revenue

def simulate(facility, ops, level_pct, shutdown_pct, horizon, actions, initial_inflow=None):
    cap=facility['tank']['capacity_bbl']; volume=level_pct/100*cap; limit=shutdown_pct/100*cap
    wells={w['id']:w for w in facility['wells']}; off=set(); t=0.; cost=0.; truck_cost=0.; trip=0. if volume>=limit-.0005*cap else None
    full_rate=sum(w['baseline_water_bpd'] for w in wells.values())
    inflow=full_rate if initial_inflow is None or initial_inflow<=0 else initial_inflow
    schedule=sorted(actions,key=lambda a:(a['at_hours'],a['type']))
    trace=[{'hours':0.,'level_pct':level_pct}]
    for action in [*schedule,{'type':'end','at_hours':horizon}]:
        at=action['at_hours']
        if at < t or at > horizon or at < 0: return {'feasible':False,'reason':'Action outside repair horizon'}
        if action['type']!='end' and at>=horizon: return {'feasible':False,'reason':'Arrival at or after repair'}
        rate=max(0,inflow-sum(wells[w]['baseline_water_bpd'] for w in off))/24
        crossing=t+max(0,limit-volume)/rate if rate>0 else float('inf')
        if trip is None and crossing <= at+1e-10: trip=crossing
        lost=sum(revenue(wells[w],ops['prices']) for w in off)
        total=sum(revenue(w,ops['prices']) for w in wells.values())
        if trip is None: cost+=lost*(at-t); volume+=rate*(at-t)
        else:
            pre=max(0,min(at,trip)-t); cost+=lost*pre+total*(at-t-pre)
            volume=min(limit,volume+rate*pre)
        t=at
        if action['type']=='truck':
            removal=action['bbl']
            if removal>volume+1e-7 or removal<=0: return {'feasible':False,'reason':'Truck over-removes available water'}
            volume-=removal; truck_cost+=ops['emergency_trucking']['cost_per_trip']
        elif action['type']=='shut_in':
            if action['well_id'] not in wells: return {'feasible':False,'reason':'Unknown well'}
            off.add(action['well_id'])
        trace.append({'hours':at,'level_pct':max(0,volume/cap*100)})
    return {'feasible':True,'prevents_shutdown':trip is None,'trip_hours':trip,'lost_revenue':round(cost,2),'truck_cost':round(truck_cost,2),'total_cost':round(cost+truck_cost,2),'trace':trace,'reason':'Accept automatic shutdown' if trip is not None else 'Tank remains below shutdown until repair'}
