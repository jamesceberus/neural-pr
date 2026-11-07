"""Fixed local UI worker. User requests choose declared parameters, never shell commands or gates."""
from pathlib import Path
import importlib.util
import json
import math
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper_repair.experiment import read,save,sha,identity,DECODE,GATE,OFFICIAL_SMALL_SHA256,now,load_pack
from whisper_repair.metrics import compare

request=read(sys.argv[1]);directory=Path(sys.argv[1]).parent

def progress(phase,done=0,total=1):save(directory/'progress.json',{'phase':phase,'done':done,'total':total,'time':now()})
def followup_module():
    spec=importlib.util.spec_from_file_location('registered_strength_protocol',Path('scripts/followup_head_strength.py').resolve())
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def run():
    kind=request['kind'];progress('Checking local setup')
    checkpoint=Path('audio_models/small.pt').resolve()
    if not checkpoint.is_file() or sha(checkpoint)!=OFFICIAL_SMALL_SHA256:raise ValueError('Pristine multilingual small.pt is missing or its official hash differs')
    import whisper,torch,importlib.metadata
    if kind=='verify_setup':
        return {'status':'ok','checkpoint':'multilingual small','checkpoint_sha256':sha(checkpoint),'official_checkpoint_verified':True,
                'runtime':{x:importlib.metadata.version(x) for x in ('openai-whisper','torch','numpy')},
                'device':'cpu','cuda_available':torch.cuda.is_available(),'development_recordings':len(load_pack('whisper_audio_dev','dev')[0]),'configuration':DECODE}
    from whisper_repair.backend import Backend
    from whisper_repair.mechanistic.probes import ProbeEngine,trace_decoding
    from whisper_repair.mechanistic.interventions import tensor_hash
    backend=Backend(checkpoint);model=backend.model;module=followup_module();parameters=request['parameters']
    layer=parameters['layer'];head=parameters['head'];scale=parameters['scale']
    if type(layer)!=int or type(head)!=int or not 0<=layer<12 or not 0<=head<12 or isinstance(scale,bool) or scale not in module.SCALES:raise ValueError('Parameters outside the declared protocol')
    projection=model.decoder.blocks[layer].attn.out;parent=tensor_hash(projection.weight)
    started=time.monotonic()
    with module.protocol_v2():
        if kind=='diagnostic':
            progress('Loading frozen diagnostic input')
            case_path=Path('audio_runs/mechanistic_v1/cases')/(parameters['case_id']+'.json')
            if parameters['case_id'] not in {x.stem for x in Path('audio_runs/mechanistic_v1/cases').glob('*.json')}:raise ValueError('Only declared development probes are available')
            case=read(case_path);engine=ProbeEngine(backend)
            before=engine.forward(case,capture_heads=[(layer,head)],return_logits=True)
            activation=before.pop('_activations');torch.save(activation,directory/'activation.pt')
            logits=before.pop('_logits')
            progress('Running controlled head intervention',1,3)
            with module.strength(model,layer,head,scale):after=engine.forward(case,return_logits=True)
            hook_logits=after.pop('_logits')
            with module.strength(model,layer,head,scale,'weight'):permanent=engine.forward(case,return_logits=True)
            matched=torch.allclose(hook_logits,permanent.pop('_logits'),atol=.0002,rtol=.00002)
            if tensor_hash(projection.weight)!=parent:raise RuntimeError('Pristine projection was not restored')
            delta=after['target_logprob']-before['target_logprob'];progress('Complete',3,3)
            return {'status':'ok','result_scope':'Exploratory fixed-prefix diagnostic, not final transcription or fresh confirmation',
                'case_id':case['case_id'],'cohort':case['cohort'],'hypothesis':parameters['hypothesis'],
                'layer':layer,'head':head,'scale':scale,'before':before,'after':after,'target_logprob_delta':delta,
                'geometric_mean_probability_ratio':math.exp(delta),'hook_weight_equivalence_passed':bool(matched),
                'pristine_projection_restored':True,'activation_artifact_sha256':sha(directory/'activation.pt'),
                'input_contract_sha256':sha(case_path),'prefix_token_ids':case['prefix_token_ids'],'target_position':case['target_position'],
                'target_token':case['target_token_text'],'window':case['window'],'elapsed_seconds':time.monotonic()-started}
        if kind=='full_development':
            manifest,pack=load_pack('whisper_audio_dev','dev');predictions={}
            for i,item in enumerate(manifest):
                progress('Transcribing '+item['id'],i,len(manifest))
                with module.strength(model,layer,head,scale):
                    with trace_decoding(model) as windows:output=backend.transcribe(Path('whisper_audio_dev')/item['audio_path'])
                result={'id':item['id'],'status':'ok','text':output['text'],'raw':output['raw'],'windows':windows}
                predictions[item['id']]=result;save(directory/'predictions'/f"{item['id']}.json",result)
            baseline={item['id']:read(Path('audio_runs/mechanistic_v1/baseline')/f"{item['id']}.json") for item in manifest}
            comparison=compare(manifest,baseline,predictions)
            paired=module.transitions(baseline,predictions,manifest)
            if tensor_hash(projection.weight)!=parent:raise RuntimeError('Pristine projection not restored')
            progress('Complete',len(manifest),len(manifest))
            return {'status':'ok','result_scope':'Development only; no new confirmation, no promotion',
                    'parameters':parameters,'comparison':comparison,'paired_transitions':paired,'checkpoint_sha256':sha(checkpoint),
                    'configuration_hash':identity(DECODE),'manifest_sha256':pack['manifest_sha256'],
                    'pristine_projection_restored':True,'elapsed_seconds':time.monotonic()-started}
    raise ValueError('Unknown UI action')

try:
    result=run();
    if sha('audio_models/small.pt')!=OFFICIAL_SMALL_SHA256:raise ValueError('Pristine checkpoint changed during the UI attempt')
    result.update(provenance=request.get('provenance',{}),checkpoint_sha256=OFFICIAL_SMALL_SHA256,time=now(),request_sha256=sha(sys.argv[1]),worker_source_sha256=sha(__file__),
                              author='explicit UI user request',agent_upgrade_status='unchanged; independent coding gate required')
    save(directory/'result.json',result)
except Exception as exc:
    save(directory/'result.json',{'status':'error','time':now(),'error':type(exc).__name__+': '+str(exc),'inference_error_is_not_silence':True})
    raise
