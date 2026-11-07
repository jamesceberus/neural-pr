# Original worker repaired

The original `neural_pr` coding worker and proposer have been repaired directly. This is a human-authored implementation fix, not an agent-policy improvement. The original completed Wonder run and failed audit remain unchanged.

## Behavior

The worker accepts one complete JSON action with a short leading progress preamble, or one JSON-fenced action. It validates the action/tool/argument schema before dispatch. It does not scan through earlier JSON objects or arrays, choose among multiple actions, guess missing syntax, accept duplicate keys, or execute unknown tools. Existing path confinement, immutable task contracts, resource budgets, independent scoring and promotion rules remain in force.

Accepted actions are executed in the same model call. The next turn receives the canonical action instead of repeating an unnecessary progress preamble in its conversation history. Raw provider responses remain in `traces/<id>.json` under `model_responses`; normalizations are journaled with a response hash. `action_recoveries` and `protocol_errors` are separately counted.

The original proposer uses the same complete-object decoder and retains its raw proposal response. It still only proposes bounded skills/context changes; it cannot award itself acceptance or promotion. The original readiness probe now has a 1,024-token budget and validates the exact readiness object.

If a genuine protocol error remains while software verification passes, the controller records a process incident without discarding the verified code. The existing proposer and independent coding-task gate decide whether a policy change is justified. Successfully recovered preambles do not manufacture a failure incident.

## Verification

Parsing the original main development trace accepts **18/18 responses**, recovering **15** that the old strict whole-string JSON decoder rejected. This replay executed no file tools and made no model calls; it is not a new coding-performance or held-out result. Per-response hashes and counts are saved in `research_runs/original_worker_fix/recorded_development_parser_replay.json`.

The full suite ran **104 tests: 99 passed, 5 skipped** because Docker access or audio-only dependencies are unavailable in that test interpreter. The live UI diagnostic/full-development checks also passed as part of this suite.

Focused tests cover preambles, code fences, quoted braces in file contents, ambiguous or truncated output, duplicate keys, unknown actions, argument schema violations, same-call execution, raw trace retention, canonical history, unchanged path confinement, readiness validation, and proposal scope. Controller tests verify that verified source progress survives a protocol incident.

```sh
.venv/bin/python -m unittest tests.test_action_protocol tests.test_controller \
  tests.test_sandbox_worker tests.test_transport tests.test_evaluator_improver \
  tests.test_wonder_learning -v
```

## Run the original launcher

From the ordinary Terminal with Docker running:

```sh
cd /Users/jameshennessy/src/cv_whsipr_hack
.venv/bin/python scripts/run_wonder_learning.py
```

The default state is now `.neural-pr-wonder-v2`. The original source was archived at `.neural-pr-wonder-v1/frozen_source_before_worker_fix`; its manifest matches the controller digest recorded by that completed run. Current controller identity guards intentionally refuse to resume the old experiment using changed worker code.

The launcher imports consumed-block metadata from earlier experiments using the same task bank, including the old audit. It preserves the earliest matching experiment deadline rather than resetting the budget. An exposed audit is skipped and reported as requiring new independent material; a new state directory does not restore freshness. The policy-only follow-up completed under the old controller and passed its pilot gate, as documented in [Verified policy upgrade](VERIFIED_POLICY_UPGRADE.md). Re-executing that historical protocol against the repaired implementation is blocked because the source controller differs.

The research UI also uses a new source-bound registry at `research_runs/wonder-v2`. Restart an existing UI server to load the repaired code. Historical reports and results remain available in their original state directories.

A live run of the repaired worker remains unverified from this restricted tool environment. The measured repair here is response handling; new software outcomes or policy improvements must come from actual executions. No consumed audit will be rerun as fresh evidence.
