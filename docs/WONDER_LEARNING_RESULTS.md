# First live Wonder coding run

The infrastructure is now working in the ordinary Terminal. Wonder completed the authored durable-job service, and the independent verifier passed all 16 application checks. The run did **not** demonstrate an agent-policy improvement.

**Subsequent result:** the separate policy follow-up completed under the original controller and passed block A: candidate 6/6, incumbent 2/6, followed by promotion and a passing application canary. See [verified policy-upgrade evidence](VERIFIED_POLICY_UPGRADE.md). The table below describes the first main-task/audit run only.

| Measurement | Actual result |
| --- | --- |
| Main coding attempts | 1 |
| Main application checks | 16/16 passed |
| Main model calls | 18 |
| Main tool calls executed | 3 |
| Main responses rejected as invalid JSON | 15/18 |
| Main worker termination | Call budget exhausted; resulting software passed |
| Policy proposal calls | 0 |
| Policy promotions | 0 |
| Independent audit runs | 8 |
| Audit software successes | 5/8 |
| Final audit decision | `audit_failed` |

The main application source was preserved at commit `3117f57017203d2afb47538ecf7d768cece993b7`. Idempotency, execution, recovery, cancellation, restart, atomic claims, fencing and API/client integration checks passed. This is an authored software fixture, not a discovered production defect.

The audit's incumbent and selected-policy hashes were identical: `ff43076cfa966003e945611829139657056e1a65e5d4e1733bc9287db0808c22`. The two labeled groups scored 2/4 and 3/4 respectively. Those are repeated attempts of the **same policy**, not evidence that one policy improved. The strict audit correctly failed because the selected-policy group did not pass every required attempt.

The three failing audit runs exhausted their call budgets before writing an implementation. Their traces contain repeated narrative text followed by a JSON action, rejected by the worker's strict JSON parser. Similar protocol failures appeared in the main development trace: 15 of 18 responses were invalid actions. The successful main code and poor action-format reliability can both be true. This identifies an observed process problem; it does not establish that a prompt change will solve it.

The original controller creates a learning incident when a main milestone fails. Here all milestones passed, so no proposer ran before final selection. The final audit cannot be reused as fresh evidence or adapted against while retaining its final-audit label. `execution_status=completed` means the workflow finished, not that every outcome passed.

## Bounded prospective follow-up

**Completed historical follow-up:** saved records confirm that this plan ran under the original strict controller. Wonder authored a candidate and the controller promoted it after block A passed. A later request repaired the original worker implementation; the CLI now refuses to rerun the historical policy-only protocol against changed code. The [policy-upgrade evidence](VERIFIED_POLICY_UPGRADE.md) and [worker implementation repair](ORIGINAL_WORKER_FIX.md) are separate results.

The follow-up harness uses **only the main development trace's protocol-error statistics**, not audit task definitions, solutions, trajectories or failed hidden checks. Wonder authored the candidate skill/context change itself, and the subsequent live paired comparison passed. The candidate was not hand-written.

```sh
.venv/bin/python scripts/run_policy_followup.py
```

Run that command from the ordinary Terminal. It:

1. Preserves the completed original experiment and freezes a separate follow-up protocol.
2. Keeps the exact Wonder model/adapter, tools, evaluation budgets, gate, environment and task bank fixed.
3. Imports the completed application commit and verifies its canary; it does not discard successful source progress.
4. Carries the consumed audit forward as ineligible. Only the untouched promotion block A is eligible.
5. Asks Wonder for at most one reusable policy proposal based on the development protocol failure. Unsupported, redundant, malformed or out-of-scope proposals stop without a promotion.
6. Freezes an eligible policy and delegates the 12 paired coding rollouts to the existing evaluator: three tasks, two attempts, two policies.
7. Activates the new hash only if the original strict gate passes and the application canary remains valid. Otherwise it retains the incumbent.

It inherits the source experiment's deadline and refuses to start when the worst-case paired comparison cannot fit. There is one registered follow-up per source to prevent using a different state directory to recycle block A. Block B remains outside this protocol. A fresh independent final audit is not available; any passing block-A result would be **pilot transfer evidence**, not a fresh final-audit acceptance or retroactive improvement of the first main episode.

This is a human-authored failure detector and coordinator around the existing autonomous proposer and evaluator. The proposed policy must be agent-authored; the harness itself is not claimed as an autonomously learned improvement. Subsequent main-task progress under a promoted procedure would remain a separate demonstration.

The completed follow-up state is `.neural-pr-wonder-policy-v2`. `followup_protocol.json` binds the development trace, source experiment, model identity, baseline policy and gate. `followup_result.json` contains the passing proposal/evaluation outcome. The source run is `.neural-pr-wonder-v1`; its historical accepted pointer remains unchanged, while the follow-up's active pointer selects the promoted policy.

Five focused checks pass for development-only evidence, refusal to recycle exposed promotion work, one registered follow-up, refusal to manufacture an incident from a clean successful trace, and delegation of exactly one block-A comparison without invoking the audit. The live proposal and paired evaluation ran in the ordinary Terminal. The restricted tool shell performed read-only evidence verification afterward.
