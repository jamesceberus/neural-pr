"""Trusted black-box tests: expected outputs stay in parent, outside task filesystem."""
import json
import tempfile
from pathlib import Path
from .bank import load, materialize
from .state import digest

# Public transport only; zero expected answers. Input/output cross the sandbox boundary.
BANK_RPC = r'''
import copy,json,sys
import task
results=[]
for name,args in json.loads(sys.stdin.read()):
    before=copy.deepcopy(args)
    try:
        value=getattr(task,name)(*args)
        results.append({'value':value,'args':args,'unchanged':args==before})
    except Exception as exc:
        result={'exception':type(exc).__name__}
        for key in ('status','body'):
            if hasattr(exc,key):result[key]=getattr(exc,key)
        results.append({'value':result,'args':args,'unchanged':args==before})
print(json.dumps(results))
'''

MAIN_RPC = r'''
import concurrent.futures,contextlib,json,sys,tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from jobservice.store import Store
from jobservice.api import create_app
from jobservice.client import Client
from jobservice.worker import tick
import httpx
results=[]
def resolve(x):
    if isinstance(x,str) and x.startswith('#'):
        idx,field=x[1:].split('.',1)
        return results[int(idx)][field]
    if isinstance(x,dict):return {k:resolve(v) for k,v in x.items()}
    if isinstance(x,list):return [resolve(v) for v in x]
    return x
request=json.loads(sys.stdin.read())
commands=request['commands'] if isinstance(request,dict) else request
fixture=request.get('fixture') if isinstance(request,dict) else None
with (contextlib.nullcontext(fixture) if fixture else tempfile.TemporaryDirectory()) as temp:
    path=Path(temp)/'jobs.sqlite'
    store=Store(path)
    api=TestClient(create_app(path))
    for raw in commands:
        command=resolve(raw);op=command.pop('op')
        try:
            if op=='api':
                if 'job_id' in command:command['url']=command['url'].format(job_id=command.pop('job_id'))
                r=api.request(**command);value={'status':r.status_code,'body':r.json()}
            elif op=='restart':
                store=Store(path);api=TestClient(create_app(path));value=True
            elif op=='parallel-submit':
                def one(_):return Store(path).submit(**command)
                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:value=list(pool.map(one,range(6)))
            elif op=='parallel-claim':
                def one(_):return Store(path).claim(**command)
                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:value=list(pool.map(one,range(6)))
            elif op=='tick':
                fail=command.pop('fail',False)
                def execute(payload):
                    if fail: raise RuntimeError('deliberate task failure')
                    return payload
                value=tick(path,execute,**command)
            elif op=='client':
                def handle(request):
                    response=api.request(request.method,request.url.path,headers=request.headers,content=request.content)
                    return httpx.Response(response.status_code,json=response.json(),request=request)
                client=Client('http://task','a',transport=httpx.MockTransport(handle))
                action=command.pop('action');value=getattr(client,action)(**command);client.close()
            else:value=getattr(store,op)(**command)
            results.append(value)
        except Exception as exc:
            value={'exception':type(exc).__name__}
            if hasattr(exc,'response'):value.update(status=exc.response.status_code,body=exc.response.json())
            results.append(value)
print(json.dumps(results))
'''

class Verifier:
    version='blackbox-v1'
    def __init__(self,sandbox): self.sandbox=sandbox

    def rpc(self, checkout, script, commands):
        result=self.sandbox.run(['python','-u','-c',script],checkout,timeout=15,input=json.dumps(commands))
        if result['code']:
            raise RuntimeError('Task process failed: '+result['stderr'][-1600:])
        try:return json.loads(result['stdout'].splitlines()[-1])
        except (ValueError,IndexError) as exc: raise RuntimeError('Invalid task protocol') from exc

    def bank(self,task,checkout):
        try:
            output=self.rpc(checkout,BANK_RPC,[[name,args] for name,args,expected in task['cases']])
            checks=[]
            for (name,args,expected),actual in zip(task['cases'],output):
                passed=actual['value']==expected
                if task['id'] in ('audit-schedule','audit-revision'):passed=passed and actual['unchanged']
                checks.append(bool(passed))
            return {'passed':len(output)==len(task['cases']) and all(checks),
                    'checks':checks,'total':len(task['cases']),'passed_checks':sum(checks)}
        except Exception as exc:
            return {'passed':False,'checks':[],'error':str(exc),'total':len(task['cases']),'passed_checks':0}

    def main(self,checkout):
        out={}
        def test(name,commands,check):
            try:
                values=self.rpc(checkout,MAIN_RPC,commands)
                assert check(values), 'observable contract violated'
                out[name]={'passed':True}
            except Exception as exc:out[name]={'passed':False,'error':str(exc)}
        submit={'op':'submit','tenant':'a','key':'k','payload':{'x':1},'max_attempts':2}
        get={'op':'get','tenant':'a','job_id':'#0.id'}
        claim={'op':'claim','now':0,'lease_seconds':10}
        finish={'op':'finish','job_id':'#0.id','token':'#1.token','now':1,'result':0}
        headers={'X-Tenant':'a','Idempotency-Key':'k'}
        test('smoke',[{'op':'api','method':'GET','url':'/health'},submit,
              {'op':'get','tenant':'other','job_id':'#1.id'}, {'op':'api','method':'GET','url':'/jobs/missing','headers':headers},
              {'op':'api','method':'POST','url':'/jobs','headers':headers,'json':{'payload':{},'max_attempts':0}},
              {'op':'client','action':'get','job_id':'missing'},
              {'op':'api','method':'POST','url':'/jobs','json':{'payload':{}}}],
             lambda v:v[0]=={'status':200,'body':{'status':'ok'}} and v[1]['state']=='queued' and v[2] is None and v[3]['status']==404 and v[4]['status']==422 and v[5]['status']==404 and v[6]['status']==422)
        test('idempotency',[submit,{'op':'restart'},submit,dict(submit,tenant='b'),dict(submit,payload={'x':2}),dict(submit,max_attempts=3),
             {'op':'client','action':'submit','key':'k','payload':{'x':2}},
             {'op':'parallel-submit','tenant':'c','key':'race','payload':{'z':2}},
             {'op':'api','method':'POST','url':'/jobs','headers':headers,'json':{'payload':{'x':2}}}],
             lambda v:v[0]['id']==v[2]['id'] and v[3]['id']!=v[0]['id'] and v[4].get('exception')=='ValueError' and v[5].get('exception')=='ValueError'
             and v[6].get('status')==409 and v[6]['body']=={'detail':'idempotency_conflict'} and len({x['id'] for x in v[7]})==1 and v[8]=={'status':409,'body':{'detail':'idempotency_conflict'}})
        test('execution',[submit,claim,dict(finish,error=''),get,claim,
             dict(finish,token='#4.token',error='bad'),get,claim],
             lambda v:v[1]['attempts']==1 and v[2] is True and v[3]['state']=='queued' and v[3]['token'] is None
             and v[4]['attempts']==2 and v[4]['token']!=v[1]['token'] and v[5] is True and v[6]['state']=='failed' and v[6]['attempts']==2 and v[7] is None)
        test('atomic_claim',[submit,{'op':'parallel-claim','now':0,'lease_seconds':10}],
             lambda v:sum(x is not None for x in v[1])==1)
        test('fencing',[submit,claim,dict(finish,token='wrong'),dict(finish,now=10),get,finish,get],
             lambda v:v[2] is False and v[3] is False and v[4]['state']=='running' and v[5] is True and v[6]['state']=='succeeded' and json.loads(v[6]['result'])==0 and v[6]['token'] is None)
        test('recovery',[submit,claim,{'op':'restart'},{'op':'recover','now':10},get,dict(claim,now=10),
             dict(finish,now=11),dict(finish,token='#5.token',now=11),get],
             lambda v:v[3]==1 and v[4]['state']=='queued' and v[5]['attempts']==2 and v[6] is False and v[7] is True and v[8]['state']=='succeeded')
        test('recovery_exhausted',[dict(submit,max_attempts=1),claim,{'op':'recover','now':10},get,claim],
             lambda v:v[2]==1 and v[3]['state']=='failed' and v[3]['token'] is None and v[4] is None)
        test('cancellation',[submit,claim,{'op':'cancel','tenant':'b','job_id':'#0.id'},
             {'op':'cancel','tenant':'a','job_id':'#0.id'},finish,{'op':'recover','now':100},get,
             {'op':'cancel','tenant':'a','job_id':'#0.id'},claim,
             {'op':'api','method':'POST','url':'/jobs/missing/cancel','headers':headers}],
             lambda v:v[2] is None and v[3]['state']=='cancelled' and v[3]['token'] is None and v[4] is False and v[5]==0 and v[6]['state']=='cancelled' and v[7]['state']=='cancelled' and v[8] is None and v[9]['status']==404)
        test('integrated_worker',[submit,{'op':'tick','now':0,'fail':True},get,{'op':'restart'}, {'op':'tick','now':1},get,
             {'op':'cancel','tenant':'a','job_id':'#0.id'},get],
             lambda v:v[1]==v[0]['id'] and v[2]['state']=='queued' and v[4]==v[0]['id'] and v[5]['state']=='succeeded' and v[5]['attempts']==2 and json.loads(v[5]['result'])=={'x':1} and v[6]['state']=='succeeded' and v[7]['state']=='succeeded')
        test('api_client_cancellation',[submit,claim,
             {'op':'api','method':'POST','url':'/jobs/{job_id}/cancel','job_id':'#0.id','headers':{'X-Tenant':'b'}},
             {'op':'api','method':'POST','url':'/jobs/{job_id}/cancel','job_id':'#0.id','headers':headers},
             {'op':'client','action':'get','job_id':'#0.id'},finish,
             {'op':'client','action':'cancel','job_id':'#0.id'},claim,
             {'op':'client','action':'cancel','job_id':'missing'}],
             lambda v:v[2]=={'status':404,'body':{'detail':'job_not_found'}} and v[3]['status']==200 and v[3]['body']['state']=='cancelled'
             and v[4]['state']=='cancelled' and v[5] is False and v[6]['state']=='cancelled' and v[7] is None and v[8]['status']==404)
        test('canonical_payload',[dict(submit,payload={'a':1,'b':2}),dict(submit,payload={'b':2,'a':1}),
             claim,dict(finish,token='#2.token'),submit,dict(submit,payload={'a':1,'b':2})],
             lambda v:v[0]['id']==v[1]['id'] and v[4].get('exception')=='ValueError' and v[5]['id']==v[0]['id'] and v[5]['state']=='succeeded')
        for index,value in enumerate((False,None,0)):
            test('success_value_'+str(index),[submit,claim,dict(finish,result=value),get],
                 lambda v,value=value:v[2] is True and v[3]['state']=='succeeded' and json.loads(v[3]['result'])==value)
        test('worker_restart',[submit,claim,{'op':'restart'},{'op':'tick','now':10},get,dict(finish,now=11)],
             lambda v:v[3]==v[0]['id'] and v[4]['state']=='succeeded' and v[4]['attempts']==2 and v[5] is False)
        # Two separate OS processes share only SQLite, ensuring module globals cannot fake restart durability.
        try:
            with tempfile.TemporaryDirectory(dir=checkout,prefix='.verify-restart-') as fixture:
                Path(fixture).chmod(0o777)
                relative=Path(fixture).name
                first=self.rpc(checkout,MAIN_RPC,{'fixture':relative,'commands':[submit,claim]})
                job_id=first[0]['id'];old_token=first[1]['token']
                second=self.rpc(checkout,MAIN_RPC,{'fixture':relative,'commands':[
                    {'op':'get','tenant':'a','job_id':job_id},{'op':'recover','now':10},dict(claim,now=10),
                    {'op':'finish','job_id':job_id,'token':old_token,'now':11,'result':'stale'},
                    {'op':'finish','job_id':job_id,'token':'#2.token','now':11,'result':{'recovered':True}},
                    {'op':'get','tenant':'a','job_id':job_id}]})
                assert second[0]['state']=='running' and second[1]==1 and second[2]['attempts']==2
                assert second[3] is False and second[4] is True and second[5]['state']=='succeeded'
                assert json.loads(second[5]['result'])=={'recovered':True}
                out['process_restart']={'passed':True}
        except Exception as exc:out['process_restart']={'passed':False,'error':str(exc)}
        # Aggregate milestones contain prerequisite slices; never lose earlier verified work.
        groups={'smoke':['smoke'],'idempotency':['idempotency','canonical_payload'],'execution':['execution','atomic_claim','fencing','success_value_0','success_value_1','success_value_2'],
                'recovery':['recovery','recovery_exhausted','worker_restart','process_restart'],'cancellation':['cancellation','api_client_cancellation','integrated_worker']}
        milestones={name:all(out[x]['passed'] for x in names) for name,names in groups.items()}
        return {'passed':all(milestones.values()),'milestones':milestones,'checks':out,'verifier_version':self.version}

    def prevalidate(self,state):
        results=[]
        for item in state.read('bank')['tasks']:
            task=load(state,item['id'])
            with tempfile.TemporaryDirectory(prefix='neural-pr-prevalidate-') as temp:
                path=Path(temp);path.chmod(0o777);materialize(task,path)
                bad=self.bank(task,path)
                (path/'task.py').write_text(task['correct'])
                good=self.bank(task,path)
                # Relevant wrong implementation: original defect plus a syntactically valid no-op.
                (path/'task.py').write_text(task['wrong'])
                wrong=self.bank(task,path)
                valid=not bad['passed'] and good['passed'] and not wrong['passed']
                results.append({'task':task['id'],'starter':bad,'reference':good,'wrong':wrong,'valid':valid})
        record={'passed':all(x['valid'] for x in results),'results':results,'verifier_version':self.version}
        state.write('prevalidation',record)
        return record
