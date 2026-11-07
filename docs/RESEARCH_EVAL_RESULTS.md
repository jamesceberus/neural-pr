# Research-agent evaluation

The new [top-level brief](research_agent_evaluation.md) is saved verbatim. The existing Whisper loader, aligned probes, edit primitives, scorer, checkpoint verification, journal, model API adapter, file tools, policy store, and UI job manager are reused. The original coding-task promotion gate is unchanged.

The core deliverable is a task → episode → executable submission → independent verdict → procedure comparison workflow. A historical engineering sweep is not a model-agent comparison. Repair, prediction, reproducibility, validity, efficiency, and reporting accuracy remain separate fields; there is no overall intelligence score.

## Actual evidence

The historical self-attention L4/H4 scale-0 submission is bound to its real parent, original exported checkpoint, source snapshot, hypothesis, event log, and per-recording outputs. The original checkpoint hash is `20ab6db230916b67e777d5330c6378f1ce9e27fe2a238832e7980b2e9376ccdd`. The importer derives a safe NPZ tensor from the trusted parent and matches the original attested projection hash. It does not trust or deserialize an arbitrary agent-authored pickle.

The independent verifier executes the submitted replay in a new public-artifact directory, validates both submitted and regenerated NPZ tensors against the pristine-based allowed edit, reconstructs full checkpoints, and loads them in fresh processes without intervention hooks. Full application regression is rerun on all 29 **exposed development** recordings with the pristine and reconstructed candidate. This is reproducibility evidence, not new held-out evidence.

| Historical measurement | Pristine | Rejected attenuation |
| --- | --- | --- |
| Non-speech lexical outputs | 9/17 | 10/17 |
| Speech edits / reference words | 13/264 | 10/264 |
| Speech corpus WER | 4.924242% | 3.787879% |
| Newly empty genuine speech | — | 0/12 |
| Inference errors | 0/29 | 0/29 |

The registered direction was a decrease in unsupported-token log probability. On the three former confirmation failures, the mean change was **+0.0283543269 nats**, contradicting that direction. Five matched controls remained at 9/17 in aggregate. The selected edit added lexical output on `whisper_synthetic_5_2` and removed none. Those 17 non-speech cases are distinct from the earlier 20-case non-speech final set. Neither set is fresh now.

The artifact passes reproducibility; the repair is rejected. A fresh PyTorch serialization can have a different file hash while containing the same edited tensor. The verifier records each actual file hash and checks the evaluated projection hash, `171d4707cce77207cc4efac836bc339f7e22a45ae27a2424edb849b7fa5976ba`, rather than claiming byte-identical serialization.

Two competent procedures are frozen using the same configured API model (`muse-spark-1.3` via the existing JSON chat adapter). The candidate adds explicit competing explanations, falsification criteria, matched controls, and source-group replication. This is a human-written procedure difference, not an autonomously learned skill. Both receive identical tools, decoding and budgets: 600 seconds, 16 API calls, 32 tool calls, 120,000 accounted tokens, and 160 trusted-tool experimental units per episode. One full recording or one diagnostic forward is one experimental unit; decoder steps vary. Arbitrary local Python compute cannot be enforceably metered on this host.

Both scheduled attempts per procedure are recorded. Model transport is blocked by DNS before a response; these are **infrastructure failures**, not deliberate abstentions, invalid scientific conclusions, or completed investigations. No frozen live submission or qualifying repair was produced. Four attempt outcomes were sealed before any protected evaluation. No procedure advantage is established.

Synthetic verifier controls exercise identity/no credit, correct tensor validation, accumulated edits, stale tensors, blanket-empty transcription, and inference-error handling. They calibrate trusted checks; they are not agent discoveries. The focused tests also execute an explicit abstention replay and confirm candidate loading is skipped.

## UI and commands

Run in an ordinary terminal; this restricted tool shell cannot bind localhost:

```sh
cd /Users/jameshennessy/src/cv_whsipr_hack
.venv/bin/python scripts/whisper_ui.py
```

Open **http://127.0.0.1:8787/research**. Restart an already running server to load the new backend. The comparison page displays the task, procedure diff, all attempts, costs, historical submission, calibration controls, and separate verdict fields. Inspect a row for complete raw measurements and artifact provenance. Model setup, playable audio, fixed-prefix probes, and full-development evaluation remain at `/`.

**Test agent API** runs a separate DNS/adapter preflight without consuming an episode. An OpenAI key is optional; use the [connection guide](API_CONNECTION.md) to distinguish networking, authentication, endpoint compatibility and quota failures.

The following commands were exercised locally. Task/comparison/submission freezes and verdicts are intentionally single-use; rerunning a consumed operation fails rather than inventing a new holdout.

```sh
.venv/bin/python -m research_eval init
.venv/bin/python -m research_eval import-historical
.audio-venv/bin/python -m research_eval controls
.venv/bin/python -m research_eval freeze-comparison
.venv/bin/python -m research_eval run-episode baseline --attempt 1
.venv/bin/python -m research_eval run-episode candidate --attempt 1
.venv/bin/python -m research_eval run-episode baseline --attempt 2
.venv/bin/python -m research_eval run-episode candidate --attempt 2
.venv/bin/python -m research_eval seal
.venv/bin/python -m research_eval verify historical-attenuation-L4H4-S0
.venv/bin/python -m research_eval compare
.venv/bin/python -m research_eval report
.venv/bin/python scripts/export_research_ui.py
```

Use a new `--root` for another frozen comparison. Do not erase the existing evidence to retry an attempt. `run-episode` starts a new context/workspace; `verify EPISODE_ID --protected` requires all four outcomes sealed and a private manifest registered **before** comparison freeze. Runtime tools and UI requests cannot choose private inputs or alter gates.

The eight mandatory challenges specify L4/H4 scales 0, 0.5, 1, 1.25 and unsupported-output/speech cohorts. The fixed target recipe comes from the pristine production window or reference token, with exact prefix/position recorded; it never compares divergent free-running prefixes. Predictions use intervention-minus-pristine mean log probability and a frozen ±0.01-nat no-effect interval. All assigned challenges remain in the coverage denominator, and incomplete measurements cannot yield a complete accuracy score. No-effect and development-empirical predictors are frozen for comparison. Protected challenge execution remains **unrun** without fresh material; the historical directional claim is scored separately.

## Fresh material and remaining gaps

All 69 old recordings are recorded in the exposure ledger. A new source-independent private pack was not obtained: the dataset request failed with a DNS `URLError`, recorded in `research_runs/authoring/network_probe.json`. No exposed set was silently relabeled fresh.

An author-only downloader is provided for an unrestricted terminal:

```sh
.venv/bin/python scripts/author_research_audio.py
```

Its network download/conversion branch is **unverified here**. It freezes a source-selection plan before fetching, selects without consulting Whisper outcomes, excludes known source/content/speaker overlap, preserves source revisions/hashes/references, and writes outside the repository. Unexpected upstream schemas fail closed. Curated non-speech labels retain `review_required=true` without independent listening; authoring alone does not confirm them.

After authoring and reviewing fresh labels, a new task/comparison can be created (this recipe is implemented but not a completed networked experiment):

```sh
.venv/bin/python -m research_eval --root research_runs/networked-v1 init \
  --private-manifest /private/tmp/whisper-research-private-v1/manifest.jsonl
.venv/bin/python -m research_eval --root research_runs/networked-v1 freeze-comparison
WHISPER_RESEARCH_ROOT=research_runs/networked-v1 .venv/bin/python scripts/whisper_ui.py
```

Run the four scheduled episodes from that UI. Seal their outcomes using the CLI, then verify their frozen submissions with `--protected`. The controller marks the protected set consumed before inference and forbids a fresh replay under another seal. Freeze all submissions first; no adaptive tuning after results are exposed.

**Isolation is logical only.** Replays run with public artifacts, sanitized environment, timeouts and process cleanup, but local Python can access the host filesystem. Docker is unavailable. No grader secrets or private fixture paths are supplied to runtime tools, but this host does not enforce secrecy, integrity, or arbitrary-code compute accounting. A fresh-context claim is not a tamper-proof evaluation claim. Enforced mounts/compute limits on a suitable host remain a gap before an adversarial or promotion-grade comparison.

Protected audio/challenges, a successful API-backed agent investigation, four complete executable live submissions, and a fair measured procedure comparison remain unrun. Free-form reporting accuracy is not graded by model opinion; only structured predictions can be checked mechanically. No model or agent-policy activation occurs. An agent-policy improvement still requires the original independent paired coding-task gate.

## Verification and artifacts

```sh
.audio-venv/bin/python -m unittest tests.test_research_eval -v
.venv/bin/python -m unittest tests.test_research_ui -v
.venv/bin/python -m unittest discover -v
```

The focused contract suite covers allowlists, parent identity, frozen-file tampering, paths, complete common-grid scoring, non-finite tensors, accumulated edits, stale tensors, distinction between missing submission and infrastructure failure, explicit executable abstention, and complete comparison sealing. UI checks cover existing-server integration, task prerequisites, session authorization, and rejection of private-input/gate overrides.

Executed verification: the full suite ran **74 tests: 69 passed, 5 skipped** (unavailable Docker/Torch/NumPy in that interpreter). The audio-environment contract suite passed **8/8**, and the research UI suite passed **4/4** after adding connection preflight. The existing UI authorization boundaries still pass. Live and recorded JavaScript pass syntax checks. Final integrity checks confirm the supplied brief is verbatim, the pristine checkpoint is unchanged, original coding/controller and mechanistic source hashes match, and no credential value appears in the new source or evidence artifacts. See `research_runs/verification/final_integrity.json`.

Local artifacts are private and ignored by Git:

- `research_runs/task.json`, `exposure.json`, `comparison.json`, `comparison_seal.json`: frozen definitions and exposure.
- `research_runs/source/`: independent Git snapshot of application/tool source.
- `research_runs/episodes/<id>/`: original workspace, controller journal, trajectory, immutable hash-bound submission, replay processes, safe tensor reconstruction, loaded-artifact attestations and per-recording results.
- `research_runs/verdicts/`, `controls.json`, `report.json`, `REPORT.md`: separate scores, every attempt, controls and conclusions.
- `research_runs/research-recorded.html`: read-only recorded UI, no credentials or private audio.
- `research_runs/verification/`: executed checks and final integrity results.

The root source tree has no writable Git metadata in this tool sandbox. Application, Whisper checkpoint and coding-policy identities remain separate; the task records its own nested source-snapshot commit.
