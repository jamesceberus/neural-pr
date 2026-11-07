# Evaluating agents that investigate and improve models

## Product decision

Build an evaluation system for agents doing model research. Give each agent a checkpoint, a reproducible defect, experimental tools, and a fixed budget. Require executable work, testable predictions, and a final intervention or explicit abstention. An independent evaluator reproduces the artifact, measures the proposed repair, and tests the agent's predictions.

The unit of evaluation is one complete agent research episode. Whisper is the first task environment. The main product question is whether one agent procedure produces better verified research outcomes than another under comparable conditions.

This is the new top-level implementation brief and replaces the episode-independent project priorities in `CODEX_BUILD_BRIEF.txt`. Reuse the existing Whisper application, experiment records, intervention manager, evaluator, and export checks. Use `CODEX_MECH_INTERP_ADDENDUM.md` for the detailed Whisper instrumentation contract. Make the research-episode comparison the core deliverable; the original autonomous policy-upgrade loop is an extension. This brief does not relax existing acceptance gates, authorize reuse of exposed evaluation data as fresh evidence, or turn planned capabilities into completed work.

Save this brief in the repository as `docs/research_agent_evaluation.md`. Update the README to explain the product through a task, an agent submission, an independent verdict, and an agent comparison. Inspect the repository first and adapt names to its structure. Do not rebuild functioning components.

## One coherent workflow

1. The trusted controller freezes a task package, scoring rules, allowed interventions, and budgets.
2. The runner starts an agent in a fresh workspace with the development materials and experimental tools.
3. The agent writes and executes investigation code, records hypotheses before testing them, and chooses a final submission.
4. The controller freezes the submission's code, patch, predictions, configuration, and hashes.
5. The independent evaluator reproduces the submitted artifact, runs protected evaluation, and returns a structured verdict.
6. The comparison report presents complete episodes from different agent configurations under the same declared conditions.

Keep autonomous changes to the agent's own procedure as a separately evaluated extension. First make the episode and comparison workflow work end to end.

## Reuse the existing pieces

| Existing component | Role in the unified product |
| --- | --- |
| Audio manifests and failure records | Task development fixtures with provenance and exposure status |
| Whisper hooks and fixed-prefix probes | Experimental tools available to research agents |
| Reversible head edits | A bounded intervention space |
| Hypothesis records and raw experiment logs | Evidence supporting or contradicting the submitted claims |
| Matched controls and speech-retention checks | Independent evaluation protocol |
| Export and fresh-process reload checks | Artifact reproducibility checks |
| Accepted-checkpoint pointer | Model-artifact promotion control |
| Agent version manifests | Identity of the procedure that produced each submission |
| Existing dashboard | Task, trajectory, submission, and verdict viewer |

The evaluator is trusted software. An optional reviewer agent can suggest additional tests, but its opinion must not determine correctness or override a gate.

## Task package

A task package contains a public development specification and a private evaluation specification. Both are versioned and hash-bound before a comparison begins.

The public part includes:

- Target checkpoint identity, parent hash, source version, and required runtime.
- Defect description, development recordings, reference transcripts, label confidence, and source groups.
- Allowed intervention families and parameter ranges.
- Functional requirements for experiment code and exported artifacts.
- Fixed decoding, preprocessing, and metric definitions.
- Resource caps, submission schema, and acceptance thresholds.
- The permitted outcome of abstaining when no acceptable repair is found.

The private part includes fresh evaluation recordings, reference outputs, fixed challenge-generation rules and seeds, and trusted verifiers. A task author can construct this material, but it must be unavailable to runtime workers and proposers.

Use the current multilingual Whisper `small` target for the first task. The target is reduced unsupported lexical output on non-speech while preserving genuine-speech recognition. Speech controls belong to this task; they are not separate independent research tasks. Different clips or repeated attempts also do not become new task families merely by receiving new IDs.

## Research episode contract

Each episode starts from the same source and model snapshot, with a fresh agent context. Record the agent model, policy version, prompt hash, tool versions, tokenizer settings where applicable, seed, and all budgets.

Expose the existing capabilities through a thin adapter: inspect model structure, read development examples, run baseline transcription, run aligned probes, apply a declared intervention, evaluate development behavior, and export a candidate. The worker may write and execute experiment code inside its workspace. Reuse the current worker's tools and API adapter.

The agent must register a hypothesis and predicted measurement direction before an experiment it later cites as a prospective test. Observations obtained before registration can motivate a hypothesis but must be labeled exploratory. Store failed and abandoned experiments as well as successful ones.

Agents submit:

```json
{
  "episode_id": "controller_assigned",
  "task_version": "frozen_task_version",
  "agent_policy_version": "frozen_policy_hash",
  "parent_checkpoint_sha256": "actual_parent_hash",
  "code_artifact": "relative_path_to_executable_work",
  "patch_manifest": null,
  "checkpoint_artifact": null,
  "claims_artifact": "relative_path_to_structured_predictions",
  "experiment_log": "relative_path_to_complete_events",
  "decision": "abstain",
  "reported_limitations": []
}
```

The example illustrates an abstaining submission. The decision enum is `submit_patch` or `abstain`; a patch submission must identify real patch and checkpoint artifacts. Implementation must validate actual paths, hashes, and identifiers. Require a reproduction entry point and explicit dependencies. A no-change submission earns no repair-improvement credit. A missing submission, infrastructure failure, invalid artifact, and deliberate abstention are distinct outcomes.

## Independent verification

The trusted evaluator performs the following sequence on the frozen submission:

1. Validate provenance, budget compliance, allowed modifications, and parent identity.
2. Run submitted code in an isolated execution environment using public fixtures. Check that it reproduces the declared intervention and does not silently alter unrelated behavior or configuration.
3. Prefer reconstructing the candidate from validated declarative edits to the trusted parent. If accepting submitted tensor artifacts, use a non-executable loading path and validate changed tensors against the permitted edit space; do not deserialize arbitrary agent-authored objects in the trusted grader.
4. Load the candidate in a fresh process and confirm that the actual evaluated artifact contains the declared change.
5. Run the pristine checkpoint and candidate under identical frozen settings on protected audio and intervention challenges.
6. Generate the verdict from measurements and fixed rules, retaining every failure and uncertainty.

For an explicit abstention, validate the executable investigation and evidence, evaluate eligible frozen predictions, and assign no repair-improvement credit. Skip candidate loading and candidate-versus-baseline checks because no patch was submitted. This branch is distinct from an invalid or missing patch submission.

Do not run agent-written code with access to grader secrets, hidden reference files, or acceptance logic. A separate context alone is not enforced isolation. Reuse container/process restrictions if available; otherwise state exactly which boundaries are logical only. Do not claim tamper-proof evaluation in that mode.

Freeze the test families before submission. The evaluator can select additional instances or seeds afterward according to those rules. Agent-authored tests are supporting material; they cannot be the sole definition of correctness. An agent reviewer can propose falsifiers, while trusted code validates their eligibility, executes them, and computes outcomes.

Keep candidate evaluation separate from deployment. Rejection leaves the accepted checkpoint unchanged. A rollback claim requires demonstrating restoration after an accepted version has actually been activated.

## Score the outcomes separately

Use a vector of results. Do not combine polished explanations, cheap execution, and failed repairs into an arbitrary overall intelligence score.

| Dimension | Observable measurement |
| --- | --- |
| Repair outcome | Non-speech failure reduction subject to speech-retention and error gates |
| Intervention prediction | Accuracy and magnitude of frozen predictions on independently selected cases and interventions |
| Reproducibility | Whether source, patch, and fresh-process checkpoint reproduce the reported behavior |
| Experimental validity | Valid baselines, controlled comparisons, complete records, and disclosed evaluation exposure |
| Efficiency | Wall-clock time, agent tokens, tool calls, decoder/model evaluations, and available compute measurements |
| Reporting accuracy | Whether the agent's claims match the measurements and their limitations |

For the first repair task, preserve the existing gate: strictly fewer non-speech recordings with lexical output, no newly empty genuine-speech transcript, no more than 0.01 absolute corpus WER degradation on genuine speech, and no inference errors. Freeze this rule before evaluation. Report raw counts, denominators, per-recording transitions, and raw transcripts.

For intervention prediction, define a finite, public challenge format and scoring rule before the comparison. In the MVP, a challenge describes an intervention, a cohort, and a fixed probe template; the agent predicts the aggregate direction and optionally magnitude/confidence. The evaluator instantiates that template on independently selected protected recordings. The agent receives no protected recording IDs, audio, labels, or trial results. Freeze exact prefixes/targets or deterministic template rules before evaluation.

Use a mandatory common challenge grid for comparative prediction metrics. Require predictions for every assigned challenge and report missing predictions and coverage. Agent-selected repair claims can be tested additionally, but do not substitute for the common grid. Compare predictions against simple no-effect or empirical baseline predictors so a mostly inert intervention set cannot create a misleading score.

Let the trusted task specify the numerical tolerance and decision thresholds. An agent cannot choose a tiny threshold or a different metric after seeing results to make its claim pass. Keep diagnostic target-token effects separate from full transcription outcomes.

For natural Whisper hallucinations, the true full mechanism is unknown. These tests can establish reproducibility, behavioral improvement, and support for specific causal predictions. They do not automatically certify the semantic meaning of a head or a complete mechanistic explanation [2, 3].

Report correct rejection and honest abstention, but do not let an always-rejecting agent win the repair task. If no agent produces a qualifying repair, state that none demonstrated improvement. If one predicts interventions better, attribute the advantage to prediction performance rather than general research superiority.

## Smallest fair agent comparison

Freeze two configurations of the same available coding model:

- Baseline procedure: the current competent research workflow with the common task and submission requirements.
- Candidate procedure: a documented change to hypothesis registration, control selection, or replication behavior.

Keep task snapshots, model identity, tool access, decoding, resources, and evaluation protocol fixed. The procedure diff is the intended intervention. Do not cripple the baseline. Both configurations may use all permitted tools and can submit a valid repair or abstain.

Run two fresh attempts per configuration if the measured runtime permits, for four episodes total. Use explicit per-episode agent-token, experimental-compute, and wall-clock limits. Report every attempt. One task and a handful of runs provide pilot evidence, not a broad ranking of model-research ability.

If time permits, add a fixed or random head-search comparator with a comparable target-model evaluation budget. Report agent-token cost separately because a scripted search does not consume the same reasoning resources.

Freeze all comparison submissions before revealing protected evaluation outcomes. The same protected cases can then support a paired comparison of these precommitted submissions. Record the set as exposed afterward and do not adapt candidates against it while continuing to call it fresh.

Choose one comparison axis at a time. A later tool-access experiment can compare behavioral-only access against internal probes with otherwise matched procedures. Changing the model, tool access, procedure, and budget simultaneously prevents attribution of an observed advantage.

## Data exposure and existing results

Every recording must have a source group, a content hash, a label-provenance field, and an exposure ledger. Preserve uncertainty in weak non-speech labels. Select new evaluation material using source-independent rules before viewing agent performance; do not choose only recordings on which one submission looks good.

The earlier 29-recording development pack, any consumed confirmation cases, and the previously inspected 40-recording final set are exposed for future adaptive experiments. They remain useful development or regression data. A new final claim requires new confirmation material. Keep all past results as historical evidence.

Import the latest reported experiment as an existing submission only after matching it to its real files and hashes. Its reported facts are:

- Selected attenuation increased the fixed unsupported-token log probability by about 0.028 nats on average.
- Application non-speech lexical-output cases increased from 9/17 to 10/17.
- Five matched controls remained at 9/17 in aggregate.
- Speech WER improved and no speech transcript became empty; exact WER values must come from the actual report.
- Export/reload checks verified that the child process loaded the edited artifact.
- The candidate was rejected and the pristine checkpoint remained accepted.

Its verdict should separate passed artifact verification, evidence against the submitted directional prediction, and failed repair acceptance. Do not relabel this as a successful repair. Do not merge these 17-recording results with the earlier 20-recording non-speech holdout results. Do not retrospectively present unrelated historical runs as a controlled agent comparison.

## Calibrate the evaluator

Use clearly labeled fixtures to establish that the verifier can distinguish relevant outcomes:

- An identity submission reproduces baseline behavior and receives no improvement credit.
- A defective implementation, such as accumulated edits or stale checkpoint loading, is detected by the corresponding independent check.
- A known-correct implementation of that fixture passes the same check.
- A submission that suppresses all output fails genuine-speech retention.

These are verifier controls, not discoveries made by a research agent. They test the grading machinery without requiring a successful natural-model repair.

If more time becomes available, add a controlled localization task with a deliberately introduced model perturbation and a known causal origin. Label it synthetic and keep it separate from native Whisper hallucinations. It can test localization and restoration, but does not establish understanding of the unmodified model's natural defect.

## Optional agent improvement loop

After the episode workflow and comparison are running, allow a proposer to turn a demonstrated process failure into a versioned procedure change. A negative scientific result does not automatically constitute a process failure.

The proposer reads development episodes and submits an exact policy diff, rationale, scope, and predicted benefit. Freeze that policy. Run both incumbent and candidate agents from identical starting snapshots on fresh investigation work. Changing only the evaluation audio for an already completed patch tests patch generalization, not whether the agent can conduct a better investigation.

For the coding-system track, include independent coding tasks that require the agent to implement or fix investigation software. Reuse the existing protected task bank if it is valid and unconsumed. Define the primary promotion metric before testing; improvements in explanation style or log completeness cannot compensate for failing required software or repair outcomes.

Only the controller may activate a policy after the paired gate passes. Preserve source progress independently of policy rollback. Human-written improvements to the procedure are legitimate comparison conditions, but must not be presented as autonomously learned agent upgrades.

This extension supports The System That Gets Better when actually demonstrated. The core independent-verification workflow is the direct fit for Trust but Verify. Software Archaeology is outside the current scope.

## Thin implementation and demonstration

Add only missing responsibilities around the current code:

- Task registry: public/private task specification and exposure ledger.
- Episode runner: pinned policy, fresh workspace, budgets, durable events, and submission freeze.
- Submission validator: schema, source, patch, provenance, and replay entry point.
- Independent verifier: existing checks plus protected evaluation and structured verdicts.
- Comparison view: all episodes, paired outcomes, resource costs, and supported conclusions.

Prefer one small coordinator and existing modules over creating a separate service for each responsibility. Support equivalent commands to run an episode, verify a frozen submission, compare episodes, and render a report. Document the actual implemented commands after running them.

The demonstration should show one task, an agent's recorded investigation, its executable submission and precommitted prediction, the independent verdict, and the comparison with another frozen configuration. Show actual failed and accepted checks. Display which claims remain unsupported. Use the existing negative result as a historical replay if live runs are not finished; label it recorded.

Prioritize the work in this order:

1. Inventory and wrap the functioning Whisper components.
2. Implement the episode/submission/verdict contract and import one verified existing run.
3. Run the independent verifier controls.
4. Obtain and protect fresh evaluation material; freeze two procedures and their comparison protocol; start bounded episodes.
5. Freeze all submissions, run protected evaluation, and report.
6. Add agent-policy self-improvement only if the core demonstration is complete.

Set the wall-clock schedule from remaining time and measured throughput. Reserve time for verification and presentation. Reduce the number of episodes before weakening boundaries or inventing completed results. Avoid an older-checkpoint sweep, broad circuit discovery, SAE training, or extensive dashboard work in this pivot.

## Completion criteria

- A research agent can complete an episode through the common interface.
- A submission contains executable work, a patch or abstention, predictions, and complete evidence references.
- The evaluator independently reproduces artifacts and applies fixed gates.
- Known-correct and deliberately defective verifier fixtures receive the expected outcomes.
- At least two frozen agent configurations can be compared without changing other experimental conditions.
- Reports separate repair, prediction, reproducibility, validity, and cost.
- Previously exposed data and incomplete evaluations are labeled accurately.
- No self-improvement or broad mechanistic-understanding claim is made without the corresponding evidence.

## Related work and positioning

ML research-agent evaluation already exists. Position this project as a focused, reproducible pilot for executable model-repair submissions and their causal predictions.

1. MLE-bench evaluates agents on machine-learning engineering tasks. https://arxiv.org/abs/2410.07095
2. SAEScientist-Bench evaluates agents using SAE tools to discover features, with separate activation and steering measurements. https://github.com/Trae1ounG/SAEScientist
3. CHIVE evaluates explanations through predictions of counterfactual outcomes and does not treat its generated explanations as ground truth. Its interventions are prompt edits; this project proposes a similar predictive discipline for internal interventions. https://alignment.anthropic.com/2026/chive/
