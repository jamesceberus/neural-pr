# Research-agent evaluation

[Private GitHub publishing and clean-checkout setup](docs/GITHUB_PUBLISH.md) · [Sanitized recorded pilot results](docs/evidence/policy_upgrade_pilot.json)

**Verified agent-policy pilot:** Wonder proposed one added skill, then the candidate completed **6/6** independent coding attempts versus **2/6** for the incumbent, with no task regression and a passing post-promotion canary. [Verified evidence and limitations](docs/VERIFIED_POLICY_UPGRADE.md). This result belongs to the original strict-parser harness; the later worker repair is separate.

**Original worker repaired:** progress-prefixed JSON actions now execute without wasting a model call; ambiguous actions still fail validation. [Fix, verification and run command](docs/ORIGINAL_WORKER_FIX.md). The same learning launcher now defaults to a fresh v2 state and retains prior evaluation exposure.

Give a coding agent Whisper-small, an observed defect, experimental tools, and a fixed budget. Require executable work and frozen predictions. A trusted evaluator reconstructs the artifact, checks the prediction, and evaluates the repair separately.

- **Task:** a hash-bound public development contract and private evaluation plan, with source groups and exposure history.
- **Submission:** a fresh episode's code, experiment log, common-grid predictions, and a parent-bound tensor edit or explicit abstention.
- **Independent verdict:** replay, validated checkpoint reconstruction, fresh-process inference, fixed audio gates, and separate outcome dimensions.
- **Comparison:** two procedures of the same configured model, identical tools and budgets, two scheduled attempts each, sealed before protected evaluation.

[Implementation brief](docs/research_agent_evaluation.md) · [Actual results, commands, and gaps](docs/RESEARCH_EVAL_RESULTS.md) · [API connection help](docs/API_CONNECTION.md)

**Open the UI:** run `.venv/bin/python scripts/whisper_ui.py`, then visit http://127.0.0.1:8787/research. The original [audio experiments and model setup UI](docs/WHISPER_UI.md) remains at `/`. A private read-only recording is saved at `research_runs/research-recorded.html`.

The historical L4/H4 attenuation submission passed artifact verification and failed its prediction and repair objective: non-speech lexical output increased from 9/17 to 10/17. It is recorded engineering evidence, excluded from the agent comparison. Both previous audio packs are exposed. A new held-out repair claim needs fresh recordings and enforced evaluation isolation. No agent-policy upgrade is claimed.

## Original coding-system extension

**First Wonder run:** the main application completed in one attempt (16/16 checks), then the final coding audit failed (5/8 runs passed). The later separate policy follow-up passed; see the verified result above. [Results and the bounded failure-driven follow-up](docs/WONDER_LEARNING_RESULTS.md).

**Execute the Wonder learning loop:** [launcher, actual execution results, and Docker/API setup](docs/WONDER_LEARNING_EXECUTION.md). Run `.venv/bin/python scripts/run_wonder_learning.py` from a networked Terminal with a running Docker engine. It preserves the original coding gate.

The original coding-task promotion gate remains operational and unchanged. Audio repair results cannot replace that independent evaluation. Earlier audio evidence remains in [audio artifact results](docs/AUDIO_RESULTS.md), [mechanistic results](docs/MECHANISTIC_RESULTS.md), and the [head-strength follow-up](docs/HEAD_STRENGTH_FOLLOWUP.md).

A local coding runner that proposes changes to its own operating procedures and delegates promotion to a separate trusted controller. The application, agent policy, and evaluation evidence have independent version histories.

This is an authored hackathon experiment using a **controlled starter repository** for a FastAPI/SQLite durable job service. It is not an independently discovered production defect. A completed software task and a validated agent improvement are separate outcomes.

**Initial Spark experiment:** controller and baseline ran, but model transport stopped at restricted DNS before authentication. That earlier starter remained unfinished with `no_validated_improvement`; see [its evidence report](docs/RESULTS.md). The newer Wonder run above is a separate experiment.

## Setup and launch

Python 3.9+ and Git are required. Python 3.12 is recommended. No frontend build is needed.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
cp .env.example .env
# Set MODEL_API_KEY in .env locally. Do not commit it.
.venv/bin/python -m neural_pr doctor --probe-api
.venv/bin/python -m neural_pr init-demo
.venv/bin/python -m neural_pr run --episodes 3
.venv/bin/python -m neural_pr resume --episodes 3
.venv/bin/python -m neural_pr report
.venv/bin/python -m neural_pr serve --port 8787
```

Open `http://127.0.0.1:8787`. The dashboard is read-only and reads real local records. It exposes no private task bank, expected answers, credentials, or mutation endpoints. It shows application commits and agent versions separately, distinguishes development/promotion/audit, and refreshes every ten seconds. This restricted build host cannot bind a localhost listener; the routes were verified through FastAPI's in-process client.

The existing `.venv` in this workspace was prepared offline from already-installed local packages because DNS prevented pip installation. `pip check` passes. Use the normal install command above in a networked environment. A reference dependency snapshot is in `requirements-tested.txt`.

## Model configuration

The research UI now uses **Meta Muse Wonder** (`muse-wonder-1.0`), configured in `ui/agent_profile.json`, with a separate comparison at `research_runs/wonder-v1`. See [Wonder setup and actual connection results](docs/MUSE_WONDER.md). Both research procedures use the same Wonder model. The connection is still blocked in this tool shell; no successful Wonder episode is claimed.

The original coding controller and historical runs retain the following frozen Meta Spark configuration:

```dotenv
NEURAL_PR_BASE_URL=https://api.meta.ai/v1
NEURAL_PR_MODEL=muse-spark-1.3
MODEL_API_KEY=your-local-key
```

The endpoint and model were checked against Meta's [official quickstart](https://dev.meta.ai/docs/quickstart) and [Chat Completions documentation](https://dev.meta.ai/docs/protocols/chat-completions). The adapter uses Chat Completions with a bounded JSON action protocol. This MVP resends public message history and does not use Responses API reasoning-state replay. It accepts the documented `max_tokens` compatibility alias.

A Gemini alternative uses Google's [OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai):

```dotenv
NEURAL_PR_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
NEURAL_PR_MODEL=gemini-3.8-flash
GEMINI_API_KEY=your-local-key
```

For another compatible provider, set `NEURAL_PR_API_KEY`. Priority is explicit override, Meta key for a Meta endpoint, or Gemini key for a Google endpoint. Do not place an override key for the wrong provider in `.env`.

The CLI loads only recognized model variables from `.env`; existing shell environment variables take precedence. Credentials travel to a killable trusted API subprocess through stdin, never process arguments. Worker code runs without credentials. Reports contain provider usage where available; transport failures have unknown token usage. Secrets supplied during this build remain only in ignored `.env` (mode 0600).

Model identity, temperature, evaluation budget, gate, bank hashes, controller code hash, and execution environment are frozen per experiment. A different model/configuration requires a new state directory:

```sh
.venv/bin/python -m neural_pr --state .neural-pr/new-experiment init-demo
```

## Isolation

`local-unenforced` is the default so that the workflow can be exercised without Docker. Path tools reject traversal, `.git` access, and symlink escapes, but **executed task code is not isolated from the host filesystem**. It can inspect or modify host files accessible to the host user. Never run adversarial code in this mode. Local comparisons cannot pass the promotion gate because integrity is unenforced. Hashes and read-only files are corruption checks, not protection against the host owner.

Docker is the supported enforcement mode. Build the public tool image and initialize a new experiment:

```sh
docker build -f Dockerfile.worker -t neural-pr-worker:0.1 .
.venv/bin/python -m neural_pr --state .neural-pr/isolated init-demo --isolation docker
.venv/bin/python -m neural_pr --state .neural-pr/isolated run --episodes 3
```

The Docker context excludes credentials and source. Each check/grading process gets only `/task`, a read-only image, temporary `/tmp`, no network, no extra capabilities, CPU/memory/process limits, and an unprivileged UID. The controller, bank, verifier, active policy pointer and expected outputs are never mounted. The API/model stays in the trusted controller; selected policy text is supplied in the prompt and cannot be edited in place. Only path-confined tools mutate the task checkout. Public RPC transport contains no expected answers; the trusted parent compares responses. Containers are removed even after timeout, and local process groups are cleaned after execution. The Docker integration test is skipped on this host because Docker is unavailable: enforcement is implemented but **not verified here**.

```sh
.venv/bin/python -m unittest tests.test_docker_isolation -v
```

## Runtime loop

1. Reconstruct frozen requirements, verified dependency-ordered milestones, current commit, relevant diffs, last independent test results, blockers and unsuccessful hypotheses. Policy context rules select additional files from the task checkout only.
2. Pin one immutable agent version for the entire attempt. Give the model bounded file listing, reads, whole-file writes and Python development checks. No shell command tool is exposed.
3. Preserve source with a Git commit even after failure. Independently verify application behavior through a black-box child process. Agent statements never determine acceptance.
4. Advance a checkpoint only when the next milestone and previously verified milestones pass. Future unfinished requirements do not block incremental progress. Preserve regressions on diagnostic branches, then restore the last verified application checkpoint and disposable fixtures.
5. Deduplicate failure incidents by objective/policy/class/check fingerprint. The live proposer sees development evidence and the incumbent policy, never held-out fixtures. It proposes transferable skill/context changes, or records a disposition. Network failure receives `unsupported_infrastructure_failure`; there is no invented skill proposal.
6. Preflight limits proposals to skills/context rules, records an exact diff, hypothesis, scope and immutable parent. Tool/routing identities are tracked but cannot change in this MVP. Solution-code filtering is a heuristic, not a proof of transferability.
7. Compare incumbent and candidate on new coding tasks in fresh contexts, from identical Git snapshots, under the same model, tools, environment and budgets. Only skills/context rules differ. The controller alone promotes a passing hash, checks that the parent is still active, and performs an application regression canary.
8. Continue the main task under the recorded active version. Run at most three consecutive coding failures on the same objective, persisted across resumes. Three failures require an explicitly recorded new approach; the runner stops instead of endlessly repeating.

The first successful API-backed development episode records calibration; the MVP retains the predeclared evaluation limits. Unavailable infrastructure does not calibrate the agent. Candidate evaluation is sequential with main episodes, with at most two proposals and one evaluation in flight. The experiment has a seven-hour wall-clock stop. Controller restarts are validated against repository, environment and code identity.

## Frozen evaluation design

Before any proposal, setup creates eight distinct tasks: three in promotion block A, three in B, and two in a reserved final audit. The private setup bank contains public contracts, starting defects, reference solutions, relevant wrong mutations and deterministic expected behavior. Setup prevalidation requires each starter and mutant to fail and each correct reference to pass. None of that private setup source is copied to runtime task checkouts. The worker sees only its assigned public contract and starter; the proposer sees development evidence. The controller implementation and tests must not be mounted into a Docker worker.

Each block runs two independent attempts per policy per task: 12 rollouts per promotion block, eight audit rollouts, at most 32 scheduled comparisons. An infrastructure failure permits one bounded retry per rollout, under the same rule for both policies; retry attempts remain recorded and can increase the number of transport attempts beyond 32. A persistent failure makes the comparison inconclusive. A failed initial API probe consults no task and does not consume the block. Once a block is consulted it is durably consumed, even if interrupted; it cannot be presented as fresh again.

Promotion requires all of:

- Strictly more completed attempts for the candidate.
- No drop on any task, required integrity and regression checks preserved.
- Balanced complete pairs, equal budgets, and budget compliance.
- Only permitted policy surfaces changed; exact evaluated hash and current parent match.
- Enforced execution isolation. Ties are rejected.

Partial checks and every paired outcome remain recorded. Two attempts across three tasks are pilot evidence, not strong statistical proof. There are no guaranteed promotions and no weakened baseline. The final audit freezes policy selection only once its API probe succeeds; no further proposals or promotions are allowed after audit consultation. All final selected audit attempts must pass; regression/failure is reported and a promoted policy is conservatively rolled back. An API-unavailable audit remains inconclusive and leaves audit tasks untouched.

## Commands and artifacts

```sh
.venv/bin/python -m neural_pr evaluate-candidate CANDIDATE_ID --block A
.venv/bin/python -m neural_pr rollback-agent
.venv/bin/python -m neural_pr rollback-application
.venv/bin/python -m neural_pr audit
.venv/bin/python -m neural_pr demo
.venv/bin/python -m neural_pr demo --exercise-controls
.venv/bin/python -m unittest discover -v
```

`demo --exercise-controls` performs an actual application rollback and restart check. It preserves existing work on a diagnostic branch, resets to the verified checkpoint, removes disposable databases, and checks the rebuilt fixture. Its unevaluated-candidate and tied-score rejection demonstrations are explicitly labeled **synthetic negative controls**. They do not count as live candidates, autonomous discoveries or model evaluation results. `rollback-agent` refuses when no accepted previous policy exists and leaves application source untouched.

All private artifacts live under `.neural-pr/`, which is ignored by Git:

| Path | Contents |
| --- | --- |
| `application/` | Controlled application's independent Git repository |
| `application.json` | Source head, verified checkpoint, milestones, fixture strategy, unfinished work |
| `policies/<hash>.json`, `active.json` | Immutable policy packages and controller-owned active pointer |
| `events.jsonl` | Fsynced hash-chained journal; malformed/tampered records fail closed |
| `attempts/<id>.json`, `traces/<id>.json` | Attempt identity, budgets, model/tool usage, timestamps, verification, private transcripts |
| `incidents/`, `candidates/` | Versioned incidents and candidate lifecycle/dispositions |
| `private/bank/`, `bank.json` | Private evaluation fixtures and frozen hashes |
| `evaluations/`, `consumed.json` | Paired results and one-use block ledger |
| `prevalidation.json` | Known-wrong/correct verifier validation |
| `final_acceptance.json`, `final_selection.json` | Integrated acceptance and consulted-audit selection |
| `controls/rejection.json` | Clearly labeled demo controls and actual recovery evidence |

Do not publish the state directory, keys, private bank, model transcripts or checkpoints. The read-only report removes raw source diffs/transcripts and does not include hidden task definitions. The dashboard is local, unauthenticated, and should remain bound to loopback. Standard Git does not restore external effects: this experiment uses fresh temporary databases per verifier process and no external job side effects.

## Design references

The episodic context/checkpoint design follows [Anthropic's long-running harness discussion](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents). Agent validation scores resulting software behavior rather than explanations, following [agent evaluation concepts](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents). One-use held-out blocks address [adaptive holdout leakage](https://research.google/blog/the-reusable-holdout-preserving-validity-in-adaptive-data-analysis/); no claim of a reusable-holdout privacy mechanism is made.

The single next experiment is to run the frozen Meta baseline, one real failure-triggered candidate and fresh block A on a networked Docker host, then select once and open the untouched audit. Do not tune against the audit.

For an offline review when a local port cannot be opened, export a private, self-contained **recorded** dashboard:

```sh
.venv/bin/python scripts/export_recorded.py
open .neural-pr/dashboard-recorded.html
```

The file is labeled with its recording time and contains the same safe report and filtered journal as the dashboard. Refresh reloads the recording; it does not imply live model activity. The restricted host also denied initialization of Git metadata at the workspace root; source files are present with `.gitignore` configured, while controlled application Git history lives in the private state directory.

## Mechanistic investigation

The [implementation specification](docs/mechanistic_interpretability.md), [measured investigation results](docs/MECHANISTIC_RESULTS.md), [versioned head-strength follow-up](docs/mechanistic_protocol_v2.md), and [follow-up results](docs/HEAD_STRENGTH_FOLLOWUP.md) preserve separate implementation, mechanism, repair and agent-policy outcomes.

```sh
.audio-venv/bin/python -m whisper_repair.mechanistic prepare
.audio-venv/bin/python -m whisper_repair.mechanistic investigate
.audio-venv/bin/python -m whisper_repair.mechanistic verify-export
.venv/bin/python scripts/audit_mechanistic.py
.venv/bin/python -m whisper_repair.mechanistic serve --port 8787
.venv/bin/python -m whisper_repair.mechanistic snapshot
```

The dashboard extends the existing Neural PR console. Its recorded offline view is `audio_runs/mechanistic_v1/dashboard-recorded.html`. The original final audio holdout is consumed; this module refuses to treat it as fresh. The original coding-policy promotion gate remains unchanged.
