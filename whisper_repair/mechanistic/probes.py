"""Aligned uncached diagnostics plus behavior-preserving production-window tracing."""
from contextlib import contextmanager,ExitStack
from dataclasses import asdict
import inspect
from pathlib import Path
import time
import types

from whisper_repair.backend import load_audio
from whisper_repair.experiment import DECODE,sha,identity
from whisper_repair.metrics import words
from .interventions import head_mode,assert_uncached

@contextmanager
def trace_decoding(model,directory=None):
    """Observe original decode results and the exact installed transcribe skip predicate."""
    import torch
    from whisper.decoding import DecodingTask
    original=model.decode;had_instance='decode' in model.__dict__;previous=model.__dict__.get('decode')
    records=[]
    def traced(_model,mel,options):
        frame=inspect.currentframe().f_back
        seek=None;thresholds={'no_speech_threshold':DECODE['no_speech_threshold'],'logprob_threshold':DECODE['logprob_threshold']}
        try:
            while frame is not None:
                if frame.f_code.co_name=='transcribe' and frame.f_globals.get('__name__')=='whisper.transcribe':
                    seek=frame.f_locals.get('seek');thresholds={key:frame.f_locals.get(key) for key in thresholds};break
                frame=frame.f_back
        finally:del frame
        result=original(mel,options)
        if isinstance(result,list):raise ValueError('Production trace supports one recording per call')
        task=DecodingTask(model,options)
        skipped=thresholds['no_speech_threshold'] is not None and result.no_speech_prob>thresholds['no_speech_threshold']
        if thresholds['logprob_threshold'] is not None and result.avg_logprob>thresholds['logprob_threshold']:skipped=False
        entry={'seek_frames':int(seek) if seek is not None else None,'seek_seconds':seek/100 if seek is not None else None,
               'token_ids':list(result.tokens),'text':result.text,'no_speech_prob':float(result.no_speech_prob),
               'avg_logprob':float(result.avg_logprob),'skip_decision':bool(skipped),'thresholds':thresholds,
               'skip_decision_source':'exact installed transcribe predicate, read current frame thresholds',
               'initial_token_ids':list(task.initial_tokens),'sot_position':task.sot_index,'decode_options':asdict(options)}
        if directory is not None:
            destination=Path(directory);destination.mkdir(parents=True,exist_ok=True)
            path=destination/f'window-{len(records)}.pt';torch.save(mel.detach().cpu().clone(),path)
            entry.update(mel_path=str(path.resolve()),mel_sha256=sha(path))
        records.append(entry)
        return result
    model.decode=types.MethodType(traced,model)
    try:yield records
    finally:
        if had_instance:model.decode=previous
        else:del model.decode
        assert_uncached(model)

class ProbeEngine:
    def __init__(self,backend):
        self.backend=backend;self.model=backend.model;self.features={}
    def encode(self,case):
        import torch
        path=case['window']['mel_path']
        if sha(path)!=case['window']['mel_sha256']:raise ValueError('Frozen audio-window features changed')
        key=case['window']['mel_sha256']
        if key not in self.features:
            with torch.inference_mode():self.features[key]=self.model.encoder(torch.load(path,map_location='cpu',weights_only=True).unsqueeze(0)).detach()
        return self.features[key]
    def task(self,case):
        from whisper.decoding import DecodingTask,DecodingOptions
        return DecodingTask(self.model,DecodingOptions(**case['decode_options']))
    def validate_case(self,case):
        task=self.task(case);prefix=case['prefix_token_ids']
        if not isinstance(prefix,list) or not prefix or any(type(x)!=int for x in prefix):raise ValueError('Use one unpadded integer prefix per probe; ragged batches are unsupported')
        if prefix[:len(task.initial_tokens)]!=list(task.initial_tokens):raise ValueError('Prefix differs from frozen production language/task/prompt/timestamp contract')
        if case['target_position']!=len(prefix)-1:raise ValueError('Target position must predict the next token from the final frozen prefix position')
        if case['sot_position']!=task.sot_index:raise ValueError('No-speech score must use the production SOT index')
        if len(prefix)>=self.model.dims.n_text_ctx or any(x<0 or x>=self.model.dims.n_vocab for x in prefix):raise ValueError('Prefix outside model limits')
        for key in ('target_token_id','comparator_token_id'):
            if type(case[key])!=int or not 0<=case[key]<self.model.dims.n_vocab:raise ValueError('Token outside vocabulary')
        return task
    def forward(self,case,intervention=None,capture_heads=(),return_logits=False):
        import torch
        task=self.validate_case(case);assert_uncached(self.model)
        tokens=torch.tensor([case['prefix_token_ids']],dtype=torch.long)
        features=self.encode(case);captures={};started=time.monotonic()
        with ExitStack() as stack,torch.inference_mode():
            if intervention:
                stack.enter_context(head_mode(self.model,**intervention))
            elif capture_heads:
                # Observation hooks may coexist, but none can change values or install caches.
                for layer,head in capture_heads:
                    bucket=[];captures[(layer,head)]=bucket
                    module=self.model.decoder.blocks[layer].attn.out
                    width=self.model.dims.n_text_state//self.model.dims.n_text_head
                    def observe(_module,inputs,layer=layer,head=head,bucket=bucket):
                        value=inputs[0]
                        if value.ndim!=3 or value.shape[-1]!=self.model.dims.n_text_state:raise ValueError('Unexpected attention output shape')
                        positions=sorted({case['target_position'],case['sot_position']})
                        bucket.append(value[:,positions,head*width:(head+1)*width].detach().clone())
                    handle=module.register_forward_pre_hook(observe);stack.callback(handle.remove)
            logits=self.model.decoder(tokens,features,kv_cache=None)
            if not torch.isfinite(logits).all():raise ValueError('Non-finite diagnostic logits')
            pos=case['target_position'];target=case['target_token_id'];eot=case['comparator_token_id']
            raw=logits[0,pos];filtered=raw.unsqueeze(0).clone()
            for logit_filter in task.logit_filters:logit_filter.apply(filtered,tokens)
            no_speech_id=task.tokenizer.no_speech
            record={'target_logit':raw[target].item(),'target_logprob':raw.log_softmax(-1)[target].item(),
                    'raw_target_eot_margin':(raw[target]-raw[eot]).item(),
                    'no_speech_probability_at_sot':logits[0,case['sot_position']].softmax(-1)[no_speech_id].item(),
                    'sot_position':case['sot_position'],'target_position':pos,'target_token_id':target,
                    'comparator_token_id':eot,'target_allowed_by_production_filters':bool(torch.isfinite(filtered[0,target])),
                    'comparator_allowed_by_production_filters':bool(torch.isfinite(filtered[0,eot])),
                    'kv_cache':None,'elapsed':time.monotonic()-started,'activation_norms':[]}
            for (layer,head),bucket in captures.items():
                clone=bucket[0];width=self.model.dims.n_text_state//self.model.dims.n_text_head
                projected=clone@self.model.decoder.blocks[layer].attn.out.weight[:,head*width:(head+1)*width].T
                record['activation_norms'].append({'layer':layer,'head':head,'positions':sorted({pos,case['sot_position']}),
                    'head_norms':clone.norm(dim=-1).flatten().tolist(),'projected_contribution_norms':projected.norm(dim=-1).flatten().tolist()})
            if return_logits:record['_logits']=logits.detach().clone()
            if captures:record['_activations']={f'{l}:{h}':bucket[0] for (l,h),bucket in captures.items()}
        assert_uncached(self.model)
        return record

def build_case(item,trace,model,cohort,partition,default_token=None):
    """Freeze a deterministic recipe: first lexical token at its actual production prefix."""
    from whisper.decoding import DecodingTask,DecodingOptions
    eligible=[]
    for index,window in enumerate(trace):
        if not window['skip_decision']:
            tokenizer=DecodingTask(model,DecodingOptions(**window['decode_options'])).tokenizer
            lexical=[j for j,token in enumerate(window['token_ids']) if token<tokenizer.eot and words(tokenizer.decode([token]))]
            if lexical:eligible.append((index,lexical[0]))
    if cohort=='unsupported_lexical' and not eligible:raise ValueError('Reported failure did not reproduce in traced production path')
    index,offset=eligible[0] if eligible else (0,None)
    window=trace[index];task=DecodingTask(model,DecodingOptions(**window['decode_options']))
    if cohort=='unsupported_lexical':
        prefix=list(window['initial_token_ids'])+window['token_ids'][:offset]
        target=window['token_ids'][offset];recipe='first lexical token in first non-skipped production window containing lexical output'
    elif cohort=='genuine_speech':
        prefix=list(window['initial_token_ids'])+[task.tokenizer.timestamp_begin]
        target=task.tokenizer.encode(' '+item['reference_text'].capitalize())[0]
        recipe='first reference token (sentence case), after initial timestamp zero; fixed reference prefix'
    else:
        prefix=list(window['initial_token_ids'])+[task.tokenizer.timestamp_begin]
        target=default_token;recipe='discovery-selected unsupported token under fixed initial timestamp prefix; diagnostic only'
    return {'case_id':item['id'],'partition':partition,'cohort':cohort,'manifest_record':item,
            'window':dict(window,parent_recording_id=item['id'],bounds_seconds=[window['seek_seconds'],min(item['duration_s'],window['seek_seconds']+30)],derived_example=True),
            'prefix_token_ids':prefix,'target_position':len(prefix)-1,'sot_position':task.sot_index,
            'target_token_id':target,'target_token_text':task.tokenizer.decode([target]),'comparator_token_id':task.tokenizer.eot,
            'decode_options':window['decode_options'],'selection_recipe':recipe,'uncached':True,
            'conditional_on_recorded_prefix':len(prefix)>len(task.initial_tokens),
            'configuration_hash':identity(DECODE)}
