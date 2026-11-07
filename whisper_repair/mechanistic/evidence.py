"""Independent status predicates and append-only evidence using the existing durable state."""
import json
from pathlib import Path
from neural_pr.state import State
from whisper_repair.experiment import save,read,rows,identity,now

CRITERIA={'min_independent_confirmation_ns_groups':3,'min_mean_ns_logprob_reduction':0.02,
          'min_direction_fraction':2/3,'min_control_advantage':0.02,'max_mean_speech_logprob_loss':0.01,
          'min_causal_effect':0.01,'numerical_multiplier':10,'logits_atol':0.0002,'logits_rtol':0.00002,
          'require_confirmed_nonspeech_for_strong_claim':True,'require_speech_retention':True}

class Evidence:
    def __init__(self,root):
        self.root=Path(root);self.state=State(root)
    def emit(self,kind,record):
        event=self.state.emit(kind,**record)
        # results.jsonl is the same append-only journal, not a second inconsistent source of truth.
        path=self.root/'results.jsonl'
        if not path.exists():path.symlink_to('events.jsonl')
        return event
    def trials(self):return [x['data'] for x in self.state.events() if x['kind']=='probe_trial']
    def completed(self):return {(x['phase'],x['case_id'],x['layer'],x['head'],x['scale']) for x in self.trials()}

def qualify(confirmation,controls,criteria,numerical_variation,retention_ok,independent_ns_groups,confirmed_labels):
    import statistics
    ns=[-x['target_logprob_delta'] for x in confirmation if x['cohort']=='unsupported_lexical' and x['status']=='ok']
    speech=[-x['target_logprob_delta'] for x in confirmation if x['cohort']=='genuine_speech' and x['status']=='ok']
    controls_ns={}
    for x in controls:
        if x['cohort']=='unsupported_lexical' and x['status']=='ok':controls_ns.setdefault((x['layer'],x['head']),[]).append(-x['target_logprob_delta'])
    control_means=[statistics.mean(values) for values in controls_ns.values()]
    effect=max(criteria['min_causal_effect'],criteria['numerical_multiplier']*numerical_variation)
    mean=statistics.mean(ns) if ns else 0
    speech_loss=statistics.mean(speech) if speech else float('inf')
    median=statistics.median(control_means) if control_means else float('inf')
    predicates={'enough_independent_ns_groups':independent_ns_groups>=criteria['min_independent_confirmation_ns_groups'],
                'ns_prediction_repeats':bool(ns) and mean>=criteria['min_mean_ns_logprob_reduction'] and sum(x>effect for x in ns)/len(ns)>=criteria['min_direction_fraction'],
                'five_matched_controls_available':len(control_means)>=5,
                'selected_beats_control_median':bool(control_means) and mean-median>=criteria['min_control_advantage'],
                'speech_not_generally_suppressed':bool(speech) and speech_loss<=criteria['max_mean_speech_logprob_loss'],
                'application_speech_retention':bool(retention_ok),
                'nonspeech_labels_verified':bool(confirmed_labels),
                'all_comparisons_complete':bool(confirmation) and all(x['status']=='ok' for x in confirmation+controls)}
    localized=any(abs(x.get('target_logprob_delta',0))>effect for x in confirmation if x['status']=='ok')
    return {'mechanism_status':'evidence_for_stated_hypothesis' if all(predicates.values()) else 'causal_localization' if localized else 'inconclusive',
            'predicates':predicates,'effective_min_effect':effect,'mean_ns_logprob_reduction':mean,
            'mean_speech_reference_logprob_loss':speech_loss if speech else None,
            'control_ns_mean_reductions':control_means,'control_ns_median_reduction':median if control_means else None,
            'qualification':'Fixed-prefix causal contribution only; prior development exposure and uncertain labels limit interpretation.'}

def summary(root):
    root=Path(root)
    if not (root/'summary.json').exists():return {'implementation_status':'unrun','mechanism_status':'inconclusive','repair_status':'not_evaluated','agent_upgrade_status':'no_validated_improvement','note':'Investigation not complete'}
    return read(root/'summary.json')

def render(root):
    root=Path(root);data=summary(root)
    lines=['# Whisper mechanistic investigation results','',f"Recorded {now()}. Development-only investigation; the earlier audio holdout is consumed.",'',
           '| Independent status | Result |','| --- | --- |']
    for key in ('implementation_status','mechanism_status','repair_status','agent_upgrade_status'):lines.append(f'| {key} | {data[key]} |')
    lines.extend(['','## Hypothesis and actual finding','',data.get('explanation','Not run.'),'',
                  'Diagnostic log probabilities are uncached fixed-prefix scores, not freely generated transcripts. A head-output effect localizes a causal contribution under that intervention; it does not establish a dedicated hallucination component. Encoder and cross-attention roles are untested.','',
                  '## Measurements and controls','', '| Head | Cohort | Cases | Mean target log-probability change |','| --- | --- | --- | --- |'])
    for row in data.get('diagnostic_table',[]):lines.append(f"| {row['head']} | {row['cohort']} | {row['n']} | {row['mean_delta']:+.6f} |")
    lines.extend(['','## Application transcription','', '| Condition | NS lexical output / 17 | Speech edits / words | Empty speech | Errors |','| --- | --- | --- | --- | --- |'])
    for row in data.get('application_table',[]):lines.append(f"| {row['condition']} | {row['nonspeech_lexical_outputs']} | {row['speech_edits']} / {row['speech_words']} | {row['empty_speech']} | {row['errors']} |")
    lines.extend(['','## Verification','', '```json',json.dumps(data.get('verification',{}),indent=2),'```','',
                  '## Executable hypothesis predicates','', '```json',json.dumps(data.get('qualification',{}),indent=2),'```','',
                  '## Provenance and gaps','',data.get('limitations',''),'',
                  'The original final audio holdout remains consumed. This investigation does not reopen it or present development confirmation as fresh held-out evidence. New repairs need a new independent audio set. The separate coding-task gate and accepted agent-policy pointer remain unchanged.','',
                  'Runtime investigator:', '```json',json.dumps(data.get('agent',{}),indent=2),'```','',
                  'Activation interchange: '+data.get('interchange','unrun; optional extension omitted to preserve core checks.'),'',
                  '## Reproduction','', '```sh',
                  '.audio-venv/bin/python -m whisper_repair.mechanistic prepare',
                  '.audio-venv/bin/python -m whisper_repair.mechanistic investigate',
                  '.audio-venv/bin/python -m whisper_repair.mechanistic verify-export',
                  '.audio-venv/bin/python -m whisper_repair.mechanistic report',
                  '.venv/bin/python -m whisper_repair.mechanistic serve --port 8787',
                  '.venv/bin/python -m whisper_repair.mechanistic snapshot','```','',
                  'Completed records are reused on resume; source/configuration changes require a new experiment directory. Commands run sequentially under the existing controller lock. `evaluate-heldout` refuses to treat the consumed original pack as fresh.','',
                  'Artifacts: `manifest.json`, `hypotheses/`, `events.jsonl` (`results.jsonl` alias), `cases/`, `activations/`, `frozen_confirmation.json`, `patch_manifest.json`, `export_verification.json`, and `summary.json` in the experiment directory. Each probe result binds exact prefix/position/window and the application source commit, agent-policy version, checkpoint and configuration hashes.'])
    text='\n'.join(lines)+'\n';(root/'REPORT.md').write_text(text)
    Path('docs/MECHANISTIC_RESULTS.md').write_text(text)
    return text
