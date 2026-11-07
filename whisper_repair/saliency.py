"""Development-only, first-order head ranking. This is a proposal heuristic, not repair evidence."""
import gc
from pathlib import Path
import time
from .experiment import Experiment,load_pack,read,rows,save,sha,identity
from .metrics import score,words
from .backend import load_audio

def rank(experiment,checkpoint):
    import numpy as np
    import torch
    import whisper
    from whisper.tokenizer import get_tokenizer
    checkpoint=Path(checkpoint).resolve()
    baseline=read(experiment.root/'experiment.json')
    if sha(checkpoint)!=baseline['checkpoint_sha256']:raise ValueError('Pristine checkpoint mismatch')
    if (experiment.root/'holdout_consulted.json').exists():raise ValueError('No tuning after holdout consultation')
    manifest,pack=load_pack(experiment.dev,'dev')
    predictions={x['id']:x for x in rows(experiment.root/'baseline_development'/'raw.jsonl')}
    if not score(manifest,predictions)['complete']:raise ValueError('Complete genuine-speech baseline is required')
    failures=[item for item in manifest if item['kind']=='nonspeech' and words(predictions[item['id']]['text'])]
    speech=[item for item in manifest if item['kind']=='speech']
    if not failures:raise ValueError('No locally observed supplied-label non-speech lexical outputs to target')
    torch.set_num_threads(4);torch.manual_seed(0);torch.use_deterministic_algorithms(True)
    model=whisper.load_model(str(checkpoint),device='cpu').float().eval()
    for parameter in model.parameters():parameter.requires_grad_(False)
    scales=torch.ones((12,12),requires_grad=True)
    hooks=[]
    for layer,block in enumerate(model.decoder.blocks):
        def hook(module,inputs,layer=layer):
            x=inputs[0];shape=x.shape
            return ((x.reshape(*shape[:-1],12,shape[-1]//12)*scales[layer].reshape(1,1,12,1)).reshape(shape),)
        hooks.append(block.cross_attn.out.register_forward_pre_hook(hook))
    tokenizer=get_tokenizer(multilingual=True,language='en',task='transcribe')
    prefix=list(tokenizer.sot_sequence_including_notimestamps)
    evidence=[];gradients={}
    started=time.monotonic()
    try:
        for kind,items in [('nonspeech',failures),('speech',speech)]:
            total=torch.zeros_like(scales)
            for item in items:
                pcm,_=load_audio(experiment.dev/item['audio_path'])
                audio=np.asarray(pcm,dtype=np.float32)/32768.0
                # Proposal heuristic uses the first 30-second encoder window only. Full recordings remain in every repair evaluation.
                with torch.no_grad():
                    mel=whisper.log_mel_spectrogram(whisper.pad_or_trim(audio),n_mels=model.dims.n_mels)
                    encoded=model.encoder(mel.unsqueeze(0))
                target=tokenizer.encode(' '+item['reference_text']) if kind=='speech' else []
                sequence=prefix+target+[tokenizer.eot]
                inputs=torch.tensor([sequence[:-1]],dtype=torch.long)
                targets=torch.tensor([sequence[1:]],dtype=torch.long)
                targets[:,:len(prefix)-1]=-100
                logits=model.decoder(inputs,encoded)
                loss=torch.nn.functional.cross_entropy(logits.reshape(-1,logits.shape[-1]),targets.reshape(-1),ignore_index=-100)
                gradient=torch.autograd.grad(loss,scales)[0].detach()
                total+=gradient
                evidence.append({'id':item['id'],'kind':kind,'loss':loss.item(),'label_provenance':item['label_provenance']})
                del logits,loss,gradient,encoded,mel
            gradients[kind]=total/len(items)
        contrast=gradients['nonspeech']-torch.relu(-gradients['speech'])
        ranking=[]
        for layer in range(12):
            for head in range(12):
                ns=gradients['nonspeech'][layer,head].item();sp=gradients['speech'][layer,head].item()
                ranking.append({'layer':layer,'head':head,'score':contrast[layer,head].item(),
                                'nonspeech_scale_gradient':ns,'speech_scale_gradient':sp,
                                'predicted_empty_target_loss_change_at_scale_075':-0.25*ns,
                                'predicted_speech_loss_change_at_scale_075':-0.25*sp})
        ranking.sort(key=lambda x:(-x['score'],x['layer'],x['head']))
        record={'checkpoint_sha256':baseline['checkpoint_sha256'],'method':'first-order decoder cross-attention head-scale gradient',
                'objective':'reduce empty-target CE on observed weak-label nonspeech failures, penalize predicted speech CE harm',
                'scope':'proposal heuristic, not full decoding or measured repair success','window':'first 30 seconds for ranking only',
                'full_development_recordings_required_for_every_repair':len(manifest),'speech_controls_in_ranking':len(speech),
                'nonspeech_failure_cases':len(failures),'evidence':evidence,'ranking':ranking,'elapsed':time.monotonic()-started}
        if sha(checkpoint)!=baseline['checkpoint_sha256']:raise RuntimeError('Pristine checkpoint changed')
        save(experiment.root/'head_ranking.json',record)
        return record
    finally:
        for hook in hooks:hook.remove()
        del model;gc.collect()
