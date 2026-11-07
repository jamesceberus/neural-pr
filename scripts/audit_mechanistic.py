"""Post-run accounting only: no model calls, new candidates, or threshold changes."""
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper_repair.experiment import read,rows,save,sha,identity,now
from whisper_repair.metrics import words
from whisper_repair.mechanistic.evidence import render,Evidence

root=Path('audio_runs/mechanistic_v1')
summary=read(root/'summary.json');manifest=read(root/'manifest.json')
selected={p.stem:read(p) for p in (root/'application'/'selected').glob('*.json') if p.stem!='comparison'}
baseline={p.stem:read(p) for p in (root/'baseline').glob('*.json')}
improved=[];regressed=[];matched_windows=[];unmatched=[]
for case_id,before in baseline.items():
    after=selected[case_id]
    if before['status']!='ok' or after['status']!='ok':continue
    original_record=next(x for x in rows('whisper_audio_dev/manifest.jsonl') if x['id']==case_id)
    if original_record['kind']=='nonspeech':
        if words(before['text']) and not words(after['text']):improved.append(case_id)
        if not words(before['text']) and words(after['text']):regressed.append(case_id)
    after_windows={(x['seek_frames'],tuple(x['initial_token_ids'])):x for x in after['windows']}
    for window in before['windows']:
        other=after_windows.get((window['seek_frames'],tuple(window['initial_token_ids'])))
        if other is None:unmatched.append({'id':case_id,'seek_frames':window['seek_frames'],'reason':'seek or initial prefix diverged'});continue
        matched_windows.append({'id':case_id,'seek_frames':window['seek_frames'],
            'initial_prefix_token_ids':window['initial_token_ids'],'baseline_skipped':window['skip_decision'],
            'candidate_skipped':other['skip_decision'],'baseline_no_speech_probability':window['no_speech_prob'],
            'candidate_no_speech_probability':other['no_speech_prob'],'baseline_avg_logprob':window['avg_logprob'],
            'candidate_avg_logprob':other['avg_logprob']})
filter_analysis={'nonspeech_lexical_output_removed_ids':improved,'new_nonspeech_lexical_output_ids':regressed,
                 'matching_window_count':len(matched_windows),'skip_decision_changes':[x for x in matched_windows if x['baseline_skipped']!=x['candidate_skipped']],
                 'unmatched_window_count':len(unmatched),'unmatched_windows':unmatched,'paired_window_scores':matched_windows,
                 'interpretation':'These are actual production-filter traces. Fixed-prefix diagnostic changes are separately recorded. Divergent prefixes/seeks are not treated as aligned causal comparisons.'}
save(root/'filter_analysis.json',filter_analysis)
dev=rows('whisper_audio_dev/manifest.jsonl')
short=[x['id'] for x in dev if x['kind']=='speech' and x['duration_s']<=3]
coverage={'all_application_speech_ids':[x['id'] for x in dev if x['kind']=='speech'],
          'short_development_speech_ids_under_3s':short,'short_ids_in_fixed_discovery':[x for x in short if x in manifest['discovery_ids']],
          'all_short_speech_evaluated_in_application':all(x in selected and selected[x]['status']=='ok' for x in short),
          'quiet_labeled_development_speech_available':False,
          'qualification':'The 2.84-second genuine-speech clip is included in every full transcription comparison, but was outside the fixed diagnostic discovery subset. No quiet-control label was invented.'}
save(root/'coverage.json',coverage)
trials=Evidence(root).trials();application_events=[x for x in Evidence(root).state.events() if x['kind'] in ('application_baseline','application_trial')]
counts={}
for trial in trials:counts[trial['phase']]=counts.get(trial['phase'],0)+1
source_snapshot=root/'source'
for relative,expected in manifest['source_hashes'].items():
    assert sha(relative)==expected
    assert sha(source_snapshot/relative)==expected
assert sha('audio_models/small.pt')==manifest['checkpoint_sha256']
assert read('.neural-pr/active.json')['version']==manifest['agent_policy_version']
summary['filter_analysis_summary']={k:filter_analysis[k] for k in ('nonspeech_lexical_output_removed_ids','new_nonspeech_lexical_output_ids','matching_window_count','unmatched_window_count')}
summary['coverage']=coverage
summary['experiment_counts']={'diagnostic_trials':counts,'application_recordings':len(application_events),'confirmation_cases':len({x['case_id'] for x in trials if x['phase']=='confirmation'})}
summary['explanation']=('The chosen self-attention intervention has a measurable causal effect on fixed-prefix token scores, '
    'but the prespecified unsupported-continuation hypothesis is not supported: on confirmation, the unsupported-token log probability '
    f"increased by {-summary['qualification']['mean_ns_logprob_reduction']:.6f} nats on average instead of decreasing. "
    f"Mean genuine-speech reference-token log probability fell by {summary['qualification']['mean_speech_reference_logprob_loss']:.6f} nats. "
    'Full development transcription worsened from 9/17 to 10/17 labeled non-speech lexical-output cases, while speech edits improved from 13/264 to 10/264. '
    'All five matched controls retained 9/17 non-speech lexical-output cases. No intervention produced empty genuine speech or inference errors. '
    'This is narrow causal localization of a token-score contribution, with inconclusive computational-role evidence, and a rejected repair.')
summary['limitations']+=' '+coverage['qualification']
summary['runtime_agency_status']='inconclusive; configured model API transport unavailable, no runtime-authored next proposal executed'
summary['final_audio_holdout_status']='not_evaluated_for_this_candidate; original set already consumed and never reopened by this module'
save(root/'summary.json',summary)
render(root)
appendix=f'''\n## Recorded filter and coverage audit\n\nNon-speech cases losing lexical output: `{improved}`. New non-speech lexical-output cases: `{regressed}`.\n\nAligned production windows (same seek and initial prefix): {len(matched_windows)}. Skip-decision changes: {len(filter_analysis['skip_decision_changes'])}. Unmatched windows: {len(unmatched)}; no causal comparison is inferred from diverged prefixes or seek positions. Raw per-window no-speech probabilities and average log probabilities remain separate in `filter_analysis.json`.\n\n{coverage['qualification']}\n\nDiagnostic trial counts: `{counts}`. Complete application-recording runs: {len(application_events)}. Runtime model-adapter calls both failed at the network boundary; no autonomous investigation claim is made.\n\nRe-run this accounting without new inference using `.venv/bin/python scripts/audit_mechanistic.py`. The four acceptance statuses remain independent and the original coding-task gate is unchanged.\n'''
for path in (root/'REPORT.md',Path('docs/MECHANISTIC_RESULTS.md')):path.write_text(path.read_text()+appendix)
print(summary['explanation'])
print('Counts:',summary['experiment_counts'])
