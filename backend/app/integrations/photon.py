"""Fail closed until a live Beta 2 signing and content-union contract is verified."""
import httpx
from app.config import settings

def status():
    return {'mode':settings.messaging_mode,'ready':settings.messaging_mode=='mock','detail':'Local simulation; no message leaves this app' if settings.messaging_mode=='mock' else 'Live unverified; inbound signing and identity fixture required'}

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
