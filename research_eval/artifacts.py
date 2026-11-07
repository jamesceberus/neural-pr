"""Non-executable agent tensor format; full checkpoints only from the trusted parent."""
from pathlib import Path
from whisper_repair.experiment import OFFICIAL_SMALL_SHA256, sha
from .core import validate_patch


def expected_projection(pristine, patch):
    import torch
    validate_patch(patch)
    if sha(pristine) != OFFICIAL_SMALL_SHA256: raise ValueError('Untrusted parent')
    payload=torch.load(pristine,map_location='cpu',weights_only=True)
    name=f"decoder.blocks.{patch['layer']}.attn.out.weight"
    original=payload['model_state_dict'][name].float()
    expected=original.clone(); width=payload['dims']['n_text_state']//payload['dims']['n_text_head']
    start=patch['head']*width;stop=start+width
    expected[:,start:stop]=original[:,start:stop]*patch['scale']
    return payload,name,original,expected,start,stop


def validate_projection(actual, expected):
    import numpy as np
    if actual.dtype != np.float32 or actual.shape != expected.shape or not np.isfinite(actual).all():
        raise ValueError('Projection dtype, shape or finiteness mismatch')
    if not np.array_equal(actual,expected): raise ValueError('Tensor differs from pristine-based allowed edit (stale or accumulated edit)')


def export_npz(pristine, patch, destination):
    import numpy as np
    _,_,_,expected,_,_=expected_projection(pristine,patch)
    np.savez_compressed(destination,projection=expected.numpy())


def reconstruct(pristine, patch, tensor, destination):
    import torch
    import numpy as np
    from whisper_repair.mechanistic.interventions import tensor_hash
    # Check ZIP metadata before decompressing. NPZ contains only one bounded float32 tensor.
    import zipfile
    with zipfile.ZipFile(tensor) as z:
        entries=z.infolist()
        if len(entries)!=1 or entries[0].filename!='projection.npy' or entries[0].file_size>3*1024*1024:
            raise ValueError('Unexpected tensor archive contents')
    payload,name,original,expected,start,stop=expected_projection(pristine,patch)
    with np.load(tensor,allow_pickle=False) as submitted:
        if submitted.files!=['projection']: raise ValueError('Unexpected tensor keys')
        actual=submitted['projection'];validate_projection(actual,expected.numpy())
    payload['model_state_dict'][name]=expected
    Path(destination).parent.mkdir(parents=True,exist_ok=True)
    torch.save(payload,destination)
    return dict(parameter=name, columns=[start,stop], parent_checkpoint_sha256=sha(pristine),
                tensor_artifact_sha256=sha(tensor), checkpoint_sha256=sha(destination),
                loaded_projection_sha256=tensor_hash(expected),
                actual_changed_values=int(torch.count_nonzero(original!=expected)),
                unrelated_tensors_preserved=True, bias_preserved=True,
                reconstruction='trusted pristine + validated declarative slice; no agent pickle deserialized')


def helper_source(pristine):
    """Public executable dependency, containing no grader rules, paths or private data."""
    return '''import hashlib
import json
import numpy as np
import torch
PARENT = '''+repr(str(Path(pristine).resolve()))+'''
PARENT_SHA = '''+repr(OFFICIAL_SMALL_SHA256)+'''
def export_head(layer, head, scale, destination):
    h=hashlib.sha256()
    with open(PARENT,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    if h.hexdigest()!=PARENT_SHA:raise ValueError('Parent hash changed')
    payload=torch.load(PARENT,map_location='cpu',weights_only=True)
    dims=payload['dims'];width=dims['n_text_state']//dims['n_text_head']
    w=payload['model_state_dict'][f'decoder.blocks.{layer}.attn.out.weight'].float().clone()
    w[:,head*width:(head+1)*width]*=scale
    np.savez_compressed(destination,projection=w.numpy())
'''
