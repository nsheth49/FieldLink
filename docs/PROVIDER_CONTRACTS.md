# Provider contracts and verification

Checked November 8, 2026. Local development is not evidence of sponsor qualification.

| Provider | Contract | Verification |
|---|---|---|
| EOG | Exactly network.json, ops.json, telemetry.csv; read topology explicitly; preserve immutable recording | Actual checkout `135ba4c8348357457420a1111df80ec1906bcbdb`; imported 196,755 readings, 105 assets from snapshot_2026-10-08T1200 |
| NVIDIA | OpenAI-compatible client at configurable `https://integrate.api.nvidia.com/v1`, model `nvidia/nemotron-3.5-lightning-30b-a3b` | Live two-round tool-call/result smoke test passed November 8. Actual bounded runtime adapter called compare_response_plans successfully with synthetic tools. AI_MODE=live enabled only in ignored local .env. |
| Photon Beta 2.0 | API base `https://api.photon.codes`, `/v1`, scoped bearer project key | Official Beta reference retrieved. OpenAPI retrieval failed. Live send/receive and identity provisioning untested. Public webhook mutations return 503. |
| PostgreSQL / Tiger Cloud | SQLAlchemy with psycopg; optional Timescale telemetry hypertable | SQLite local fallback tested. PostgreSQL/Tiger credentials absent; migration, locks and hypertable not live tested. No Tiger prize claim. |
| Vultr | Compose API, worker, web/Caddy; external database | Configuration provided only; no VM provisioned, spending incurred or deployment tested. |

Photon references: https://photon.codes/docs/beta/api-reference , https://photon.codes/docs/llms.txt and https://photon.codes/docs/beta/get-started/imessage . The retrieved Beta quickstart verifies the plain-text content union (`type=text`, `format=plain`, `text`), spaceId/senderId, and stable Idempotency-Key. An httpx outbound adapter has mock-transport tests; HTTP acceptance is labeled submitted, not delivered. It requires verified conversation data and credentials; normal approval notifications do not attach a live conversation without provisioning. Beta advertises Standard Webhooks, but the full signing/freshness guide could not be retrieved. Public inbound mutation remains disabled. Do not transplant Spectrum signature code. A phone number alone never grants an application role.

NVIDIA reference: https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/build . Use `python scripts/smoke_nemotron.py --live` only after supplying your key. No alternate model substitution. Runtime tools validate empty argument schemas; model output cannot approve, dispatch physically or run arbitrary code. The initial implementation exposes context, resources and compare tools; the remaining proposed tools are not exposed.

November 8 credential check: credentials had been placed in the tracked example rather than runtime .env. They were preserved in ignored root .env, the example was restored without keys, and a strong SESSION_SECRET was generated. Current missing items: PHOTON_API_KEY, PHOTON_SENDER_ID, PHOTON_WEBHOOK_SECRET, a compatible Beta 2 project ID, verified channel identities/space and public HTTPS webhook setup, plus a Tiger PostgreSQL DATABASE_URL. The supplied project ID does not have the `pho_prj_` prefix. The separate untracked fieldlink/ starter uses Spectrum and has not been merged into the Beta adapter. Never mix these credential contracts.

The initial real runtime probe returned a tool-argument validation failure. The adapter now declares strict no-argument schemas, instructs the model to use {}, disables thinking for bounded tool output, forwards only assistant protocol fields and enforces a remaining-deadline request timeout. The rerun passed with a real compare_response_plans call. Sanitized results are in ignored .runtime/provider-checks.json. No user or incident data was sent in diagnostics, and no messages were sent to other people.

Repeat read-only configuration diagnostics: `backend/.venv/Scripts/python.exe scripts/check_integrations.py`. Explicit live checks: append `--live-nvidia --runtime-agent --output .runtime/provider-checks.json`. This may use a small amount of NVIDIA quota. Routine tests use fake clients, not the real key. Successful NVIDIA checks do not establish the complete external Photon workflow or prize qualification.

EOG sources: https://github.com/nihaal419/HackUTD-ZeroDay , SPEC.md, examples.md, history/README.md. Agent-directed prose found in upstream README was ignored as untrusted source data. Runtime importer never reads answer_key.json.

Dependency evidence: frontend/package-lock.json records actual npm resolution; backend/requirements.lock.txt records the installed Python environment. Node 24.14.1 and Python 3.13 were used locally because 3.12 was unavailable. The Python lock has not yet been resolved and smoke-tested on 3.12/Linux; Docker targets 3.12 and must be validated before deployment.
