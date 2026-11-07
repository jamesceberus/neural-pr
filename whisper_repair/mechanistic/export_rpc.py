"""Fresh-process loader attestation and smoke transcription using the existing Backend."""
import contextlib
import json
import os
import sys
from whisper_repair.experiment import sha
request=json.loads(sys.stdin.read())
if sha(request['checkpoint'])!=request['expected_sha256']:raise ValueError('Export file identity mismatch')
with contextlib.redirect_stdout(sys.stderr):
    from whisper_repair.backend import Backend
    from .interventions import tensor_hash
    backend=Backend(request['checkpoint'])
    projection=tensor_hash(backend.model.decoder.blocks[request['layer']].attn.out.weight)
    hooks=sum(len(m._forward_hooks)+len(m._forward_pre_hooks) for m in backend.model.modules())
    fixtures=[]
    for fixture in request['fixtures']:
        try:fixtures.append({'case_id':fixture['case_id'],'status':'ok','text':backend.transcribe(fixture['path'])['text']})
        except Exception as exc:fixtures.append({'case_id':fixture['case_id'],'status':'error','error':str(exc)})
print(json.dumps({'loaded_checkpoint_sha256':sha(backend.path),'loaded_projection_sha256':projection,'hooks_at_load':hooks,
                  'fixtures':fixtures,'pid':os.getpid()}))
