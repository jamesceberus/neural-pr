# Actual build and execution results

Recorded 2026-11-07T19:21:59.354472+00:00. Build start 2026-11-07T18:53:41.508455+00:00; elapsed **28.3 minutes**, within the seven-hour maximum. Finished engineering checks early; external execution limitations remain.

| Outcome | Evidence |
| --- | --- |
| Main software task | **Incomplete**: smoke verified; idempotency, execution, recovery and cancellation unfinished in the controlled starter |
| Agent improvement | **no_validated_improvement**; incumbent retained |
| Real main episode attempts | 2; both model transports failed before authentication |
| Completed live coding/evaluation rollouts | 0 / 0 |
| Runtime incident | 1 deduplicated infrastructure incident, 2 occurrences |
| Real model-generated proposals | 0; infrastructure failure has an explicit unsupported disposition |
| Real promotion / rejection / policy rollback | 0 / 0 / 0 |
| Actual application rollback | 1; source checkpoint restored, diagnostic branch preserved, disposable fixture removed |
| Synthetic controls | Tied-score gate rejected; unevaluated activation denied; active policy unchanged. Human-authored and explicitly labeled |
| Final audit | **inconclusive**, model_api_unavailable; no task consulted |
| Consumed blocks | None; A, B and audit remain fresh to runtime agents |
| Evaluation setup | All eight starters fail, all eight references pass, all eight relevant wrong mutations fail |
| Final automated tests | **40 passed, 1 skipped** (41 total); Docker isolation test skipped |
| Dependency / JavaScript checks | pip check passes; live and recorded dashboard scripts pass node --check |
| Credential scan | No supplied credential occurs outside ignored, mode-0600 .env |

## Separate identities

- Current application commit: `0f82db8f811b6f49b39fea27eec4e05cd3625e66`.
- Last verified application checkpoint: `0f82db8f811b6f49b39fea27eec4e05cd3625e66`.
- Original and final active agent policy: `ff43076cfa966003e945611829139657056e1a65e5d4e1733bc9287db0808c22`.
- Verifier: `blackbox-v1`; full trusted code and environment hashes are frozen in private `experiment.json`.
- Model configured: Meta `muse-spark-1.3`, `https://api.meta.ai/v1`. Credentials for Meta and Gemini were supplied locally, but neither could be authenticated because DNS failed first.

The root workspace started empty. Unrelated Whisper audio files appeared during the build and were left untouched. Root `.git` creation was denied by host permissions; controlled application Git repositories and diagnostic branches work under the private state directory.

## Usage and overhead

Two main-episode model transport attempts, zero completed API responses, zero worker tool calls and zero proposer calls. **Provider token usage is unknown**, not a validated zero. The raw report's collected token sum is zero because no usage response arrived; `token_usage_status` explicitly marks it unavailable.

Recorded main worker transport time: 0.077s. Live evaluation rollout overhead: 0s (no rollout began). The separate final-audit connectivity probe took 0.039s. The report's evaluation-overhead field excludes preflight connectivity probes. Build wall time includes engineering, independent application checks, setup validation, test controls, documentation and execution rehearsal.

The final suite completed in 69.861 seconds. Twelve **scripted test-control** rollouts exercised paired recording, identical Git starting snapshots, equal budgets and one-use consumption in disposable unit-test state. They are not included in the live rollout counts and provide no evidence of agent improvement. A trusted, test-only job-service reference passes the full integrated verifier, including recovery across two separate OS processes; it was never transplanted into the actual runtime starter.

## Integrity and demonstration limits

Docker/Podman are absent. macOS sandbox-exec is installed but its sandbox_apply call is denied. Supported Docker enforcement is implemented but unverified here, and **local execution has no enforced filesystem/process secrecy**. The gate refuses to promote on this local evidence. Model subprocesses receive credentials over stdin; runtime task processes do not inherit them.

Outbound API DNS and local port binding are denied. FastAPI dashboard routes were tested through an in-process client; no live browser server or visual browser QA is claimed. Open the private, self-contained [recorded dashboard](../.neural-pr/dashboard-recorded.html) for an offline review. It visibly labels the snapshot time and synthetic controls.

An actual separate-process `resume`, application rollback, fixture cleanup and smoke verification were executed. No policy rollback is claimed because no candidate was accepted. Earlier implementation rehearsal states are preserved under `.neural-pr/archives/`; they also consulted no held-out tasks. Their controller hashes intentionally differ from the final frozen experiment.

## Reproduction and artifacts

See [setup and exact commands](../README.md) and [the three-minute script](DEMO_SCRIPT.md).

- `.neural-pr/report.json`: safe structured summary of real final state.
- `.neural-pr/dashboard-recorded.html`: private recorded evidence console.
- `.neural-pr/events.jsonl`: 19 hash-chained real execution events.
- `.neural-pr/attempts/`, `incidents/`: source/policy identities and actual failure evidence.
- `.neural-pr/controls/rejection.json`: exact **human-authored control** skill diff and negative-control decisions; actual application restore evidence.
- `.neural-pr/prevalidation.json`: eight-task known-wrong/known-correct calibration.
- `.neural-pr/final_acceptance.json`: actual integrated starter results, including unfinished requirements.
- `.neural-pr/evaluations/`: inconclusive audit request; no paired live scores.
- `.neural-pr/verification/unittest.txt`: full final test log.

**Single next experiment:** use a networked Docker host, keep Meta fixed, calibrate one actual baseline coding episode, propose one transferable change from a real development failure, compare on fresh block A, select once, and open the untouched audit. Retain the incumbent if the candidate ties or fails. Do not tune after audit consultation.
