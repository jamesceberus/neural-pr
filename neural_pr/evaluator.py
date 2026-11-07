"""One-use held-out blocks, paired live coding runs and a frozen pilot gate."""
from dataclasses import asdict
from pathlib import Path
import tempfile
import time
import uuid
from .bank import load, materialize
from .sandbox import git, init_repository
from .state import digest, now
from .worker import Budget, Worker

GATE = {'version':'pilot-v1','attempts_per_policy_per_task':2,'max_candidates':2,
        'infrastructure_retries':1,'strictly_more_completions':True,'no_task_regression':True,
        'ties':'reject','require_enforced_isolation':True,'audit_rollouts':8}

def gate(rows, task_ids, expected_pairs=2, integrity=True):
    counts={role:{task:0 for task in task_ids} for role in ('incumbent','candidate')}
    seen=set();infrastructure=False
    for row in rows:
        key=(row['role'],row['task_id'],row['repeat'])
        if key in seen or row['role'] not in counts or row['task_id'] not in task_ids:
            return {'decision':'inconclusive','reason':'duplicate_or_unknown_pair','counts':counts}
        seen.add(key)
        if row['worker']['result']=='infrastructure_failure':infrastructure=True
        if row['worker']['within_budget'] and row['verification']['passed']:
            counts[row['role']][row['task_id']]+=1
    wanted={(role,task,repeat) for role in counts for task in task_ids for repeat in range(expected_pairs)}
    if seen!=wanted or infrastructure:
        return {'decision':'inconclusive','reason':'incomplete_or_infrastructure_failure','counts':counts}
    if not integrity:
        return {'decision':'inconclusive','reason':'isolation_integrity_unenforced','counts':counts}
    if any(not row['worker']['within_budget'] for row in rows):
        return {'decision':'reject','reason':'resource_budget_violation','counts':counts}
    if any(counts['candidate'][t]<counts['incumbent'][t] for t in task_ids):
        return {'decision':'reject','reason':'per_task_regression','counts':counts}
    if sum(counts['candidate'].values())<=sum(counts['incumbent'].values()):
        return {'decision':'reject','reason':'tie_or_no_improvement','counts':counts}
    return {'decision':'pass','reason':'strict_paired_improvement','counts':counts}

class Evaluator:
    def __init__(self,state,store,model,sandbox,verifier):
        self.state=state;self.store=store;self.model=model;self.sandbox=sandbox;self.verifier=verifier

    def evaluate(self,candidate,block,kind='promotion'):
        config=self.state.read('experiment')
        if config['gate']!=GATE:raise RuntimeError('Gate changed after freeze')
        if config['model']!=self.model.identity():raise ValueError('Model configuration differs from frozen experiment')
        if kind=='promotion' and self.state.read('final_selection'):raise ValueError('Policy selection is final; audit cannot be tuned against')
        if kind=='promotion' and block not in ('A','B'):raise ValueError('Promotions require block A or B')
        if kind=='audit' and block!='audit':raise ValueError('Audit requires reserved audit tasks')
        version=candidate['version'];parent=candidate['parent']
        self.store.get(version);self.store.get(parent)
        if kind=='promotion' and self.store.get(version)['parent']!=parent:raise ValueError('Candidate parent mismatch')
        if kind=='promotion' and parent!=self.store.active():raise ValueError('Stale candidate')
        consumed=self.state.read('consumed',{})
        if block in consumed:raise ValueError('Block already consumed; cannot reuse as fresh evidence')
        # A connectivity failure before consulting any held-out tasks does not consume a block.
        probe=self.model.probe()
        self.state.emit('evaluation_api_probe',kind_requested=kind,result=probe)
        if not probe['ready']:
            record={'id':uuid.uuid4().hex,'kind':kind,'decision':'inconclusive','reason':'model_api_unavailable',
                    'probe':probe,'candidate':version,'incumbent':parent,'rows':[],'block':None,'time':now()}
            record['record_hash']=digest(record)
            self.state.write('evaluations/'+record['id'],record)
            return record
        if kind=='audit':
            self.state.write('final_selection',{'selected':version,'baseline':parent,'time':now()})
            self.state.emit('final_policy_selected',version=version)
        identifier=uuid.uuid4().hex
        consumed[block]={'evaluation_id':identifier,'time':now()}
        self.state.write('consumed',consumed)
        self.state.emit('block_consumed',block=block,evaluation_id=identifier,kind_requested=kind)
        record={'id':identifier,'kind':kind,'candidate':version,'incumbent':parent,'block':block,
                'rows':[],'model':config['model'],'budget':config['evaluation_budget'],
                'gate':GATE,'environment_digest':self.sandbox.environment_digest(),
                'isolation':self.sandbox.mode,'time':now(),'decision':'inconclusive',
                'reason':'evaluation_interrupted','configuration_differences':['skills','context_rules']}
        self.state.write('evaluations/'+identifier,record)
        tasks=[x['id'] for x in self.state.read('bank')['tasks'] if x['block']==block]
        budget=Budget(**config['evaluation_budget'])
        worker=Worker(self.model,self.sandbox,self.state)
        started=time.monotonic()
        for task_id in tasks:
            task=load(self.state,task_id)
            for repeat in range(GATE['attempts_per_policy_per_task']):
                # Alternate order to reduce systematic time/order effects.
                roles=[('incumbent',parent),('candidate',version)]
                if repeat%2:roles.reverse()
                for role,policy_version in roles:
                    row=None
                    for infrastructure_try in range(GATE['infrastructure_retries']+1):
                        with tempfile.TemporaryDirectory(prefix='neural-pr-rollout-') as temp:
                            path=Path(temp);path.chmod(0o777);materialize(task,path)
                            base=init_repository(path)
                            run_id=uuid.uuid4().hex
                            policy=self.store.get(policy_version)
                            context=build_context(path,policy,{'objective':task['contract']},contract=task['contract'])
                            attempt={'run_id':run_id,'task_id':task_id,'application_base_commit':base,
                                     'agent_version':policy_version,'environment_digest':record['environment_digest'],
                                     'evaluator_version':self.verifier.version,'budget':asdict(budget),'start_time':now(),
                                     'evaluation_id':identifier,'role':role,'repeat':repeat,'infrastructure_try':infrastructure_try}
                            self.state.write('attempts/'+run_id,attempt)
                            self.state.emit('attempt_started',**attempt)
                            work=worker.run(run_id,path,policy,context,budget)
                            verification=self.verifier.bank(task,path)
                            diff=git(path,'diff','--no-ext-diff')
                            attempt.update(end_time=now(),result=work['result'],worker=work,verification=verification,diff=diff)
                            self.state.write('attempts/'+run_id,attempt)
                            self.state.emit('attempt_finished',run_id=run_id,result=work['result'],passed=verification['passed'])
                            row={'role':role,'task_id':task_id,'repeat':repeat,'run_id':run_id,'agent_version':policy_version,
                                 'worker':work,'verification':verification,'infrastructure_try':infrastructure_try}
                            if work['result']!='infrastructure_failure':break
                    record['rows'].append(row)
                    self.state.write('evaluations/'+identifier,record)
        outcome=gate(record['rows'],tasks,integrity=self.sandbox.mode=='docker')
        if kind=='audit':
            # Audit measures preservation and completions; it does not authorize promotion or tuning.
            counts=outcome['counts']
            valid=all(row['worker']['within_budget'] and row['worker']['result']!='infrastructure_failure' for row in record['rows'])
            complete=len(record['rows'])==len(tasks)*2*GATE['attempts_per_policy_per_task']
            preserved=all(counts['candidate'][t]>=counts['incumbent'][t] for t in tasks)
            all_final_pass=all(counts['candidate'][t]==GATE['attempts_per_policy_per_task'] for t in tasks)
            decision='audit_pass' if valid and complete and preserved and all_final_pass else 'audit_failed'
            if self.sandbox.mode!='docker' or not complete:decision='inconclusive'
            outcome={'decision':decision,'reason':'untouched_final_comparison' if self.sandbox.mode=='docker' else 'audit_isolation_integrity_unenforced','counts':counts}
        record.update(outcome,elapsed=time.monotonic()-started,end_time=now())
        record['record_hash']=digest(record)
        self.state.write('evaluations/'+identifier,record)
        self.state.emit('evaluation_finished',evaluation_id=identifier,decision=record['decision'],reason=record['reason'])
        return record

def build_context(checkout,policy,facts,contract=None):
    from .sandbox import Files, Sandbox
    from .state import canonical
    files=Files(checkout,Sandbox())
    context='FROZEN TASK CONTRACT:\n'+(contract if contract is not None else files.call('read',{'path':'TASK.md'}))+'\nTRUSTED EPISODIC STATE:\n'+canonical(facts)
    included=set(['TASK.md'])
    for pattern in policy['content']['context_rules']:
        # Only concrete paths/globs under this checkout. No host filesystem traversal.
        try:
            files.path(pattern)
            matches=sorted(Path(checkout).glob(pattern)) if '*' in pattern else [Path(checkout)/pattern]
            for path in matches:
                relative=str(path.relative_to(checkout))
                if relative not in included and path.is_file():
                    context+='\nFILE '+relative+':\n'+files.call('read',{'path':relative})[:12000]
                    included.add(relative)
                    if len(context)>26000:return context[:30000]
        except (ValueError,OSError):continue
    return context
