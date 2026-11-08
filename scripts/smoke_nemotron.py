"""Explicit opt-in harmless live tool call. Never messages a phone."""
import argparse
from openai import OpenAI
from app.config import settings
p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');args=p.parse_args()
if not args.live or not settings.nvidia_api_key:raise SystemExit('Requires --live and NVIDIA_API_KEY in ignored .env')
c=OpenAI(api_key=settings.nvidia_api_key,base_url=settings.nvidia_api_base,timeout=30,max_retries=0)
r=c.chat.completions.create(model=settings.nvidia_model,messages=[{'role':'user','content':'Call get_test_value once. This is a harmless integration smoke test.'}],tools=[{'type':'function','function':{'name':'get_test_value','description':'Return the constant 7','parameters':{'type':'object','properties':{},'additionalProperties':False}}}],max_tokens=256)
calls=r.choices[0].message.tool_calls
assert calls and calls[0].function.name=='get_test_value','Model did not return expected tool call'
print('Verified tool-call response:',settings.nvidia_model,'get_test_value (no side effects)')
