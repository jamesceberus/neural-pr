"""A static cross-attention head attenuation, with no decoding/filtering changes."""
def attenuate_head(state,layer,head,scale,n_heads=12):
    import torch
    if not 0<=head<n_heads or not 0<=scale<=1:raise ValueError('Invalid head or attenuation')
    key=f'decoder.blocks.{layer}.cross_attn.out.weight'
    weight=state[key]
    if weight.ndim!=2 or weight.shape[1]%n_heads:raise ValueError('Attention output width is not divisible by head count')
    width=weight.shape[1]//n_heads
    with torch.no_grad():weight[:,head*width:(head+1)*width].mul_(scale)
    return key
