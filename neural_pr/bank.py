"""Trusted setup authoring. This file and its reference answers NEVER enter worker context."""
import copy
import json
from pathlib import Path
from .state import atomic_json, digest

# Distinct coding defects. Only starter + public task contract are copied to a rollout.
TASKS = [
 {'id':'scope', 'block':'A', 'contract':'Implement reserve(rows,tenant,key,value). Rows are dictionaries. Reuse only matching tenant AND key with equal value. Return existing row or append {tenant,key,value}. Conflicts raise ValueError. Preserve unrelated rows.',
  'starter':"def reserve(rows, tenant, key, value):\n    for row in rows:\n        if row['key'] == key:\n            return row\n    row = dict(tenant=tenant, key=key, value=value)\n    rows.append(row)\n    return row\n",
  'correct':"def reserve(rows, tenant, key, value):\n    for row in rows:\n        if row['tenant'] == tenant and row['key'] == key:\n            if row['value'] != value: raise ValueError('conflict')\n            return row\n    row = dict(tenant=tenant,key=key,value=value)\n    rows.append(row)\n    return row\n",
  'cases':[['reserve',[[{'tenant':'a','key':'k','value':1}],'b','k',2],{'tenant':'b','key':'k','value':2}],['reserve',[[{'tenant':'a','key':'k','value':1}],'a','k',2],{'exception':'ValueError'}],['reserve',[[],'a','k',1],{'tenant':'a','key':'k','value':1}],['reserve',[[{'tenant':'a','key':'k','value':1}],'a','k',1],{'tenant':'a','key':'k','value':1}]]},
 {'id':'fencing', 'block':'A', 'contract':'Implement complete(job,token,now,value), mutating and returning job. Complete only running state, exact token, lease_until > now. Otherwise leave entire job unchanged. On accepted completion set state succeeded, result value, token and lease_until None. Values may be false/null/zero.',
  'starter':"def complete(job, token, now, value):\n    job.update(state='succeeded',result=value)\n    return job\n",
  'correct':"def complete(job, token, now, value):\n    if job['state']=='running' and job['token']==token and job['lease_until']>now:\n        job.update(state='succeeded',result=value,token=None,lease_until=None)\n    return job\n",
  'cases':[]},
 {'id':'client-errors', 'block':'A', 'contract':'Implement unwrap(status,body). For 200..299 return body unchanged, even false/null. Other statuses raise ApiError with .status and .body preserving originals. ApiError must subclass Exception.',
  'starter':"class ApiError(Exception):\n    pass\ndef unwrap(status, body):\n    return body or {}\n",
  'correct':"class ApiError(Exception):\n    def __init__(self,status,body):\n        self.status=status\n        self.body=body\n        super().__init__(str(status))\ndef unwrap(status, body):\n    if not 200 <= status < 300: raise ApiError(status,body)\n    return body\n",
  'cases':[['unwrap',[409,{'detail':'conflict'}],{'exception':'ApiError','status':409,'body':{'detail':'conflict'}}],['unwrap',[404,None],{'exception':'ApiError','status':404,'body':None}],['unwrap',[200,False],False],['unwrap',[204,None],None],['unwrap',[201,{'id':3}],{'id':3}]]},
 {'id':'recovery', 'block':'B', 'contract':'Implement recover(jobs,now) mutating and returning list. Only running jobs with lease_until <= now transition. Clear token and lease. If attempts < max_attempts queue, else fail. Preserve other fields and all other jobs. Exact expiry is expired.',
  'starter':"def recover(jobs, now):\n    return jobs\n",
  'correct':"def recover(jobs, now):\n    for j in jobs:\n        if j['state']=='running' and j['lease_until']<=now:\n            j.update(state='queued' if j['attempts']<j['max_attempts'] else 'failed',token=None,lease_until=None)\n    return jobs\n",
  'cases':[]},
 {'id':'retry-bound', 'block':'B', 'contract':'Implement fail(job,error): running job -> queued if attempts < max_attempts else failed; attempts already count claims. Save error even empty string, clear token/lease. Preserve attempts. Other states untouched. Return job.',
  'starter':"def fail(job, error):\n    job['state'] = 'queued' if job['attempts'] <= job['max_attempts'] else 'failed'\n    return job\n",
  'correct':"def fail(job,error):\n    if job['state']=='running':\n        job.update(state='queued' if job['attempts']<job['max_attempts'] else 'failed',result=error,token=None,lease_until=None)\n    return job\n",
  'cases':[]},
 {'id':'tenant-cancel', 'block':'B', 'contract':'Implement cancel(jobs,tenant,id). Return None for absent or foreign id. For own queued/running set cancelled and clear token/lease. Preserve terminal states and unrelated jobs. Return matching job.',
  'starter':"def cancel(jobs, tenant, id):\n    for j in jobs:\n        if j['id']==id:\n            j['state']='cancelled'\n            return j\n",
  'correct':"def cancel(jobs,tenant,id):\n    for j in jobs:\n        if j['id']==id and j['tenant']==tenant:\n            if j['state'] in ('queued','running'): j.update(state='cancelled',token=None,lease_until=None)\n            return j\n    return None\n",
  'cases':[]},
 {'id':'audit-schedule', 'block':'audit', 'contract':'Implement choose(jobs,tenant,now). Return id of ready queued job belonging to tenant with attempts < max_attempts and available_at <= now. Choose lowest (available_at,id). Never mutate input. Return None if none.',
  'starter':"def choose(jobs, tenant, now):\n    return jobs[0]['id'] if jobs else None\n",
  'correct':"def choose(jobs,tenant,now):\n    ready=[j for j in jobs if j['tenant']==tenant and j['state']=='queued' and j['attempts']<j['max_attempts'] and j['available_at']<=now]\n    return min(ready,key=lambda j:(j['available_at'],j['id']))['id'] if ready else None\n",
  'cases':[]},
 {'id':'audit-revision', 'block':'audit', 'contract':'Implement update(record,expected_revision,patch). If revision differs raise ValueError, without mutation. Reject patch keys id/revision/tenant via ValueError, without mutation. Otherwise return updated COPY with revision incremented once; original unchanged, including when patch empty.',
  'starter':"def update(record, expected_revision, patch):\n    record.update(patch)\n    return record\n",
  'correct':"def update(record,expected_revision,patch):\n    if record['revision']!=expected_revision or {'id','revision','tenant'} & patch.keys(): raise ValueError('conflict')\n    return dict(record,**patch,revision=record['revision']+1)\n",
  'cases':[]},
]

def job(**values):
    return dict(dict(id='one',tenant='a',state='running',attempts=1,max_attempts=3,
                     token='current',lease_until=10,result=None,available_at=0), **values)

def definitions():
    tasks = copy.deepcopy(TASKS)
    fencing = tasks[1]['cases']
    for state,token,lease,now in [('running','old',10,5),('cancelled','current',10,5),('running','current',10,10),('succeeded','current',10,5),('running','current',10,5)]:
        source=job(state=state,token='current',lease_until=lease)
        expected=copy.deepcopy(source)
        if state=='running' and token=='current' and lease>now:
            expected.update(state='succeeded',result=0,token=None,lease_until=None)
        fencing.append(['complete',[source,token,now,0],expected])
    for state,attempts,expiry in [('running',1,10),('running',3,10),('running',1,11),('cancelled',1,0),('queued',1,0)]:
        source=job(state=state,attempts=attempts,lease_until=expiry)
        expected=copy.deepcopy(source)
        if state=='running' and expiry<=10:
            expected.update(state='queued' if attempts<3 else 'failed',token=None,lease_until=None)
        tasks[3]['cases'].append(['recover',[[source],10],[expected]])
    for state,attempts,error in [('running',1,'bad'),('running',3,''),('running',4,'bad'),('cancelled',1,'bad'),('succeeded',1,'bad')]:
        source=job(state=state,attempts=attempts)
        expected=copy.deepcopy(source)
        if state=='running': expected.update(state='queued' if attempts<3 else 'failed',result=error,token=None,lease_until=None)
        tasks[4]['cases'].append(['fail',[source,error],expected])
    for tenant,state in [('a','running'),('b','running'),('a','succeeded'),('a','cancelled'),('a','queued')]:
        source=job(state=state)
        expected=copy.deepcopy(source) if tenant=='a' else None
        if tenant=='a' and state in ('running','queued'): expected.update(state='cancelled',token=None,lease_until=None)
        tasks[5]['cases'].append(['cancel',[[source],tenant,'one'],expected])
    tasks[6]['cases']=[['choose',[[job(id='foreign',tenant='b'),job(id='z',state='queued',available_at=2),job(id='a',state='queued',available_at=2)],'a',5],'a'],
        ['choose',[[job(state='queued',attempts=3)],'a',5],None],['choose',[[job(state='queued',available_at=6)],'a',5],None],
        ['choose',[[job(state='cancelled')],'a',5],None],['choose',[[],'a',5],None]]
    record={'id':'one','tenant':'a','revision':2,'value':0}
    tasks[7]['cases']=[['update',[record,1,{'value':2}],{'exception':'ValueError'}],
        ['update',[record,2,{'tenant':'b'}],{'exception':'ValueError'}],
        ['update',[record,2,{}],dict(record,revision=3)],
        ['update',[record,2,{'value':9}],dict(record,revision=3,value=9)]]
    mutants={
        'scope':("row['tenant'] == tenant and ",""),
        'fencing':("job['lease_until']>now","job['lease_until']>=now"),
        'client-errors':('200 <= status < 300','200 <= status <= 409'),
        'recovery':("j['lease_until']<=now","j['lease_until']<now"),
        'retry-bound':("job['attempts']<job['max_attempts']","job['attempts']<=job['max_attempts']"),
        'tenant-cancel':(" and j['tenant']==tenant",""),
        'audit-schedule':("j['available_at']<=now","j['available_at']<now"),
        'audit-revision':("record['revision']!=expected_revision or ",""),
    }
    # Boundary case distinguishes the schedule comparator mutant.
    tasks[6]['cases'].append(['choose',[[job(state='queued',available_at=5)],'a',5],'one'])
    for task in tasks:
        original,replacement=mutants[task['id']]
        assert original in task['correct']
        task['wrong']=task['correct'].replace(original,replacement)
    return tasks

def freeze(state):
    directory = state.root / 'private' / 'bank'
    directory.mkdir(parents=True, exist_ok=True)
    manifest=[]
    for task in definitions():
        path=directory/(task['id']+'.json')
        if path.exists() and json.loads(path.read_text()) != task:
            raise RuntimeError('Refusing to overwrite a frozen task')
        atomic_json(path,task)
        path.chmod(0o400)
        manifest.append({'id':task['id'],'block':task['block'],'hash':digest(task)})
    old=state.read('bank')
    value={'tasks':manifest,'bank_hash':digest(manifest),'verifier_version':'blackbox-v1'}
    if old and old!=value: raise RuntimeError('Bank changed after freeze')
    state.write('bank',value)
    return value

def load(state, task_id):
    task=json.loads((state.root/'private'/'bank'/(task_id+'.json')).read_text())
    item=next(x for x in state.read('bank')['tasks'] if x['id']==task_id)
    if digest(task)!=item['hash']: raise RuntimeError('Frozen task hash mismatch')
    return task

def materialize(task, directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'task.py').write_text(task['starter'])
    (directory/'TASK.md').write_text(task['contract'])
    (directory/'smoke.py').write_text('import task\nprint("module imports")\n')
    (directory/'.gitignore').write_text('__pycache__/\n*.sqlite*\n')
