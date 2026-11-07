"""Read-only evidence audit. Never executes agents, task graders or held-out inputs."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from neural_pr.state import State,digest,now
from neural_pr.policy_store import PolicyStore
from neural_pr.evaluator import gate
from whisper_repair.experiment import read,save,sha

ROOT=Path(__file__).resolve().parents[1]


def verify(root):
    root=Path(root).resolve();state=State(root);result=state.read('followup_result')
    evaluation=state.read('evaluations/'+result['evaluation_id']);events=state.events();config=state.read('experiment')
    store=PolicyStore(state);before=store.get(evaluation['incumbent']);after=store.get(evaluation['candidate'])
    rows=evaluation['rows'];tasks=sorted({r['task_id'] for r in rows});active=state.read('active')
    recomputed=gate(rows,tasks,integrity=evaluation['isolation']=='docker')
    checks=dict(journal_hash_chain_valid=True,
        evaluation_hash_valid=digest({k:v for k,v in evaluation.items() if k!='record_hash'})==evaluation['record_hash'],
        gate_recomputed_pass=recomputed['decision']=='pass' and recomputed['counts']==evaluation['counts'],
        distinct_policy_versions=evaluation['incumbent']!=evaluation['candidate'],
        exact_parent=after['parent']==evaluation['incumbent'],
        only_skills_or_context_changed=all(before['content'][k]==after['content'][k] for k in ('tools_version','routing_version')),
        identical_model_and_environment=evaluation['model']==config['model'] and evaluation['environment_digest']==config['environment_digest'],
        active_pointer_matches_evaluation=active['version']==evaluation['candidate'] and active['evaluation_id']==evaluation['id'],
        all_rows_budget_compliant=all(r['worker']['within_budget'] for r in rows),
        no_infrastructure_failures=all(r['worker']['result']!='infrastructure_failure' for r in rows),
        twelve_complete_rows=len(rows)==12,
        audit_not_reused=state.read('consumed')['audit'].get('ineligible_as_fresh') is True and evaluation['block']=='A')
    statistics={role:dict(successes=0,attempts=0,model_calls=0,tool_calls=0,tokens=0,seconds=0.,responses=0,json_rejections=0) for role in ('incumbent','candidate')}
    per_task={};pairings={};trace_bindings={}
    for row in rows:
        attempt=state.read('attempts/'+row['run_id']);role=row['role'];s=statistics[role]
        checks['identical_budgets']=checks.get('identical_budgets',True) and attempt['budget']==evaluation['budget']
        checks['identical_row_environment']=checks.get('identical_row_environment',True) and attempt['environment_digest']==evaluation['environment_digest']
        checks['correct_policy_on_every_row']=checks.get('correct_policy_on_every_row',True) and row['agent_version']==evaluation[role]
        pairings.setdefault(row['task_id'],set()).add(attempt['application_base_commit'])
        s['attempts']+=1;s['successes']+=row['verification']['passed'];s['seconds']+=row['worker']['elapsed']
        for key in ('model_calls','tool_calls','tokens'):s[key]+=row['worker']['usage'][key]
        per_task.setdefault(row['task_id'],dict(incumbent=0,candidate=0))[role]+=row['verification']['passed']
        path=root/'traces'/(row['run_id']+'.json');trace=read(path);trace_bindings[row['run_id']]=sha(path)
        # Measure the ORIGINAL whole-string JSON parser; do not apply the later recovery fix.
        for message in trace['messages']:
            if message['role']!='assistant':continue
            s['responses']+=1
            try:valid=isinstance(json.loads(message['content']),dict)
            except (ValueError,TypeError):valid=False
            s['json_rejections']+=not valid
    checks['identical_starters']=all(len(heads)==1 for heads in pairings.values())
    proposer=[e for e in events if e['kind']=='proposer_call' and e['data']['candidate_id']==result['candidate']['id']]
    frozen=[e for e in events if e['kind']=='candidate_disposition' and e['data'].get('version')==evaluation['candidate'] and e['data']['status']=='development_checked']
    consumed=[e for e in events if e['kind']=='block_consumed' and e['data']['evaluation_id']==evaluation['id']]
    checks['proposal_frozen_before_protected_work']=bool(proposer and frozen and consumed and proposer[0]['sequence']<frozen[0]['sequence']<consumed[0]['sequence'])
    canary=[e for e in events if e['kind']=='canary_checked' and e['data']['candidate_id']==result['candidate']['id']]
    checks['application_canary_passed']=bool(canary and canary[-1]['data']['verification']['passed'])
    protocol=state.read('followup_protocol');source=Path(protocol['source_state'])
    archive=read(source/'frozen_source_before_worker_fix.json');directory=source/'frozen_source_before_worker_fix'
    checks['original_controller_archive_matches']=archive['controller_digest']==config['controller_digest'] and all(sha(directory/name)==value for name,value in archive['files'].items())
    checks['gate_source_unchanged']=sha(ROOT/'neural_pr/evaluator.py')==archive['files']['neural_pr/evaluator.py']
    checks['source_development_evidence_bound']=sha(source/'traces'/(protocol['evidence']['source_run_id']+'.json'))==protocol['evidence']['trace_sha256']
    pairs=[]
    for task in tasks:
        for repeat in (0,1):
            pair={row['role']:row['verification']['passed'] for row in rows if row['task_id']==task and row['repeat']==repeat}
            pairs.append(pair)
    summary=dict(verified=all(checks.values()),scope='Pilot agent-authored policy improvement under the ORIGINAL strict JSON worker',
        state=str(root),evaluation_id=evaluation['id'],model=evaluation['model'],original_controller_digest=config['controller_digest'],
        incumbent=evaluation['incumbent'],candidate=evaluation['candidate'],active_policy=active['version'],
        policy_change=after['content']['skills'][len(before['content']['skills']):],checks=checks,statistics=statistics,per_task=per_task,
        paired_transitions=dict(candidate_only=sum(p['candidate'] and not p['incumbent'] for p in pairs),incumbent_only=sum(p['incumbent'] and not p['candidate'] for p in pairs),both_pass=sum(p['candidate'] and p['incumbent'] for p in pairs)),
        candidate_frozen_before_block_consultation=checks['proposal_frozen_before_protected_work'],
        final_audit='Unavailable; consumed original audit was excluded',
        current_parser_fix='Subsequent human-authored engineering change; this result does not validate the policy under the repaired parser',
        subsequent_main_work_under_promoted_policy='Not demonstrated',
        artifact_hashes=dict(evaluation=sha(root/'evaluations'/(evaluation['id']+'.json')),candidate_package=sha(root/'policies'/(evaluation['candidate']+'.json')),journal=sha(root/'events.jsonl'),traces=trace_bindings),verified_at=now())
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--state',default=str(ROOT/'.neural-pr-wonder-policy-v2'))
    args=parser.parse_args();summary=verify(args.state);destination=ROOT/'research_runs/policy_upgrade_verified/summary.json';save(destination,summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('artifact_hashes','checks')},indent=2))
    if not summary['verified']:print(json.dumps(summary['checks'],indent=2));sys.exit(1)
