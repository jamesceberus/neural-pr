# Whisper mechanistic investigation implementation addendum

## Task for Codex

Add a bounded mechanistic investigation module to the existing Whisper repair project. Integrate it into the current application and autonomous coding runner. Read the repository instructions and CODEX_BUILD_BRIEF.txt, inspect what already works, and extend those components rather than building another framework. Save this specification in the repository as docs/mechanistic_interpretability.md and link it from the README.

The module should investigate a specific question: which internal components contribute to unsupported word generation on non-speech, and what causal evidence supports that attribution? It should produce reproducible experiments, a qualified explanation, and an optional permanent checkpoint edit. A successful implementation may conclude that no useful edit or convincing mechanism was found.

Keep the existing agent improvement system operational. Audio experiments evaluate Whisper interventions; independent coding tasks evaluate changes to the coding agent's skills and context. An improvement on audio never substitutes for the coding-task promotion gate.

This addendum strengthens the Whisper milestone inside the existing seven-hour deadline. It does not create a second seven-hour project. Prioritize a working baseline, one controlled investigation, export verification, and an honest report. Activation interchange is a stretch experiment. Exhaustive circuit discovery, sparse autoencoder training, new model training, and a new orchestration framework are outside this MVP.

## What the project must distinguish

Mechanistic interpretability investigates internal computations. Identifying a component affected by an intervention is a useful localization result, but does not automatically explain its computational role. Held-out improvement tests generalization of a repair. Keep these evidence categories separate [1, 2].

| Evidence | Question answered | Appropriate claim |
| --- | --- | --- |
| Reproducible failure | Does this checkpoint fail under the frozen configuration? | Behavioral defect observed |
| Activation measurements | Which internal states differ across cases? | Descriptive association |
| Controlled head intervention | Does changing a component alter a specified outcome? | Causal effect under the tested intervention |
| Hypothesis tests with matched controls | Does the effect fit a specific role better than competing explanations? | Evidence for a narrow causal hypothesis |
| Frozen checkpoint on held-out audio | Does the repair retain its benefit on unseen recordings? | Pilot evidence of a generalizing repair |
| Independent coding-task comparison | Does a new agent policy perform better? | Pilot evidence of an agent upgrade |

Do not label a head a dedicated hallucination detector or hallucination neuron. Do not infer understanding from the fraction of weights changed, an attention heatmap, or the agent's narrative. The system must be able to report a useful repair with inconclusive mechanism evidence, or a causal finding with no acceptable repair.

## Working hypothesis and alternatives

Start with this explicit, revisable hypothesis:

> A decoder component contributes to unsupported continuation when acoustic evidence is weak. Attenuating its output reduces the model's preference for that continuation, with a smaller effect on genuine speech.

This is a starting hypothesis, not a finding. Record its predicted effect, measurement, scope, and a result that would weaken it before running the corresponding experiment.

Test these alternatives where the available evidence permits:

- The intervention suppresses transcription generally.
- The selected component is no more relevant than comparable control heads.
- The final transcript improves because the existing no-speech filter skips the segment, while raw continuation preference barely changes.
- The apparent signal reflects a different decoder prefix, audio window, or token position.
- The effect was selected by searching a small development set and does not repeat on reserved cases.

A decoder-only study cannot establish that the encoder and cross-attention are uninvolved. Narrow the explanation to the components and conditions actually tested.

## Model and data contract

Use the original openai-whisper PyTorch implementation and the already selected checkpoint. The default is multilingual small. If the project previously selected base or tiny because of hardware constraints, retain it and report that identity. Changing checkpoints requires a new baseline and experiment record. Inspect the installed code rather than assuming a different implementation has the same module layout [3].

Record the checkpoint identifier and file hash, package version or source commit, model dimensions, device, dtype, preprocessing, language, task, timestamp settings, prompt history, decoding options, and filter thresholds. Use inference mode, a frozen configuration, and a recorded seed where randomness is involved. Never switch decoding settings after seeing results to manufacture an improvement.

Reuse whisper_audio_dev.zip and whisper_audio_holdout.zip from the existing project. The development pack has 29 recordings; the held-out pack has 40. They include non-speech candidates and genuine speech controls. Resolve each audio_path relative to its manifest and map its partition field. Preserve provenance, hashes, and the review_required flag. The packs' local_whisper_status=not_run is not evidence that any selected checkpoint fails.

Establish baseline behavior before selecting components. Distinguish three development cohorts:

1. Non-speech with unsupported lexical output.
2. Non-speech with a correctly empty transcript.
3. Genuine speech, including short or quiet examples when available.

Keep uncertain non-speech labels exploratory until checked; a VAD label alone is insufficient. If short or quiet speech controls exist only in the held-out pack, keep them there. Additional development recordings must have their own references and provenance. Record missing control coverage instead of inventing it.

Before component selection, reserve a source-grouped development confirmation subset when enough independent examples exist. Keep derivatives of one recording in the same partition. Use discovery cases to select heads, scales, target tokens, and donor pairs; use confirmation once on a frozen hypothesis. If there are too few eligible cases, report the mechanistic finding as exploratory. The final audio holdout remains separate and inaccessible to the runtime proposer.

## Two execution paths

### Application transcription

Reuse the application's frozen model.transcribe path. Keep normal preprocessing, segmentation, decoder filters, and no-speech filtering. Evaluate complete recordings and preserve raw output. Record inference failures separately from empty transcripts.

Capture each window's decoder result and final skip decision when practical, including no_speech_prob, avg_logprob, relevant thresholds, seek offset, and token IDs. Instrument without changing behavior. Whisper's skip decision depends on both no-speech probability and average log probability [5].

### Diagnostic forward pass

Add a separate uncached, teacher-forced decoder path for internal experiments. Use it to measure comparable internal states and intervention effects. These diagnostic scores are not application transcription metrics.

For each probe, freeze the exact audio window, feature-extraction settings, prefix token IDs, target position, target token, and optional comparator token. Derive the prefix and indices from the installed tokenizer and actual decoding configuration. The token at position j in the input produces logits predicting the next token; avoid an off-by-one target.

Prefer single-window cases and an initial task prefix without historical transcript text. If a failure requires a later continuation, use the same recorded prefix for every condition and label the result conditional on that prefix. Include the same language, task, timestamp, and prompt tokens. Do not compare freely generated transcripts after their prefixes diverge.

Use one example per probe or batch equal-length prefixes. Do not pad arbitrary token sequences and assume the original decoder supplies a suitable text padding mask. Clear inference caches between independent runs; the diagnostic path should pass no KV cache.

For recordings longer than a model window, identify the actual window and seek offset where the failure occurs. A diagnostic excerpt is a derived example with a parent recording and bounds. Do not silently truncate the audio and claim it reproduces the original failure.

## Measurements and hook implementation

Begin with decoder self-attention. Use a temporary forward pre-hook on model.decoder.blocks[layer].attn.out. In the original implementation, its input contains concatenated head outputs before output projection. Verify shape and ordering in the installed version, then interpret the last dimension as n_heads blocks of head_dim. Attention weights may be unavailable on a fused attention path; head-output instrumentation should not depend on them [3].

Capture only the declared token positions and candidate components. Store detached clones, not references to mutable tensors. Remove hooks in finally blocks. Capture and intervention modes must be explicit; observation alone must leave model output unchanged.

Record per-head activation norms and, if cheap, projected contribution norms as descriptive diagnostics. A high norm does not establish semantic meaning. Do not treat an intermediate vector's direct vocabulary projection as the complete causal effect of a head: later layers can transform that contribution. Use a forward intervention for the main causal measurement.

The primary diagnostic measurement is the change in log probability of a fixed, unsupported next token at a fixed prefix. Record the original value, intervention value, and signed difference. For genuine speech, measure the corresponding reference token at a reference prefix. Retain per-example results rather than only an aggregate.

An optional secondary measurement is the raw logit margin between the unsupported token and EOT at that same position. Clearly identify it as a raw diagnostic. EOT may be suppressed by decoding filters at some positions. Record whether the candidate token and comparator are permitted by the production filters.

Record no-speech probability at its actual start-of-transcript position separately. It is not interchangeable with EOT at the next-transcript-token position. The original decoder reads these at different positions [4]. Do not define a generic hallucination score by subtracting unrelated no-speech and continuation logits.

## Controlled head attenuation

Support two mutually exclusive intervention modes:

- A diagnostic hook scales the selected head output before projection.
- A permanent edit scales the matching input columns of the output projection from a pristine weight snapshot.

For a fixed scalar, these implement the same linear attenuation, apart from numerical precision. Verify their equivalence on an actual forward pass. Never enable both together, which would apply the attenuation twice.

Use the installed model's dimensions. For a head h, compute its contiguous column slice from head_dim = n_text_state // n_text_head. The permanent assignment is:

```python
# Specification of the operation; integrate with the project's edit manager.
W[:, start:stop] = pristine_W[:, start:stop] * scale
```

Scale columns, preserve projection bias, and leave unrelated tensors unchanged. The hook used for equivalence must cover the same token positions as the weight edit; a permanent edit applies at every position. Single-position interventions are distinct experiments and must be labeled accordingly.

Each independent candidate starts from pristine tensors. Do not multiply an already modified slice. Clear caches, validate finite outputs, and restore all edited slices after each candidate. Record both the targeted parameter count and the number of values actually changed.

Use scales from the existing set 0, 0.25, 0.5, 0.75, 1. Include scale 1 as an identity control. Evaluate a seed-fixed set of control heads matched by layer, scale, and parameter budget where possible. Report every control, including those that perform as well as or better than the selected head.

Select on discovery data and compare on reserved development cases where possible. A best-of-many selected head beating random heads on the same selection data is exploratory evidence, not an unbiased significance test.

## Bounded search and runtime agency

Reuse the existing worker/proposer adapter. Give the runtime investigator structured tools for inspecting model dimensions, requesting development summaries, running declared probes, proposing a head intervention, and reading results. Keep acceptance logic in the trusted controller.

A hypothesis record should include:

```json
{
  "hypothesis_id": "allocated_by_controller",
  "parent_experiment_id": null,
  "claim": "A selected component raises unsupported continuation preference",
  "predicted_direction": "decrease_target_logprob_when_attenuated",
  "alternative": "general_suppression_of_transcription",
  "component": {"kind": "decoder_self_attention", "layer": 0, "head": 0},
  "position_scope": "all_prefix_positions",
  "discovery_case_ids": [],
  "control_case_ids": [],
  "control_head_ids": [],
  "intervention": {"kind": "head_scale", "scale": 0.5},
  "would_weaken_claim": "Comparable effects on genuine speech and control heads"
}
```

The component indices above illustrate the schema; they are not a discovered head. Fill records with real case IDs, validated indices, and evidence references. Validate proposals against an allowlist and explicit shape/range checks. The agent proposes experiments; the controller executes, logs, and scores them.

Use this initial budget, reducing it before the search if measured throughput requires it:

- At most 12 fixed discovery cases, spanning the available cohorts, reused across intervention conditions. This is a case limit, not a limit of 12 total forward passes.
- At most 24 distinct head interventions for coarse screening at one declared scale.
- At most three shortlisted heads and the remaining declared scales for refinement.
- At most three finalists evaluated through full application transcription on development recordings.
- For the selected candidate, five seed-fixed matched control heads where the architecture permits; use all eligible heads if fewer exist.
- At most one frozen candidate sent to the final audio holdout.

Calibrate per-case runtime before searching. Set a hard development-search deadline, initially capped at 30 minutes and shortened to fit the existing schedule. Reserve measured time for confirmation, export/reload, final paired evaluation, reporting, and the original demonstration window. Do not start a comparison whose predicted cost exceeds its remaining budget. If the deadline interrupts a comparison, mark it incomplete and inconclusive; do not present the completed side alone as evidence of improvement.

Cache audio features when the encoder and preprocessing are unchanged. Never reuse decoder caches between candidates. Save completed experiment records incrementally and resume without replaying finished trials.

The runtime agent should use observed development evidence to propose at least one next experiment and state its predicted outcome. A fixed sweep is an acceptable engineering baseline, but label it as a sweep. Do not claim autonomous investigation from a human-written explanation attached afterward.

## Activation interchange extension

Implement this only after the core path works and the deadline permits. It strengthens a causal investigation but is not required to finish the software.

Create a donor-recipient pair with the same prefix token IDs, token positions, model version, and reasonably comparable audio conditions. Prefer controlled, documented variants of the same non-speech source that differ in baseline behavior. Freeze the pair on discovery data. If suitable pairs do not exist, report the experiment unavailable; do not fabricate a clean counterpart.

Cache the candidate head's activation from an unmodified donor forward pass. In the recipient, replace only that head at the declared position or positions, before output projection. Leave other components unchanged. Measure the recipient's fixed target-token score before and after replacement.

Include a self-patch, a no-op hook, and matched control-head swaps. Test both donor directions when feasible. Report each direction separately; asymmetric effects are possible and do not automatically invalidate an experiment. A change under an imposed prefix does not establish that the model would spontaneously generate that prefix.

Treat transfers between dissimilar inputs as potentially unnatural internal states. Show donor IDs, recording provenance, prefix, positions, and any matching limitations. Patching methods and metrics can materially affect the conclusion [2]. Do not infer universal necessity or sufficiency from one successful swap.

Activation interchange is an experiment, not automatically a deployable weight edit. Only the constant head-scaling intervention in the supported edit manager is compiled into the saved checkpoint.

## Acceptance and evidence statuses

Persist four independent outcomes. The report and dashboard must not collapse them into one success badge.

| Status field | Meaning |
| --- | --- |
| implementation_status | Required software checks pass, fail, or remain unrun |
| mechanism_status | Descriptive only, causal localization, evidence for the stated hypothesis, or inconclusive |
| repair_status | Development only, held-out accepted, rejected, inconclusive, or not evaluated |
| agent_upgrade_status | Result from the existing independent coding-task gate |

An intervention effect exceeding the declared identity/numerical tolerance supports a causal contribution under that intervention. Use the stronger hypothesis label only when prespecified predictions repeat beyond the selection cases, appropriate controls are available, and the observed effects discriminate at least the main competing explanation. Before searching, encode the minimum independent case count, predicted direction, minimum effect above measured numerical variation, control comparison, and speech-retention requirement as executable quantitative criteria. Missing or unmet criteria block the stronger label. Log every predicate and result; do not let the language model award this label from its prose. Small case counts remain pilot evidence and do not establish a full circuit.

Reuse the existing audio repair gate. Before the final evaluation, freeze the model, candidate patch, configuration, metrics, and thresholds. For the current pilot, the selected artifact must have strictly fewer non-speech recordings with unwanted lexical output, no newly empty genuine-speech transcript, at most 0.01 absolute corpus WER degradation on genuine speech, and no inference failures. Report raw counts, denominators, WER, dropouts, and errors for both checkpoints. Never compute WER against empty non-speech references as the primary defect metric.

Define lexical output and text normalization once. Preserve raw transcripts alongside normalized scoring text. A timeout is an error, not a correctly silent recording. A held-out baseline with no hallucinations makes reduction inconclusive; never report an improvement percentage with a zero denominator.

The trusted evaluator runs the pristine checkpoint and the frozen exported candidate on the same held-out recordings. Keep this material outside the runtime investigator's mount. Freeze any final mechanistic confirmation protocol before exposing its cases as well. After held-out exposure, stop tuning on that set. A rejected artifact leaves the accepted checkpoint active and retains all evidence.

Do not require a positive research result for implementation_status=passed. Valid outcomes include no reproducible defect, no localized component, no acceptable repair, or insufficient evidence.

## Artifacts and integration

Adapt names to the repository's current package structure. Suggested responsibilities are:

- probes.py: aligned decoder inputs, hook lifecycle, diagnostic scores, and trace metadata.
- interventions.py: candidate validation, pristine restoration, head scaling, and optional activation interchange.
- investigator.py: bounded structured proposals using the existing agent adapter.
- evidence.py: experiment records, evidence qualifications, and report generation.

Reuse the current loader, scorer, edit manager, checkpoint store, event log, and dashboard wherever they exist. Add equivalent CLI operations for probe preparation, running an investigation, evaluating a frozen candidate, and rendering the report. Document the actual commands implemented; do not publish proposed command names as tested commands.

Every experiment record must bind the hypothesis and intervention to the application commit, agent policy version, checkpoint hash, configuration hash, manifest hash, source recording and window, prefix token IDs, target position, controls, seed, timing, raw measurements, error state, and artifact paths. Store large activation arrays separately with hashes. Do not include credentials.

Produce an experiment manifest, append-only results JSONL, per-example scores, a structured evidence summary, and a readable report. If a candidate is exported, include the patch manifest, pristine parent hash, changed tensor slices, scale, actual changed-value count, exported checkpoint hash, and reload verification. Include negative and failed experiments.

Extend the existing dashboard with a compact evidence view: audio and transcript before/after, diagnostic score changes, selected head versus controls, genuine-speech retention, experiment provenance, and the four separate statuses. Mark recorded traces as recorded. A heatmap is optional; numbers, controls, and reproducible commands take priority.

Keep the Whisper checkpoint version separate from the coding agent's policy version and the application's source commit. An agent skill learned from a failed investigation still needs the original independent coding-task evaluation before promotion. Preserve the current rollback behavior.

## Required verification

Write focused checks for boundaries that could invalidate the experiment:

1. Observation and identity: capturing activations, a no-op hook, and scale 1 preserve logits within declared numerical tolerance and preserve deterministic transcript output on a fixture.
2. Intervention equivalence: all-position hook scaling and the permanent column edit agree within dtype-appropriate tolerance on the same real model input. Applying both modes simultaneously is rejected.
3. State isolation: candidates run independently from pristine tensors; exceptions remove hooks and restore state; rollback restores the original parameter hash and output.
4. Token alignment: compare diagnostic target logits and start-of-transcript no-speech probability with the corresponding unmodified decoder forward pass. Reject mismatched prefixes, positions, or unsupported ragged batches.
5. Scoring integrity: an inference error cannot become a success; empty genuine speech is counted; output normalization and speech-only corpus WER are fixed.
6. Export integrity: a fresh process loads the saved candidate with no intervention hooks and reproduces the candidate's smoke results. Confirm it did not accidentally reload the stock checkpoint.
7. Evaluation separation: runtime proposals cannot select final holdout inputs or alter gate thresholds. A consumed evaluation cannot be presented as a fresh holdout.

Report unrun checks as unrun. Use synthetic fixtures for software failures where useful, but label them separately from real Whisper evidence. Do not invent model improvements to complete the demo.

## Execution order and time limits

Fit this work into the existing schedule and preserve its demonstration reserve. With the baseline application available, cap new implementation work at roughly 90 minutes and calibrate experiment runtime before the search. If the baseline is still missing, complete it first and reduce the investigation scope. Do not spend the remaining hackathon on exhaustive probes.

1. Inspect existing components, verify one actual baseline failure, and freeze the diagnostic contract.
2. Implement aligned probes and the identity/equivalence checks.
3. Run the bounded discovery search, speech controls, and matched head controls; freeze one hypothesis and candidate.
4. Use the reserved development confirmation cases. Add activation interchange only if sufficient time and appropriate pairs remain.
5. Export and reload the candidate, run the one-time final audio comparison, and produce the evidence report.
6. Demonstrate the actual agent proposal, causal experiment, repair decision, and independent agent-policy status.

Cut activation interchange first if needed, then reduce the number of candidate heads. Preserve controls, speech retention, rollback, and honest statuses. If no reproducible defect appears, stop the head search and report that result; keep the software usable for a future dataset.

## Completion checklist

- The existing project still runs and its agent-policy gate remains intact.
- A real baseline and every evaluated configuration are recorded.
- At least one controlled internal experiment runs end to end, or the absence of an eligible failure is explicitly recorded.
- Diagnostic scores and application outcomes are reported separately.
- Control heads and genuine-speech retention are included.
- Any exported artifact passes fresh-process reload checks.
- Held-out audio is consumed once after candidate freeze.
- A rejected or inconclusive model-promotion result leaves the incumbent checkpoint active; an inconclusive mechanism claim alone does not decide model promotion.
- The final report states what the evidence establishes and gives exact reproduction commands.

## References

Use these as methodological and implementation references. Pin the installed source version in run records; a mutable main URL is not a version identifier.

1. Elhage and colleagues, A Mathematical Framework for Transformer Circuits. Mechanistic interpretability as reverse engineering internal computations. https://transformer-circuits.pub/2021/framework/
2. Zhang and Nanda, Towards Best Practices of Activation Patching in Language Models. Localization, metric selection, and intervention-design limitations. https://arxiv.org/abs/2309.16042
3. OpenAI Whisper model implementation. Verify the actual attention layout and projection behavior before hooking or editing. https://github.com/openai/whisper/blob/main/whisper/model.py
4. OpenAI Whisper decoding implementation. Prefix construction, no-speech position, and logit filters. https://github.com/openai/whisper/blob/main/whisper/decoding.py
5. OpenAI Whisper transcription implementation. Windowing and no-speech filtering behavior. https://github.com/openai/whisper/blob/main/whisper/transcribe.py
6. Wang and colleagues, Calm-Whisper. Prior work uses decoder head masking to investigate non-speech hallucinations, followed by selective fine-tuning. Head ablation itself is not a new contribution; the project investigates autonomous, controlled diagnosis and verified repair. https://arxiv.org/abs/2505.12969
