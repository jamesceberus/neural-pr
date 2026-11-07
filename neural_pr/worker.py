"""Bounded, fresh-context runtime coding-model loop. No controller tools exposed."""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import time
import re
import urllib.error
import urllib.request
from .sandbox import Files
from .state import canonical, now

@dataclass(frozen=True)
class Budget:
    seconds: int = 150
    model_calls: int = 10
    tool_calls: int = 16
    tokens: int = 80000
    output_tokens: int = 5000

class InfrastructureError(RuntimeError):
    pass


ACTION_PROTOCOL = 'single-action-json-v2'


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key')
        result[key]=value
    return result


def _finite_json(_):
    raise ValueError('Non-finite JSON values are not allowed')


def parse_json_object(raw):
    """Decode one complete object, optionally wrapped in bounded prose or a JSON fence.

    Never scan past an earlier object/array, guess a truncated object, select among
    multiple actions, or treat arbitrary JSON in a narrative as executable code.
    """
    if not isinstance(raw,str):raise ValueError('Action response must be text')
    text=raw.strip();mode='strict'
    if text.startswith('```'):
        fence=re.fullmatch(r'```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```',text,re.IGNORECASE)
        if not fence:raise ValueError('Expected exactly one complete JSON fence')
        text=fence.group(1).strip();mode='fenced'
        if not text.startswith('{'):raise ValueError('Expected one action object')
    elif not text.startswith('{'):
        start=text.find('{')
        if start<0 or start>1024 or any(c in text[:start] for c in '[]}`'):
            raise ValueError('Expected one unambiguous action object')
        text=text[start:];mode='preamble'
    decoder=json.JSONDecoder(object_pairs_hook=_unique_object,parse_constant=_finite_json)
    action,end=decoder.raw_decode(text)
    if text[end:].strip():raise ValueError('Only one action is permitted; trailing text or additional actions are rejected')
    if not isinstance(action,dict):raise ValueError('Expected one action object')
    return action,mode


def parse_action(raw):
    """Validate the complete action before any file tool can run."""
    action,mode=parse_json_object(raw)
    if 'done' in action:
        if set(action)-{'done','summary'} or action['done'] is not True:
            raise ValueError('Done must be true and cannot be combined with a tool')
        if 'summary' in action and (not isinstance(action['summary'],str) or len(action['summary'])>3000):
            raise ValueError('Summary must be bounded text')
        return action,mode
    if set(action)-{'tool','arguments'} or action.get('tool') not in ('list','read','write','check'):
        raise ValueError('Unknown action or tool')
    arguments=action.get('arguments',{})
    if not isinstance(arguments,dict):raise ValueError('Tool arguments must be an object')
    tool=action['tool'];allowed={'list':set(),'read':{'path'},'write':{'path','content'},'check':{'path'}}[tool]
    if set(arguments)-allowed or (tool in ('read','write') and set(arguments)!=allowed):raise ValueError('Tool argument schema mismatch')
    if 'path' in arguments and (not isinstance(arguments['path'],str) or not 0<len(arguments['path'])<=4096 or '\0' in arguments['path']):
        raise ValueError('Path must be bounded text')
    if tool=='write' and (not isinstance(arguments['content'],str) or len(arguments['content'])>100000):raise ValueError('Write exceeds file budget')
    return dict(action,arguments=arguments),mode


class Model:
    def __init__(self, base_url=None, model=None, key=None):
        self.base_url=(base_url or os.environ.get('NEURAL_PR_BASE_URL','https://api.meta.ai/v1')).rstrip('/')
        self.model=model or os.environ.get('NEURAL_PR_MODEL','muse-spark-1.3')
        provider_key=os.environ.get('GEMINI_API_KEY') if 'generativelanguage.googleapis.com' in self.base_url else os.environ.get('MODEL_API_KEY')
        self.key=key or os.environ.get('NEURAL_PR_API_KEY') or provider_key
        if not self.base_url.startswith('https://') and not self.base_url.startswith(('http://127.0.0.1:','http://localhost:')):
            raise ValueError('Use HTTPS or a loopback endpoint')

    def identity(self):
        return {'base_url':self.base_url,'model':self.model,'adapter':'json-chat-v1','temperature':0.2}

    def complete(self, messages, max_tokens=5000, timeout=60):
        if not self.key: raise InfrastructureError('No API key configured')
        payload={'model':self.model,'messages':messages,'temperature':0.2,'max_tokens':max_tokens,
                 'response_format':{'type':'json_object'}}
        # The API transport runs in a killable trusted subprocess: socket timeouts alone do not bound a dribbling response.
        import sys
        from .sandbox import execute
        transport = r"""
import json,sys,urllib.request,urllib.error
request=json.loads(sys.stdin.read())
req=urllib.request.Request(request['url'],data=json.dumps(request['payload']).encode(),
    headers={'Authorization':'Bearer '+request['key'],'Content-Type':'application/json'})
try:
    with urllib.request.urlopen(req,timeout=request['timeout']) as response:
        data=json.loads(response.read(1500000))
    print(json.dumps({'content':data['choices'][0]['message']['content'],'usage':data.get('usage',{})}))
except urllib.error.HTTPError as exc:
    print(json.dumps({'error':'Model API returned HTTP '+str(exc.code)}))
except (urllib.error.URLError,TimeoutError,OSError) as exc:
    print(json.dumps({'error':'Model API unavailable ('+type(exc).__name__+')'}))
except (ValueError,KeyError,IndexError,TypeError):
    print(json.dumps({'error':'Malformed model API response'}))
"""
        result=execute([sys.executable,'-c',transport],timeout=max(0.1,timeout),output_limit=2000000,
            input=canonical({'url':self.base_url+'/chat/completions','payload':payload,'key':self.key,'timeout':max(0.1,timeout)}))
        if result['code']:
            raise InfrastructureError('Model API transport timeout' if result['code']==124 else 'Model API transport failed')
        try:
            data=json.loads(result['stdout'])
            if 'error' in data:raise InfrastructureError(data['error'])
            if not isinstance(data['content'],str):raise ValueError('Expected text content')
            return data['content'],data['usage']
        except (ValueError,KeyError,TypeError):
            raise InfrastructureError('Malformed model API response') from None

    def probe(self):
        started=time.monotonic()
        try:
            content,usage=self.complete([{'role':'user','content':'Return exactly {"ready":true} as JSON.'}],max_tokens=1024,timeout=30)
            try:
                value=json.loads(content)
                ready=isinstance(value,dict) and set(value)=={'ready'} and value['ready'] is True
            except (ValueError,TypeError):ready=False
            return {'ready':ready,'model':self.model,'elapsed':time.monotonic()-started,'usage':usage,
                    **({} if ready else {'error':'Readiness response must be exactly the required JSON object'})}
        except InfrastructureError as exc:
            return {'ready':False,'model':self.model,'elapsed':time.monotonic()-started,'error':str(exc)}

SYSTEM = '''You are the runtime coding worker. Complete the task contract in the isolated checkout.
Your selected immutable policy applies for this entire attempt. Never access hidden graders or controller state.
Respond with exactly ONE JSON object per turn, no markdown. Supported actions:
{"tool":"list","arguments":{}}
{"tool":"read","arguments":{"path":"relative/file.py"}}
{"tool":"write","arguments":{"path":"relative/file.py","content":"entire file content"}}
{"tool":"check","arguments":{"path":"smoke.py"}}
{"done":true,"summary":"what changed and unfinished work"}
Use public development tests as needed. Your assertions are not trusted acceptance results.
Start your reply with { and end it with }. Put any final explanation in the done summary.
Do not prepend progress updates, repeat an action, or send more than one action in a reply.
Do not spend the episode only explaining. Edit source and check the integrated callers.
'''

class Worker:
    def __init__(self,model,sandbox,state):self.model=model;self.sandbox=sandbox;self.state=state

    def run(self,run_id,checkout,policy,context,budget):
        start=time.monotonic();files=Files(checkout,self.sandbox)
        messages=[{'role':'system','content':SYSTEM+'\nPOLICY:\n'+canonical(policy['content'])},
                  {'role':'user','content':context}]
        counts={'model_calls':0,'tool_calls':0,'tokens':0,'prompt_tokens':0,'completion_tokens':0,'usage_reported':True,
                'action_recoveries':0,'protocol_errors':0}
        responses=[]
        result='budget_exhausted';summary='';error=None
        while counts['model_calls']<budget.model_calls and time.monotonic()-start<budget.seconds:
            remaining=budget.seconds-(time.monotonic()-start)
            # UTF-8 bytes conservatively reserve input tokens; provider-reported usage remains separately recorded.
            reserve=len(canonical(messages).encode())+budget.output_tokens+128
            if counts['tokens']+reserve>budget.tokens:break
            counts['model_calls']+=1
            try:
                raw,usage=self.model.complete(messages,budget.output_tokens,min(remaining,60))
            except InfrastructureError as exc:
                result='infrastructure_failure';error=str(exc);counts['usage_reported']=False
                self.state.emit('model_call_failed',run_id=run_id,call=counts['model_calls'],error=error)
                break
            reported=usage.get('total_tokens')
            used=reported if isinstance(reported,int) else reserve
            counts['tokens']+=used
            counts['prompt_tokens']+=usage.get('prompt_tokens',0)
            counts['completion_tokens']+=usage.get('completion_tokens',0)
            counts['usage_reported']=counts['usage_reported'] and reported is not None
            self.state.emit('model_call',run_id=run_id,call=counts['model_calls'],usage=usage,
                            accounted_tokens=used,model=self.model.model)
            response={'call':counts['model_calls'],'raw_content':raw};responses.append(response)
            context_added=False
            try:
                action,mode=parse_action(raw);response.update(validation_status='accepted',format=mode)
                # Keep exact provider output in the trace. Replay canonical actions to avoid
                # reinforcing a progress preamble that the provider emitted despite JSON mode.
                messages.append({'role':'assistant','content':canonical(action)});context_added=True
                if mode!='strict':
                    counts['action_recoveries']+=1
                    self.state.emit('worker_action_normalized',run_id=run_id,call=counts['model_calls'],format=mode,
                                    raw_sha256=hashlib.sha256(raw.encode()).hexdigest(),protocol=ACTION_PROTOCOL)
                if action.get('done') is True:
                    result='submitted';summary=str(action.get('summary',''))[:3000];break
                if counts['tool_calls']>=budget.tool_calls:break
                counts['tool_calls']+=1
                remaining=budget.seconds-(time.monotonic()-start)
                if remaining<=0:break
                reply=files.call(action['tool'],action.get('arguments',{}),timeout=min(20,remaining))
                self.state.emit('worker_tool',run_id=run_id,tool=action['tool'],
                                path=action.get('arguments',{}).get('path'),result=str(reply)[:1500])
            except (ValueError,KeyError,OSError,TypeError) as exc:
                if not context_added:
                    counts['protocol_errors']+=1;response.update(validation_status='rejected',error=type(exc).__name__)
                    messages.append({'role':'assistant','content':raw})
                reply={'tool_error':type(exc).__name__+': '+str(exc)[:600]}
                if not context_added:reply['required_format']='Return exactly one JSON action object. No progress text, trailing text, multiple actions or duplicate keys.'
                self.state.emit('worker_tool_error',run_id=run_id,error=reply)
            messages.append({'role':'user','content':canonical(reply)[:30000]})
        elapsed=time.monotonic()-start
        if elapsed>budget.seconds or counts['tokens']>budget.tokens:result='budget_exhausted'
        record={'result':result,'summary':summary,'error':error,'usage':counts,'elapsed':elapsed,
                'action_protocol':ACTION_PROTOCOL,
                'within_budget':elapsed<=budget.seconds+0.25 and counts['tokens']<=budget.tokens and counts['tool_calls']<=budget.tool_calls and counts['model_calls']<=budget.model_calls}
        self.state.write('traces/'+run_id,{'messages':messages,'model_responses':responses,'record':record})
        return record
