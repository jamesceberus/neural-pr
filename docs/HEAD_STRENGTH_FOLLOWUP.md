# Head-strength direction follow-up (protocol v2)

Near its original operating point, this component contribution may restrain unsupported continuation. Modestly increasing its strength should reduce that continuation preference.

**Exploratory development analysis only.** All diagnostic cases, including former confirmation cases, informed this hypothesis. No fresh confirmation or final holdout is claimed. Pristine multilingual small remains active.

The previous repair is rejected. The original study and gate are unchanged. This protocol explicitly extends allowed scales to 0, 0.9, 1, 1.1, and 1.25 in a process-local context that restores the old defaults. Every condition starts from pristine projection values.

| Scale | Cohort | N | Mean Δ log p | Median Δ log p | Increase / decrease / numerical tie | Geometric-mean p ratio |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0 | unsupported_lexical | 7 | -0.002383 | +0.006575 | 4 / 3 / 0 | 0.997620 |
| 0.0 | correctly_empty | 5 | +0.044618 | +0.038352 | 5 / 0 / 0 | 1.045629 |
| 0.0 | genuine_speech | 8 | -0.004239 | -0.002093 | 2 / 6 / 0 | 0.995770 |
| 0.9 | unsupported_lexical | 7 | -0.000115 | +0.000838 | 4 / 3 / 0 | 0.999885 |
| 0.9 | correctly_empty | 5 | +0.004672 | +0.004081 | 5 / 0 / 0 | 1.004683 |
| 0.9 | genuine_speech | 8 | -0.000556 | -0.000304 | 2 / 6 / 0 | 0.999444 |
| 1.0 | unsupported_lexical | 7 | +0.000000 | +0.000000 | 0 / 0 / 7 | 1.000000 |
| 1.0 | correctly_empty | 5 | +0.000000 | +0.000000 | 0 / 0 / 5 | 1.000000 |
| 1.0 | genuine_speech | 8 | +0.000000 | +0.000000 | 0 / 0 / 8 | 1.000000 |
| 1.1 | unsupported_lexical | 7 | +0.000079 | -0.000891 | 3 / 4 / 0 | 1.000079 |
| 1.1 | correctly_empty | 5 | -0.004722 | -0.004152 | 0 / 5 / 0 | 0.995289 |
| 1.1 | genuine_speech | 8 | +0.000578 | +0.000308 | 6 / 2 / 0 | 1.000578 |
| 1.25 | unsupported_lexical | 7 | +0.000143 | -0.002286 | 3 / 4 / 0 | 1.000143 |
| 1.25 | correctly_empty | 5 | -0.011899 | -0.010482 | 0 / 5 / 0 | 0.988171 |
| 1.25 | genuine_speech | 8 | +0.001509 | +0.000804 | 6 / 2 / 0 | 1.001510 |

A probability ratio is a relative change in fixed target-token probability, not a percentage-point change in hallucination rate. All five matched heads and every per-case score are in `diagnostic_summary.json` and `events.jsonl`.

| Application condition | NS lexical output /17 | Speech edits / words | New empty speech | Errors | Fixed / regressed NS IDs |
| --- | --- | --- | --- | --- | --- |
| Pristine (recorded baseline) | 9 | 13 / 264 | 0 | 0 | — |
| Original scale 0 (recorded, diagnostic effect reproduced) | 10 | 10 / 264 | 0 | 0 | See original paired-transition file |
| selected_0.9 | 9 | 12 / 264 | 0 | 0 | [] / [] |
| selected_1.1 | 9 | 13 / 264 | 0 | 0 | [] / [] |
| selected_1.25 | 9 | 13 / 264 | 0 | 0 | [] / [] |
| control_H3_1.1 | 9 | 13 / 264 | 0 | 0 | [] / [] |
| control_H6_1.1 | 9 | 13 / 264 | 0 | 0 | [] / [] |
| control_H2_1.1 | 9 | 13 / 264 | 0 | 0 | [] / [] |
| control_H7_1.1 | 9 | 13 / 264 | 0 | 0 | [] / [] |
| control_H10_1.1 | 9 | 12 / 264 | 0 | 0 | [] / [] |

## Interpretation

Repair status: **rejected**. Fresh confirmation: **unavailable**. Accepted artifact: **pristine small.pt**. Agent-policy result: **no_validated_improvement**, from the separate coding-task gate.

Original scale-zero diagnostic reproduction: `{'max_delta_difference': 0.0, 'n': 8, 'passed': True}`. Hook/weight equivalence and identity variation are in `numerical_checks.json`.

For changed recordings, the transition files record no-speech probability, average log probability, skip decisions and whether window/prefix alignment held. Unaligned windows are not treated as controlled diagnostic comparisons. Newly failing and fixed recordings are listed separately; net counts are not used as a substitute for paired transitions.

No held-out data was reopened. There is no generalization claim. Do not tune further on the consumed original holdout.

## Reproduction

```sh
.audio-venv/bin/python scripts/followup_head_strength.py run
.venv/bin/python scripts/followup_head_strength.py report
```

The runner has a 15-minute experiment deadline with a supervising process timeout; completed records are reused. The source, old source identity, exact probe hashes, hypothesis, seed, criteria and new scale allowlist are registered in `manifest.json` before the first scaled comparison.

## Paired transitions from the rejected original edit

| Original condition | Fixed NS IDs | Regressed NS IDs | Net added failures |
| --- | --- | --- | --- |
| control_0 | [] | [] | 0 |
| control_1 | [] | [] | 0 |
| control_2 | [] | [] | 0 |
| control_3 | [] | [] | 0 |
| control_4 | [] | [] | 0 |
| selected | [] | ['whisper_synthetic_5_2'] | 1 |

## Former partitions, separately reported

Former confirmation is development data for this new hypothesis. Separating these results exposes selection-dependent sign reversals; it does not restore freshness.

| Former partition | Scale | NS cases | Mean Δ log p | Median Δ log p | Up / down / tie | Relative probability ratio |
| --- | --- | --- | --- | --- | --- | --- |
| discovery | 0 | 4 | -0.025436 | -0.004023 | 2 / 2 / 0 | 0.974885 |
| discovery | 0.9 | 4 | -0.002456 | -0.000339 | 2 / 2 / 0 | 0.997547 |
| discovery | 1 | 4 | +0.000000 | +0.000000 | 0 / 0 / 4 | 1.000000 |
| discovery | 1.1 | 4 | +0.002422 | +0.000306 | 2 / 2 / 0 | 1.002425 |
| discovery | 1.25 | 4 | +0.006008 | +0.000735 | 2 / 2 / 0 | 1.006026 |
| confirmation | 0 | 3 | +0.028354 | +0.006575 | 2 / 1 / 0 | 1.028760 |
| confirmation | 0.9 | 3 | +0.003006 | +0.000838 | 2 / 1 / 0 | 1.003011 |
| confirmation | 1 | 3 | +0.000000 | +0.000000 | 0 / 0 / 3 | 1.000000 |
| confirmation | 1.1 | 3 | -0.003045 | -0.000891 | 1 / 2 / 0 | 0.996960 |
| confirmation | 1.25 | 3 | -0.007677 | -0.002297 | 1 / 2 / 0 | 0.992353 |

## Per-case direction test

| Case | Former subset | Δ at 0 | Δ at 0.9 | Δ at 1.1 | Δ at 1.25 | Bidirectional prediction |
| --- | --- | --- | --- | --- | --- | --- |
| audioset_audioset_0000893 | discovery | -0.10719 | -0.01056 | +0.01050 | +0.02615 | False |
| audioset_audioset_0000900 | discovery | +0.00953 | +0.00092 | -0.00092 | -0.00229 | True |
| audioset_audioset_0000905 | discovery | -0.01757 | -0.00160 | +0.00154 | +0.00376 | False |
| audioset_audioset_0000911 | confirmation | +0.00657 | +0.00084 | -0.00089 | -0.00230 | True |
| audioset_audioset_0000912 | confirmation | -0.02978 | -0.00277 | +0.00272 | +0.00672 | False |
| one_minute_silence | discovery | +0.01350 | +0.00141 | -0.00142 | -0.00359 | True |
| whisper_synthetic_5 | confirmation | +0.10827 | +0.01095 | -0.01096 | -0.02745 | True |

## Matched-control comparison

| Scale | Selected mean NS Δ | Matched head means | Control median mean |
| --- | --- | --- | --- |
| 0.9 | -0.000115 | [(2, 0.000211), (3, -0.000109), (6, 0.000677), (7, 8e-05), (10, 7e-06)] | +0.000080 |
| 1.1 | +0.000079 | [(2, -0.00021), (3, 0.000106), (6, -0.000677), (7, -8.3e-05), (10, -6e-06)] | -0.000083 |
| 1.25 | +0.000143 | [(2, -0.000531), (3, 0.000262), (6, -0.001693), (7, -0.000205), (10, -2.2e-05)] | -0.000205 |

## Qualified follow-up conclusion

The bidirectional fixed-token prediction holds on 4/7 reused non-speech probes. No amplification setting passed the unchanged full-development repair gate. The fixed-token evidence does not establish a useful repair; stop pursuing this head under this hypothesis and retain the pristine checkpoint.

No claim of a dedicated detector or restraint mechanism is established. Effects on reference-token probabilities, matched controls, paired transcript transitions and filtering traces must be read together. A worsening attenuation intervention alone does not establish beneficial amplification.

Infrastructure recovery: the first supervisor inherited the coding worker’s 2 MB regular-file cap. Its partial tail and logs were preserved, complete hash-verified records were retained, and only the trusted research supervisor/source-recovery guard changed. Numerical experiment code, model, inputs, gate, scale budget and original 900-second deadline were unchanged. See `infrastructure_recovery/` and `execution_patch.json`.

Detailed accounting command: `.venv/bin/python scripts/report_head_strength_detail.py`.
