# FieldLink

Field operations prototype: validated EOG recordings → causal incidents → deterministic shared-fleet plans → operator constraints → exact supervisor approval → simulated dispatch and acknowledgment.

**Local workflow implemented; live NVIDIA tool calling verified. Photon, Tiger Cloud and Vultr remain unverified.** The example defaults to mock providers; the configured local .env now uses live NVIDIA and mock messaging. See [build status](docs/BUILD_STATUS.md), [provider contracts](docs/PROVIDER_CONTRACTS.md), [evaluation](docs/EVALUATION.md), and [demo/runbook](docs/DEMO.md).

## Setup on Windows

Requires compatible Node LTS (22.12+ in Node 22 or newer) and Python 3.12. This machine was validated using Node 24.14.1 and Python 3.13 because 3.12 is absent.

```powershell
# Use -PythonVersion 3.13 on this machine.
./scripts/setup.ps1 -PythonVersion 3.12
git clone https://github.com/nihaal419/HackUTD-ZeroDay.git data/vendor/eog
git -C data/vendor/eog checkout 135ba4c8348357457420a1111df80ec1906bcbdb
backend/.venv/Scripts/python.exe -m app.cli import-dataset --path data/vendor/eog/history/snapshot_2026-10-08T1200
```

The script generates random credentials once and preserves existing users. For the initialized workspace, credentials for all three roles are in ignored `.runtime/credentials.json`; the local supervisor password is also in `.runtime/e2e-password`. Keep these private. No fixed default passwords are shipped.

If PowerShell execution policy prevents scripts, run these directly:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
backend/.venv/Scripts/python.exe -m pip install -e ./backend --no-deps
npm --prefix frontend ci
Copy-Item .env.example .env
backend/.venv/Scripts/python.exe -m app.cli migrate
backend/.venv/Scripts/python.exe -m app.cli seed-users
```

## Run in three terminals

```powershell
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --port 8080
```

```powershell
backend/.venv/Scripts/python.exe -m app.worker
```

```powershell
npm --prefix frontend run dev
```

Open http://localhost:5173. Health: http://127.0.0.1:8080/api/health . OpenAPI: http://127.0.0.1:8080/docs . Worker is required for analysis, plans and operator replies. Root .env is loaded explicitly. PostgreSQL URLs use `postgresql+psycopg://`; configure TLS for Tiger Cloud.

Choose the snapshot and Interactive scenario, then New run. Compare S2 plans. Report `S2_TRUCK_1 unavailable for 60 scenario minutes` in Conversations. Review v2, approve as supervisor, and acknowledge separately. All dispatches are simulated.


Docker/Caddy assets under deploy/ target external PostgreSQL. Python 3.12/Linux, Tiger service and Vultr deployment need smoke tests. Full limitations and live-integration blockers are in docs/BUILD_STATUS.md.
