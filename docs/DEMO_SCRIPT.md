# Three-minute presentation — actual restricted-host outcome

Use the latest [results](RESULTS.md), `.neural-pr/report.json` and `.neural-pr/controls/rejection.json`. Every synthetic example is labeled. Do not describe this build as a successful self-improvement experiment.

## 0:00–0:30 — State the experiment and the result

“Neural PR separates three histories: application code, reusable agent policy, and evaluation evidence. The task is an authored durable-job-service starter, not a production bug we discovered. This host blocked cloud API DNS, local port binding, and OS sandbox creation. We built and exercised the controller, but the live coding task remains unfinished and the result is no validated improvement.”

Show:

```sh
.venv/bin/python -m neural_pr report
```

Point to the separate source commit and agent-version hash. The dashboard can be launched on an unrestricted local host using `serve --port 8787`; this build verified its routes in-process and did not serve a browser preview.

## 0:30–1:00 — Actual failure, persistence and restart

“Two real transport attempts stopped before authentication. They created one incident with two occurrences. The controller recorded an infrastructure disposition rather than inventing a skill improvement. Successful API calls, provider token usage and coding rollouts are absent.”

Show `attempts/`, `incidents/`, `events.jsonl`, and `application.json`. Point out that `resume` was a separate CLI process and reconstructed the original active policy and verified application checkpoint. No baseline requirement was weakened.

## 1:00–1:40 — Policy change and gate, explicitly a control

“No live model-generated proposal exists. This next example is a human-authored synthetic negative control. It adds a reusable failed-hypothesis procedure; synthetic tied paired scores are rejected, and an unevaluated candidate cannot activate.”

Open `.neural-pr/controls/rejection.json` and show its label, exact diff, tied-score decision and `active_unchanged: true`. The same control is labeled in the dashboard's proposal card. Show the unit-tested gate conditions: strict improvement, no per-task decline, equal budgets, balanced pairs and isolation. The 12-rollout wiring test is scripted test infrastructure, not live evidence.

Explain that all eight real held-out tasks were prevalidated against starting defects, correct references and relevant wrong implementations. All A/B/audit blocks remain unconsumed.

## 1:40–2:15 — Actual rollback and independent validation

“The demonstration performed a real application rollback. It committed diagnostic work to a branch, restored the last verified source checkpoint, deleted a disposable fixture, and ran a restart smoke check. Policy rollback is separate and cannot erase verified source progress.”

Show `application_rolled_back` and `resume_verified` journal events and the diagnostic branch:

```sh
git -C .neural-pr/application branch --list
.venv/bin/python -m neural_pr demo
```

To repeat the real rollback exercise, use `demo --exercise-controls`. It deliberately restores the verified application checkpoint and preserves the prior work on another diagnostic branch.

## 2:15–3:00 — Honest limits and next experiment

“The integrated acceptance check reports the actual unfinished starter. The final audit is inconclusive because no model call succeeded; the audit tasks remain untouched. This host cannot verify Docker enforcement. Local code execution is explicitly unenforced and cannot authorize promotion. Tests validate the controller's mechanics, not the claim that an agent improved.”

Show exact setup/resume commands in README and the public results table. The next experiment is one frozen Meta baseline and one real failure-triggered proposal on a networked Docker host, followed by fresh promotion block A and a once-only final audit. No tuning after the audit.
