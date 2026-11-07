"""A bounded extension of the existing loader/evaluator, not a second agent framework."""
from dataclasses import asdict
from pathlib import Path
import gc
import hashlib
import json
import random
import shutil
import statistics
import time
import uuid

from neural_pr.state import State,lock
from neural_pr.sandbox import init_repository,git
from whisper_repair.backend import Backend
from whisper_repair.experiment import Experiment,DECODE,GATE,OFFICIAL_SMALL_SHA256,load_pack,read,rows,save,sha,identity,now
from whisper_repair.metrics import words,score,compare
from .probes import ProbeEngine,trace_decoding,build_case
from .interventions import head_mode,tensor_hash,validate,assert_uncached
from .checkpoints import export_candidate
from .evidence import Evidence,CRITERIA,qualify,render
from .investigator import Investigator

DEFAULT_ROOT='audio_runs/mechanistic_v1'
SEED=1729
CLAIM='A decoder component contributes to unsupported continuation when acoustic evidence is weak. Attenuating its output reduces preference for that continuation, with a smaller effect on genuine speech.'

def component_hashes():
    base=Path(__file__).resolve().parents[2]
    return {str(p.relative_to(base)):sha(p) for directory in ('whisper_repair','neural_pr') for p in sorted((base/directory).rglob('*.py'))}

def source_group(item):
    if item['id'].startswith('whisper_synthetic_5'):return 'github1873_synthetic_5_family'
    return item.get('source_recording_id') or item.get('upstream_source_url') or item['id']

class Investigation:
    def __init__(self,root=DEFAULT_ROOT,checkpoint='audio_models/small.pt',dev='whisper_audio_dev'):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.checkpoint=Path(checkpoint).resolve();self.dev=Path(dev).resolve()
        self.evidence=Evidence(self.root);self.state=self.evidence.state
        self.backend=None;self.engine=None
    def load(self):
        if self.backend is None:self.backend=Backend(self.checkpoint);self.engine=ProbeEngine(self.backend)
        return self.backend
    def check_manifest(self):
        manifest=read(self.root/'manifest.json')
        if manifest['source_hashes']!=component_hashes():raise RuntimeError('Source changed after protocol freeze; preserve this run and use a new --root')
        if sha(self.checkpoint)!=manifest['checkpoint_sha256']:raise RuntimeError('Pristine checkpoint mismatch')
        if read('.neural-pr/active.json')['version']!=manifest['agent_policy_version']:raise RuntimeError('Pinned agent version changed')
        return manifest
    def provenance(self):
        m=read(self.root/'manifest.json')
        return {key:m[key] for key in ('experiment_id','application_commit','agent_policy_version','checkpoint_sha256','configuration_hash','manifest_sha256','seed')}
    def prepare(self):
        if (self.root/'prepared.json').exists():self.check_manifest();return read(self.root/'prepared.json')
        if sha(self.checkpoint)!=OFFICIAL_SMALL_SHA256:raise ValueError('Use the original already-selected multilingual small checkpoint')
        manifest,pack=load_pack(self.dev,'dev')
        discovery=['one_minute_silence','audioset_audioset_0000893','audioset_audioset_0000900','audioset_audioset_0000905',
                   'audioset_audioset_0000896','audioset_audioset_0000899','audioset_audioset_0000901','audioset_audioset_0000903',
                   '2277-149896-0000','2277-149896-0001','5338-24640-0001','5338-24640-0002']
        confirmation=['whisper_synthetic_5','whisper_synthetic_5_2','audioset_audioset_0000911','audioset_audioset_0000912','audioset_audioset_0000914',
                      '84-121550-0009','84-121550-0010','84-121550-0011','84-121550-0012']
        by_id={x['id']:x for x in manifest}
        if {source_group(by_id[x]) for x in discovery}&{source_group(by_id[x]) for x in confirmation}:raise ValueError('Source-group leakage between discovery and confirmation')
        source=self.root/'source'
        if not source.exists():
            source.mkdir()
            for relative in component_hashes():
                p=source/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(relative,p)
            (source/'mechanistic_interpretability.md').write_text(Path('docs/mechanistic_interpretability.md').read_text())
            init_repository(source)
        app_commit=git(source,'rev-parse','HEAD')
        active=read('.neural-pr/active.json')['version']
        record={'experiment_id':self.root.name,'created':now(),'application_commit':app_commit,
                'application_commit_scope':'Isolated source snapshot using existing Git checkpoint helper; root .git writes unavailable',
                'agent_policy_version':active,'checkpoint_identifier':'openai-whisper/small multilingual',
                'checkpoint_sha256':sha(self.checkpoint),'configuration':DECODE,'configuration_hash':identity(DECODE),
                'manifest_sha256':pack['manifest_sha256'],'manifest':pack['manifest'],'seed':SEED,
                'source_hashes':component_hashes(),'discovery_ids':discovery,'confirmation_ids':confirmation,
                'source_groups':{x['id']:source_group(x) for x in manifest},'criteria':CRITERIA,'repair_gate':GATE,
                'budget':{'discovery_case_limit':12,'coarse_heads':24,'shortlist':3,'scales':[0,.25,.5,.75,1],
                          'full_application_finalists':1,'matched_controls':5,'search_seconds':600,'hard_search_max_seconds':1800},
                'hypothesis':CLAIM,'predicted_direction':'decrease_target_logprob_when_attenuated',
                'would_weaken_claim':'Similar speech suppression, comparable controls, filter-only changes, or failure to repeat on confirmation',
                'prior_exposure':'All development cases were used in an earlier cross-attention experiment; confirmation is prospective only for this self-attention selection.',
                'holdout_status':'original audio holdout already consumed; no new final evaluation permitted',
                'missing_control_coverage':'No new short/quiet genuine-speech recordings in development. Original short-phrase holdout remains excluded.'}
        if (self.root/'manifest.json').exists() and read(self.root/'manifest.json')!=record:
            # Resume an interrupted preparation from the original frozen protocol rather than changing its timestamps.
            record=self.check_manifest()
        else:save(self.root/'manifest.json',record)
        self.evidence.emit('protocol_frozen',{'manifest_hash':identity(record),**self.provenance()})
        backend=self.load();save(self.root/'dimensions.json',asdict(backend.model.dims))
        installed=Path(__import__('whisper').__file__).parent
        save(self.root/'installed_source.json',{'files':{name:sha(installed/name) for name in ('model.py','decoding.py','transcribe.py','tokenizer.py')},
               'inspection':'qkv_attention permutes batch/head/token/dim to batch/token/head/dim then flattens; attn.out input is contiguous concatenated heads',
               'head_output_shape':[1,'prefix_length',backend.model.dims.n_text_state],
               'versions':read('audio_runs/runtime_identity.json')['versions']})
        baseline={};traces={}
        previous={x['id']:x for x in rows('audio_runs/baseline_development/raw.jsonl')}
        for item in manifest:
            path=self.root/'baseline'/f"{item['id']}.json"
            if path.exists():saved=read(path)
            else:
                started=time.monotonic()
                with trace_decoding(backend.model,self.root/'windows'/item['id']) as windows:output=backend.transcribe(self.dev/item['audio_path'])
                saved={'id':item['id'],'status':'ok','text':output['text'],'raw':output['raw'],'audio_stats':output['audio_stats'],
                       'windows':windows,'elapsed':time.monotonic()-started,'matches_existing_baseline_text':output['text']==previous[item['id']]['text']}
                save(path,saved)
                self.evidence.emit('application_baseline',{'case_id':item['id'],'status':'ok','text':output['text'],'artifact':str(path),**self.provenance()})
            baseline[item['id']]=saved;traces[item['id']]=saved['windows']
        if not all(x['matches_existing_baseline_text'] for x in baseline.values()):raise RuntimeError('Instrumented baseline changes transcript; stop investigation')
        save(self.root/'baseline_metrics.json',score(manifest,baseline))
        default_token=None;case_ids=[]
        for case_id in discovery:
            item=by_id[case_id];cohort='genuine_speech' if item['kind']=='speech' else 'unsupported_lexical' if words(baseline[case_id]['text']) else 'correctly_empty'
            case=build_case(item,traces[case_id],backend.model,cohort,'discovery',default_token)
            if default_token is None:default_token=case['target_token_id']
            case.update(source_group=source_group(item),manifest_sha256=pack['manifest_sha256'])
            save(self.root/'cases'/f'{case_id}.json',case);case_ids.append(case_id)
        prepared={'discovery_ids':case_ids,'default_unsupported_token':default_token,'baseline_metrics':score(manifest,baseline),
                  'baseline_observation_transcripts_identical':True,'confirmation_not_probed':True}
        save(self.root/'prepared.json',prepared)
        return prepared
    def case(self,case_id):return read(self.root/'cases'/f'{case_id}.json')
    def measure(self,case,layer,head,scale,phase,baseline=None,mode='hook'):
        self.load();validate(self.backend.model,layer,head,scale)
        key=(phase,case['case_id'],layer,head,scale)
        for record in self.evidence.trials():
            if (record['phase'],record['case_id'],record['layer'],record['head'],record['scale'])==key:return record
        baseline=baseline or self.engine.forward(case)
        hypothesis_id=f"{phase}-L{layer}-H{head}-S{scale}"
        hypothesis={'hypothesis_id':hypothesis_id,'parent_experiment_id':self.root.name,'claim':CLAIM,
                    'predicted_direction':'decrease_target_logprob_when_attenuated','alternative':'general_suppression_of_transcription',
                    'component':{'kind':'decoder_self_attention','layer':layer,'head':head},'position_scope':'all_prefix_positions',
                    'discovery_case_ids':read(self.root/'manifest.json')['discovery_ids'],
                    'control_case_ids':[case['case_id']] if case['cohort']!='unsupported_lexical' else [],
                    'control_head_ids':self.state.read('frozen_confirmation',{}).get('control_heads',[]),
                    'intervention':{'kind':'head_scale','scale':scale},'would_weaken_claim':'Comparable effects on genuine speech/control heads or no confirmation repeat'}
        path=self.root/'hypotheses'/f'{hypothesis_id}.json'
        if not path.exists():save(path,hypothesis)
        started=time.monotonic()
        try:
            changed=self.engine.forward(case,{'layer':layer,'head':head,'scale':scale,'mode':mode})
            record={'status':'ok','baseline':baseline,'intervention_measurement':changed,
                    'target_logprob_delta':changed['target_logprob']-baseline['target_logprob'],
                    'no_speech_probability_delta':changed['no_speech_probability_at_sot']-baseline['no_speech_probability_at_sot'],
                    'raw_margin_delta':changed['raw_target_eot_margin']-baseline['raw_target_eot_margin'],'error':None}
        except Exception as exc:record={'status':'error','error':type(exc).__name__+': '+str(exc),'target_logprob_delta':None}
        record.update(phase=phase,case_id=case['case_id'],cohort=case['cohort'],source_group=case['source_group'],
                      layer=layer,head=head,scale=scale,position_scope='all_prefix_positions',hypothesis_id=hypothesis_id,
                      hypothesis_hash=identity(hypothesis),elapsed=time.monotonic()-started,
                      input={'prefix_token_ids':case['prefix_token_ids'],'target_position':case['target_position'],
                             'target_token_id':case['target_token_id'],'sot_position':case['sot_position'],'window':case['window'],
                             'manifest_record':case['manifest_record']},**self.provenance())
        self.evidence.emit('probe_trial',record)
        return record
    def verify(self,case,layer=0,head=0):
        import torch
        self.load();model=self.backend.model
        base=self.engine.forward(case,return_logits=True);reference=base.pop('_logits');captures=[]
        checks={};variation=[]
        for mode in ('capture','noop','hook'):
            with head_mode(model,layer,head,1,mode=mode,capture=captures):result=self.engine.forward(case,return_logits=True)
            logits=result.pop('_logits');error=(reference-logits).abs().max().item()
            checks[mode+'_identity']={'passed':bool(torch.allclose(reference,logits,atol=CRITERIA['logits_atol'],rtol=CRITERIA['logits_rtol'])),'max_logit_difference':error}
            variation.append(abs(base['target_logprob']-result['target_logprob']))
        module=model.decoder.blocks[layer].attn.out;parent=tensor_hash(module.weight)
        for scale in (0,.25,.5,.75,1):
            hook=self.engine.forward(case,{'layer':layer,'head':head,'scale':scale,'mode':'hook'},return_logits=True)
            weight=self.engine.forward(case,{'layer':layer,'head':head,'scale':scale,'mode':'weight'},return_logits=True)
            a=hook.pop('_logits');b=weight.pop('_logits')
            checks['equivalence_'+str(scale)]={'passed':bool(torch.allclose(a,b,atol=CRITERIA['logits_atol'],rtol=CRITERIA['logits_rtol'])),
                                               'max_logit_difference':(a-b).abs().max().item()}
            if tensor_hash(module.weight)!=parent:raise RuntimeError('Candidate state leaked after equivalence test')
        checks['double_mode_rejected']={'passed':False}
        try:
            with head_mode(model,layer,head,.5,mode='weight'):
                with head_mode(model,layer,head,.5,mode='hook'):pass
        except ValueError:checks['double_mode_rejected']={'passed':True}
        try:
            with head_mode(model,layer,head,.25,mode='weight'):raise RuntimeError('synthetic exception control')
        except RuntimeError:pass
        restored=self.engine.forward(case,return_logits=True).pop('_logits')
        checks['exception_rollback']={'passed':tensor_hash(module.weight)==parent and bool(torch.equal(restored,reference))}
        tokens=torch.tensor([case['prefix_token_ids']]);features=self.engine.encode(case)
        with torch.inference_mode():direct=model.decoder(tokens,features,kv_cache=None)
        checks['target_alignment']={'passed':direct[0,case['target_position'],case['target_token_id']].item()==base['target_logit']}
        no_speech_id=self.engine.task(case).tokenizer.no_speech
        checks['sot_alignment']={'passed':direct[0,case['sot_position']].softmax(-1)[no_speech_id].item()==base['no_speech_probability_at_sot']}
        fixture=Path(case['manifest_record']['audio_path']);audio=self.dev/fixture
        plain=self.backend.transcribe(audio)['text']
        for mode in ('capture','noop','hook'):
            with head_mode(model,layer,head,1,mode=mode):text=self.backend.transcribe(audio)['text']
            checks[mode+'_transcript_identity']={'passed':text==plain}
        checks['all_passed']=all(x['passed'] for x in checks.values())
        checks['numerical_logprob_variation']=max(variation)
        save(self.root/'verification.json',checks)
        return checks
    def _deadline(self):
        clock=self.state.read('search_clock')
        return clock['deadline_unix'] if clock else float('inf')
    def _afford(self,seconds):
        if time.time()+seconds>self._deadline():raise TimeoutError('Comparison exceeds remaining development budget; preserve incomplete/inconclusive evidence')
    def _rank(self,records):
        good=[x for x in records if x['status']=='ok']
        if len(good)!=len(read(self.root/'manifest.json')['discovery_ids']):return float('-inf')
        means={cohort:statistics.mean(x['target_logprob_delta'] for x in good if x['cohort']==cohort)
               for cohort in ('unsupported_lexical','correctly_empty','genuine_speech')}
        return -means['unsupported_lexical']-max(0,-means['genuine_speech'])-.25*max(0,-means['correctly_empty'])
    def transcribe_condition(self,name,layer=None,head=None,scale=1):
        manifest,pack=load_pack(self.dev,'dev');predictions={};self.load()
        for item in manifest:
            path=self.root/'application'/name/f"{item['id']}.json"
            if path.exists():result=read(path)
            else:
                started=time.monotonic()
                try:
                    self._afford(3)
                    if layer is None:
                        with trace_decoding(self.backend.model) as windows:result=self.backend.transcribe(self.dev/item['audio_path'])
                    else:
                        with head_mode(self.backend.model,layer,head,scale,mode='hook'):
                            with trace_decoding(self.backend.model) as windows:result=self.backend.transcribe(self.dev/item['audio_path'])
                    result.update(status='ok',id=item['id'],windows=windows)
                except Exception as exc:result={'id':item['id'],'status':'error','error':type(exc).__name__+': '+str(exc)}
                result['elapsed']=time.monotonic()-started;save(path,result)
                self.evidence.emit('application_trial',{'condition':name,'case_id':item['id'],'status':result['status'],
                    'artifact':str(path),'intervention':{'layer':layer,'head':head,'scale':scale},**self.provenance()})
            predictions[item['id']]=result
        baseline={item['id']:read(self.root/'baseline'/f"{item['id']}.json") for item in manifest}
        comparison=compare(manifest,baseline,predictions);save(self.root/'application'/name/'comparison.json',comparison)
        return comparison
    def investigate(self):
        manifest=self.check_manifest();self.load()
        if (self.root/'summary.json').exists():return read(self.root/'summary.json')
        if not self.state.read('search_clock'):
            self.state.write('search_clock',{'start_unix':time.time(),'deadline_unix':time.time()+manifest['budget']['search_seconds'],'time':now()})
        discovery=[self.case(x) for x in manifest['discovery_ids']]
        randomizer=random.Random(SEED)
        heads=[(layer,head) for layer in range(self.backend.model.dims.n_text_layer)
               for head in randomizer.sample(range(self.backend.model.dims.n_text_head),2)]
        save(self.root/'coarse_plan.json',{'heads':heads,'scale':.5,'seed':SEED,'selection':'seed-fixed engineering sweep, not an autonomous discovery'})
        baselines={};calibration=[]
        import torch
        for case in discovery:
            started=time.monotonic()
            result=self.engine.forward(case,capture_heads=heads)
            activations=result.pop('_activations')
            path=self.root/'activations'/f"{case['case_id']}.pt";path.parent.mkdir(exist_ok=True)
            torch.save(activations,path)
            save(self.root/'diagnostic_baselines'/f"{case['case_id']}.json",dict(result,activation_artifact=str(path),activation_sha256=sha(path)))
            baselines[case['case_id']]=result;calibration.append(time.monotonic()-started)
        cost=max(statistics.mean(calibration),.01)
        save(self.root/'calibration.json',{'seconds_per_case_including_encoder_and_capture':cost,
                                         'predicted_coarse_seconds':cost*len(heads)*len(discovery),'measured_cases':len(calibration),
                                         'feature_cache':'encoder features reused; decoder KV cache always None','before_search':True})
        self._afford(cost*len(heads)*len(discovery)+180)
        verification=self.verify(discovery[0])
        if not verification['all_passed']:raise RuntimeError('Identity/alignment/equivalence checks failed; do not search')
        investigator=Investigator(self.root)
        public_summary={'case_ids':manifest['discovery_ids'],'cohorts':{x['case_id']:x['cohort'] for x in discovery},
                        'baseline_scores':{key:value['target_logprob'] for key,value in baselines.items()},'declared_coarse_heads':heads,
                        'criteria':CRITERIA,'no_confirmation_or_holdout_inputs':True}
        def request_probe(case_id,layer,head,scale):
            if case_id not in manifest['discovery_ids'] or (layer,head) not in heads or scale!=.5:raise ValueError('Probe outside the frozen discovery/coarse budget')
            self._afford(cost)
            return self.measure(self.case(case_id),layer,head,scale,'coarse',baselines[case_id])
        first_agent=investigator.ask('initial',asdict(self.backend.model.dims),public_summary,request_probe)
        if first_agent.get('proposal'):
            p=first_agent['proposal'];validate(self.backend.model,p['layer'],p['head'],p['scale'])
            self.evidence.emit('runtime_proposal',{'phase':'initial','proposal':p,**self.provenance()})
        rankings=[]
        for layer,head in heads:
            self._afford(cost*len(discovery))
            results=[self.measure(case,layer,head,.5,'coarse',baselines[case['case_id']]) for case in discovery]
            rankings.append({'layer':layer,'head':head,'scale':.5,'score':self._rank(results)})
            save(self.root/'coarse_ranking.json',sorted(rankings,key=lambda x:-x['score']))
        shortlist=sorted(rankings,key=lambda x:-x['score'])[:3]
        save(self.root/'shortlist.json',shortlist)
        next_agent=investigator.ask('next_experiment',asdict(self.backend.model.dims),public_summary,request_probe,
                                   results={'ranked_discovery_heads':sorted(rankings,key=lambda x:-x['score']),
                                            'requested_next_step':'propose attenuation and a falsifiable prediction for one measured head'})
        refinements=[]
        for component in shortlist:
            for scale in (0,.25,.5,.75,1):
                layer=component['layer'];head=component['head']
                phase='coarse' if scale==.5 else 'refinement'
                self._afford(cost*len(discovery))
                result=[self.measure(case,layer,head,scale,phase,baselines[case['case_id']]) for case in discovery]
                refinements.append({'layer':layer,'head':head,'scale':scale,'score':self._rank(result)})
                save(self.root/'refinement_results.json',refinements)
        selected=max((x for x in refinements if x['scale']!=1),key=lambda x:x['score'])
        runtime_executed=False
        proposal=next_agent.get('proposal')
        if proposal:
            validate(self.backend.model,proposal['layer'],proposal['head'],proposal['scale'])
            if any(all(x[k]==proposal[k] for k in ('layer','head','scale')) for x in refinements):
                runtime_executed=True
                self.evidence.emit('runtime_next_experiment_executed',{'proposal':proposal,**self.provenance()})
        layer=selected['layer'];head=selected['head'];scale=selected['scale']
        eligible=[x for x in range(self.backend.model.dims.n_text_head) if x!=head]
        controls=[{'layer':layer,'head':h,'scale':scale} for h in random.Random(SEED+1).sample(eligible,min(5,len(eligible)))]
        hypothesis={'hypothesis_id':uuid.uuid4().hex,'parent_experiment_id':manifest['experiment_id'],'claim':CLAIM,
                    'predicted_direction':'decrease_target_logprob_when_attenuated','alternative':'general_suppression_of_transcription',
                    'component':{'kind':'decoder_self_attention','layer':layer,'head':head},'position_scope':'all_prefix_positions',
                    'discovery_case_ids':manifest['discovery_ids'],'control_case_ids':manifest['confirmation_ids'],
                    'control_head_ids':controls,'intervention':{'kind':'head_scale','scale':scale},
                    'would_weaken_claim':'Failure to reduce unsupported token preference on three independent confirmation sources, comparable speech effects, or control heads as effective',
                    'criteria':CRITERIA,'selected_on':'discovery only','agent_source':'runtime model adapter' if runtime_executed else 'engineering sweep; API unavailable or no executed model proposal'}
        frozen={'time':now(),'selected':selected,'control_heads':controls,'hypothesis':hypothesis,
                'confirmation_ids':manifest['confirmation_ids'],'target_recipe':'first lexical token in pristine production trace; genuine-speech reference token; empty controls use discovery token',
                'manifest_hash':identity(manifest),'criteria':CRITERIA}
        if (self.root/'frozen_confirmation.json').exists():
            old=read(self.root/'frozen_confirmation.json')
            if old['selected']!=selected or old['control_heads']!=controls:raise ValueError('Cannot adapt confirmation selection after freeze')
            frozen=old
        else:save(self.root/'frozen_confirmation.json',frozen)
        self.evidence.emit('mechanistic_confirmation_frozen',{'protocol_hash':identity(frozen),**self.provenance()})
        confirmation=[];by_id={x['id']:x for x in load_pack(self.dev,'dev')[0]};default=read(self.root/'prepared.json')['default_unsupported_token']
        for case_id in frozen['confirmation_ids']:
            item=by_id[case_id];baseline=read(self.root/'baseline'/f'{case_id}.json')
            if item['kind']=='nonspeech' and baseline['text'].strip() and not words(baseline['text']):continue
            cohort='genuine_speech' if item['kind']=='speech' else 'unsupported_lexical' if words(baseline['text']) else 'correctly_empty'
            case=build_case(item,baseline['windows'],self.backend.model,cohort,'confirmation',default)
            case.update(source_group=source_group(item),manifest_sha256=manifest['manifest_sha256'])
            save(self.root/'cases'/f'{case_id}.json',case);confirmation.append(case)
        confirmation_results=[];control_results=[]
        for case in confirmation:
            self._afford(cost*(1+len(controls)))
            baseline=self.engine.forward(case)
            confirmation_results.append(self.measure(case,layer,head,scale,'confirmation',baseline))
            for control in controls:control_results.append(self.measure(case,**control,phase='confirmation_control',baseline=baseline))
        # Full application evaluations include all 12 genuine-speech examples, including confirmation examples.
        predicted_pair=statistics.mean(read(self.root/'baseline'/f"{x['id']}.json")['elapsed'] for x in by_id.values())*29
        self._afford(predicted_pair*(1+len(controls))*1.3)
        selected_app=self.transcribe_condition('selected',layer,head,scale)
        comparisons=[('selected',selected_app)]
        for index,control in enumerate(controls):comparisons.append((f'control_{index}_H{control["head"]}',self.transcribe_condition(f'control_{index}',**control)))
        patch=export_candidate(self.checkpoint,self.root/'export'/'candidate.pt',layer,head,scale,self.backend.model)
        frozen_candidate={'time':now(),'patch':patch,'decode':DECODE,'gate':GATE,'source_hashes':manifest['source_hashes'],
                          'configuration_hash':manifest['configuration_hash'],'confirmation_protocol_hash':identity(frozen),
                          'development_gate_passed':selected_app['gate_pass'],'final_holdout':'blocked: original set already consumed'}
        save(self.root/'frozen_candidate.json',{'package':frozen_candidate,'sha256':identity(frozen_candidate)})
        baseline_metrics=read(self.root/'baseline_metrics.json');application_table=[]
        def app_row(name,value):
            return {'condition':name,'nonspeech_lexical_outputs':len(value['nonspeech']['lexical_output_ids']),
                    'speech_edits':value['speech']['edits'],'speech_words':value['speech']['reference_words'],
                    'empty_speech':len(value['speech']['empty_ids']),'errors':len(value['errors'])}
        application_table.append(app_row('pristine',baseline_metrics))
        for name,result in comparisons:application_table.append(app_row(name,result['candidate']))
        retention=(selected_app['candidate']['complete'] and not selected_app['newly_empty_speech_ids']
                   and selected_app['speech_wer_delta'] is not None and selected_app['speech_wer_delta']<=.01)
        groups={x['source_group'] for x in confirmation_results if x['cohort']=='unsupported_lexical'}
        verified_labels=all(not x['input']['manifest_record'].get('review_required',True) for x in confirmation_results if x['cohort']=='unsupported_lexical')
        qualification=qualify(confirmation_results,control_results,CRITERIA,verification['numerical_logprob_variation'],retention,len(groups),verified_labels)
        diagnostic_table=[]
        for condition,records in [('selected',confirmation_results)]+[(f'control_L{c["layer"]}_H{c["head"]}',[x for x in control_results if x['head']==c['head']]) for c in controls]:
            for cohort in ('unsupported_lexical','correctly_empty','genuine_speech'):
                values=[x['target_logprob_delta'] for x in records if x['cohort']==cohort and x['status']=='ok']
                if values:diagnostic_table.append({'head':condition,'cohort':cohort,'n':len(values),'mean_delta':statistics.mean(values)})
        summary={'implementation_status':'unrun','mechanism_status':qualification['mechanism_status'],
                 'repair_status':'development_only' if selected_app['gate_pass'] else 'rejected',
                 'agent_upgrade_status':read('.neural-pr/report.json')['improvement_outcome'],
                 'selected':selected,'control_heads':controls,'qualification':qualification,'verification':verification,
                 'application_table':application_table,'diagnostic_table':diagnostic_table,'patch':patch,
                 'agent':{'initial_status':first_agent['status'],'next_status':next_agent['status'],'runtime_next_proposal_executed':runtime_executed,
                          'investigation_mode':'autonomous_model_proposal' if runtime_executed else 'seed_fixed_engineering_sweep; no autonomous investigation claim'},
                 'explanation':'A fixed-prefix self-attention intervention changes measured token preference. The executable predicates below determine whether this supports the proposed role, rather than a broad suppression effect.',
                 'limitations':manifest['prior_exposure']+' Non-speech labels remain uncertain. No new short/quiet speech controls were added. The original final audio holdout was consumed before this addendum; a new set is needed for any new repair. Root source is snapshotted in an isolated Git repository; runtime filesystem secrecy is not enforced.',
                 'interchange':'unrun; no documented clean/unsupported same-source pair was established; prioritize matched attenuation controls and export integrity.',
                 'accepted_checkpoint':'pristine small.pt; no automatic promotion without new heldout evidence',
                 'hypothesis_id':frozen['hypothesis']['hypothesis_id'],'timing':self.state.read('search_clock')}
        save(self.root/'summary.json',summary)
        self.verify_export()
        return read(self.root/'summary.json')
    def verify_export(self):
        self.check_manifest()
        package=read(self.root/'frozen_candidate.json');patch=package['package']['patch']
        if identity(package['package'])!=package['sha256'] or sha(patch['exported_checkpoint'])!=patch['exported_checkpoint_sha256']:raise ValueError('Frozen export hash mismatch')
        selected=read(self.root/'frozen_confirmation.json')['selected'];self.load()
        fixture_ids=['one_minute_silence','2277-149896-0000']
        import os,sys
        from neural_pr.sandbox import execute
        expected=[]
        for case_id in fixture_ids:
            case=self.case(case_id)
            with head_mode(self.backend.model,selected['layer'],selected['head'],selected['scale'],mode='hook'):
                text=self.backend.transcribe(self.dev/case['manifest_record']['audio_path'])['text']
            expected.append({'case_id':case_id,'path':str(self.dev/case['manifest_record']['audio_path']),'text':text})
        environment={key:value for key,value in os.environ.items() if not key.endswith(('API_KEY','TOKEN'))}
        response=execute([sys.executable,'-m','whisper_repair.mechanistic.export_rpc'],timeout=90,
            input=json.dumps({'checkpoint':patch['exported_checkpoint'],'expected_sha256':patch['exported_checkpoint_sha256'],
                              'layer':selected['layer'],'fixtures':expected}),env=environment)
        if response['code']:raise RuntimeError('Fresh export verifier failed: '+response['stderr'][-1000:])
        actual=json.loads(response['stdout']);results=[]
        for before,after in zip(expected,actual['fixtures']):
            results.append({'case_id':before['case_id'],'status':after['status'],'hook_text':before['text'],
                            'fresh_export_text':after.get('text'),'passed':after['status']=='ok' and before['text']==after.get('text')})
        export={'passed':len(results)==len(expected) and all(x['passed'] for x in results)
                and actual['loaded_checkpoint_sha256']==patch['exported_checkpoint_sha256']
                and actual['loaded_projection_sha256']==patch['loaded_projection_sha256'] and actual['hooks_at_load']==0,
                'fixtures':results,'fresh_process':True,'child_pid':actual['pid'],'no_intervention_hooks_in_child':actual['hooks_at_load']==0,
                'child_loaded_checkpoint_sha256':actual['loaded_checkpoint_sha256'],
                'child_loaded_projection_sha256':actual['loaded_projection_sha256'],
                'checkpoint_sha256':sha(patch['exported_checkpoint']),'distinct_from_stock':sha(patch['exported_checkpoint'])!=sha(self.checkpoint),
                'tensor_reload_verified':patch['reloaded_state_verified'],'selected_head':selected}
        save(self.root/'export_verification.json',export)
        summary=read(self.root/'summary.json');summary['verification']['export']=export
        required=summary['verification']['all_passed'] and export['passed']
        summary['implementation_status']='passed' if required else 'failed';save(self.root/'summary.json',summary)
        render(self.root)
        return export
