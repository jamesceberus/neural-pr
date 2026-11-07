# Executing the Wonder self-improvement loop

**Current implementation:** [the original worker is now repaired](ORIGINAL_WORKER_FIX.md). The launcher defaults to `.neural-pr-wonder-v2` and preserves evaluation exposure from earlier runs. The infrastructure history below describes the earlier setup phase.

The approved execution was attempted in `.neural-pr-wonder-v1`. It is currently **blocked by infrastructure**, not a failed coding experiment or an agent upgrade.

**Latest ordinary-Terminal result:** the updated Wonder probe passed (`48` total tokens, `finish_reason=stop`) and Docker's daemon became reachable. The build then failed because `docker-credential-desktop` was missing from `PATH`. The launcher now locates that installed helper under Docker Desktop's `Contents/Resources/bin`, adds the directory to its process environment, and preserves the existing Docker CLI preference and credential configuration. A child-process test verifies helper discovery. Full image build after this correction remains unverified from the restricted tool shell.

Run `.venv/bin/python scripts/run_wonder_learning.py` again from the ordinary Terminal. No manual credential-store edits or repeated old `python -m neural_pr ...` commands are needed.

Actual results:

- The ordinary Terminal reached Meta but the original 32-token probe reported `Malformed model API response`. Its raw response was not captured, so token exhaustion is a hypothesis, not an established cause.
- Docker CLI is installed, but no daemon is listening at the configured endpoint. The image build therefore failed. The buildx deprecation warning is secondary.
- `init-demo --isolation docker` refused with `Build the Docker worker image first`; the subsequent `run` refused with `Run init-demo first`.
- The restricted tool shell still cannot reach the API. A subsequent request using the new adapter returns `Model API unavailable (URLError)`.
- Zero coding attempts, policy proposals, promotions or held-out blocks have been consumed. No completed hard coding task or self-improvement is claimed.

## Adapter correction

`ui/meta_model.py` provides a versioned `meta-wonder-json-chat-v2` adapter for new coding experiments. It reuses the existing supervised subprocess mechanism. Its identity includes its source hash, fixed temperature and reasoning effort. The original `neural_pr` controller, legacy adapter, historical source snapshots and acceptance gate are unchanged.

The new readiness check allows 1,024 completion tokens, requests minimal reasoning and requires the exact JSON readiness object. Agent calls use fixed low reasoning effort and the existing caller token budget, identically for incumbent and candidate. The adapter uses Meta's documented `max_completion_tokens` and `reasoning_effort` parameters. Final text, empty/reasoning-only responses and truncated completions are distinguished. Reasoning text and raw provider error bodies are not exposed by diagnostics. See [Meta's Chat Completions documentation](https://dev.meta.ai/docs/protocols/chat-completions).

This is an authored transport fix, **not a learned agent policy improvement**. A successful live Wonder response using it remains unverified here. The original direct `python -m neural_pr ... doctor` command still uses its frozen legacy adapter; use the launcher/preflight below for the updated Wonder adapter.

## Resume from an ordinary Terminal

Install and start a Docker engine. On this Mac, [Docker Desktop's official installation instructions](https://docs.docker.com/desktop/setup/install/mac-install/) describe installation and startup. A Homebrew Docker client alone does not supply the Linux daemon. Wait until the engine is running, then:

```sh
cd /Users/jameshennessy/src/cv_whsipr_hack
docker info
.venv/bin/python scripts/run_wonder_learning.py
```

The launcher automatically checks the API, builds `Dockerfile.worker` if a running engine needs the image, initializes a fresh isolated coding experiment, and delegates up to 30 episodes to the existing controller. The controller preserves source checkpoints, proposes only from eligible failures, evaluates fresh coding blocks, and promotes only a passing policy hash. The launcher runs the reserved final audit only after the main task completes. Ties, outages and unavailable isolation do not earn improvement credit. Existing experiment deadlines and repeated-failure limits remain enforced by the controller.

Rerunning the launcher resumes the existing frozen experiment. It does not reset its seven-hour clock or recycle consumed evaluation blocks. It preserves stopped/failed execution records. A completed run cannot be silently reopened with a changed model or launcher. No new framework or gate is introduced.

To diagnose the connection separately, without consuming a coding attempt:

```sh
.venv/bin/python scripts/whisper_ui.py --check-agent
```

The UI's **Test agent API** button uses the same updated readiness check. Its independent research-episode workflow remains distinct from this coding-policy promotion loop.

## Evidence and verification

`learning_execution.json` is the latest execution status; `executions/<id>.json` and the hash-chained journal preserve individual launcher runs. `execution-result.json` captures the latest CLI output. Once coding actually starts, the existing controller writes its attempts, incidents, policy diffs, paired evaluations and active pointer in the same state directory. `learning_report.json` records its report after the coding loop.

Nineteen focused tests pass across `tests.test_meta_model`, `tests.test_wonder_learning`, `tests.test_research_ui` and `tests.test_transport`. They use labeled synthetic provider envelopes and launcher fixtures to check token exhaustion, strict readiness validation, credential sanitization, no protected-data consumption on infrastructure failure, delegation to the unchanged controller, preservation of the final audit on unfinished work, and refusal to resume unenforced isolation as enforced. They do not count as live agent results.

Two additional Docker-helper checks pass: resolution in a child process while retaining the selected Docker executable, and preservation of an already configured helper while rejecting a non-executable candidate. The launcher suite now passes 6/6 checks.

At that setup stage the source identity still matched and live execution was unavailable. Later ordinary-Terminal runs completed the main coding task and a separate policy follow-up passed its pilot gate. See [the verified policy-upgrade result](VERIFIED_POLICY_UPGRADE.md) and [the subsequent source-versioned worker fix](ORIGINAL_WORKER_FIX.md) for current status.
