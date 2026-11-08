import copy
import json
from pathlib import Path
import pytest
from app.domain.forecast import countdown, revenue
from app.domain.simulator import simulate
from app.domain.detector import detect
from app.domain.ingest import validate
from app.domain.planner import compare

@pytest.fixture
def config():
    f={'id':'FAC','wells':[{'id':'W1','baseline_water_bpd':1200,'oil_bpd':240,'gas_mcfd':0},{'id':'W2','baseline_water_bpd':1200,'oil_bpd':240,'gas_mcfd':0}],'tank':{'id':'T','capacity_bbl':1000},'pump':{'id':'P','max_flow_bpd':3600,'start_level_pct':70,'stop_level_pct':30},'pipeline':{'id':'L'}}
    n={'defaults':{'tank_limits_pct':{'warning':85,'shutdown':90}},'systems':[{'id':'SYS','facilities':[f]}]}
    o={'prices':{'oil_per_bbl':60,'gas_per_mcf':3},'expected_repair_hours':{'pump_failure':6},'emergency_trucking':{'truck_capacity_bbl':150,'cost_per_trip':100},'systems':{'SYS':{'emergency_fleet_size':1,'facilities':{'FAC':{'response_min':30,'cycle_min':120}}}}}
    return n,o,f

def sensor_rows(samples):
    rows=[]
    for i,sample in enumerate(samples):
        status,flow,level,received=sample
        for asset,metric,value in [('P','status',status),('P','flow_bpd',flow),('T','level_pct',level),('L','receive_flow_bpd',received),('FAC','inflow_bpd',2400)]: rows.append((i*300,asset,metric,value))
    return rows

def test_countdown_units_and_trip():
    assert countdown(80,1000,90,2400,0)[0]==1
    assert countdown(90,1000,90,0,0)[0]==0
    assert countdown(50,1000,90,0,100)[0] is None

def test_boundary_truck_does_not_prevent_earlier_crossing(config):
    n,o,f=config
    result=simulate(f,o,80,90,3,[{'type':'truck','at_hours':1,'bbl':150}])
    assert result['trip_hours']==1 and not result['prevents_shutdown']
    assert result['lost_revenue']==2400

def test_before_boundary_and_overremoval(config):
    n,o,f=config
    result=simulate(f,o,80,90,2,[{'type':'truck','at_hours':.5,'bbl':150}])
    assert result['prevents_shutdown']
    assert not simulate(f,o,1,90,2,[{'type':'truck','at_hours':0,'bbl':150}])['feasible']
    assert not simulate(f,o,80,90,2,[{'type':'truck','at_hours':2,'bbl':150}])['feasible']

def test_delayed_shut_cost_and_no_double_count(config):
    n,o,f=config
    result=simulate(f,o,80,90,3,[{'type':'shut_in','well_id':'W1','at_hours':.5}])
    assert result['trip_hours']==pytest.approx(1.5)
    assert result['lost_revenue']==2400
    assert simulate(f,o,80,90,3,[])['total_cost']==2400

def test_healthy_noisy_cycles(config):
    n,o,f=config
    samples=[(0,0,30.04,0),(0,0,50,0),(1,3600,70.1,3590),(1,3600,50,3590),(0,0,30.08,0),(0,0,50,0)]*4
    result=detect(n,o,sensor_rows(samples),len(samples)*300)
    assert not [e for e in result['history'] if not e['provisional']]

def test_explicit_fault_shutdown_repair_and_causality(config):
    n,o,f=config
    samples=[(1,3600,71,3590),(2,0,75,0),(2,0,90,0),(2,0,90,0),(1,3600,88,3590)]
    rows=sensor_rows(samples)
    at=detect(n,o,rows,900)
    assert len(at['events'])==1 and at['events'][0]['hours_to_limit']==0
    assert at['events'][0]['remaining_repair_hours']==pytest.approx(6-600/3600)
    repaired=detect(n,o,rows,1200)
    assert not repaired['events'] and repaired['history'][0]['status']=='resolved'
    assert all(e['ts']<=900 for e in at['events'][0]['evidence'])

def test_missed_start_leak_and_degradation(config):
    n,o,f=config
    failure=detect(n,o,sensor_rows([(0,0,75,0)]*4),900)
    assert failure['events'][0]['category']=='pump_failure' and not failure['events'][0]['provisional']
    leak=detect(n,o,sensor_rows([(1,3600,65,2800)]*6),1500)
    assert any(e['category']=='pipeline_leak' and not e['provisional'] for e in leak['events'])
    worn=detect(n,o,sensor_rows([(1,2800-i*10,65,2800-i*10) for i in range(15)]+[(2,0,75,0)]),4500)
    assert {'pump_degradation','pump_failure'} <= {e['category'] for e in worn['events']}

def test_missing_marks_uncertainty(config):
    n,o,f=config
    result=detect(n,o,[(0,'P','status',2)],0)
    assert result['data_quality'] and not result['events']

def test_planner_shared_fleet_and_constraint(config):
    n,o,f=config
    second=copy.deepcopy(f);second['id']='FAC2'
    n['systems'][0]['facilities'].append(second);o['systems']['SYS']['facilities']['FAC2']={'response_min':30,'cycle_min':120}
    events=[{'facility_id':fid,'system_id':'SYS','category':'pump_failure','provisional':False,'remaining_repair_hours':2,'level_pct':80} for fid in ['FAC','FAC2']]
    state={'events':events,'facilities':[{'facility_id':fid,'inflow_bpd':2400} for fid in ['FAC','FAC2']]}
    p=compare(n,o,state,'SYS',0)
    calendar=p['recommended']['reservations']
    assert len(calendar)<=1
    q=compare(n,o,state,'SYS',0,[{'truck_id':'SYS_TRUCK_1','until':3600}])
    assert not q['recommended']['reservations']
    assert q['recommended']['total_cost']<=q['baseline']['total_cost']

def test_import_rejects_duplicate_nonfinite_and_time_mismatch(config):
    n,o,f=config
    files={'network.json':json.dumps(n).encode(),'ops.json':json.dumps(o).encode(),'telemetry.csv':b'timestamp,ts_unix,asset_id,metric,value\n1970-01-01T00:00:00Z,0,P,status,1\n'}
    assert validate(files)[4].shape[0]==1
    files['telemetry.csv']+=b'1970-01-01T00:00:00Z,0,P,status,1\n'
    with pytest.raises(ValueError,match='Duplicate'): validate(files)
    files['telemetry.csv']=b'timestamp,ts_unix,asset_id,metric,value\n1970-01-01T00:00:00Z,0,P,flow_bpd,inf\n'
    with pytest.raises(ValueError,match='Nonfinite'):validate(files)
    files['telemetry.csv']=b'timestamp,ts_unix,asset_id,metric,value\n1970-01-01T00:00:00Z,300,P,status,1\n'
    with pytest.raises(ValueError,match='Inconsistent'):validate(files)
