# Head-strength follow-up protocol v2

This is an explicit user-requested extension of [the implementation addendum](mechanistic_interpretability.md). It changes the intervention scale set for one bounded follow-up, not the original repair gate or the failed experiment.

Hypothesis, registered before the follow-up measurements:

> Near its original operating point, this component’s contribution may restrain unsupported continuation. Modestly increasing its strength should reduce that continuation preference.

Model: the same pristine multilingual small checkpoint. Component: decoder self-attention layer 4, head 4 (zero-based). Scales: **0, 0.9, 1.0, 1.1, 1.25**. Scale 0 reproduces the previous negative intervention; 1.0 is identity. Five controls use the same layer, head dimension, scale, and parameter budget. Control identities come from the previous frozen seed-fixed set; their old stored `scale` fields describe the parent experiment, while each new trial records its actual v2 scale explicitly.

The implementation uses a process-local protocol context to extend the scale allowlist and export operation. It restores the old defaults and operation in `finally`. Legacy source files, failed records, gate thresholds, and accepted checkpoint are preserved. Every condition restores pristine tensors, uses the original fixed audio windows and prefix/target positions, and clears decoder caches.

The diagnostic set contains the same 20 frozen inputs (12 former discovery and eight former confirmation). **All are now development analysis. None is fresh confirmation for this hypothesis.** Report the former partitions separately as well as in aggregate. Report mean, median, direction counts above numerical identity variation, geometric-mean probability ratios, and every control. A ratio of probabilities is not a percentage-point change in hallucination incidence.

Full-recording comparisons use all 29 development recordings and every genuine-speech control. They test selected-head scales 0.9, 1.1 and 1.25, plus the five matched control heads at 1.1. Original scale-zero and identity application results are explicitly reused from the preceding study; their paired transitions are audited, and scale-zero diagnostic effects are reproduced. No old transcript is presented as a fresh inference result.

A promising amplification candidate must still pass the unchanged audio repair gate: strictly fewer non-speech lexical-output cases, no newly empty genuine speech, at most 0.01 absolute speech WER degradation and no inference errors. Even a development pass cannot promote a model without new source-independent confirmation and audio holdout. The original 40-recording holdout is already consumed and is not reopened.

The experiment budget is 900 seconds, with a supervising process timeout of 920 seconds to allow orderly startup. The overall addendum/project deadline remains in force. Completed trials persist and resume without being replayed. An interrupted comparison is incomplete and inconclusive.

Commands:

```sh
.audio-venv/bin/python scripts/followup_head_strength.py run
.venv/bin/python scripts/followup_head_strength.py report
```

The source snapshot, exact input hashes, hypothesis, seeds, old source identities, scale set and budget are saved before the scaled comparisons in `audio_runs/mechanistic_direction_v2/manifest.json`. Audio results and independent coding-agent policy results remain separate.
