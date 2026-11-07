"""Render measured audio results; keep policy evidence in its own report."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper_repair.experiment import read,rows,save,sha,now,OFFICIAL_SMALL_SHA256
from whisper_repair.metrics import words

root=Path('audio_runs');manifest=rows('whisper_audio_dev/manifest.jsonl')
baseline=read(root/'baseline_development'/'metrics.json')
raw={x['id']:x for x in rows(root/'baseline_development'/'raw.jsonl')}
known=rows(root/'known_failures.jsonl')
# Keep this directly observed degeneration distinct from the predeclared lexical metric.
for index,item in enumerate(manifest,1):
    prediction=raw[item['id']]
    if prediction['status']=='ok' and prediction['text'].strip() and not words(prediction['text']) and prediction['text'].count('...')>=3:
        if any(x['id']==item['id'] for x in known):continue
        known.append({'id':item['id'],'failure_class':'repeated_nonlexical_punctuation_diagnostic',
            'prediction':prediction,'reference_text':item['reference_text'],'manifest':'whisper_audio_dev/manifest.jsonl',
            'manifest_line':index,'manifest_link':str(Path('whisper_audio_dev/manifest.jsonl').resolve())+':'+str(index),
            'manifest_sha256':sha('whisper_audio_dev/manifest.jsonl'),'audio_sha256':item['sha256'],
            'audio_path':str(Path('whisper_audio_dev')/item['audio_path']),'label_provenance':item['label_provenance'],
            'review_required':item.get('review_required',True),'source_url':item.get('source_url'),
            'source_recording_id':item.get('source_recording_id'),'source_dataset':item.get('source_dataset'),
            'local_observation':True,'confirmed_hallucination':False,
            'metric_disposition':'Does not increment the lexical hallucination count.'})
for observation in known:
    stats=observation['prediction'].get('audio_stats',{})
    if stats.get('exact_digital_silence') and words(observation['prediction'].get('text','')):
        observation['local_label_evidence']={'method':'every PCM16 sample equals zero','frames':stats['frames'],'rms':0.0,'human_review':False}
        observation['confirmed_hallucination']=True
text=''.join(json.dumps(x,sort_keys=True)+'\n' for x in known)
(root/'known_failures.jsonl').write_text(text);Path('known_failures.jsonl').write_text(text)
save(root/'known_failures_status.json',{'status':'observed','baseline_complete':baseline['complete'],'count':len(known),
 'recordings_inferred':len(raw),'lexical_nonspeech_failure_records':len(baseline['nonspeech']['lexical_output_ids']),
 'nonlexical_diagnostics':sum(x['failure_class']=='repeated_nonlexical_punctuation_diagnostic' for x in known),
 'definition':'Observed transcription deviations/errors and separately labeled punctuation degeneration; nonspeech labels require review.'})
search=read(root/'search_results.json') if (root/'search_results.json').exists() else []
frozen=read(root/'frozen_candidate.json') if (root/'frozen_candidate.json').exists() else None
heldout=read(root/'heldout_comparison.json') if (root/'heldout_comparison.json').exists() else None
reproductions=read(root/'reproduction_results.json')
case_table=[]
for item in reproductions:
    prediction=item['raw_prediction'];text=prediction.get('text','')
    outcome='Reproduced on verified all-zero audio' if item['lexical_output_observed'] and prediction.get('audio_stats',{}).get('exact_digital_silence') else 'Lexical failure behavior reproduces (conditional on supplied non-speech label)' if item['lexical_output_observed'] else 'No lexical failure; repeated punctuation' if text.strip() else 'Empty output; reported failure not reproduced'
    excerpt=text if len(text)<130 else text[:127]+'…'
    case_table.append('| `'+item['id']+'` | '+('`'+excerpt.replace('|','/')+'`' if text else '(empty)')+' | '+outcome+' |')
search_table=['| Attempt | Decoder layer / head | Scale | NS lexical clips / 17 | Speech WER | New empty speech | Errors | Dev gate |','| --- | --- | --- | --- | --- | --- | --- | --- |']
for n,x in enumerate(search,1):search_table.append(f"| {n} | {x['layer']} / {x['head']} | {x['scale']} | {x['nonspeech_lexical_outputs']} | {x['speech_wer']:.4%} | {len(x['newly_empty_speech'])} | {len(x['errors'])} | {'pass' if x['gate_pass'] else 'reject'} |")
metrics='Held-out evaluation has not run. The pack remains quarantined until a candidate is frozen.'
if heldout:
    before=heldout['baseline'];after=heldout['candidate'];ns=before['nonspeech']['recordings'];sp=before['speech']['recordings']
    metrics=f'''| Held-out metric | Baseline | Frozen candidate |
| --- | --- | --- |
| Complete recordings | {before['recordings']-len(before['errors'])} / {before['recordings']} | {after['recordings']-len(after['errors'])} / {after['recordings']} |
| Non-speech lexical outputs under supplied labels | {len(before['nonspeech']['lexical_output_ids'])} / {ns} | {len(after['nonspeech']['lexical_output_ids'])} / {ns} |
| Weak-label NS lexical outputs | {len(before['nonspeech']['weak_label_lexical_output_ids'])} | {len(after['nonspeech']['weak_label_lexical_output_ids'])} |
| Stronger-source-label NS lexical outputs | {len(before['nonspeech']['strong_label_lexical_output_ids'])} | {len(after['nonspeech']['strong_label_lexical_output_ids'])} |
| Speech corpus WER ({sp} speech clips) | {before['speech']['edits']} / {before['speech']['reference_words']} = {before['speech']['wer']:.4%} | {after['speech']['edits']} / {after['speech']['reference_words']} = {after['speech']['wer']:.4%} |
| Empty speech outputs | {len(before['speech']['empty_ids'])} | {len(after['speech']['empty_ids'])} |
| Errors / timeouts | {len(before['errors'])} | {len(after['errors'])} |

**Newly empty speech transcripts:** {len(heldout['newly_empty_speech_ids'])}; IDs: `{heldout['newly_empty_speech_ids']}`.

**Held-out pilot gate:** {'PASS' if heldout['gate_pass'] else 'FAIL'}. Speech WER change: {heldout['speech_wer_delta']*100:+.4f} percentage points. No tuning after this comparison.

Full per-recording checks, every error and the label-strength split are preserved in `audio_runs/heldout_comparison.json`.
'''
selection='No candidate is selected or frozen.'
if frozen:
    p=frozen['package'];i=p['intervention']
    selection=f"Development repair gate passed: **{p['development_gate_passed']}**. Selection status: `{p['selection_status']}`. The selected artifact is an experimental comparison candidate, not an approved repair. Frozen saved-weight candidate: decoder `{i['parameter']}`, head **{i['column_head']}**, scale **{i['scale']}** (zero-based indices). Candidate checkpoint SHA-256 `{i['checkpoint_sha256']}`; freeze-package SHA-256 `{frozen['sha256']}`."
result_title='No held-out artifact result yet.'
if heldout:result_title='The frozen weight artifact passes both pilot gates on this sample.' if heldout['gate_pass'] and frozen['package']['development_gate_passed'] else 'No validated Whisper weight improvement; retain the original checkpoint.'
elapsed=sum(x.get('elapsed',0) for x in raw.values())
report=f'''# Whisper artifact results

Recorded {now()}.

**{result_title}** Audio findings apply to this checkpoint, decoding configuration and convenience sample. They do not establish coding-agent skills or context-policy improvement; see [the separate agent-policy report](AGENT_POLICY_RESULTS.md).

## Untouched baseline and five reported cases

The original multilingual **small** checkpoint was loaded with the original `openai-whisper` PyTorch implementation. Its bytes match the [official loader's SHA-256](https://raw.githubusercontent.com/openai/whisper/main/whisper/__init__.py): `{OFFICIAL_SMALL_SHA256}`. The same pristine hash was checked again after inference and each edit. No model switch occurred. The initial full-development baseline required approximately **{elapsed:.2f}s** of measured inference (including initial model loads), comfortably within the first 15-minute testing window.

| Reported reproduction | Raw text (excerpt; complete output saved) | Local outcome |
| --- | --- | --- |
{chr(10).join(case_table)}

Thus **2/5 reported cases reproduce lexical non-speech failure behavior** under the supplied labels. The invented narrative differs from the upstream quoted narrative. Repeated ellipses are a distinct observed degeneration, not a lexical hallucination. The original five labels remain contributor-reported and lack local human review. Additionally, `one_minute_silence` is computationally verified to contain **960,768 zero PCM samples** (RMS 0), independently confirming no acoustic speech in that case. The synthetic narrative case remains conditional on its supplied non-speech label. [Upstream reports](https://github.com/openai/whisper/discussions/1873) are provenance, not proof of performance on small.

Full original return dictionaries, segments, tokens and confidence fields: `audio_runs/baseline_reproduction/raw.jsonl`. The reproduction summary is `audio_runs/reproduction_results.json`. These were saved before any other development transcription or weight edit.

## All development recordings and observed failures

All **29** development recordings match their supplied audio and manifest hashes; the extracted manifest matches `whisper_audio_dev.zip`. Every candidate evaluation includes all **12 genuine-speech** clips and all **17 supplied-label non-speech** clips.

Baseline: **{len(baseline['nonspeech']['lexical_output_ids'])}/17** non-speech clips produce lexical text, all under originally weak/unreviewed labels; the all-zero silence case has additional direct signal verification. Genuine-speech WER: **{baseline['speech']['edits']}/{baseline['speech']['reference_words']} = {baseline['speech']['wer']:.4%}**. Empty speech transcripts: **{len(baseline['speech']['empty_ids'])}**. Errors/timeouts: **{len(baseline['errors'])}**.

`known_failures.jsonl` contains **{len(known)} locally observed records**: nine weak-label non-speech lexical outputs, six speech transcription mismatches, and one separately labeled repeated-punctuation diagnostic. Each links to the original manifest record and preserves its label provenance, audio/manifest hash and raw local prediction. Contributor reports and VAD labels are not promoted to independent human confirmation. The all-zero silence entry separately records its computational verification and is marked a confirmed zero-signal lexical hallucination. The complete copy and status summary also live under `audio_runs/`.

## Development-only weight selection

A first-order gradient proposal ranked decoder cross-attention heads using the nine locally observed non-speech lexical cases and all 12 genuine-speech references. It used a first 30-second window solely for proposal ranking, not for performance scoring. Proposal quality is not assumed: every saved artifact is independently reloaded and transcribes every full development recording.

The predeclared search orders the four highest-ranked heads at scales 0.75, then 0.5, with a maximum of eight candidates and stopping at the first development gate pass. All eight were used; none passed. To complete the requested final comparison, selection was separated from repair approval **before any holdout access**: among nonregressing measured candidates, choose lowest NS lexical count, then speech WER, then least attenuation, then parameter/head. That selected the 0.75 attenuation of layer 2/head 5. The baseline remained the accepted artifact. No candidate-search budget was extended and neither the gate, scorer, nor decoding implementation changed. The exact selection-only source diff and original source are preserved under `audio_runs/protocol_versions/`. No head or scale is chosen using held-out results. The gate requires strictly fewer supplied-label NS lexical outputs, no newly empty genuine speech, no more than one absolute percentage point speech WER increase, complete coverage and no errors.

{chr(10).join(search_table)}

{selection}

The edit scales only the selected head's input-column block of the decoder cross-attention output projection. Each proposal starts from the pristine checkpoint. All state tensors are hashed; export/reload must match the intended tensors and only the selected parameter may differ. A separate original-Whisper inference process reloads each saved candidate. This is a static **weight-artifact experiment**, not an inference filter or decoding-policy change.

## Complete held-out comparison

{metrics}

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
'''
Path('docs/AUDIO_RESULTS.md').write_text(report)
print(result_title)
