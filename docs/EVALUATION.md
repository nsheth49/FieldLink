# Practice evaluation

The isolated evaluator is outside backend/app and is the only evaluation code that reads the practice answer key. Runtime detection and planning never receive the key. Baseline 2 was tuned on practice telemetry after the initial conservative 10% leak / 15% degradation settings missed early ongoing events. This is development data, not held-out generalization.

Snapshot: snapshot_2026-10-08T1200, ending October 8, 2026 at 12:00 UTC. Exact inputs are content-hashed in the dataset manifest. Parameters: 3% sustained stable-flow imbalance with pipeline pressure corroboration where available; six running samples below 95% configured flow with downward median trend; explicit pump fault or sustained failure to start. Stop-setpoint tolerance is 0.5 percentage point to accommodate noise.

| Category | Predictions / actual | Precision | Recall | Mean confirmation delay | Matched status accuracy |
|---|---|---|---|---|---|
| Pump failure | 5 / 5 | 1.00 | 1.00 | 0 s | 1.00 |
| Pipeline leak | 3 / 3 | 1.00 | 1.00 | 14,500 s (4.03 h) | 1.00 |
| Pump degradation | 5 / 5 | 1.00 | 1.00 | 56,940 s (15.82 h) | 1.00 |

Machine output: practice-evaluation.json. Predictions: practice-predictions.json. Matching is one-to-one same asset/category, with overlapping episodes OR onset within 30 minutes; closest onset chosen first. Slow changes may have long onset-to-confirmation delay despite matching correctly. Resolved timestamps also need more calibration. These are rule-based heuristic confidence scores, not a trained model or calibrated statistical probabilities.

Reproduce from the root after producing predictions:

```powershell
backend/.venv/Scripts/python.exe eval/evaluate.py --predictions docs/practice-predictions.json --answer-key data/vendor/eog/history/snapshot_2026-10-08T1200/answer_key.json --output docs/practice-evaluation.json
```

No final unseen test folder was imported or evaluated. Full-week evaluation, countdown error distribution, and cost comparison against snapshot reference schedules remain pending. Do not equate onset reference plans with snapshot-now plans.

The local browser test measures functional success, not live message latency. No Photon round-trip or acknowledgment latency has been measured. The browser scenario reports a truck unavailable for 60 scenario minutes, receives revised v2, approves exactly that plan, and explicitly acknowledges it. This does not qualify a live integration.

Planner limits: bounded enumeration, simultaneous initial calls, minute-grid common shut-in time per selected well subset, equal trip counts per assigned group, initial unavailable trucks excluded. Joint branch-and-bound enforces a shared fleet; it does not enumerate every sequential yard-return assignment or heterogeneous delayed shut-in schedule. Report least cost found, never proven global optimum.
