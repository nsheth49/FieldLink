# Local demo and operational runbook

1. Run setup, clone the pinned EOG source, and import snapshot_2026-10-08T1200 using README commands. Keep generated credentials private.
2. Start API on 8080, worker, and Vite on 5173 in separate terminals. Open http://localhost:5173 and sign in as supervisor.
3. Choose the snapshot, select Interactive scenario, then New run. Wait for six active incidents. S2 failures sort by shutdown countdown, then production at risk.
4. Inspect the tank chart and expand sensor evidence. Observed readings stop at the cursor. The dashed simulated trace is a proposal from the simulator, never recorded future telemetry.
5. Compare S2 plans. Review the do-nothing baseline, least cost found, shared-truck schedule and accepted/prevented shutdowns.
6. Open Conversations. Send `S2_TRUCK_1 unavailable for 60 scenario minutes`. Mock assistant records the structured constraint and recalculates once. Try `until 10` to demonstrate clarification instead of guessing.
7. Return to Overview and review version 2. Approve simulated plan. The server checks role, exact version, fingerprint, expiry and reservations. Acknowledge explicitly; provider delivery does not count as acknowledgment.
8. Evaluation exposes parameters, provenance and sponsor-compatible JSON export. Use the isolated CLI to compare practice predictions. All mock providers and SQLite fallback remain visibly identified.
9. For replay, create a fresh historical replay run. Resume/pause, change speed, or seek from Settings; seeking creates a new run. No automated outbound incident messages are enabled in replay.

Expected snapshot baseline is approximately $12,120 under the current observed rates; actual candidate costs depend on constraints and minute-grid search. Use calculated UI figures. All dispatches are simulated. No live sponsor qualification is established.

Recovery: stop/restart the worker; runs, plans, reservations and messages persist in the database. Failed jobs retry three times with bounded backoff. Outbound ambiguous submissions are marked unknown and are not resent automatically. Live delivery reconciliation remains blocked. Approval notifications use a unique durable outbox key.

Hosting preparation: configure a TLS PostgreSQL DATABASE_URL using `postgresql+psycopg://...`, a long SESSION_SECRET, APP_ENV=production and APP_PUBLIC_URL=https://your-host in ignored .env. Configure APP_HOST in the Compose shell environment. Enable Timescale extension before the initial migration if using a Tiger service; extension absence retains plain PostgreSQL. Run `docker compose -f deploy/compose.yml up --build -d`, then seed users with `docker compose -f deploy/compose.yml exec api python -m app.cli seed-users`. Deploy only on a user-approved machine. Expose HTTPS and required HTTP validation; keep database and API ports private. Docker/Vultr has not been exercised here.

Before a live demonstration: verify Python 3.12/Linux locks, PostgreSQL schema/locking, real Nemotron tools, Photon authenticated channel/identity, signature freshness, real sanitized fixture, outbox reconciliation and actual iMessage send/reply with consenting testers. Never paste secrets into frontend config. Record failures and provider status rather than implying success.
