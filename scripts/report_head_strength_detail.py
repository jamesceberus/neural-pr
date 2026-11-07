"""Inspect recorded paired transitions and former partitions; never runs or selects a model."""
from pathlib import Path
import math
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from neural_pr.state import State
from whisper_repair.experiment import read,save,now

root=Path('audio_runs/mechanistic_direction_v2')
records=[e['data'] for e in State(root).events() if e['kind']=='probe_trial']
if not (root/'summary.json').exists():raise SystemExit('Experiment incomplete; no final interpretation rendered')
summary=read(root/'summary.json');numeric=read(root/'numerical_checks.json');tolerance=numeric['direction_tolerance']
head=read(root/'manifest.json')['component']['head']
strata=[]
for partition in ('discovery','confirmation'):
 for role in ('selected','matched_control'):
  for h in sorted({x['head'] for x in records if x['role']==role}):
   for scale in (0,.9,1,1.1,1.25):
    for cohort in ('unsupported_lexical','correctly_empty','genuine_speech'):
     values=[x['target_logprob_delta'] for x in records if x['status']=='ok' and x['former_partition']==partition and x['head']==h and x['scale']==scale and x['cohort']==cohort]
     if values:strata.append({'former_partition':partition,'role':role,'head':h,'scale':scale,'cohort':cohort,'n':len(values),
       'mean':statistics.mean(values),'median':statistics.median(values),'increased':sum(x>tolerance for x in values),
       'decreased':sum(x< -tolerance for x in values),'ties':sum(abs(x)<=tolerance for x in values),'probability_ratio':math.exp(statistics.mean(values))})
save(root/'stratified_diagnostics.json',strata)
case_rows=[]
ids=sorted({x['case_id'] for x in records if x['cohort']=='unsupported_lexical'})
for case_id in ids:
 selected={x['scale']:x for x in records if x['case_id']==case_id and x['head']==head}
 row={'id':case_id,'former_partition':selected[1]['former_partition'],'deltas':{str(s):selected[s]['target_logprob_delta'] for s in (0,.9,1,1.1,1.25)}}
 row['bidirectional_prediction_holds']=row['deltas']['0.9']>tolerance and row['deltas']['1.1']< -tolerance
 row['amplification_direction_persists']=row['deltas']['1.25']<row['deltas']['1.1']+tolerance
 case_rows.append(row)
save(root/'per_case_direction_test.json',case_rows)
control_summary=[]
for scale in (.9,1.1,1.25):
 selected_values=[x['target_logprob_delta'] for x in records if x['head']==head and x['scale']==scale and x['cohort']=='unsupported_lexical']
 controls=[]
 for h in sorted({x['head'] for x in records if x['role']=='matched_control'}):
  controls.append({'head':h,'mean':statistics.mean(x['target_logprob_delta'] for x in records if x['head']==h and x['scale']==scale and x['cohort']=='unsupported_lexical')})
 control_summary.append({'scale':scale,'selected_mean':statistics.mean(selected_values),'controls':controls,'control_median_mean':statistics.median(x['mean'] for x in controls)})
save(root/'matched_control_comparison.json',control_summary)
original=read(root/'original_paired_transitions.json')['conditions']
lines=['\n## Paired transitions from the rejected original edit','',
 '| Original condition | Fixed NS IDs | Regressed NS IDs | Net added failures |','| --- | --- | --- | --- |']
for name,result in original.items():lines.append(f"| {name} | {result['fixed_nonspeech_ids']} | {result['regressed_nonspeech_ids']} | {result['net_additional_failures']} |")
lines+=['','## Former partitions, separately reported','',
 'Former confirmation is development data for this new hypothesis. Separating these results exposes selection-dependent sign reversals; it does not restore freshness.',
 '', '| Former partition | Scale | NS cases | Mean Δ log p | Median Δ log p | Up / down / tie | Relative probability ratio |',
 '| --- | --- | --- | --- | --- | --- | --- |']
for x in strata:
 if x['role']=='selected' and x['cohort']=='unsupported_lexical':lines.append(f"| {x['former_partition']} | {x['scale']} | {x['n']} | {x['mean']:+.6f} | {x['median']:+.6f} | {x['increased']} / {x['decreased']} / {x['ties']} | {x['probability_ratio']:.6f} |")
lines+=['','## Per-case direction test','', '| Case | Former subset | Δ at 0 | Δ at 0.9 | Δ at 1.1 | Δ at 1.25 | Bidirectional prediction |','| --- | --- | --- | --- | --- | --- | --- |']
for x in case_rows:lines.append(f"| {x['id']} | {x['former_partition']} | {x['deltas']['0']:+.5f} | {x['deltas']['0.9']:+.5f} | {x['deltas']['1.1']:+.5f} | {x['deltas']['1.25']:+.5f} | {x['bidirectional_prediction_holds']} |")
lines+=['','## Matched-control comparison','', '| Scale | Selected mean NS Δ | Matched head means | Control median mean |','| --- | --- | --- | --- |']
for x in control_summary:lines.append(f"| {x['scale']} | {x['selected_mean']:+.6f} | {[(p['head'],round(p['mean'],6)) for p in x['controls']]} | {x['control_median_mean']:+.6f} |")
failures=[x for x in summary['application'] if x['condition'].startswith('selected_') and not x['comparison']['gate_pass']]
coherent=sum(x['bidirectional_prediction_holds'] for x in case_rows)
interpretation=f"The bidirectional fixed-token prediction holds on {coherent}/{len(case_rows)} reused non-speech probes. "
if not summary['candidate']:
 interpretation+='No amplification setting passed the unchanged full-development repair gate. The fixed-token evidence does not establish a useful repair; stop pursuing this head under this hypothesis and retain the pristine checkpoint.'
else:
 interpretation+='One amplification setting passed the development repair gate, but its evidence is exploratory. The frozen artifact remains unaccepted until new source-independent confirmation and fresh held-out recordings are available.'
lines+=['','## Qualified follow-up conclusion','',interpretation,'',
 'No claim of a dedicated detector or restraint mechanism is established. Effects on reference-token probabilities, matched controls, paired transcript transitions and filtering traces must be read together. A worsening attenuation intervention alone does not establish beneficial amplification.','',
 'Infrastructure recovery: the first supervisor inherited the coding worker’s 2 MB regular-file cap. Its partial tail and logs were preserved, complete hash-verified records were retained, and only the trusted research supervisor/source-recovery guard changed. Numerical experiment code, model, inputs, gate, scale budget and original 900-second deadline were unchanged. See `infrastructure_recovery/` and `execution_patch.json`.',
 '', 'Detailed accounting command: `.venv/bin/python scripts/report_head_strength_detail.py`.']
appendix='\n'.join(lines)+'\n'
for path in (root/'REPORT.md',Path('docs/HEAD_STRENGTH_FOLLOWUP.md')):path.write_text(path.read_text()+appendix)
save(root/'interpretation.json',{'time':now(),'direction_consistent_cases':coherent,'ns_cases':len(case_rows),'conclusion':interpretation,'fresh_confirmation':False,'fresh_holdout':False,'pristine_retained':True})
print(interpretation)
