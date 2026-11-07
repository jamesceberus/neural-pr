"""Temporary head modes reuse the existing static column-edit operation."""
from contextlib import contextmanager
import hashlib
import math

SCALES=(0.0,0.25,0.5,0.75,1.0)

def tensor_hash(tensor):
    return hashlib.sha256(tensor.detach().cpu().contiguous().numpy().tobytes()).hexdigest()

def validate(model,layer,head,scale):
    dims=model.dims
    if type(layer)!=int or type(head)!=int or not 0<=layer<dims.n_text_layer or not 0<=head<dims.n_text_head:
        raise ValueError('Invalid decoder self-attention layer/head')
    if isinstance(scale,bool) or not isinstance(scale,(float,int)) or not math.isfinite(scale) or scale not in SCALES:
        raise ValueError('Scale must be one of 0, .25, .5, .75, 1')
    if dims.n_text_state%dims.n_text_head:raise ValueError('Invalid head layout')

def assert_uncached(model):
    for block in model.decoder.blocks:
        for attn in (block.attn,block.cross_attn):
            for module in (attn.key,attn.value):
                if module._forward_hooks:raise ValueError('Decoder KV cache hooks must be removed before independent probes')

@contextmanager
def head_mode(model,layer,head,scale=1.0,mode='hook',positions=None,capture=None):
    """All-position hook and column edit are exclusive. Restore weights/hooks even on exceptions."""
    import torch
    from whisper_repair.weights import attenuate_head
    validate(model,layer,head,scale)
    if mode not in ('capture','noop','hook','weight'):raise ValueError('Unknown intervention mode')
    if getattr(model,'_mechanistic_mode',None) is not None:raise ValueError('Only one intervention mode may be active; double attenuation is forbidden')
    if mode=='weight' and positions is not None:raise ValueError('A permanent weight edit applies at all positions')
    if positions is not None and (not positions or any(type(x)!=int or x<0 for x in positions)):
        raise ValueError('Invalid token positions')
    module=model.decoder.blocks[layer].attn.out
    width=model.dims.n_text_state//model.dims.n_text_head;start=head*width;stop=start+width
    original=module.weight.detach().clone() if mode=='weight' else None
    bias_hash=tensor_hash(module.bias) if module.bias is not None else None
    handle=None;model._mechanistic_mode=mode
    try:
        if mode=='weight':
            # The model is pristine at entry, and this context always restores its full projection.
            with torch.no_grad():
                module.weight.copy_(original)
                attenuate_head({f'decoder.blocks.{layer}.cross_attn.out.weight':module.weight},layer,head,float(scale),model.dims.n_text_head)
        else:
            def hook(_module,inputs):
                value=inputs[0]
                if value.ndim!=3 or value.shape[-1]!=model.dims.n_text_state:raise ValueError('Unexpected concatenated head-output shape')
                selected=list(range(value.shape[1])) if positions is None else positions
                if max(selected,default=-1)>=value.shape[1]:raise ValueError('Capture position outside prefix')
                if capture is not None:
                    capture.append(value[:,selected,start:stop].detach().clone())
                if mode in ('capture','noop') or scale==1:return None
                changed=value.clone();changed[:,selected,start:stop]*=scale
                return (changed,)
            handle=module.register_forward_pre_hook(hook)
        yield {'layer':layer,'head':head,'mode':mode,'scale':scale,'position_scope':'all_prefix_positions' if positions is None else list(positions),
               'parameter':f'decoder.blocks.{layer}.attn.out.weight','columns':[start,stop],
               'targeted_parameter_count':module.weight.shape[0]*width}
    finally:
        if handle is not None:handle.remove()
        if original is not None:
            with torch.no_grad():module.weight.copy_(original)
        model._mechanistic_mode=None
        if module.bias is not None and tensor_hash(module.bias)!=bias_hash:raise RuntimeError('Projection bias changed')
