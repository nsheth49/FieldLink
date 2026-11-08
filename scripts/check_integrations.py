"""Explicit read-only provider diagnostics. Never print credentials or send messages."""
import argparse
import json
import time
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from app.config import ROOT, settings


class TestArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')


def configuration():
    required = ('PHOTON_API_KEY', 'PHOTON_PROJECT_ID', 'PHOTON_SENDER_ID', 'PHOTON_WEBHOOK_SECRET')
    photon = {name: bool(getattr(settings, name.lower())) for name in required}
    return {
        'runtime_env_exists': (ROOT / '.env').exists(),
        'nvidia': {'key_present': bool(settings.nvidia_api_key), 'mode': settings.ai_mode, 'model': settings.nvidia_model},
        'photon': {'mode': settings.messaging_mode, 'configured': photon,
                   'beta_project_id_format': settings.photon_project_id.startswith('pho_prj_'),
                   'beta_project_key_format': settings.photon_api_key.startswith('pho_sk_'),
                   'inbound_enabled': False},
        'database': {'configured': not settings.database_url.startswith('sqlite:'),
                     'type': 'sqlite' if settings.database_url.startswith('sqlite:') else 'postgresql'},
        'session_secret_configured': len(settings.session_secret) >= 32 and not settings.session_secret.startswith('replace-'),
    }


def nvidia_smoke():
    if not settings.nvidia_api_key:
        return {'status': 'missing_key'}
    started = time.monotonic()
    try:
        client = OpenAI(api_key=settings.nvidia_api_key, base_url=settings.nvidia_api_base, timeout=20, max_retries=0)
        tool = {'type': 'function', 'function': {
            'name': 'get_test_value', 'description': 'Return the constant integer 7. Harmless diagnostic only.',
            'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}}
        messages = [{'role': 'user', 'content': 'Call get_test_value once, then report only its returned value.'}]
        result = client.chat.completions.create(
            model=settings.nvidia_model, messages=messages, tools=[tool],
            tool_choice={'type': 'function', 'function': {'name': 'get_test_value'}},
            max_tokens=256, extra_body={'chat_template_kwargs': {'enable_thinking': False}})
        answer = result.choices[0].message
        calls = answer.tool_calls or []
        if len(calls) != 1 or calls[0].function.name != 'get_test_value':
            return {'status': 'tool_call_missing'}
        TestArgs.model_validate_json(calls[0].function.arguments)
        messages.append({'role': 'assistant', 'content': answer.content, 'tool_calls': [
            {'id': call.id, 'type': 'function', 'function': {'name': call.function.name, 'arguments': call.function.arguments}}
            for call in calls]})
        messages.append({'role': 'tool', 'tool_call_id': calls[0].id, 'content': '{"value":7}'})
        final = client.chat.completions.create(model=settings.nvidia_model, messages=messages, max_tokens=128,
                                               extra_body={'chat_template_kwargs': {'enable_thinking': False}})
        return {'status': 'passed' if '7' in (final.choices[0].message.content or '') else 'tool_result_not_grounded',
                'tool': 'get_test_value', 'rounds': 2, 'elapsed_ms': round((time.monotonic() - started) * 1000)}
    except Exception as error:
        # Provider exception messages/bodies may contain request details; never print them.
        return {'status': 'failed', 'error_type': type(error).__name__,
                'http_status': getattr(error, 'status_code', None),
                'elapsed_ms': round((time.monotonic() - started) * 1000)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-nvidia', action='store_true', help='Make two tiny NVIDIA diagnostic completions')
    parser.add_argument('--runtime-agent', action='store_true', help='Verify the real bounded adapter against harmless synthetic tools')
    parser.add_argument('--output', type=Path, help='Write sanitized JSON report')
    args = parser.parse_args()
    report = configuration()
    if args.live_nvidia:
        report['nvidia']['smoke'] = nvidia_smoke()
    if args.runtime_agent:
        from app.integrations.nemotron import reply
        if settings.ai_mode != 'live':
            report['nvidia']['runtime_agent'] = {'status':'requires_live_mode'}
        else:
            result=reply('Recalculate the response using compare_response_plans and report the plan version. This is a harmless synthetic test.', {
                'get_incident_context':lambda:{'simulation':True,'incident':'diagnostic','events':[]},
                'get_system_resources':lambda:{'simulation':True,'truck_ids':[]},
                'compare_response_plans':lambda:{'simulation':True,'version':1,'total_cost':0}})
            traces=result['trace']
            report['nvidia']['runtime_agent']={'status':'passed' if any(t.get('tool')=='compare_response_plans' and t.get('mode')=='live' for t in traces) and not any('error' in t for t in traces) else 'failed','trace':traces}
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text)
    if args.live_nvidia and report['nvidia']['smoke']['status'] != 'passed':
        raise SystemExit(1)
    if args.runtime_agent and report['nvidia']['runtime_agent']['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
