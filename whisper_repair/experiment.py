"""Audio-only experiment: untouched baseline, full-dev weight candidates, once-only heldout."""
import datetime
import gc
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

from .backend import load_audio
from .metrics import compare, score, words

OFFICIAL_SMALL_SHA256='9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794'

DECODE={'implementation':'original-openai-whisper','model_family':'multilingual small','device':'cpu','fp16':False,
        'language':'en','task':'transcribe','temperature':0.0,'beam_size':1,'condition_on_previous_text':True,
        'compression_ratio_threshold':2.4,'logprob_threshold':-1.0,'no_speech_threshold':0.6,
        'threads':4,'seed':0,'deterministic_algorithms':True,'preprocessing':'unchanged PCM16 / 32768, full audio'}
GATE={'strictly_fewer_supplied_label_nonspeech_lexical_outputs':True,'max_speech_wer_absolute_increase':0.01,
      'max_newly_empty_genuine_speech':0,'max_errors':0,'require_complete_manifest':True,
      'weak_nonspeech_labels':'diagnostic, not independently verified hallucinations'}

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def identity(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w') as stream:
        stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)
def read(path):return json.loads(Path(path).read_text())
def code_hash():
    return identity({p.name:sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))})
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def load_pack(directory,partition):
    directory=Path(directory).resolve();path=directory/'manifest.jsonl'
    expected=(directory/'manifest.sha256').read_text().split()[0]
    if sha(path)!=expected:raise ValueError('Manifest hash mismatch')
    manifest=rows(path)
    if len({item['id'] for item in manifest})!=len(manifest):raise ValueError('Duplicate recording IDs')
    for item in manifest:
        if item['partition']!=partition:raise ValueError('Unexpected dataset partition')
        audio=(directory/item['audio_path']).resolve()
        if directory not in audio.parents:raise ValueError('Audio path escapes pack')
        if sha(audio)!=item['sha256']:raise ValueError('Audio hash mismatch: '+item['id'])
        load_audio(audio)
    return manifest,{'manifest':str(path),'manifest_sha256':expected,'count':len(manifest),'partition':partition}

class InferenceProcess:
    def __init__(self,checkpoint,log,seconds=180):
        self.log=Path(log).open('a')
        env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
        for key in list(env):
            if key.endswith(('API_KEY','TOKEN')):env.pop(key)
        self.proc=subprocess.Popen([sys.executable,'-m','whisper_repair.rpc','--checkpoint',str(checkpoint)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1,start_new_session=True,env=env)
        try:
            self.metadata=self.receive(seconds)
            if not self.metadata.get('ready'):raise RuntimeError(self.metadata.get('error','Whisper could not load'))
        except Exception:
            self.close();raise
    def receive(self,seconds):
        if not select.select([self.proc.stdout],[],[],seconds)[0]:
            self.close();raise TimeoutError('Whisper process exceeded its time budget')
        line=self.proc.stdout.readline()
        if not line:raise RuntimeError('Whisper process exited; inspect model stderr log')
        return json.loads(line)
    def transcribe(self,path,seconds=180):
        self.proc.stdin.write(canonical({'path':str(path)})+'\n');self.proc.stdin.flush()
        return self.receive(seconds)
    def close(self):
        if hasattr(self,'proc'):
            try:os.killpg(self.proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            self.proc.wait()
        if hasattr(self,'log'):self.log.close()

class Experiment:
    def __init__(self,root='audio_runs',dev='whisper_audio_dev'):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True);self.dev=Path(dev).resolve()

    def inspect(self):
        manifest,info=load_pack(self.dev,'dev')
        info.update(reproduction_ids=[x['id'] for x in manifest if x['category']=='reported_repro'],
                    genuine_speech_ids=[x['id'] for x in manifest if x['kind']=='speech'],
                    label_provenance={x['id']:x['label_provenance'] for x in manifest})
        if len(info['reproduction_ids'])!=5:raise ValueError('Expected all five reported reproduction cases')
        save(self.root/'development_inventory.json',info);return info

    def stage(self,name,manifest,pack,checkpoint,config,reuse=None,deadline=None):
        directory=self.root/name;directory.mkdir(parents=True,exist_ok=True)
        metadata={'checkpoint':str(checkpoint),'checkpoint_sha256':sha(checkpoint),'decode':DECODE,
                  'manifest':pack,'ids':[item['id'] for item in manifest],'configuration':config,'evaluation_code_hash':code_hash()}
        meta_path=directory/'run.json'
        if meta_path.exists() and read(meta_path)!=metadata:raise ValueError('Attempt identity changed; use a new audio run directory')
        save(meta_path,metadata)
        raw_path=directory/'raw.jsonl'
        prior=rows(raw_path) if raw_path.exists() else []
        predictions={item['id']:item for item in prior}
        if len(prior)!=len(predictions) or not set(predictions)<={x['id'] for x in manifest}:raise ValueError('Unexpected/duplicate prior prediction')
        process=None
        try:
            for item in manifest:
                if item['id'] in predictions:continue
                started=time.monotonic()
                remaining=deadline-started if deadline is not None else 180
                if remaining<=0:raise TimeoutError('Initial 15-minute small-model test window exhausted; inspect saved raw outputs and latency before checkpoint choice')
                if reuse and item['id'] in reuse:
                    prediction=dict(reuse[item['id']],reused_from='baseline_reproduction/raw.jsonl')
                else:
                    if process is None:
                        process=InferenceProcess(checkpoint,directory/'model_stderr.log',seconds=min(180,remaining))
                        save(directory/'runtime.json',process.metadata)
                    try:prediction=process.transcribe(Path(pack['manifest']).parent/item['audio_path'],seconds=min(180,deadline-time.monotonic()) if deadline is not None else 180)
                    except (TimeoutError,RuntimeError,BrokenPipeError,ValueError) as exc:
                        prediction={'status':'timeout' if isinstance(exc,TimeoutError) else 'error','error':type(exc).__name__+': '+str(exc)}
                        process.close();process=None
                    prediction.update(id=item['id'],time=now(),elapsed=time.monotonic()-started)
                prediction.update(audio_sha256=item['sha256'],manifest_line=1+next(i for i,x in enumerate(rows(pack['manifest'])) if x['id']==item['id']),
                                  checkpoint_sha256=metadata['checkpoint_sha256'],decode_hash=identity(DECODE))
                with raw_path.open('a') as stream:
                    stream.write(canonical(prediction)+'\n');stream.flush();os.fsync(stream.fileno())
                predictions[item['id']]=prediction
        finally:
            if process:process.close()
        if sha(checkpoint)!=metadata['checkpoint_sha256']:raise RuntimeError('Checkpoint mutated during inference')
        return predictions

    def baseline(self,checkpoint):
        checkpoint=Path(checkpoint).resolve()
        inventory=self.inspect()
        if not checkpoint.is_file():raise FileNotFoundError('Untouched multilingual small .pt checkpoint is missing')
        if sha(checkpoint)!=OFFICIAL_SMALL_SHA256:raise ValueError('Baseline bytes differ from official original multilingual small.pt SHA-256')
        manifest,pack=load_pack(self.dev,'dev')
        fingerprint={'checkpoint_sha256':sha(checkpoint),'decode':DECODE,'manifest_sha256':pack['manifest_sha256'],'gate':GATE,'evaluation_code_hash':code_hash()}
        config_path=self.root/'experiment.json'
        if config_path.exists() and read(config_path)!=fingerprint:raise ValueError('Baseline configuration changed; use new --runs directory')
        save(config_path,fingerprint)
        deadline=time.monotonic()+900
        repro=[x for x in manifest if x['category']=='reported_repro']
        # Mandatory ordering: every reported reproduction case is transcribed and saved before other development work.
        reported=self.stage('baseline_reproduction',repro,pack,checkpoint,fingerprint,deadline=deadline)
        reproduction=[]
        for item in repro:
            prediction=reported[item['id']]
            reproduction.append({'id':item['id'],'raw_prediction':prediction,
                'reported_issue':item.get('reported_issue'),'reported_models':item.get('reported_models'),
                'lexical_output_observed':bool(words(prediction['text'])) if prediction['status']=='ok' else None,
                'reproduction_status':'observed_lexical_output_under_unreviewed_nonspeech_label' if prediction['status']=='ok' and words(prediction['text']) else 'not_reproduced_under_this_configuration' if prediction['status']=='ok' else 'inference_error',
                'label_provenance':item['label_provenance'],'review_required':item.get('review_required',True),
                'manifest':pack['manifest'],'manifest_sha256':pack['manifest_sha256']})
        save(self.root/'reproduction_results.json',reproduction)
        predictions=self.stage('baseline_development',manifest,pack,checkpoint,fingerprint,reuse=reported,deadline=deadline)
        scores=score(manifest,predictions);save(self.root/'baseline_development'/'metrics.json',scores)
        known=[]
        for index,item in enumerate(manifest,1):
            prediction=predictions[item['id']];metric=scores['per_recording'][item['id']]
            failure='inference_error' if prediction['status']!='ok' else 'speech_transcription_error' if item['kind']=='speech' and metric['edits'] else 'lexical_output_on_supplied_nonspeech_label' if item['kind']!='speech' and metric['lexical_output'] else None
            if failure:
                known.append({'id':item['id'],'failure_class':failure,'prediction':prediction,
                    'reference_text':item['reference_text'],'metrics':metric,'manifest':pack['manifest'],
                    'manifest_link':Path(pack['manifest']).as_uri()+'#L'+str(index),'manifest_line':index,
                    'manifest_sha256':pack['manifest_sha256'],'audio_path':str(self.dev/item['audio_path']),
                    'audio_sha256':item['sha256'],'label_provenance':item['label_provenance'],
                    'review_required':item.get('review_required',True),'source_url':item.get('source_url'),
                    'source_recording_id':item.get('source_recording_id'),'source_dataset':item.get('source_dataset'),
                    'source_revision':item.get('source_revision'),'source_row_index':item.get('source_row_index'),
                    'license':item.get('license'),'local_observation':True,
                    'confirmed_hallucination':False if item.get('review_required',True) else failure=='lexical_output_on_supplied_nonspeech_label'})
        text=''.join(canonical(item)+'\n' for item in known)
        (self.root/'known_failures.jsonl').write_text(text)
        Path('known_failures.jsonl').write_text(text)
        save(self.root/'known_failures_status.json',{'status':'observed','baseline_complete':scores['complete'],'count':len(known),
            'definition':'Observed transcription deviations/errors; weak-label nonspeech outputs require review.'})
        return scores

    def evaluate_edit(self,pristine,layer,head,scale):
        if (self.root/'holdout_consulted.json').exists():raise ValueError('Holdout consulted: no further tuning')
        baseline=read(self.root/'experiment.json');pristine=Path(pristine).resolve()
        if sha(pristine)!=baseline['checkpoint_sha256']:raise ValueError('Pristine checkpoint identity mismatch')
        manifest,pack=load_pack(self.dev,'dev')
        original={x['id']:x for x in rows(self.root/'baseline_development'/'raw.jsonl')}
        if not score(manifest,original)['complete']:raise ValueError('Complete baseline including genuine speech is required')
        if not 0<=scale<=1 or not 0<=layer<12 or not 0<=head<12:raise ValueError('Expected small decoder layer/head 0..11 and scale 0..1')
        identifier=identity({'parent':baseline['checkpoint_sha256'],'layer':layer,'head':head,'scale':scale})
        directory=self.root/'candidates'/identifier;directory.mkdir(parents=True,exist_ok=True)
        checkpoint=directory/'candidate.pt'
        if not checkpoint.exists():
            import torch
            payload=torch.load(pristine,map_location='cpu',weights_only=True)
            dims=payload['dims']
            if (dims['n_text_layer'],dims['n_text_head'])!=(12,12):raise ValueError('Checkpoint does not match multilingual small architecture')
            from .weights import attenuate_head
            def state_hashes(state):
                return {name:hashlib.sha256(tensor.detach().cpu().contiguous().numpy().tobytes()).hexdigest() for name,tensor in state.items()}
            before=state_hashes(payload['model_state_dict'])
            changed=attenuate_head(payload['model_state_dict'],layer,head,scale)
            expected=state_hashes(payload['model_state_dict'])
            modified=[name for name in before if before[name]!=expected[name]]
            if any(name!=changed for name in modified):raise RuntimeError('Unexpected parameter changes')
            temporary=directory/'candidate.partial.pt';torch.save(payload,temporary);temporary.replace(checkpoint)
            del payload;gc.collect()
            restored=torch.load(checkpoint,map_location='cpu',weights_only=True)
            if state_hashes(restored['model_state_dict'])!=expected:raise RuntimeError('Exported weight reload differs from intended candidate')
            save(directory/'export_validation.json',{'reloaded':True,'modified_parameters':modified,'expected_state_hash':identity(expected)})
            del restored;gc.collect()
        if sha(pristine)!=baseline['checkpoint_sha256']:raise RuntimeError('Pristine checkpoint mutated')
        intervention={'kind':'static_weight_edit','parameter':f'decoder.blocks.{layer}.cross_attn.out.weight',
                      'column_head':head,'scale':scale,'parent_sha256':baseline['checkpoint_sha256'],
                      'checkpoint_sha256':sha(checkpoint),'checkpoint':str(checkpoint)}
        save(directory/'intervention.json',intervention)
        # A NEW inference process reloads the saved artifact; no edited in-memory model supplies evidence.
        candidate=self.stage('candidates/'+identifier+'/development',manifest,pack,checkpoint,intervention)
        result=compare(manifest,original,candidate);save(directory/'comparison.json',result)
        return {'id':identifier,'intervention':intervention,'comparison':result}

    def freeze(self):
        if (self.root/'holdout_consulted.json').exists():raise ValueError('Holdout consumed; candidate selection cannot change')
        eligible=[];exploratory=[]
        for path in (self.root/'candidates').glob('*/comparison.json'):
            result=read(path);candidate=result['candidate'];baseline=result['baseline']
            intervention=read(path.parent/'intervention.json')
            order=(len(candidate['nonspeech']['lexical_output_ids']),candidate['speech']['wer'],
                   1-intervention['scale'],intervention['parameter'],intervention['column_head'],path.parent.name)
            if result['gate_pass']:eligible.append(order)
            # Freezing an experimental comparison does not approve a repair or relax its gate.
            if (baseline['complete'] and candidate['complete'] and not result['newly_empty_speech_ids']
                and result['speech_wer_delta'] is not None and result['speech_wer_delta']<=0.01
                and len(candidate['nonspeech']['lexical_output_ids'])<=len(baseline['nonspeech']['lexical_output_ids'])):
                exploratory.append(order)
        pool=eligible or exploratory
        if not pool:raise ValueError('No development-qualified or nonregressing exploratory candidate; retain baseline.')
        identifier=min(pool)[-1];directory=self.root/'candidates'/identifier
        selection_status='development_gate_passed' if eligible else 'exploratory_selection_development_gate_failed'
        intervention=read(directory/'intervention.json')
        if sha(intervention['checkpoint'])!=intervention['checkpoint_sha256']:raise ValueError('Candidate bytes changed')
        package={'candidate_id':identifier,'intervention':intervention,'baseline':read(self.root/'experiment.json'),
                 'selection_status':selection_status,'development_gate_passed':bool(eligible),
                 'selection_rule':'Prefer gate passes; otherwise nonregressing exploratory candidate, ordered by NS lexical count, WER, least attenuation, parameter and head',
                 'evaluation_code_hash':code_hash(),'gate':GATE,'freeze_time':now(),
                 'development_comparison_sha256':sha(directory/'comparison.json')}
        record={'package':package,'sha256':identity(package)}
        path=self.root/'frozen_candidate.json'
        if path.exists() and read(path)['package']['candidate_id']!=identifier:raise ValueError('Candidate already frozen; use a new experiment')
        if not path.exists():save(path,record);path.chmod(0o444)
        return read(path)

    def heldout(self,pack_directory,baseline_checkpoint,resume=False):
        # Every frozen-artifact check precedes ANY access to held-out manifest or audio.
        frozen=read(self.root/'frozen_candidate.json');package=frozen['package']
        if identity(package)!=frozen['sha256'] or package['evaluation_code_hash']!=code_hash():raise ValueError('Frozen candidate/evaluator changed')
        intervention=package['intervention']
        if sha(intervention['checkpoint'])!=intervention['checkpoint_sha256'] or sha(baseline_checkpoint)!=package['baseline']['checkpoint_sha256']:
            raise ValueError('Checkpoint differs from frozen selection')
        ledger=self.root/'holdout_consulted.json'
        if ledger.exists():
            if not resume or read(ledger)['candidate_hash']!=frozen['sha256']:raise ValueError('Holdout already consumed; only exact frozen run may resume')
        else:save(ledger,{'candidate_hash':frozen['sha256'],'time':now(),'status':'consumed','integrity':'logical quarantine only; OS secrecy not enforced'})
        manifest,pack=load_pack(pack_directory,'heldout')
        if not any(x['kind']=='speech' for x in manifest):raise ValueError('Genuine speech controls are required')
        baseline=self.stage('heldout_baseline',manifest,pack,Path(baseline_checkpoint).resolve(),package['baseline'])
        candidate=self.stage('heldout_candidate',manifest,pack,Path(intervention['checkpoint']),intervention)
        result=compare(manifest,baseline,candidate)
        result.update(candidate_hash=frozen['sha256'],pack=pack,no_further_tuning=True,
                      result_scope='Whisper artifact only; not evidence of coding-agent policy improvement')
        save(self.root/'heldout_comparison.json',result)
        return result
