"""Check DNS and the exact existing agent adapter without revealing credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from neural_pr.worker import Model
from ui.agent_config import configure
from whisper_repair.experiment import save


def check():
    configure();model=Model();host=urlparse(model.base_url).hostname
    if model.model=='muse-wonder-1.0' and model.base_url=='https://api.meta.ai/v1':
        from ui.meta_model import WonderModel
        model=WonderModel()
    dns_code='''import json,socket,sys
try:
 socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM)
 print(json.dumps({'ready':True}))
except OSError as e:
 print(json.dumps({'ready':False,'error_type':type(e).__name__,'error':str(e)}))
'''
    try:
        dns=subprocess.run([sys.executable,'-c',dns_code,host],capture_output=True,text=True,timeout=8,
                           env={'PATH':os.environ.get('PATH',''),'PYTHONDONTWRITEBYTECODE':'1'})
        resolution=json.loads(dns.stdout) if dns.returncode==0 else dict(ready=False,error_type='resolver_process_failed')
    except subprocess.TimeoutExpired:resolution=dict(ready=False,error_type='resolver_timeout')
    result=dict(model_identity=model.identity(),credentials_present=bool(model.key),dns=resolution,
                credentials_validated=False,ready=False)
    if not resolution['ready']:
        result.update(failure_stage='dns',next_step='Run this check in an ordinary Mac Terminal outside the restricted tool shell. If DNS also fails there, check the configured hostname, VPN/proxy and DNS settings. A different API key does not fix DNS.')
    elif not model.key:
        result.update(failure_stage='credentials_missing',next_step='Set the configured provider key in the local .env file; never paste it into chat.')
    else:
        probe=model.probe();result['probe']=probe;result['ready']=probe['ready'];result['credentials_validated']=probe['ready']
        error=probe.get('error','')
        if probe['ready']:result.update(failure_stage=None,next_step='Connection works. Start a NEW frozen comparison; preserve the failed attempts.')
        elif any('HTTP '+str(code) in error for code in (401,403)):
            result.update(failure_stage='authentication_or_access',next_step='The provider is reachable. Check the provider-specific key and account/model permissions.')
        elif any('HTTP '+str(code) in error for code in (400,404,422)):
            result.update(failure_stage='endpoint_model_or_request',next_step='Check the endpoint, model ID and compatibility with the current JSON Chat Completions request. The key alone may not be the issue.')
        elif 'HTTP 429' in error:
            result.update(failure_stage='quota_or_rate_limit',next_step='Check provider quota/billing and retry limits.')
        else:result.update(failure_stage='transport_or_provider',next_step='DNS resolved, but the adapter did not complete. Check TLS, proxy/firewall, service status and the recorded HTTP error if present.')
    return result


if __name__=='__main__':
    result=check()
    if len(sys.argv)>1:
        directory=Path(sys.argv[1]).parent
        save(directory/'result.json',dict(status='ok',connection=result,result_scope='Connection preflight only; no research attempt or comparison consumed'))
    print(json.dumps(result,indent=2))
