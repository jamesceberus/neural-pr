"""One prospective policy proposal from development protocol errors; use untouched block A.

The consumed final audit is carried forward as ineligible, never recycled.
"""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from neural_pr.controller import Controller,controller_digest
from neural_pr.sandbox import Sandbox,git
from neural_pr.state import State,digest,lock,now
from neural_pr.evaluator import GATE
from whisper_repair.experiment import sha
from ui.agent_config import configure
from ui.meta_model import WonderModel
from scripts.run_wonder_learning import ROOT,prepare_docker_path


def development_evidence(source):
    source=Path(source).resolve();state=State(source)
    consumed=state.read('consumed',{})
    if 'A' in consumed:raise ValueError('Source block A is already consumed; it cannot be a fresh confirmation')
    attempts=[state.read('attempts/'+p.stem) for p in sorted((source/'attempts').glob('*.json'))]
    main=[a for a in attempts if a.get('task_id','').startswith('main:') and a.get('objective_passed') and a.get('worker',{}).get('within_budget')]
    if not main:raise ValueError('Need a real, budget-compliant development coding episode')
    for attempt in main:
        path=source/'traces'/(attempt['run_id']+'.json');trace=json.loads(path.read_text())
        responses=[m['content'] for m in trace['messages'] if m['role']=='assistant'];failures=0
        for raw in responses:
            try:valid=isinstance(json.loads(raw),dict)
            except (ValueError,TypeError):valid=False
            failures+=not valid
        if failures:
            return dict(checks={'strict_action_json':dict(passed=False,invalid_responses=failures,total_responses=len(responses))},
                        development_code_passed=True,worker_result=attempt['worker']['result'],source_run_id=attempt['run_id'],
                        source_commit=attempt['source_commit'],agent_version=attempt['agent_version'],trace_sha256=sha(path),
                        observation='The coding worker rejected assistant responses containing narrative before a JSON action. These calls consumed budget. No hidden test, expected answer or task solution is included.',
                        scope='Observed development protocol failure despite successful software output; transfer benefit is unproven')
    raise ValueError('No observed development protocol failure; do not fabricate a learning incident')


def freeze_protocol(source,target):
    source=Path(source).resolve();target=Path(target).resolve()
    if source==target:raise ValueError('Preserve the completed source experiment; use a separate follow-up state')
    old=State(source);state=State(target);evidence=development_evidence(source)
    protocol=dict(version='development-protocol-policy-followup-v1',source_state=str(source),source_experiment_sha256=sha(source/'experiment.json'),
                  source_model=old.read('experiment')['model'],baseline=evidence['agent_version'],evidence=evidence,
                  proposal_inputs='development format-error evidence and incumbent policy only; no audit trajectories or task definitions',
                  comparison_block='A',gate=GATE,maximum_proposals=1,maximum_evaluations=1,
                  original_consumed_blocks=old.read('consumed',{}),final_audit='Unavailable: previous audit is exposed; new independent audit required',
                  claim_scope='Prospective pilot coding-policy comparison after the completed main task; not retroactive improvement of its first episode')
    existing=state.read('followup_protocol')
    if existing and existing!=protocol:raise ValueError('Frozen follow-up protocol changed; retain it and use a new state')
    if not existing:
        state.write('followup_protocol',protocol);state.emit('followup_protocol_frozen',protocol_sha256=digest(protocol))
    # Exactly one registered follow-up per source prevents a fresh --state from recycling block A.
    with lock(source/'followup_registration.lock'):
        registration=old.read('followup_registration')
        if registration and registration['state']!=str(target):raise ValueError('A follow-up is already registered for this source; resume its state instead of recycling the benchmark')
        if not registration:old.write('followup_registration',dict(state=str(target),protocol_sha256=digest(protocol),registered=now()))
    return protocol


def execute(source,target,prepare_only=False):
    protocol=freeze_protocol(source,target);state=State(target)
    if prepare_only:return dict(status='prepared_not_executed',state=str(state.root),evidence=protocol['evidence'],protocol_sha256=digest(protocol))
    with lock(state.root/'followup.lock'):
        if state.read('followup_result'):return state.read('followup_result')
        configure();prepare_docker_path();model=WonderModel()
        if model.identity()!=protocol['source_model']:raise ValueError('Keep the exact source model/adapter fixed for this procedure comparison')
        source_limits=State(source).read('experiment')
        deadline=dt.datetime.fromisoformat(source_limits['created_at'])+dt.timedelta(hours=source_limits['deadline_hours'])
        required_seconds=source_limits['evaluation_budget']['seconds']*12+120
        if (deadline-dt.datetime.now(dt.timezone.utc)).total_seconds()<required_seconds:
            return dict(status='insufficient_remaining_budget',reason='Preserve the source experiment deadline; do not start an incomplete paired comparison')
        probe=model.probe();sandbox=Sandbox.doctor()
        state.write('followup_preflight',dict(api=probe,sandbox=sandbox))
        if not probe['ready'] or not sandbox['image_ready']:
            return dict(status='blocked_infrastructure',api=probe,sandbox=sandbox,heldout_consumed=state.read('consumed',{}))
        original=Controller(source,model=model);original.validate_identity()
        controller=Controller(state.root,model=model)
        if not state.read('experiment'):controller.initialize('docker')
        with lock(state.root/'controller.lock'):
            controller.validate_identity()
            source_config=original.state.read('experiment');config=state.read('experiment')
            for key in ('model','gate','main_budget','evaluation_budget','controller_digest','environment_digest','bank_hash'):
                if source_config[key]!=config[key]:raise ValueError('Uncontrolled comparison difference: '+key)
            # Preserve every exposure BEFORE requesting a proposal or opening promotion work.
            consumed=state.read('consumed',{})
            for block,record in protocol['original_consumed_blocks'].items():
                consumed.setdefault(block,dict(record,exposure_imported_from=protocol['source_state'],ineligible_as_fresh=True))
            # The final audit may never be reopened even if the source metadata was incomplete.
            consumed.setdefault('audit',dict(reason='source final audit exposed; reserved from reuse',ineligible_as_fresh=True))
            state.write('consumed',consumed)
            if not state.read('development_import'):
                snapshot=copy.deepcopy(original.state.read('application'))
                if git(controller.checkout,'rev-list','--max-parents=0','HEAD')!=snapshot['application_base_commit']:
                    raise ValueError('Development application starter differs')
                git(controller.checkout,'fetch',str(original.checkout),snapshot['last_verified_commit'])
                git(controller.checkout,'merge','--ff-only','FETCH_HEAD')
                verified=controller.verifier.main(controller.checkout)
                if not verified['passed']:raise ValueError('Imported completed application failed its independent canary')
                snapshot.update(source_commit=snapshot['last_verified_commit'],last_verification=verified)
                state.write('application',snapshot)
                config['calibration']=dict(source_config['calibration'],imported_from=protocol['source_state'])
                config['created_at']=source_config['created_at'];config['deadline_hours']=source_config['deadline_hours']
                state.write('experiment',config)
                state.write('development_import',dict(source_commit=snapshot['last_verified_commit'],verification=verified,source_evidence_sha256=digest(protocol['evidence'])))
            if not state.read('followup_candidate'):
                if controller.store.active()!=protocol['baseline']:raise ValueError('Incumbent changed before the prospective comparison')
                if state.read('proposal_count',{'count':0})['count']:
                    raise ValueError('A proposal call was already reserved; inspect its result before retrying')
                evidence=protocol['evidence']
                incident=controller.improver.incident('Reliable structured actions under a fixed coding-call budget',evidence['source_commit'],
                    evidence['agent_version'],evidence,'development_action_protocol_failure',
                    'Software completed; protocol errors wasted calls. Any policy transfer benefit must be established on untouched coding work. Consumed audit results are excluded from proposal inputs.')
                print('Requesting one Wonder-authored policy proposal from development protocol errors.',flush=True)
                candidate=controller.improver.propose(incident)
                state.write('followup_candidate',dict(candidate_id=candidate['id'] if candidate else None))
            candidate_id=state.read('followup_candidate')['candidate_id']
            candidate=state.read('candidates/'+candidate_id) if candidate_id else None
            if not candidate or (candidate['status']!='development_checked' and not candidate.get('evaluation_id')):
                result=dict(status='no_eligible_candidate',candidate=candidate,agent_improvement_demonstrated=False,
                            heldout_consumed=state.read('consumed',{}),final_audit='not rerun; exposed')
                state.write('followup_result',result);return result
            if candidate.get('evaluation_id'):
                evaluation=state.read('evaluations/'+candidate['evaluation_id'])
            else:
                if 'A' in state.read('consumed',{}):raise ValueError('Block A was consumed by an interrupted evaluation; cannot replay it as fresh')
                print('Frozen candidate '+candidate['version']+'. Running paired block A: 12 independent coding rollouts.',flush=True)
                evaluation=controller.evaluate_candidate(candidate_id,block='A')
            final_candidate=state.read('candidates/'+candidate_id);report=controller.report()
            state.write('followup_report',report)
            result=dict(status='evaluated',candidate=final_candidate,evaluation_id=evaluation['id'],decision=evaluation['decision'],
                        counts=evaluation.get('counts'),active_policy=controller.store.active(),
                        agent_improvement_demonstrated=final_candidate['status']=='promoted' and evaluation['decision']=='pass',
                        scope=protocol['claim_scope'],final_audit='Unavailable: original audit exposed; not rerun',
                        heldout_consumed=state.read('consumed',{}),source_completed_application_preserved=True)
            state.write('followup_result',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default=str(ROOT/'.neural-pr-wonder-v1'))
    parser.add_argument('--state',default=str(ROOT/'.neural-pr-wonder-policy-v2'))
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    config=State(args.source).read('experiment',{})
    if not args.prepare_only and config.get('controller_digest')!=controller_digest():
        parser.error('The original worker was repaired after this source run. Its frozen policy-only follow-up is superseded; use scripts/run_wonder_learning.py for the new controller version. The old audit remains consumed.')
    print(json.dumps(execute(args.source,args.state,args.prepare_only),indent=2))

if __name__=='__main__':main()
