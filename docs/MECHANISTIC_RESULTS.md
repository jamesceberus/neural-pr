# Whisper mechanistic investigation results

Recorded 2026-11-07T20:17:28.734332+00:00. Development-only investigation; the earlier audio holdout is consumed.

| Independent status | Result |
| --- | --- |
| implementation_status | passed |
| mechanism_status | causal_localization |
| repair_status | rejected |
| agent_upgrade_status | no_validated_improvement |

## Hypothesis and actual finding

The chosen self-attention intervention has a measurable causal effect on fixed-prefix token scores, but the prespecified unsupported-continuation hypothesis is not supported: on confirmation, the unsupported-token log probability increased by 0.028354 nats on average instead of decreasing. Mean genuine-speech reference-token log probability fell by 0.010447 nats. Full development transcription worsened from 9/17 to 10/17 labeled non-speech lexical-output cases, while speech edits improved from 13/264 to 10/264. All five matched controls retained 9/17 non-speech lexical-output cases. No intervention produced empty genuine speech or inference errors. This is narrow causal localization of a token-score contribution, with inconclusive computational-role evidence, and a rejected repair.

Diagnostic log probabilities are uncached fixed-prefix scores, not freely generated transcripts. A head-output effect localizes a causal contribution under that intervention; it does not establish a dedicated hallucination component. Encoder and cross-attention roles are untested.

## Measurements and controls

| Head | Cohort | Cases | Mean target log-probability change |
| --- | --- | --- | --- |
| selected | unsupported_lexical | 3 | +0.028354 |
| selected | correctly_empty | 1 | +0.017985 |
| selected | genuine_speech | 4 | -0.010447 |
| control_L4_H3 | unsupported_lexical | 3 | +0.006987 |
| control_L4_H3 | correctly_empty | 1 | -0.002730 |
| control_L4_H3 | genuine_speech | 4 | +0.004614 |
| control_L4_H6 | unsupported_lexical | 3 | -0.002364 |
| control_L4_H6 | correctly_empty | 1 | +0.007174 |
| control_L4_H6 | genuine_speech | 4 | +0.011796 |
| control_L4_H2 | unsupported_lexical | 3 | +0.002350 |
| control_L4_H2 | correctly_empty | 1 | -0.012030 |
| control_L4_H2 | genuine_speech | 4 | +0.004959 |
| control_L4_H7 | unsupported_lexical | 3 | +0.004192 |
| control_L4_H7 | correctly_empty | 1 | -0.019157 |
| control_L4_H7 | genuine_speech | 4 | +0.006030 |
| control_L4_H10 | unsupported_lexical | 3 | +0.000486 |
| control_L4_H10 | correctly_empty | 1 | -0.004104 |
| control_L4_H10 | genuine_speech | 4 | -0.003315 |

## Application transcription

| Condition | NS lexical output / 17 | Speech edits / words | Empty speech | Errors |
| --- | --- | --- | --- | --- |
| pristine | 9 | 13 / 264 | 0 | 0 |
| selected | 10 | 10 / 264 | 0 | 0 |
| control_0_H3 | 9 | 13 / 264 | 0 | 0 |
| control_1_H6 | 9 | 12 / 264 | 0 | 0 |
| control_2_H2 | 9 | 11 / 264 | 0 | 0 |
| control_3_H7 | 9 | 11 / 264 | 0 | 0 |
| control_4_H10 | 9 | 11 / 264 | 0 | 0 |

## Verification

```json
{
  "all_passed": true,
  "capture_identity": {
    "max_logit_difference": 0.0,
    "passed": true
  },
  "capture_transcript_identity": {
    "passed": true
  },
  "double_mode_rejected": {
    "passed": true
  },
  "equivalence_0": {
    "max_logit_difference": 0.0,
    "passed": true
  },
  "equivalence_0.25": {
    "max_logit_difference": 0.0,
    "passed": true
  },
  "equivalence_0.5": {
    "max_logit_difference": 0.0,
    "passed": true
  },
  "equivalence_0.75": {
    "max_logit_difference": 2.300739288330078e-05,
    "passed": true
  },
  "equivalence_1": {
    "max_logit_difference": 0.0,
    "passed": true
  },
  "exception_rollback": {
    "passed": true
  },
  "export": {
    "checkpoint_sha256": "20ab6db230916b67e777d5330c6378f1ce9e27fe2a238832e7980b2e9376ccdd",
    "child_loaded_checkpoint_sha256": "20ab6db230916b67e777d5330c6378f1ce9e27fe2a238832e7980b2e9376ccdd",
    "child_loaded_projection_sha256": "171d4707cce77207cc4efac836bc339f7e22a45ae27a2424edb849b7fa5976ba",
    "child_pid": 60766,
    "distinct_from_stock": true,
    "fixtures": [
      {
        "case_id": "one_minute_silence",
        "fresh_export_text": " you you you",
        "hook_text": " you you you",
        "passed": true,
        "status": "ok"
      },
      {
        "case_id": "2277-149896-0000",
        "fresh_export_text": " He was in a fevered state of mind, owing to the blight his wife's action threatened to cast upon his entire future.",
        "hook_text": " He was in a fevered state of mind, owing to the blight his wife's action threatened to cast upon his entire future.",
        "passed": true,
        "status": "ok"
      }
    ],
    "fresh_process": true,
    "no_intervention_hooks_in_child": true,
    "passed": true,
    "selected_head": {
      "head": 4,
      "layer": 4,
      "scale": 0,
      "score": 0.025435715913772583
    },
    "tensor_reload_verified": true
  },
  "hook_identity": {
    "max_logit_difference": 0.0,
    "passed": true
  },
  "hook_transcript_identity": {
    "passed": true
  },
  "noop_identity": {
    "max_logit_difference": 0.0,
    "passed": true
  },
  "noop_transcript_identity": {
    "passed": true
  },
  "numerical_logprob_variation": 0.0,
  "sot_alignment": {
    "passed": true
  },
  "target_alignment": {
    "passed": true
  }
}
```

## Executable hypothesis predicates

```json
{
  "control_ns_mean_reductions": [
    -0.006987253824869792,
    0.0023642381032307944,
    -0.002350012461344401,
    -0.00419155756632487,
    -0.000486453374226888
  ],
  "control_ns_median_reduction": -0.002350012461344401,
  "effective_min_effect": 0.01,
  "mean_ns_logprob_reduction": -0.028354326883951824,
  "mean_speech_reference_logprob_loss": 0.010447362437844276,
  "mechanism_status": "causal_localization",
  "predicates": {
    "all_comparisons_complete": true,
    "application_speech_retention": true,
    "enough_independent_ns_groups": true,
    "five_matched_controls_available": true,
    "nonspeech_labels_verified": false,
    "ns_prediction_repeats": false,
    "selected_beats_control_median": false,
    "speech_not_generally_suppressed": false
  },
  "qualification": "Fixed-prefix causal contribution only; prior development exposure and uncertain labels limit interpretation."
}
```

## Provenance and gaps

All development cases were used in an earlier cross-attention experiment; confirmation is prospective only for this self-attention selection. Non-speech labels remain uncertain. No new short/quiet speech controls were added. The original final audio holdout was consumed before this addendum; a new set is needed for any new repair. Root source is snapshotted in an isolated Git repository; runtime filesystem secrecy is not enforced. The 2.84-second genuine-speech clip is included in every full transcription comparison, but was outside the fixed diagnostic discovery subset. No quiet-control label was invented.

The original final audio holdout remains consumed. This investigation does not reopen it or present development confirmation as fresh held-out evidence. New repairs need a new independent audio set. The separate coding-task gate and accepted agent-policy pointer remain unchanged.

Runtime investigator:
```json
{
  "initial_status": "infrastructure_unavailable",
  "investigation_mode": "seed_fixed_engineering_sweep; no autonomous investigation claim",
  "next_status": "infrastructure_unavailable",
  "runtime_next_proposal_executed": false
}
```

Activation interchange: unrun; no documented clean/unsupported same-source pair was established; prioritize matched attenuation controls and export integrity.

## Reproduction

```sh
.audio-venv/bin/python -m whisper_repair.mechanistic prepare
.audio-venv/bin/python -m whisper_repair.mechanistic investigate
.audio-venv/bin/python -m whisper_repair.mechanistic verify-export
.audio-venv/bin/python -m whisper_repair.mechanistic report
.venv/bin/python -m whisper_repair.mechanistic serve --port 8787
.venv/bin/python -m whisper_repair.mechanistic snapshot
```

Completed records are reused on resume; source/configuration changes require a new experiment directory. Commands run sequentially under the existing controller lock. `evaluate-heldout` refuses to treat the consumed original pack as fresh.

Artifacts: `manifest.json`, `hypotheses/`, `events.jsonl` (`results.jsonl` alias), `cases/`, `activations/`, `frozen_confirmation.json`, `patch_manifest.json`, `export_verification.json`, and `summary.json` in the experiment directory. Each probe result binds exact prefix/position/window and the application source commit, agent-policy version, checkpoint and configuration hashes.

## Recorded filter and coverage audit

Non-speech cases losing lexical output: `[]`. New non-speech lexical-output cases: `['whisper_synthetic_5_2']`.

Aligned production windows (same seek and initial prefix): 32. Skip-decision changes: 0. Unmatched windows: 2; no causal comparison is inferred from diverged prefixes or seek positions. Raw per-window no-speech probabilities and average log probabilities remain separate in `filter_analysis.json`.

The 2.84-second genuine-speech clip is included in every full transcription comparison, but was outside the fixed diagnostic discovery subset. No quiet-control label was invented.

Diagnostic trial counts: `{'coarse': 288, 'refinement': 144, 'confirmation': 8, 'confirmation_control': 40}`. Complete application-recording runs: 203. Runtime model-adapter calls both failed at the network boundary; no autonomous investigation claim is made.

Re-run this accounting without new inference using `.venv/bin/python scripts/audit_mechanistic.py`. The four acceptance statuses remain independent and the original coding-task gate is unchanged.
