# Verified pilot coding-policy improvement

Wonder authored a policy change from recorded development protocol failures. The trusted controller froze it, compared it with the incumbent on untouched block A, recomputed a passing gate, promoted the exact evaluated hash and passed the completed application's canary. This is an actual pilot policy improvement under the **original strict JSON worker**.

| Coding task | Incumbent | Candidate |
| --- | --- | --- |
| Scope | 0/2 | 2/2 |
| Fencing | 1/2 | 2/2 |
| Client errors | 1/2 | 2/2 |
| **Total** | **2/6** | **6/6** |

There were four candidate-only successes, zero incumbent-only successes and two shared successes. All 12 rollouts had matching per-task starting commits, identical budgets, the same Wonder model/adapter and the same Docker environment. The gate required strictly more completions, no per-task regression, complete pairs, budget compliance and enforced isolation. A `budget_exhausted` worker label does not override independently verified software completed within its fixed budget.

The sole policy change appended this skill:

> For every coding-worker action, output exactly one strict JSON action object as the entire response, with no narrative, explanation, or markdown before or after it.

The incumbent's existing system instructions already requested JSON. This result supports the added skill's usefulness in this bounded pilot; it does not imply a new general reasoning capability.

| Secondary measurement | Incumbent | Candidate |
| --- | --- | --- |
| Whole-response JSON rejections | 39/60 | 22/59 |
| Executed tool calls | 21 | 36 |
| Model calls | 60 | 59 |
| Accounted model tokens | 40,420 | 43,402 |
| Worker elapsed seconds, summed | 96.48 | 102.28 |

These measurements are consistent with fewer wasted format-error turns permitting more useful work. They do not independently establish a mechanism or eliminate sampling uncertainty. Three tasks and two attempts per task are pilot evidence.

## Provenance and checks

- Incumbent: `ff43076cfa966003e945611829139657056e1a65e5d4e1733bc9287db0808c22`.
- Candidate/active follow-up policy: `75ce5b3dd14f539005135595da5508c5e0e9788b62ca70291b85c426d5425d20`.
- Evaluation: `cdecee936db54e96860d94e86ae30d0f`.
- Controller digest: `81b2556f806a6d8c9b7f8f510b6475881171351a864215d5c96c72ca71bfbfa8`.
- Model: `muse-wonder-1.0`, `meta-wonder-json-chat-v2`, low reasoning effort, temperature 0.2; identical across conditions.
- Frozen candidate event: 2026-11-07 22:26:04 UTC; block A consumed at 22:26:05 UTC.
- Promotion: 22:29:29 UTC; application canary passed at 22:29:35 UTC.

The read-only verifier checks the evaluation record hash, journal hash chain, policy package hashes/parent, candidate freeze before protected consultation, pairing, equal starters/budgets/environment, active-pointer identity, original controller archive, unchanged gate source, application canary and development-trace provenance. It recomputes the original gate from saved rows. It executes no model, tool action, hidden task or grader:

```sh
.venv/bin/python scripts/verify_policy_upgrade.py
```

The machine-readable result is `research_runs/policy_upgrade_verified/summary.json`. All evidence checks currently pass. Artifacts retain per-attempt trace hashes, raw measurements and the original evaluation record. The accepted pointer is in `.neural-pr-wonder-policy-v2/active.json`; it is scoped to that experiment.

## Boundaries

The main application was completed before this follow-up. Its source commit, `3117f57017203d2afb47538ecf7d768cece993b7`, was preserved and verified. The follow-up demonstrates transfer of an agent-authored procedural change to independent coding work after that task, not retroactive improvement of its first episode or continued main-task progress after promotion.

The original final audit was already exposed and was correctly excluded. A fresh independent final audit remains unavailable. Block A is now consumed; it must not be rerun as fresh evidence. Block B remains unused and is not opened by this evidence verification.

The later [original-worker implementation repair](ORIGINAL_WORKER_FIX.md) is a separate human-authored engineering change. It tolerates one validated action after a short preamble. The policy result above was recorded under the earlier strict parser; it does not establish the added skill's benefit under the repaired parser. No policy has been silently promoted into that new harness based on this earlier evaluation.

Whisper weight-edit outcomes remain separate: this coding-policy result is not evidence of an improved audio checkpoint.
