def countdown(level_pct, capacity_bbl, shutdown_pct, inflow_bpd, pump_flow_bpd):
    if level_pct >= shutdown_pct - 0.05: return 0.0, 'Tank already tripped'
    net = (inflow_bpd-pump_flow_bpd)/24
    if net <= 0: return None, 'No positive net inflow'
    return max(0, (shutdown_pct-level_pct)/100*capacity_bbl/net), 'Constant current net inflow estimate'

def revenue(well, prices):
    return (well['oil_bpd']*prices['oil_per_bbl'] + well['gas_mcfd']*prices['gas_per_mcf'])/24
