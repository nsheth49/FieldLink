# FieldLink build status

Updated November 8, 2026. Local mock vertical slice works; the complete live sponsor demonstration is not complete.

## Implemented

- [x] Inspected empty repository; extracted complete spec in order to BUILD_SPEC.md with table rows preserved. Source document unchanged.
- [x] EOG reference checkout pinned to `135ba4c8348357457420a1111df80ec1906bcbdb`. Agent-directed upstream README text ignored as untrusted data.
- [x] Transactional, hash-addressed three-file import; original files retained, topology and numeric checks, timestamps, duplicate keys, unknown metrics and nonfinite data validation.
- [x] SQLAlchemy schema, Alembic migration, persistent state and optional existing Timescale extension path; SQLite local fallback exercised.
- [x] Causal state machine for failures, leaks and degradation; evidence, suspect/confirmed/resolved status, missing-data labels and priority countdowns.
- [x] Event-based simulator; exact threshold crossing, no over-removal or revenue double counting, remaining repair horizon, shared fleet, mixed candidates and minute-grid delayed shut-ins.
- [x] Snapshot, replay and scenario modes; cursor-capped queries; backward seek creates a fresh run; observed/simulated chart separation.
- [x] Scrypt provisioned credentials, expiring opaque sessions, supervisor/operator/judge checks, scope checks, origin/request protection; no registration or client-selected role.
- [x] Atomic version/fingerprint/expiry/resource checks, concurrent approval protection, simulated dispatch, rejection/superseding and acknowledgment audit.
- [x] Worker-owned replay, analysis, planning and durable conversation jobs; bounded retries; unique outbox keys and unknown-delivery handling.
- [x] Structured truck constraints with source and scenario expiry; ambiguity clarification; bounded Nemotron tool loop, mock fallback and visible sanitized tool activity.
- [x] React/TypeScript/Vite dashboard, Router, TanStack polling, Recharts, CSS Modules and Lucide; plans, evidence, conversations, approval, evaluation and import/settings.
- [x] Isolated evaluator; real snapshot practice results; setup script, dependency locks, deployment configuration and demo runbook.

## Evidence

Imported 196,755 readings / 105 assets. At snapshot now, detector shows three failures, two degradation events and one leak. Practice evaluation matched all 13 episodes with zero false alarms under declared overlap/onset rules; gradual-condition delays remain large. See EVALUATION.md.

Latest validation: 27 backend tests passed, including strict live-adapter protocol, credential-safe provider diagnostics, worker recovery and authorization checks; 3 Vitest tests passed; TypeScript/Vite production build passed. Earlier pip check, migration rerun and one actual Playwright mock flow passed: snapshot → v1 → truck constraint → v2 → exact approval → acknowledgment at laptop width and mobile overflow. The browser flow has not been repeated against live NVIDIA. Vite retains a non-failing large-bundle warning.

November 8 API follow-up: moved configured values from the tracked example into ignored .env, restored the example, generated SESSION_SECRET and verified NVIDIA through a real two-round tool/result exchange plus actual bounded adapter calling compare_response_plans with synthetic tools. Corrected strict tool schema compatibility and disabled thinking to fit the bounded token output. AI_MODE=live locally; messaging stays mock. No external message was sent.

## Remaining blockers and gaps

- [x] NVIDIA credentials and real tool-call smoke test, including bounded adapter check. Complete NVIDIA/Photon workflow and prize qualification still unverified.
- [ ] Photon project/channel, verified tester identities, complete signature/freshness contract and real sanitized fixture. Outbound Beta plain-text adapter is mock-transport tested only; public webhook mutations return 503. No live round trip or Photon qualification claim.
- [ ] Tiger Cloud credentials, TLS, PostgreSQL/Timescale migration and locking smoke tests. SQLite does not qualify.
- [ ] Python 3.12 unavailable locally; lock resolved on 3.13, Node 24.14.1. Docker targets 3.12; Linux/Compose compatibility untested.
- [ ] Optional approved Vultr VM/budget/hostname. No paid resources or external deployment provisioned.
- [ ] Real provider-event dedup/reordering, live outbox reconciliation, reminders, coalesced incident notifications, live message latency and production login rate limiting.
- [ ] Planner omits sequential yard-return reassignments, unequal trips per called group and independently delayed per-well times. Completeness refers only to implemented candidate space, never proven global optimum.
- [ ] Proposed simulator traces are separate from recordings; continuously advancing interactive forecast execution is not implemented. Approval records simulated dispatch only.
- [ ] COMPLETE/EXPIRED lifecycle automation and database-level append-only audit triggers. Audit is currently append-only through application routes.
- [ ] Full-week and final unseen evaluation, countdown-error distribution and reference-plan cost gaps. No held-out folder imported.

No credentials committed. Local testing credentials are in ignored .runtime. All dispatches are simulated.
