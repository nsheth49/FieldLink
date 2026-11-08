"""Fail closed until a live Beta 2 signing and content-union contract is verified."""
import httpx
from app.config import settings

def status():
    fields={'PHOTON_API_KEY':settings.photon_api_key,'PHOTON_PROJECT_ID':settings.photon_project_id,
            'PHOTON_SENDER_ID':settings.photon_sender_id,'PHOTON_WEBHOOK_SECRET':settings.photon_webhook_secret}
    missing=[key for key,value in fields.items() if not value]
    issues=[]
    if settings.photon_project_id and not settings.photon_project_id.startswith('pho_prj_'):
        issues.append('Project ID is not a Photon Beta 2 project ID (pho_prj_...)')
    if settings.photon_api_key and not settings.photon_api_key.startswith('pho_sk_'):
        issues.append('Use a scoped Photon Beta 2 project API key (pho_sk_...)')
    return {'mode':settings.messaging_mode,'ready':settings.messaging_mode=='mock',
            'configured':not missing and not issues,'missing':missing,'issues':issues,'inbound_enabled':False,
            'detail':'Local simulation; no message leaves this app' if settings.messaging_mode=='mock' else 'Live unverified; inbound signing and identity fixture required'}

def send(payload,client=None):
    if settings.messaging_mode=='mock': return {'delivery':'mock','provider_id':None}
    if not settings.photon_api_key or not settings.photon_project_id or not settings.photon_sender_id or not payload.get('verified_space_id'):
        raise RuntimeError('Live Photon requires credentials and a verified allowlisted conversation')
    body={'spaceId':payload['verified_space_id'],'senderId':settings.photon_sender_id,'content':{'type':'text','format':'plain','text':f'[SIMULATION · scenario {payload["scenario_ts"]} UTC epoch] {payload["text"][:1500]}'}}
    headers={'Authorization':f'Bearer {settings.photon_api_key}','Idempotency-Key':payload['idempotency_key']}
    def submit(c):
        response=c.post(f'https://api.photon.codes/v1/projects/{settings.photon_project_id}/messages',json=body,headers=headers)
        response.raise_for_status(); result=response.json()
        return {'delivery':'submitted','provider_id':result.get('id')}
    if client is not None:return submit(client)
    with httpx.Client(timeout=10) as c:return submit(c)

def verify_envelope(raw,headers):
    raise RuntimeError('Trusted webhooks disabled until provider signature/freshness contract is established')
