export type User={id:string;role:string}
export type Dataset={id:string;name:string;start:number;end:number;manifest:Record<string,string>}
export type Incident={event_id:string;system_id:string;facility_id:string;asset_id:string;category:string;status:string;provisional:boolean;level_pct:number;hours_to_limit:number|null;remaining_repair_hours:number;onset_unix:number;confidence:number;evidence:{asset_id:string;metric:string;value:number;ts:number}[]}
export type Facility={facility_id:string;system_id:string;level_pct:number;inflow_bpd:number;flow_bpd:number;observed_ts:number}
export type Action={type:string;at_hours:number;truck_id?:string;well_id?:string;bbl?:number}
export type FacilityPlan={facility_id:string;actions:Action[];total_cost:number;lost_revenue:number;truck_cost:number;prevents_shutdown:boolean;reason:string;trace:{hours:number;level_pct:number}[]}
export type Solution={total_cost:number;facilities:FacilityPlan[];reservations:{truck_id:string;start:number;end:number}[]}
export type Plan={id:string;version:number;fingerprint:string;status:string;expires:number;system_id:string;baseline:Solution;recommended:Solution;alternatives:Solution[];search_complete:boolean;optimality:string;elapsed_ms:number;truck_ids:string[];incident_count:number}
export type State={id:string;dataset_id:string;mode:string;cursor:number;paused:boolean;speed:number;revision:number;analysis_pending:boolean;events?:Incident[];history?:Incident[];facilities?:Facility[];data_quality?:string[];constraints:{id:string;truck_id:string;until:number;source:string}[];jobs:{kind:string;status:string}[];parameters?:Record<string,string|number>;providers:{ai:string;messaging:{mode:string;ready:boolean;detail:string}};topology:{defaults:{tank_limits_pct:{warning:number;shutdown:number}};systems:{id:string;facilities:{id:string;tank:{id:string};pump:{id:string};pipeline:{id:string};wells:{id:string}[]}[]}[]};ops:{systems:Record<string,{emergency_fleet_size:number}>}}
export type Message={id:string;actor:string;text:string;delivery:string;scenario_ts:number;wall_ts:number}
export async function api<T>(path:string,body?:unknown):Promise<T>{
 const response=await fetch(`/api${path}`,{credentials:'include',method:body===undefined?'GET':'POST',headers:{'X-FieldLink-Request':'1',...(body instanceof FormData?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body)})
 const result=await response.json().catch(()=>({}));if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:`Request failed (${response.status})`);return result as T
}
export const utc=(ts:number)=>new Date(ts*1000).toISOString().replace('T',' ').slice(0,16)+' UTC'
export const money=(v:number)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(v)
export const title=(v:string)=>v.replaceAll('_',' ')
