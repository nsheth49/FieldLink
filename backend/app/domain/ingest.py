"""Only the three allowed files enter runtime. Reference prose is never executable."""
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import pandas as pd
from sqlalchemy import insert
from app.db.models import Dataset, Asset, Telemetry
from app.config import ROOT

METRICS = {'facility': {'inflow_bpd'}, 'well': {'water_bpd', 'status'}, 'tank': {'level_pct'}, 'pump': {'status', 'flow_bpd', 'discharge_psi'}, 'pipeline': {'receive_flow_bpd', 'pressure_psi'}}

def facilities(network):
    for system in network['systems']:
        for facility in system['facilities']:
            yield system, facility

def positive(value, label, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f'Invalid numeric configuration: {label}')

def validate(files):
    if set(files) != {'network.json', 'ops.json', 'telemetry.csv'}:
        raise ValueError('Exactly network.json, ops.json and telemetry.csv are required')
    network, ops = json.loads(files['network.json']), json.loads(files['ops.json'])
    assets = {}
    positive(network['defaults']['tank_limits_pct']['shutdown'], 'shutdown')
    for system, f in facilities(network):
        config = ops['systems'][system['id']]
        positive(config['emergency_fleet_size'], 'fleet', True)
        positive(config['facilities'][f['id']]['response_min'], 'response')
        positive(config['facilities'][f['id']]['cycle_min'], 'cycle')
        positive(f['tank']['capacity_bbl'], 'capacity')
        positive(f['pump']['max_flow_bpd'], 'pump flow')
        if not 0 <= f['pump']['stop_level_pct'] < f['pump']['start_level_pct'] < network['defaults']['tank_limits_pct']['shutdown'] <= 100:
            raise ValueError('Invalid pump setpoints or shutdown limit')
        for w in f['wells']:
            for key in ('baseline_water_bpd', 'oil_bpd', 'gas_mcfd'): positive(w[key], key, True)
        items = [('facility', f), *[('well', w) for w in f['wells']], *[(k, f[k]) for k in ('tank', 'pump', 'pipeline')]]
        for kind, asset in items:
            if asset['id'] in assets: raise ValueError('Duplicate asset ID')
            assets[asset['id']] = {'kind': kind, 'system_id': system['id'], 'facility_id': f['id'], **asset}
    for value in ops['prices'].values(): positive(value, 'price', True)
    positive(ops['expected_repair_hours']['pump_failure'], 'repair')
    for value in ops['emergency_trucking'].values(): positive(value, 'trucking')
    import io
    frame = pd.read_csv(io.BytesIO(files['telemetry.csv']))
    if set(frame.columns) != {'timestamp', 'ts_unix', 'asset_id', 'metric', 'value'} or frame.empty:
        raise ValueError('Invalid telemetry columns or empty CSV')
    if frame.isna().any().any(): raise ValueError('Missing telemetry values')
    for col in ('ts_unix', 'value'):
        frame[col] = pd.to_numeric(frame[col], errors='raise')
        if not frame[col].map(math.isfinite).all(): raise ValueError('Nonfinite telemetry')
    if not frame.asset_id.isin(assets).all(): raise ValueError('Unknown asset')
    for asset, metric in frame[['asset_id','metric']].drop_duplicates().itertuples(index=False, name=None):
        if metric not in METRICS[assets[asset]['kind']]: raise ValueError('Unknown asset metric')
    if frame.duplicated(['ts_unix', 'asset_id', 'metric']).any(): raise ValueError('Duplicate reading')
    timestamps = pd.to_datetime(frame.timestamp, utc=True, errors='raise').astype('datetime64[ns, UTC]').astype('int64') / 1e9
    if ((timestamps-frame.ts_unix).abs() > 0.5).any(): raise ValueError('Inconsistent timestamps')
    status = frame[frame.metric == 'status']
    if not status.value.isin([0,1,2]).all(): raise ValueError('Invalid status code')
    well_status=status[status.asset_id.map(lambda a: assets[a]['kind']=='well')]
    if not well_status.value.isin([0,1]).all(): raise ValueError('Invalid well status code')
    if ((frame.metric=='level_pct') & ((frame.value<0)|(frame.value>100))).any(): raise ValueError('Tank level outside 0 to 100')
    frame = frame.sort_values('ts_unix')
    digest = hashlib.sha256()
    for name in sorted(files): digest.update(name.encode()+b'\0'+files[name])
    return digest.hexdigest(), network, ops, assets, frame

def import_files(db, files, name):
    did, network, ops, assets, frame = validate(files)
    if db.get(Dataset, did): return did, {'duplicate': True, 'rows': len(frame)}
    target = ROOT / 'data' / 'imports' / did
    target.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items(): (target / filename).write_bytes(content)
    manifest = {k: hashlib.sha256(v).hexdigest() for k,v in files.items()}
    db.add(Dataset(id=did, name=name, network=network, ops=ops, manifest=manifest, start=float(frame.ts_unix.min()), end=float(frame.ts_unix.max())))
    db.flush()
    db.execute(insert(Asset), [{'dataset_id': did, 'id': key, 'topology': value} for key,value in assets.items()])
    rows = frame.rename(columns={'ts_unix': 'ts'}).drop(columns=['timestamp']).to_dict('records')
    for offset in range(0, len(rows), 5000): db.execute(insert(Telemetry), [{'dataset_id': did, **r} for r in rows[offset:offset+5000]])
    return did, {'rows': len(rows), 'assets': len(assets), 'manifest': manifest}

def import_folder(db, path):
    path = Path(path)
    return import_files(db, {name: (path / name).read_bytes() for name in ('network.json','ops.json','telemetry.csv')}, path.name)
