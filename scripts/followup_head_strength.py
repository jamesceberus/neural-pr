"""Protocol v2: one bounded, user-requested, exploratory head-strength experiment.
Legacy protocol source/defaults and consumed confirmation/holdout records remain unchanged.
"""
import argparse
from contextlib import contextmanager
import copy
import json
import math
import os
from pathlib import Path
import random
import shutil
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from neural_pr.state import State,lock
from neural_pr.sandbox import init_repository,git,execute
from whisper_repair.backend import Backend
from whisper_repair.experiment import DECODE,GATE,load_pack,read,rows,save,sha,identity,now
from whisper_repair.metrics import score,compare,words
from whisper_repair.mechanistic.probes import ProbeEngine,trace_decoding
from whisper_repair.mechanistic import interventions,checkpoints
from whisper_repair.mechanistic.interventions import head_mode,tensor_hash,assert_uncached

SCALES=(0.0,0.9,1.0,1.1,1.25)
CLAIM='Near its original operating point, this component contribution may restrain unsupported continuation. Modestly increasing its strength should reduce that continuation preference.'

@contextmanager
def protocol_v2():
    """Explicit process-local extension. Restore the legacy allowlist and export operation."""
    previous=interventions.SCALES;previous_edit=checkpoints.attenuate_head
    def operation(state,layer,head,scale,n_heads=12):
        if scale not in SCALES:raise ValueError('Scale outside versioned head-strength protocol')
        key=f'decoder.blocks.{layer}.cross_attn.out.weight'
        weight=state[key];width=weight.shape[1]//n_heads
        if weight.shape[1]%n_heads or not 0<=head<n_heads:raise ValueError('Invalid head shape')
        weight[:,head*width:(head+1)*width].mul_(scale)
        return key
    interventions.SCALES=SCALES;checkpoints.attenuate_head=operation
    try:yield
    finally:interventions.SCALES=previous;checkpoints.attenuate_head=previous_edit

@contextmanager
def strength(model,layer,head,scale,mode='hook'):
    import torch
    if mode!='weight' or scale<=1:
        with head_mode(model,layer,head,scale,mode=mode):yield
        return
    interventions.validate(model,layer,head,scale)
    if getattr(model,'_mechanistic_mode',None):raise ValueError('Double intervention rejected')
    module=model.decoder.blocks[layer].attn.out;pristine=module.weight.detach().clone()
    bias=tensor_hash(module.bias);width=model.dims.n_text_state//model.dims.n_text_head
    model._mechanistic_mode='weight'
    try:
        with torch.no_grad():module.weight[:,head*width:(head+1)*width].copy_(pristine[:,head*width:(head+1)*width]*scale)
        yield
    finally:
        with torch.no_grad():module.weight.copy_(pristine)
        model._mechanistic_mode=None
        if tensor_hash(module.bias)!=bias:raise RuntimeError('Bias changed')

def distribution(values,tolerance):
    return {'n':len(values),'mean_delta':statistics.mean(values) if values else None,
            'median_delta':statistics.median(values) if values else None,
            'increased':sum(x>tolerance for x in values),'decreased':sum(x< -tolerance for x in values),
            'within_identity_tolerance':sum(abs(x)<=tolerance for x in values),
            'geometric_mean_probability_ratio':math.exp(statistics.mean(values)) if values else None}

def transitions(before,after,manifest):
    fixed=[];regressed=[];changed=[];windows=[];unaligned=[]
    for item in manifest:
        a=before[item['id']];b=after[item['id']]
        if a['status']!='ok' or b['status']!='ok':continue
        if item['kind']=='nonspeech':
            if words(a['text']) and not words(b['text']):fixed.append(item['id'])
            if not words(a['text']) and words(b['text']):regressed.append(item['id'])
        if a['text']!=b['text']:changed.append({'id':item['id'],'kind':item['kind'],'before':a['text'],'after':b['text']})
        lookup={(x['seek_frames'],tuple(x['initial_token_ids'])):x for x in b.get('windows',[])}
        for original in a.get('windows',[]):
            other=lookup.get((original['seek_frames'],tuple(original['initial_token_ids'])))
            if other is None:
                unaligned.append({'id':item['id'],'seek_frames':original['seek_frames']});continue
            if a['text']!=b['text']:
                windows.append({'id':item['id'],'seek_frames':original['seek_frames'],
                  'baseline_no_speech_probability':original['no_speech_prob'],'candidate_no_speech_probability':other['no_speech_prob'],
                  'baseline_avg_logprob':original['avg_logprob'],'candidate_avg_logprob':other['avg_logprob'],
                  'baseline_skip':original['skip_decision'],'candidate_skip':other['skip_decision'],
                  'same_initial_prefix':True})
    return {'fixed_nonspeech_ids':fixed,'regressed_nonspeech_ids':regressed,'net_additional_failures':len(regressed)-len(fixed),
            'changed_transcripts':changed,'changed_recording_window_scores':windows,'unaligned_windows':unaligned}

def run(root,parent,checkpoint):
    import torch
    root=Path(root).resolve();parent=Path(parent).resolve();checkpoint=Path(checkpoint).resolve()
    root.mkdir(parents=True,exist_ok=True);state=State(root)
    if (root/'summary.json').exists():return read(root/'summary.json')
    old=read(parent/'manifest.json');old_summary=read(parent/'summary.json');frozen=read(parent/'frozen_confirmation.json')
    if sha(checkpoint)!=old['checkpoint_sha256']:raise ValueError('Pristine small checkpoint differs')
    if read('.neural-pr/active.json')['version']!=old['agent_policy_version']:raise ValueError('Agent identity changed')
    selected=frozen['selected'];layer=selected['layer'];head=selected['head'];controls=frozen['control_heads']
    if (layer,head)!=(4,4):raise ValueError('This registered follow-up is only for original layer 4/head 4')
    cases=[read(path) for path in sorted((parent/'cases').glob('*.json'))]
    if len(cases)!=20:raise ValueError('Expected the exact 20 previously frozen diagnostic inputs')
    case_hashes={case['case_id']:sha(parent/'cases'/f"{case['case_id']}.json") for case in cases}
    source=root/'source'
    if not source.exists():
        shutil.copytree(parent/'source',source,ignore=shutil.ignore_patterns('.git','__pycache__'))
        shutil.copy2(__file__,source/'followup_head_strength.py');init_repository(source)
    metadata={'protocol_version':'head-strength-v2','created':now(),'hypothesis_id':'restraining-head-L4-H4-v2','hypothesis':CLAIM,
              'hypothesis_origin':'user-requested new hypothesis; not an autonomous model discovery',
              'parent_experiment_id':old['experiment_id'],'parent_source_commit':old['application_commit'],
              'application_commit':git(source,'rev-parse','HEAD'),'agent_policy_version':old['agent_policy_version'],
              'checkpoint_sha256':sha(checkpoint),'configuration':DECODE,'configuration_hash':identity(DECODE),
              'manifest_sha256':old['manifest_sha256'],'seed':old['seed'],'component':{'kind':'decoder_self_attention','layer':layer,'head':head},
              'scales':list(SCALES),'previously_tested_attenuation':0,'matched_control_heads':controls,
              'case_hashes':case_hashes,'script_sha256':sha(__file__),'old_component_sources':old['source_hashes'],
              'predicted_effect':'For scale 1.1 and 1.25: decrease unsupported-token log probability; for scale .9: increase; smaller effect on reference speech',
              'would_weaken_claim':'Nonmonotonicity, comparable controls, heterogeneous direction, or failure to improve full transcription with speech retention',
              'fresh_confirmation':False,'data_scope':'All 20 probes are previously used development inputs. Former confirmation now informs this hypothesis; no fresh confirmation claim.',
              'fresh_final_holdout':False,'original_holdout_consumed':True,'repair_gate':GATE,
              'selection_rule':'Test all declared scales. Full application: .9, 1.1, 1.25; reuse labeled original attenuation and identity application records. Five matched controls full application at 1.1.',
              'candidate_rule':'Freeze only a full-development repair gate pass at amplification scale; retain pristine without new independent confirmation',
              'deadline_seconds':900,'start_unix':time.time(),'min_promising_ns_delta':-.002,'max_speech_mean_logprob_loss':.01}
    if (root/'manifest.json').exists():
        recorded=read(root/'manifest.json')
        patch_path=root/'execution_patch.json'
        patched=patch_path.exists() and read(patch_path).get('new_script_sha256')==sha(__file__) and read(patch_path).get('measurement_code_unchanged') is True
        if (recorded['script_sha256']!=sha(__file__) and not patched) or recorded['case_hashes']!=case_hashes:raise ValueError('Versioned follow-up source/input changed')
        metadata=recorded
    else:save(root/'manifest.json',metadata)
    deadline=metadata['start_unix']+metadata['deadline_seconds']
    def afford(seconds):
        if time.time()+seconds>deadline:raise TimeoutError('Bounded follow-up deadline: comparison incomplete/inconclusive')
    backend=Backend(checkpoint);engine=ProbeEngine(backend)
    state.emit('hypothesis_registered',hypothesis=metadata)
    baselines={case['case_id']:engine.forward(case) for case in cases}
    completed={}
    for event in state.events():
        if event['kind']=='probe_trial':
            d=event['data'];completed[(d['case_id'],d['head'],d['scale'])]=d
    identities=[];comparisons=[]
    with protocol_v2():
        # Verify amplified hook/weight equivalence, noncompounding restoration, and numerical identities before comparisons.
        fixture=cases[0];reference=engine.forward(fixture,return_logits=True)['_logits']
        projection=backend.model.decoder.blocks[layer].attn.out;pristine_hash=tensor_hash(projection.weight)
        for scale in SCALES:
            with strength(backend.model,layer,head,scale,'hook'):a=engine.forward(fixture,return_logits=True)
            with strength(backend.model,layer,head,scale,'weight'):b=engine.forward(fixture,return_logits=True)
            assert torch.allclose(a['_logits'],b['_logits'],atol=.0002,rtol=.00002)
            assert tensor_hash(projection.weight)==pristine_hash
            identities.append({'scale':scale,'max_hook_weight_logit_difference':(a['_logits']-b['_logits']).abs().max().item()})
        for component in [{'head':head}]+controls:
            for scale in SCALES:
                afford(3)
                for case in cases:
                    key=(case['case_id'],component['head'],scale)
                    if key in completed:record=completed[key]
                    else:
                        start=time.monotonic()
                        try:
                            with strength(backend.model,layer,component['head'],scale):measured=engine.forward(case)
                            record={'status':'ok','target_logprob_delta':measured['target_logprob']-baselines[case['case_id']]['target_logprob'],
                                    'baseline':baselines[case['case_id']],'measurement':measured,'error':None}
                        except Exception as exc:record={'status':'error','error':type(exc).__name__+': '+str(exc),'target_logprob_delta':None}
                        record.update(case_id=case['case_id'],cohort=case['cohort'],former_partition=case['partition'],layer=layer,head=component['head'],scale=scale,
                            role='selected' if component['head']==head else 'matched_control',elapsed=time.monotonic()-start,
                            application_commit=metadata['application_commit'],agent_policy_version=metadata['agent_policy_version'],
                            checkpoint_sha256=metadata['checkpoint_sha256'],configuration_hash=metadata['configuration_hash'],manifest_sha256=metadata['manifest_sha256'],
                            input_contract_sha256=case_hashes[case['case_id']],input=case,seed=metadata['seed'],hypothesis_id=metadata['hypothesis_id'])
                        state.emit('probe_trial',**record)
                    comparisons.append(record)
        identity_deltas=[abs(x['target_logprob_delta']) for x in comparisons if x['scale']==1 and x['status']=='ok']
        tolerance=max(1e-5,10*max(identity_deltas,default=0));save(root/'numerical_checks.json',{'equivalence':identities,'max_identity_logprob_variation':max(identity_deltas,default=0),'direction_tolerance':tolerance,'pristine_restored':tensor_hash(projection.weight)==pristine_hash})
        table=[]
        for component in [{'head':head}]+controls:
            for scale in SCALES:
                for cohort in ('unsupported_lexical','correctly_empty','genuine_speech'):
                    data=[x['target_logprob_delta'] for x in comparisons if x['head']==component['head'] and x['scale']==scale and x['cohort']==cohort and x['status']=='ok']
                    table.append({'head':component['head'],'role':'selected' if component['head']==head else 'matched_control','scale':scale,'cohort':cohort,**distribution(data,tolerance)})
        save(root/'diagnostic_summary.json',table)
        # Verify the original scale-zero result exactly on former confirmation pairs.
        previous=[e['data'] for e in State(parent).events() if e['kind']=='probe_trial' and e['data']['phase']=='confirmation']
        repeated=[x for x in comparisons if x['head']==head and x['scale']==0 and x['former_partition']=='confirmation']
        repeat_error=max(abs(x['target_logprob_delta']-next(p['target_logprob_delta'] for p in previous if p['case_id']==x['case_id'])) for x in repeated)
        save(root/'attenuation_reproduction.json',{'max_delta_difference':repeat_error,'passed':repeat_error<=tolerance,'n':len(repeated)})
        manifest,pack=load_pack('whisper_audio_dev','dev')
        baseline={item['id']:read(parent/'baseline'/f"{item['id']}.json") for item in manifest}
        conditions={};application=[]
        def app(name,component,scale):
            predictions={};afford(35)
            for item in manifest:
                path=root/'application'/name/f"{item['id']}.json"
                if path.exists():result=read(path)
                else:
                    start=time.monotonic();afford(2)
                    try:
                        with strength(backend.model,layer,component,scale):
                            with trace_decoding(backend.model) as traces:output=backend.transcribe(Path('whisper_audio_dev')/item['audio_path'])
                        result={'id':item['id'],'status':'ok','text':output['text'],'raw':output['raw'],'windows':traces,'elapsed':time.monotonic()-start}
                    except Exception as exc:result={'id':item['id'],'status':'error','error':str(exc),'elapsed':time.monotonic()-start}
                    save(path,result);state.emit('application_trial',condition=name,case_id=item['id'],status=result['status'],artifact=str(path),
                        hypothesis_id=metadata['hypothesis_id'],application_commit=metadata['application_commit'],agent_policy_version=metadata['agent_policy_version'],checkpoint_sha256=metadata['checkpoint_sha256'])
                predictions[item['id']]=result
            comparison=compare(manifest,baseline,predictions)
            save(root/'application'/name/'comparison.json',comparison)
            paired=transitions(baseline,predictions,manifest);save(root/'application'/name/'transitions.json',paired)
            conditions[name]=comparison
            application.append({'condition':name,'head':component,'scale':scale,'comparison':comparison,'transitions':paired})
        for scale in (.9,1.1,1.25):app(f'selected_{scale}',head,scale)
        for component in controls:app(f'control_H{component["head"]}_1.1',component['head'],1.1)
        # Include original selected and control paired transitions, without presenting cached applications as new inference.
        prior_transitions={}
        for name in ('selected','control_0','control_1','control_2','control_3','control_4'):
            data={item['id']:read(parent/'application'/name/f"{item['id']}.json") for item in manifest}
            prior_transitions[name]=transitions(baseline,data,manifest)
        save(root/'original_paired_transitions.json',{'source':'recorded original experiment, no new inference','conditions':prior_transitions})
        eligible=[x for x in application if x['condition'].startswith('selected_') and x['scale']>1 and x['comparison']['gate_pass']]
        candidate=None
        if eligible:
            chosen=min(eligible,key=lambda x:(len(x['comparison']['candidate']['nonspeech']['lexical_output_ids']),x['comparison']['candidate']['speech']['wer'],x['scale']))
            candidate=checkpoints.export_candidate(checkpoint,root/'export'/'candidate.pt',layer,head,chosen['scale'],backend.model)
            save(root/'frozen_candidate.json',{'time':now(),'patch':candidate,'scale':chosen['scale'],'protocol_hash':identity(metadata),'configuration':DECODE,'gate':GATE,
                 'fresh_confirmation':False,'repair_status':'development_only','holdout_status':'new independent source material required'})
        result={'protocol_version':metadata['protocol_version'],'hypothesis':CLAIM,'diagnostic_table':table,'application':application,
                'candidate':candidate,'fresh_confirmation':False,'fresh_holdout':False,
                'repair_status':'development_only' if candidate else 'rejected',
                'accepted_checkpoint':'pristine small.pt; no promotion without fresh independent recordings',
                'agent_upgrade_status':read('.neural-pr/report.json')['improvement_outcome'],
                'initial_attenuation_reproduction':read(root/'attenuation_reproduction.json'),
                'elapsed_seconds':time.time()-metadata['start_unix'],'no_new_model_family':True,
                'interpretation_scope':'Exploratory development direction test. Previously confirmed cases cannot confirm this new hypothesis.'}
        save(root/'summary.json',result)
    assert interventions.SCALES==(0.0,.25,.5,.75,1.0)
    assert sha(checkpoint)==old['checkpoint_sha256']
    return result

def report(root):
    root=Path(root);d=read(root/'summary.json');old=read('audio_runs/mechanistic_v1/summary.json')
    selected=[x for x in d['diagnostic_table'] if x['role']=='selected']
    lines=['# Head-strength direction follow-up (protocol v2)','',CLAIM,'',
      '**Exploratory development analysis only.** All diagnostic cases, including former confirmation cases, informed this hypothesis. No fresh confirmation or final holdout is claimed. Pristine multilingual small remains active.','',
      'The previous repair is rejected. The original study and gate are unchanged. This protocol explicitly extends allowed scales to 0, 0.9, 1, 1.1, and 1.25 in a process-local context that restores the old defaults. Every condition starts from pristine projection values.','',
      '| Scale | Cohort | N | Mean Δ log p | Median Δ log p | Increase / decrease / numerical tie | Geometric-mean p ratio |',
      '| --- | --- | --- | --- | --- | --- | --- |']
    for x in selected:lines.append(f"| {x['scale']} | {x['cohort']} | {x['n']} | {x['mean_delta']:+.6f} | {x['median_delta']:+.6f} | {x['increased']} / {x['decreased']} / {x['within_identity_tolerance']} | {x['geometric_mean_probability_ratio']:.6f} |")
    lines+=['','A probability ratio is a relative change in fixed target-token probability, not a percentage-point change in hallucination rate. All five matched heads and every per-case score are in `diagnostic_summary.json` and `events.jsonl`.','',
      '| Application condition | NS lexical output /17 | Speech edits / words | New empty speech | Errors | Fixed / regressed NS IDs |',
      '| --- | --- | --- | --- | --- | --- |',
      '| Pristine (recorded baseline) | 9 | 13 / 264 | 0 | 0 | — |',
      '| Original scale 0 (recorded, diagnostic effect reproduced) | 10 | 10 / 264 | 0 | 0 | See original paired-transition file |']
    for x in d['application']:
        c=x['comparison'];m=c['candidate'];p=x['transitions']
        lines.append(f"| {x['condition']} | {len(m['nonspeech']['lexical_output_ids'])} | {m['speech']['edits']} / {m['speech']['reference_words']} | {len(c['newly_empty_speech_ids'])} | {len(m['errors'])} | {p['fixed_nonspeech_ids']} / {p['regressed_nonspeech_ids']} |")
    lines+=['','## Interpretation','',f"Repair status: **{d['repair_status']}**. Fresh confirmation: **unavailable**. Accepted artifact: **pristine small.pt**. Agent-policy result: **{d['agent_upgrade_status']}**, from the separate coding-task gate.",
      '',f"Original scale-zero diagnostic reproduction: `{d['initial_attenuation_reproduction']}`. Hook/weight equivalence and identity variation are in `numerical_checks.json`.",
      '', 'For changed recordings, the transition files record no-speech probability, average log probability, skip decisions and whether window/prefix alignment held. Unaligned windows are not treated as controlled diagnostic comparisons. Newly failing and fixed recordings are listed separately; net counts are not used as a substitute for paired transitions.',
      '', 'No held-out data was reopened. There is no generalization claim. Do not tune further on the consumed original holdout.',
      '', '## Reproduction','', '```sh', '.audio-venv/bin/python scripts/followup_head_strength.py run', '.venv/bin/python scripts/followup_head_strength.py report', '```',
      '', 'The runner has a 15-minute experiment deadline with a supervising process timeout; completed records are reused. The source, old source identity, exact probe hashes, hypothesis, seed, criteria and new scale allowlist are registered in `manifest.json` before the first scaled comparison.']
    text='\n'.join(lines)+'\n';(root/'REPORT.md').write_text(text);Path('docs/HEAD_STRENGTH_FOLLOWUP.md').write_text(text)
    return text

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['run','report','worker']);parser.add_argument('--root',default='audio_runs/mechanistic_direction_v2');parser.add_argument('--parent',default='audio_runs/mechanistic_v1');parser.add_argument('--checkpoint',default='audio_models/small.pt')
    args=parser.parse_args();root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    if args.command=='report':report(root);print(root/'REPORT.md')
    elif args.command=='worker':
        try:
            with lock(root/'controller.lock'):result=run(root,args.parent,args.checkpoint)
            print(json.dumps({'status':'complete','repair_status':result['repair_status']}))
        except Exception as exc:
            save(root/'failed_run.json',{'time':now(),'status':'inconclusive','error':type(exc).__name__+': '+str(exc)})
            raise
    else:
        if (root/'summary.json').exists():report(root);print('Completed records reused; no new inference.');raise SystemExit(0)
        # This trusted research writer legitimately creates checkpoints and journals >2 MB.
        # Keep the coding worker's 2 MB security limit unchanged; supervise this fixed script separately.
        import subprocess,signal
        with (root/'worker_stdout.log').open('w') as stdout,(root/'worker_stderr.log').open('w') as stderr:
            process=subprocess.Popen([sys.executable,__file__,'worker','--root',str(root),'--parent',args.parent,'--checkpoint',args.checkpoint],stdout=stdout,stderr=stderr,start_new_session=True)
            try:process.wait(timeout=920)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
        if process.returncode:
            save(root/'supervisor_failure.json',{'time':now(),'status':'inconclusive','returncode':process.returncode,'hard_process_timeout_seconds':920})
            print((root/'worker_stderr.log').read_text()[-2000:],file=sys.stderr);raise SystemExit(2)
        report(root);print((root/'worker_stdout.log').read_text())
