"""Single trusted owner of attempts, checkpoints, evaluation and policy activation."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
from .bank import freeze
from .evaluator import Evaluator, GATE, build_context
from .improver import Improver
from .policy_store import PolicyStore
from .sandbox import Sandbox, commit, git, init_repository
from .state import State, digest, lock, now
from .verifier import Verifier
from .worker import Budget, Model, Worker

MILESTONES=['smoke','idempotency','execution','recovery','cancellation']

def controller_digest():
    root=Path(__file__).parent
    return digest({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(root.glob('*.py'))})

class Controller:
    def __init__(self,root='.neural-pr',model=None):
        self.state=State(root);self.store=PolicyStore(self.state);self.model=model or Model()
        experiment=self.state.read('experiment',{})
        self.sandbox=Sandbox(experiment.get('isolation','local-unenforced'))
        self.verifier=Verifier(self.sandbox)
        self.evaluator=Evaluator(self.state,self.store,self.model,self.sandbox,self.verifier)
        self.improver=Improver(self.state,self.store,self.model)
        self.checkout=self.state.root/'application'

    def initialize(self,isolation='local-unenforced'):
        with lock(self.state.root/'controller.lock'):
            if self.state.read('experiment'):
                self.validate_identity();return self.report()
            self.sandbox=Sandbox(isolation);self.verifier=Verifier(self.sandbox)
            self.evaluator=Evaluator(self.state,self.store,self.model,self.sandbox,self.verifier)
            if isolation=='docker' and not Sandbox.doctor()['image_ready']:
                raise RuntimeError('Build the Docker worker image first')
            baseline=self.store.initialize()
            freeze(self.state)
            prevalidation=self.verifier.prevalidate(self.state)
            if not prevalidation['passed']:raise RuntimeError('Evaluation bank prevalidation failed; see private artifact')
            template=Path(__file__).parent/'templates'
            if self.checkout.exists():raise ValueError('Uninitialized application directory exists; preserve it and use a fresh --state directory')
            shutil.copytree(template,self.checkout,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            self.checkout.chmod(0o777)
            (self.checkout/'.gitignore').write_text('__pycache__/\n*.sqlite*\n')
            base=init_repository(self.checkout)
            smoke=self.sandbox.run(['python','smoke.py'],self.checkout)
            if smoke['code']:raise RuntimeError('Starter smoke failed: '+smoke['stderr'])
            verification=self.verifier.main(self.checkout)
            if not verification['milestones']['smoke']:raise RuntimeError('Starter smoke contract failed')
            experiment={'created_at':now(),'baseline':baseline,'model':self.model.identity(),
                        'gate':GATE,'evaluation_budget':asdict(Budget()),
                        'main_budget':asdict(Budget(seconds=300,model_calls=18,tool_calls=24,tokens=160000)),
                        'task_contract':(template/'TASK.md').read_text(),'controller_digest':controller_digest(),'environment_digest':self.sandbox.environment_digest(),
                        'isolation':isolation,'bank_hash':self.state.read('bank')['bank_hash'],
                        'deadline_hours':7,'max_repeated_failure':3,'calibration':'pending_live_development_episode'}
            self.state.write('experiment',experiment)
            snapshot={'application_base_commit':base,'source_commit':base,'last_verified_commit':base,
                      'verified_milestones':['smoke'],'last_verification':verification,'unfinished':MILESTONES[1:],
                      'fixture_state':{'strategy':'fresh disposable database per verifier process','persistent_external_effects':False},
                      'blocker':None,'unsuccessful_attempts':[],'next_action':'Implement idempotency across persistence, API and client'}
            self.state.write('application',snapshot)
            self.state.emit('initialized',application_commit=base,agent_version=baseline,isolation=isolation,
                            bank_hash=experiment['bank_hash'],controller_digest=experiment['controller_digest'])
            return self.report()

    def validate_identity(self):
        experiment=self.state.read('experiment')
        if not experiment:raise ValueError('Run init-demo first')
        if experiment['controller_digest']!=controller_digest():raise RuntimeError('Trusted controller changed after freeze; use a new experiment state')
        if experiment['environment_digest']!=self.sandbox.environment_digest():raise RuntimeError('Environment identity changed; use a new experiment state')
        if experiment['model']!=self.model.identity():raise RuntimeError('Worker model/endpoint changed after freeze; use a new experiment state')
        self.state.events();self.store.active()
        snapshot=self.state.read('application')
        if git(self.checkout,'rev-parse','--show-toplevel')!=str(self.checkout):raise RuntimeError('Repository identity mismatch')
        if git(self.checkout,'rev-list','--max-parents=0','HEAD')!=snapshot['application_base_commit']:raise RuntimeError('Application root commit mismatch')
        git(self.checkout,'cat-file','-e',snapshot['last_verified_commit']+'^{commit}')
        return snapshot

    def recover(self):
        snapshot=self.validate_identity()
        for path in (self.state.root/'attempts').glob('*.json') if (self.state.root/'attempts').exists() else []:
            attempt=json.loads(path.read_text())
            if not attempt.get('end_time'):
                attempt.update(end_time=now(),result='interrupted')
                self.state.write('attempts/'+attempt['run_id'],attempt)
                self.state.emit('attempt_recovered',run_id=attempt['run_id'],result='interrupted')
        # All services/fixtures are ephemeral. No worker daemon survives an episode.
        if git(self.checkout,'status','--porcelain'):
            source=commit(self.checkout,'Preserve interrupted episode on resume')
            snapshot['source_commit']=source
            self.state.write('application',snapshot)
        smoke=self.sandbox.run(['python','smoke.py'],self.checkout)
        verification=self.verifier.main(self.checkout)
        lost=[x for x in snapshot['verified_milestones'] if not verification['milestones'][x]]
        if smoke['code'] or lost:
            self._rollback_application('resume regression')
            verification=self.verifier.main(self.checkout)
            if not all(verification['milestones'][x] for x in snapshot['verified_milestones']):
                raise RuntimeError('Verified application checkpoint no longer passes')
        active=self.state.read('active')
        events=self.state.events()
        if active.get('evaluation_id') and not any(e['kind']=='policy_promoted' and e['data'].get('evaluation_id')==active['evaluation_id'] for e in events):
            self.state.emit('policy_promotion_recovered',version=active['version'],evaluation_id=active['evaluation_id'])
        self.state.emit('resume_verified',application_commit=git(self.checkout,'rev-parse','HEAD'),
                        agent_version=self.store.active(),smoke_passed=not smoke['code'])
        return verification

    def _rollback_application(self,reason):
        snapshot=self.state.read('application')
        diagnostic=commit(self.checkout,'Diagnostic preservation before application rollback')
        branch='diagnostic/'+uuid.uuid4().hex[:12]
        git(self.checkout,'branch',branch,diagnostic)
        git(self.checkout,'reset','--hard',snapshot['last_verified_commit'])
        # Fixture state is disposable by contract; remove local ephemeral databases/caches as well as source rollback.
        for path in self.checkout.rglob('*'):
            if path.is_file() and (path.name.endswith(('.sqlite','.sqlite-wal','.sqlite-shm')) or '.pyc'==path.suffix):path.unlink()
        snapshot['source_commit']=snapshot['last_verified_commit']
        snapshot['blocker']=None
        self.state.write('application',snapshot)
        self.state.emit('application_rolled_back',commit=snapshot['last_verified_commit'],diagnostic_branch=branch,
                        preserved_commit=diagnostic,reason=reason,fixtures='recreated empty disposable databases')
        return snapshot['last_verified_commit']

    def rollback_application(self):
        with lock(self.state.root/'controller.lock'):
            self.validate_identity();return self._rollback_application('operator')

    def rollback_agent(self):
        with lock(self.state.root/'controller.lock'):
            self.validate_identity();return self.store.rollback()

    def episode(self):
        snapshot=self.validate_identity()
        if not snapshot['unfinished']:return {'result':'already_complete'}
        objective=snapshot['unfinished'][0]
        policy_version=self.store.active();policy=self.store.get(policy_version)
        identifier=uuid.uuid4().hex
        experiment=self.state.read('experiment')
        facts={'objective':objective,'milestones':snapshot['verified_milestones'],
               'source_commit':snapshot['source_commit'],'last_trusted_tests':snapshot['last_verification'],
               'blocker':snapshot['blocker'],'unsuccessful_attempts':snapshot['unsuccessful_attempts'][-3:],
               'next_action':snapshot['next_action'],
               'recent_diff':git(self.checkout,'diff',snapshot['last_verified_commit'],'HEAD')[-8000:]}
        attempt={'run_id':identifier,'task_id':'main:'+objective,'application_base_commit':git(self.checkout,'rev-parse','HEAD'),
                 'agent_version':policy_version,'environment_digest':experiment['environment_digest'],
                 'evaluator_version':self.verifier.version,'budget':experiment['main_budget'],'start_time':now()}
        self.state.write('attempts/'+identifier,attempt);self.state.emit('attempt_started',**attempt)
        work=Worker(self.model,self.sandbox,self.state).run(identifier,self.checkout,policy,
                  build_context(self.checkout,policy,facts,contract=experiment['task_contract']),Budget(**experiment['main_budget']))
        source=commit(self.checkout,'Runtime episode '+identifier+' ('+work['result']+')')
        verification=self.verifier.main(self.checkout)
        lost=[x for x in snapshot['verified_milestones'] if not verification['milestones'][x]]
        passed=not lost and verification['milestones'][objective] and work['within_budget']
        attempt.update(end_time=now(),result='verified_progress' if passed else work['result'],
                       worker=work,verification=verification,source_commit=source,objective_passed=passed)
        self.state.write('attempts/'+identifier,attempt)
        self.state.emit('attempt_finished',run_id=identifier,result=attempt['result'],objective_passed=passed,
                        application_commit=source,agent_version=policy_version)
        snapshot.update(source_commit=source,last_verification=verification)
        if passed:
            # Only dependency-ordered milestones advance, and all previously completed checks must remain valid.
            for milestone in MILESTONES:
                if verification['milestones'][milestone]:
                    if milestone not in snapshot['verified_milestones']:snapshot['verified_milestones'].append(milestone)
                else:break
            snapshot['last_verified_commit']=source;snapshot['blocker']=None
        else:
            snapshot['blocker']=work.get('error') or ('regression: '+','.join(lost) if lost else 'Unresolved '+objective)
            snapshot['unsuccessful_attempts'].append({'run_id':identifier,'objective':objective,'result':work['result'],'commit':source})
        snapshot['unfinished']=[x for x in MILESTONES if x not in snapshot['verified_milestones']]
        snapshot['next_action']='Complete '+snapshot['unfinished'][0] if snapshot['unfinished'] else 'Run final integrated acceptance and untouched audit'
        self.state.write('application',snapshot)
        if experiment['calibration']=='pending_live_development_episode' and work['usage']['model_calls'] and work['result']!='infrastructure_failure':
            experiment['calibration']={'run_id':identifier,'elapsed':work['elapsed'],'usage':work['usage'],
                                       'decision':'retain predeclared evaluation budgets','frozen_before_blocks':not bool(self.state.read('consumed',{}))}
            self.state.write('experiment',experiment)
        incident=None
        if not passed:
            incident=self.improver.incident(objective,source,policy_version,verification,
                'infrastructure_failure' if work['result']=='infrastructure_failure' else 'regression' if lost else 'no_verified_progress',
                'Future milestones are expected unfinished; proposal evidence concerns only the attempted milestone or regression.')
        elif work['usage'].get('protocol_errors',0):
            incident=self.improver.incident(objective,source,policy_version,
                {'checks':{'action_protocol':{'passed':False,'rejected_responses':work['usage']['protocol_errors']}},
                 'application_verification':verification,'usage':work['usage']},
                'protocol_failure_with_verified_progress',
                'Software progress is verified. Rejected action responses wasted calls; any transferable policy benefit must pass independent coding evaluation.')
        if lost:self._rollback_application('episode regression')
        return {'attempt':attempt,'incident':incident}

    def evaluate_candidate(self,candidate_id,block=None):
        candidate=self.state.read('candidates/'+candidate_id)
        if not candidate or candidate['status']!='development_checked':raise ValueError('Candidate must pass preflight/development scope checks')
        if self.state.read('experiment')['calibration']=='pending_live_development_episode':
            raise ValueError('Calibrate one live development episode before opening held-out work')
        consumed=self.state.read('consumed',{})
        block=block or next((x for x in ('A','B') if x not in consumed),None)
        if not block:raise ValueError('No fresh promotion block remains')
        evaluation=self.evaluator.evaluate(candidate,block)
        candidate.update(status='heldout_evaluated',evaluation_id=evaluation['id'])
        self.state.write('candidates/'+candidate_id,candidate)
        if evaluation['decision']=='pass':
            self.store.promote(candidate['version'],evaluation['id'])
            candidate['status']='promoted'
            canary=self.verifier.main(self.checkout)
            baseline=self.state.read('application')['verified_milestones']
            if any(not canary['milestones'][x] for x in baseline):
                self.store.rollback('canary_failure; trigger is not causal proof')
                candidate['status']='rejected';candidate['reason']='canary rollback trigger; no causal claim'
            self.state.emit('canary_checked',candidate_id=candidate_id,verification=canary)
        else:candidate['status']='rejected' if evaluation['decision']=='reject' else 'inconclusive'
        candidate['reason']=evaluation['reason'];self.state.write('candidates/'+candidate_id,candidate)
        return evaluation

    def run(self,episodes=3,resume=False):
        with lock(self.state.root/'controller.lock'):
            self.validate_identity()
            if resume:self.recover()
            current=self.state.read('application')
            objective=current['unfinished'][0] if current['unfinished'] else None
            previous=current['unsuccessful_attempts']
            repeated=0
            for old in reversed(previous):
                if old['objective']!=objective or old['result']=='infrastructure_failure':break
                repeated+=1
            if repeated>=3:
                self.state.emit('run_stopped',reason='persisted repeated_failure_limit; requires a new approach')
                return self.report()
            for _ in range(episodes):
                experiment=self.state.read('experiment')
                import datetime as dt
                age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(experiment['created_at'])).total_seconds()
                if age>experiment['deadline_hours']*3600:
                    self.state.emit('run_stopped',reason='seven_hour_experiment_deadline');break
                outcome=self.episode()
                if outcome.get('result')=='already_complete':break
                attempt=outcome['attempt']
                if attempt['worker']['result']=='infrastructure_failure':
                    self.state.emit('proposal_disposition',incident_id=outcome['incident']['id'],disposition='unsupported_infrastructure_failure',reason='Restore model connectivity; no evidence for a reusable policy change')
                    self.state.emit('run_stopped',reason='infrastructure_unavailable; do not repeat identical API failures');break
                repeated=0 if attempt['objective_passed'] else repeated+1
                incident=outcome['incident']
                if incident and not self.state.read('final_selection'):
                    candidate=self.improver.propose(incident)
                    if candidate and candidate['status']=='development_checked':self.evaluate_candidate(candidate['id'])
                if repeated>=3:
                    self.state.emit('run_stopped',reason='repeated_failure_limit; requires a concrete new approach');break
            return self.report()

    def audit(self):
        with lock(self.state.root/'controller.lock'):
            self.validate_identity()
            selected=self.store.active()
            selection=self.state.read('final_selection')
            if selection and selection['selected']!=selected:raise ValueError('Final policy selection already frozen')
            result=self.evaluator.evaluate({'version':selected,'parent':self.state.read('experiment')['baseline']},'audit',kind='audit')
            if result['decision']=='audit_failed' and self.state.read('active').get('previous'):
                self.store.rollback('final audit failure; stop tuning')
            self.state.write('final_acceptance',self.verifier.main(self.checkout))
            return result

    def report(self):
        events=self.state.events()
        def records(name):
            directory=self.state.root/name
            return [json.loads(p.read_text()) for p in sorted(directory.glob('*.json'))] if directory.exists() else []
        attempts=records('attempts');evaluations=records('evaluations');candidates=records('candidates')
        promotions=sum(e['kind']=='policy_promoted' for e in events)
        rollbacks=sum(e['kind']=='policy_rolled_back' for e in events)
        app=self.state.read('application',{})
        experiment=self.state.read('experiment',{})
        total={'model_calls':0,'tool_calls':0,'tokens':0,'elapsed':0.0}
        for attempt in attempts:
            worker=attempt.get('worker',{})
            for key in ('model_calls','tool_calls','tokens'):total[key]+=worker.get('usage',{}).get(key,0)
            total['elapsed']+=worker.get('elapsed',0)
        total['token_usage_status']='provider_reported_or_conservative_bound' if all(a.get('worker',{}).get('usage',{}).get('usage_reported',True) for a in attempts) else 'unavailable_for_failed_api_requests'
        total['proposer_calls']=sum(e['kind']=='proposer_call' for e in events)
        total['proposer_tokens']=sum(e['data'].get('usage',{}).get('total_tokens',0) for e in events if e['kind']=='proposer_call')
        return {'name':'Neural PR','main_task_complete':not bool(app.get('unfinished',True)),
                'improvement_outcome':'pilot_validated_improvement' if promotions and not rollbacks else 'no_validated_improvement',
                'active_agent_version':self.state.read('active',{}).get('version'),
                'application':app,'model':experiment.get('model'),'isolation':experiment.get('isolation','unknown'),
                'integrity_enforced':experiment.get('isolation')=='docker',
                'counts':{'promotions':promotions,'rejections':sum(c['status']=='rejected' for c in candidates),
                          'rollbacks':rollbacks,'application_rollbacks':sum(e['kind']=='application_rolled_back' for e in events),
                          'incidents':len(records('incidents')),'attempts':len(attempts),'evaluation_rollouts':sum(len(e['rows']) for e in evaluations)},
                'usage':total,'experiment_created_at':experiment.get('created_at'),'evaluation_overhead_seconds':sum(e.get('elapsed',0) for e in evaluations),
                'consumed_blocks':self.state.read('consumed',{}),'evaluations':evaluations,'candidates':candidates,
                'attempts':[{k:v for k,v in a.items() if k not in ('diff',)} for a in attempts],
                'incidents':records('incidents'),'final_audit':next((e for e in reversed(evaluations) if e['kind']=='audit'),None),
                'final_acceptance':self.state.read('final_acceptance'),'event_count':len(events),
                'labeled_controls':self.state.read('controls/rejection'),'prevalidation':{'passed':self.state.read('prevalidation',{}).get('passed')},
                'limitation':'Pilot evidence only; local fallback does not enforce grader/process secrecy or integrity.' if experiment.get('isolation')!='docker' else 'Docker denies host mounts and network; host administrator remains trusted.'}
