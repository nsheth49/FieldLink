import { useQuery } from '@tanstack/react-query'
import { Activity } from 'lucide-react'
import { api } from '../../api'
import s from '../../App.module.css'
type Trace={job_id:string;status:string;elapsed_ms?:number;trace:{tool?:string;mode?:string;error?:string}[]}
export function ToolActivity({runId}:{runId:string}){
 const data=useQuery({queryKey:['activity',runId],queryFn:()=>api<Trace[]>(`/runs/${runId}/activity`),enabled:!!runId,refetchInterval:2000})
 if(!data.data?.length)return null
 return <details className={s.evidence}><summary><span><Activity size={13}/> Assistant tool activity</span></summary>{data.data.map(job=><div key={job.job_id}><p>{job.status} · {job.elapsed_ms??'—'} ms</p>{job.trace.map((t,i)=><p key={i}>{t.tool||t.error} · {t.mode||'fallback'}</p>)}</div>)}</details>
}
