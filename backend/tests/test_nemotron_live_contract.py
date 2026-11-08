from types import SimpleNamespace

from app.integrations import nemotron, photon


def tool_call(arguments='{}', name='compare_response_plans'):
    return SimpleNamespace(id='call-test', function=SimpleNamespace(name=name, arguments=arguments))


def install_client(monkeypatch, answers):
    requests = []
    timeouts = []

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def with_options(self, **kwargs):
            timeouts.append(kwargs['timeout'])
            return self

        def create(self, **kwargs):
            requests.append(kwargs)
            message = answers.pop(0)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(nemotron, 'OpenAI', Client)
    monkeypatch.setattr(nemotron.settings, 'ai_mode', 'live')
    monkeypatch.setattr(nemotron.settings, 'nvidia_api_key', 'secret-test-key-not-for-output')
    return requests, timeouts


def test_live_tool_protocol_and_thinking_budget(monkeypatch):
    requests, timeouts = install_client(monkeypatch, [
        SimpleNamespace(content=None, tool_calls=[tool_call()], reasoning_content='must not be exposed'),
        SimpleNamespace(content='Review plan version 2 with your supervisor.', tool_calls=None),
    ])
    executions = []
    result = nemotron.reply('Please replan', {'compare_response_plans': lambda: executions.append(1) or {'version': 2}})
    assert executions == [1]
    assert result['trace'] == [{'tool': 'compare_response_plans', 'mode': 'live'}]
    assert 'supervisor' in result['text']
    schema = requests[0]['tools'][0]['function']
    assert schema['strict'] is True and schema['parameters']['required'] == []
    assert schema['parameters']['additionalProperties'] is False
    assert all(r['extra_body']['chat_template_kwargs']['enable_thinking'] is False for r in requests)
    assert all(0 < timeout <= 10 for timeout in timeouts)
    assistant = requests[1]['messages'][2]
    assert set(assistant) == {'role', 'content', 'tool_calls'}
    assert requests[1]['messages'][3]['role'] == 'tool'
    assert 'secret-test-key-not-for-output' not in str(result)


def test_invalid_tool_arguments_have_no_side_effect(monkeypatch):
    install_client(monkeypatch, [SimpleNamespace(content=None, tool_calls=[tool_call('{"role":"supervisor"}')])])
    executions = []
    result = nemotron.reply('Approve', {'compare_response_plans': lambda: executions.append(1)})
    assert not executions
    assert result['trace'][0]['error'] == 'ValidationError'
    assert result['trace'][0]['validation_fields'] == [['role']]
    assert 'secret-test-key-not-for-output' not in str(result)


def test_unknown_tool_and_excessive_calls_are_rejected(monkeypatch):
    for calls in ([tool_call(name='execute_shell')], [tool_call() for _ in range(7)]):
        install_client(monkeypatch, [SimpleNamespace(content=None, tool_calls=calls)])
        executions = []
        result = nemotron.reply('test', {'compare_response_plans': lambda: executions.append(1)})
        assert not executions
        assert result['trace'][0]['error'] == 'ValueError'


def test_photon_diagnostics_distinguish_missing_and_incompatible(monkeypatch):
    for name in ('photon_api_key', 'photon_sender_id', 'photon_webhook_secret'):
        monkeypatch.setattr(photon.settings, name, '')
    monkeypatch.setattr(photon.settings, 'photon_project_id', 'spectrum-project-not-beta')
    result = photon.status()
    assert not result['configured'] and not result['inbound_enabled']
    assert set(result['missing']) == {'PHOTON_API_KEY', 'PHOTON_SENDER_ID', 'PHOTON_WEBHOOK_SECRET'}
    assert 'pho_prj_' in result['issues'][0]
    assert 'spectrum-project-not-beta' not in str(result)
