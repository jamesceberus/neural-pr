"""Versioned Wonder transport for new coding experiments; frozen legacy adapter stays intact."""
import hashlib
import json
from pathlib import Path
import sys
import time
from neural_pr.worker import Model,InfrastructureError
from neural_pr.state import canonical
from neural_pr.sandbox import execute


def decode_response(data):
    """Return final text only. No reasoning text, credentials or raw error bodies in diagnostics."""
    metadata={'response_type':type(data).__name__}
    if not isinstance(data,dict):return {'error':'Expected a JSON response object','metadata':metadata}
    metadata['has_error']='error' in data
    choices=data.get('choices');metadata['choices_count']=len(choices) if isinstance(choices,list) else None
    if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):
        return {'error':'Response has no completion choices','metadata':metadata}
    choice=choices[0];message=choice.get('message');reason=choice.get('finish_reason')
    metadata['finish_reason']=reason if reason in ('stop','length','tool_calls','content_filter',None) else 'other'
    if not isinstance(message,dict):return {'error':'Response has no completion message','metadata':metadata}
    content=message.get('content');metadata['content_type']=type(content).__name__
    metadata['content_characters']=len(content) if isinstance(content,str) else None
    metadata['reasoning_present']=bool(message.get('reasoning_content') or message.get('reasoning'))
    metadata['refusal_present']=bool(message.get('refusal'))
    usage=data.get('usage',{});usage=usage if isinstance(usage,dict) else {}
    safe_usage={k:v for k,v in usage.items() if k in ('total_tokens','prompt_tokens','completion_tokens') and type(v) is int and v>=0}
    details=usage.get('completion_tokens_details',{})
    if isinstance(details,dict) and type(details.get('reasoning_tokens')) is int:
        safe_usage['completion_tokens_details']={'reasoning_tokens':details['reasoning_tokens']}
    metadata['usage']=safe_usage
    if reason=='length':return {'error':'Completion token budget exhausted before a complete final answer; increase its output budget','metadata':metadata,'usage':safe_usage}
    if not isinstance(content,str) or not content.strip():
        return {'error':'Response contains no final text; reasoning or refusal is not an agent action','metadata':metadata,'usage':safe_usage}
    return {'content':content,'usage':safe_usage,'metadata':metadata}


TRANSPORT=r'''
import json,sys,urllib.request,urllib.error
from ui.meta_model import decode_response
request=json.loads(sys.stdin.read())
req=urllib.request.Request(request['url'],data=json.dumps(request['payload']).encode(),headers={'Authorization':'Bearer '+request['key'],'Content-Type':'application/json'})
try:
    with urllib.request.urlopen(req,timeout=request['timeout']) as response:
        body=response.read(1500001)
        if len(body)>1500000:raise ValueError('response_too_large')
        data=json.loads(body)
    print(json.dumps(decode_response(data)))
except urllib.error.HTTPError as exc:
    print(json.dumps({'error':'Model API returned HTTP '+str(exc.code),'metadata':{'http_status':exc.code}}))
except (urllib.error.URLError,TimeoutError,OSError) as exc:
    print(json.dumps({'error':'Model API unavailable ('+type(exc).__name__+')','metadata':{'transport_error':type(exc).__name__}}))
except (ValueError,KeyError,IndexError,TypeError):
    print(json.dumps({'error':'Provider returned invalid JSON or an oversized response','metadata':{'response_parse_failed':True}}))
'''


class WonderModel(Model):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.last_metadata={}
        if self.base_url!='https://api.meta.ai/v1' or self.model!='muse-wonder-1.0':
            raise ValueError('Wonder adapter requires muse-wonder-1.0 on Meta Model API')

    def identity(self):
        return dict(super().identity(),adapter='meta-wonder-json-chat-v2',reasoning_effort='low',
                    adapter_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

    def complete(self,messages,max_tokens=5000,timeout=60):
        return self._complete(messages,max_tokens,timeout,'low')

    def _complete(self,messages,max_tokens,timeout,effort):
        if not self.key:raise InfrastructureError('No API key configured')
        payload=dict(model=self.model,messages=messages,temperature=.2,max_completion_tokens=max_tokens,
                     reasoning_effort=effort,response_format={'type':'json_object'})
        result=execute([sys.executable,'-c',TRANSPORT],timeout=max(.1,timeout),output_limit=2000000,
                       cwd=Path(__file__).resolve().parents[1],
                       input=canonical(dict(url=self.base_url+'/chat/completions',payload=payload,key=self.key,timeout=max(.1,timeout))))
        if result['code']:raise InfrastructureError('Model API transport timeout' if result['code']==124 else 'Model API transport failed')
        try:
            reply=json.loads(result['stdout']);self.last_metadata=reply.get('metadata',{})
            if 'error' in reply:raise InfrastructureError(reply['error'])
            if not isinstance(reply.get('content'),str) or not isinstance(reply.get('usage'),dict):raise ValueError()
            return reply['content'],reply['usage']
        except (ValueError,KeyError,TypeError):raise InfrastructureError('Invalid transport response') from None

    def probe(self):
        started=time.monotonic()
        try:
            content,usage=self._complete([{'role':'user','content':'Return exactly {"ready":true} as JSON.'}],1024,30,'minimal')
            try:
                parsed=json.loads(content)
                valid=isinstance(parsed,dict) and set(parsed)=={'ready'} and parsed['ready'] is True
            except (ValueError,TypeError):valid=False
            return dict(ready=valid,model=self.model,elapsed=time.monotonic()-started,usage=usage,
                        metadata=self.last_metadata,**({} if valid else {'error':'Readiness response did not match the required JSON object'}))
        except InfrastructureError as exc:
            return dict(ready=False,model=self.model,elapsed=time.monotonic()-started,error=str(exc),metadata=self.last_metadata)
