# Whisper artifact results

Recorded 2026-11-07T19:47:52.654478+00:00.

**No validated Whisper weight improvement; retain the original checkpoint.** Audio findings apply to this checkpoint, decoding configuration and convenience sample. They do not establish coding-agent skills or context-policy improvement; see [the separate agent-policy report](AGENT_POLICY_RESULTS.md).

## Untouched baseline and five reported cases

The original multilingual **small** checkpoint was loaded with the original `openai-whisper` PyTorch implementation. Its bytes match the [official loader's SHA-256](https://raw.githubusercontent.com/openai/whisper/main/whisper/__init__.py): `9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794`. The same pristine hash was checked again after inference and each edit. No model switch occurred. The initial full-development baseline required approximately **30.19s** of measured inference (including initial model loads), comfortably within the first 15-minute testing window.

| Reported reproduction | Raw text (excerpt; complete output saved) | Local outcome |
| --- | --- | --- |
| `dima_clip` | (empty) | Empty output; reported failure not reproduced |
| `no_sound_test` | (empty) | Empty output; reported failure not reproduced |
| `one_minute_silence` | ` you you you` | Reproduced on verified all-zero audio |
| `whisper_synthetic_5` | ` I'm not sure what I'm doing here. I'm just going to go back to the beginning of the game. I'm just going to go back to the beg…` | Lexical failure behavior reproduces (conditional on supplied non-speech label) |
| `whisper_synthetic_5_2` | ` ... ... ... ... ... ... ... ... ... ... ... ... ...` | No lexical failure; repeated punctuation |

Thus **2/5 reported cases reproduce lexical non-speech failure behavior** under the supplied labels. The invented narrative differs from the upstream quoted narrative. Repeated ellipses are a distinct observed degeneration, not a lexical hallucination. The original five labels remain contributor-reported and lack local human review. Additionally, `one_minute_silence` is computationally verified to contain **960,768 zero PCM samples** (RMS 0), independently confirming no acoustic speech in that case. The synthetic narrative case remains conditional on its supplied non-speech label. [Upstream reports](https://github.com/openai/whisper/discussions/1873) are provenance, not proof of performance on small.

Full original return dictionaries, segments, tokens and confidence fields: `audio_runs/baseline_reproduction/raw.jsonl`. The reproduction summary is `audio_runs/reproduction_results.json`. These were saved before any other development transcription or weight edit.

## All development recordings and observed failures

All **29** development recordings match their supplied audio and manifest hashes; the extracted manifest matches `whisper_audio_dev.zip`. Every candidate evaluation includes all **12 genuine-speech** clips and all **17 supplied-label non-speech** clips.

Baseline: **9/17** non-speech clips produce lexical text, all under originally weak/unreviewed labels; the all-zero silence case has additional direct signal verification. Genuine-speech WER: **13/264 = 4.9242%**. Empty speech transcripts: **0**. Errors/timeouts: **0**.

`known_failures.jsonl` contains **16 locally observed records**: nine weak-label non-speech lexical outputs, six speech transcription mismatches, and one separately labeled repeated-punctuation diagnostic. Each links to the original manifest record and preserves its label provenance, audio/manifest hash and raw local prediction. Contributor reports and VAD labels are not promoted to independent human confirmation. The all-zero silence entry separately records its computational verification and is marked a confirmed zero-signal lexical hallucination. The complete copy and status summary also live under `audio_runs/`.

## Development-only weight selection

A first-order gradient proposal ranked decoder cross-attention heads using the nine locally observed non-speech lexical cases and all 12 genuine-speech references. It used a first 30-second window solely for proposal ranking, not for performance scoring. Proposal quality is not assumed: every saved artifact is independently reloaded and transcribes every full development recording.

The predeclared search orders the four highest-ranked heads at scales 0.75, then 0.5, with a maximum of eight candidates and stopping at the first development gate pass. All eight were used; none passed. To complete the requested final comparison, selection was separated from repair approval **before any holdout access**: among nonregressing measured candidates, choose lowest NS lexical count, then speech WER, then least attenuation, then parameter/head. That selected the 0.75 attenuation of layer 2/head 5. The baseline remained the accepted artifact. No candidate-search budget was extended and neither the gate, scorer, nor decoding implementation changed. The exact selection-only source diff and original source are preserved under `audio_runs/protocol_versions/`. No head or scale is chosen using held-out results. The gate requires strictly fewer supplied-label NS lexical outputs, no newly empty genuine speech, no more than one absolute percentage point speech WER increase, complete coverage and no errors.

| Attempt | Decoder layer / head | Scale | NS lexical clips / 17 | Speech WER | New empty speech | Errors | Dev gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 / 11 | 0.75 | 10 | 4.9242% | 0 | 0 | reject |
| 2 | 1 / 3 | 0.75 | 9 | 4.9242% | 0 | 0 | reject |
| 3 | 6 / 3 | 0.75 | 9 | 4.9242% | 0 | 0 | reject |
| 4 | 2 / 5 | 0.75 | 9 | 4.5455% | 0 | 0 | reject |
| 5 | 1 / 11 | 0.5 | 10 | 4.9242% | 0 | 0 | reject |
| 6 | 1 / 3 | 0.5 | 9 | 4.5455% | 0 | 0 | reject |
| 7 | 6 / 3 | 0.5 | 9 | 4.9242% | 0 | 0 | reject |
| 8 | 2 / 5 | 0.5 | 10 | 4.5455% | 0 | 0 | reject |

Development repair gate passed: **False**. Selection status: `exploratory_selection_development_gate_failed`. The selected artifact is an experimental comparison candidate, not an approved repair. Frozen saved-weight candidate: decoder `decoder.blocks.2.cross_attn.out.weight`, head **5**, scale **0.75** (zero-based indices). Candidate checkpoint SHA-256 `9eeb7c9f22cb6c1df1fdbcacf37e79b94c7b219275a78076442867279a0457fd`; freeze-package SHA-256 `3185acc05629bd79f9cb68c42f06a3508661575b9800ddf5901a5ee9170b98ed`.

The edit scales only the selected head's input-column block of the decoder cross-attention output projection. Each proposal starts from the pristine checkpoint. All state tensors are hashed; export/reload must match the intended tensors and only the selected parameter may differ. A separate original-Whisper inference process reloads each saved candidate. This is a static **weight-artifact experiment**, not an inference filter or decoding-policy change.

## Complete held-out comparison

| Held-out metric | Baseline | Frozen candidate |
| --- | --- | --- |
| Complete recordings | 40 / 40 | 40 / 40 |
| Non-speech lexical outputs under supplied labels | 9 / 20 | 9 / 20 |
| Weak-label NS lexical outputs | 0 | 0 |
| Stronger-source-label NS lexical outputs | 9 | 9 |
| Speech corpus WER (20 speech clips) | 5 / 337 = 1.4837% | 5 / 337 = 1.4837% |
| Empty speech outputs | 0 | 0 |
| Errors / timeouts | 0 | 0 |

**Newly empty speech transcripts:** 0; IDs: `[]`.

**Held-out pilot gate:** FAIL. Speech WER change: +0.0000 percentage points. No tuning after this comparison.

Full per-recording checks, every error and the label-strength split are preserved in `audio_runs/heldout_comparison.json`.


The extracted holdout was moved outside the editing workspace before any audio work; its manifest, labels and waveforms were not read by the audio evaluator until the candidate was frozen. **Filesystem secrecy is not OS-enforced on this host**: this agent has broad filesystem read capability, the archive remains in Downloads, and filenames were visible in earlier project inspection. This is logical quarantine, not a tamper-proof or fully blind evaluation. No held-out tuning was performed. The one-use consultation ledger and frozen checkpoint/evaluator hashes are retained.

## Configuration and scoring

Original `openai-whisper`; multilingual small; CPU float32; English transcription; temperature 0; beam size 1; previous-window context enabled; compression-ratio threshold 2.4; log-probability threshold −1.0; no-speech threshold 0.6; seed 0; deterministic PyTorch; four CPU threads. All full WAV samples are preserved, with no trimming, denoising, loudness normalization or VAD filtering. Baseline and candidate settings are identical. Runtime versions are saved per stage.

Corpus WER is total Levenshtein word edits / total reference words, not a mean of clip WERs. Scoring uses Unicode NFKC, case-folding, internal apostrophes and letter/number tokenization, ignoring punctuation. No numeric expansion or English spelling normalization is applied. Raw text remains unchanged. Empty speech means zero lexical words, including punctuation-only output. Errors/timeouts are recorded separately and cannot count as silent successes. Supplied-label non-speech lexical outputs are reported separately by label strength; no new human audio annotation is claimed.

## Reproduce and inspect

```sh
.audio-venv/bin/python -m whisper_repair baseline --checkpoint audio_models/small.pt
.audio-venv/bin/python -m whisper_repair rank-heads --checkpoint audio_models/small.pt
.audio-venv/bin/python scripts/run_whisper_development.py
.audio-venv/bin/python -m whisper_repair heldout --checkpoint audio_models/small.pt --pack /private/tmp/neural-pr-audio-holdout-quarantine/whisper_audio_holdout
.audio-venv/bin/python scripts/report_whisper_audio.py
```

After holdout consultation, search/ranking/selection commands refuse further tuning. Only `heldout --resume` may continue an interrupted run using the exact frozen artifact and evaluator. Use a new development-only run directory for a genuinely new experiment, with a fresh independent holdout; this pack is no longer fresh once consulted.

Artifacts: `audio_runs/protocol.json`, `baseline_reproduction/`, `baseline_development/`, `head_ranking.json`, `search_plan.json`, `search_results.json`, `candidates/`, `frozen_candidate.json`, `holdout_consulted.json`, `heldout_baseline/`, `heldout_candidate/`, and `heldout_comparison.json`. Original and candidate weights remain private and ignored by Git. Audio metric and access-guard tests: 12 passed; those tests are engineering evidence, not Whisper accuracy evidence. The exact installed runtime and default decoding options are recorded in `audio_runs/runtime_identity.json`.
