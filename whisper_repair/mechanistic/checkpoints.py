"""Export a self-attention edit using the existing edit operation and hash utilities."""
import gc
from pathlib import Path
from whisper_repair.experiment import sha,save,identity
from whisper_repair.weights import attenuate_head
from .interventions import tensor_hash,validate

def export_candidate(pristine,destination,layer,head,scale,model):
    import torch
    validate(model,layer,head,scale)
    if getattr(model,'_mechanistic_mode',None):raise ValueError('Cannot export a model with intervention hooks enabled')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    parent=sha(pristine)
    payload=torch.load(pristine,map_location='cpu',weights_only=True)
    state=payload['model_state_dict'];name=f'decoder.blocks.{layer}.attn.out.weight'
    before={key:tensor_hash(value) for key,value in state.items()}
    pristine_dtype=str(state[name].dtype)
    state[name]=state[name].float()  # Preserve loaded-model FP32 attenuation exactly rather than re-quantizing its edited slice.
    original=state[name].clone();heads=payload['dims']['n_text_head'];width=payload['dims']['n_text_state']//heads
    start=head*width;stop=start+width
    # Alias lets the existing cross-attention edit primitive operate on the actual self-attention tensor.
    attenuate_head({f'decoder.blocks.{layer}.cross_attn.out.weight':state[name]},layer,head,float(scale),heads)
    changed_values=int(torch.count_nonzero(original[:,start:stop]!=state[name][:,start:stop]).item())
    after={key:tensor_hash(value) for key,value in state.items()}
    changed=[key for key in before if before[key]!=after[key]]
    if any(key!=name for key in changed):raise RuntimeError('Unrelated tensor changed during export')
    temporary=destination.with_suffix('.partial.pt');torch.save(payload,temporary);temporary.replace(destination)
    del payload,state,original;gc.collect()
    reloaded=torch.load(destination,map_location='cpu',weights_only=True)
    actual={key:tensor_hash(value) for key,value in reloaded['model_state_dict'].items()}
    if actual!=after:raise RuntimeError('Fresh tensor reload differs from intended export')
    del reloaded;gc.collect()
    if sha(pristine)!=parent:raise RuntimeError('Pristine parent changed')
    manifest={'kind':'decoder_self_attention_head_scale','pristine_parent_sha256':parent,'parameter':name,
              'tensor_slice':{'rows':'all','columns':[start,stop]},'scale':scale,'layer':layer,'head':head,
              'targeted_parameter_count':model.dims.n_text_state*width,'actual_changed_value_count':changed_values,
              'bias_preserved':True,'unrelated_tensors_preserved':True,'changed_parameters':changed,
              'pristine_parameter_dtype':pristine_dtype,'export_parameter_dtype':'torch.float32',
              'loaded_projection_sha256':after[name],
              'exported_checkpoint':str(destination.resolve()),'exported_checkpoint_sha256':sha(destination),
              'reloaded_state_verified':True,'state_hash':identity(after)}
    save(destination.parent/'patch_manifest.json',manifest)
    return manifest
