"""Run the existing failure-driven coding loop with Wonder and enforced isolation.

This launcher owns no scoring or promotion rules. It delegates them to neural_pr.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from neural_pr.controller import Controller
from neural_pr.sandbox import Sandbox
from neural_pr.state import State,lock,now
from ui.meta_model import WonderModel as Model
from ui.agent_config import configure
from whisper_repair.experiment import sha

ROOT=Path(__file__).resolve().parents[1]


def prepare_docker_path(candidates=None):
    """Expose the installed Desktop helper to Docker without rewriting credential settings."""
    helper='docker-credential-desktop';found=shutil.which(helper)
    if found:return dict(status='already_available',credential_helper=found)
    if candidates is None:
        candidates=[Path('/Applications/Docker.app/Contents/Resources/bin'),Path.home()/'Applications/Docker.app/Contents/Resources/bin'] if sys.platform=='darwin' else []
    for directory in map(Path,candidates):
        target=directory/helper
        if target.is_file() and os.access(target,os.X_OK):
            current=os.environ.get('PATH','');parts=[part for part in current.split(os.pathsep) if part]
            if str(directory) not in parts:parts.append(str(directory))
            os.environ['PATH']=os.pathsep.join(parts)
            return dict(status='added_to_process_path',credential_helper=str(target),docker_cli=shutil.which('docker'))
    return dict(status='helper_not_found',credential_helper=None)


def inherit_exposure(state,search_root=ROOT):
    """A new controller version does not make an old task bank fresh again."""
    bank=state.read('bank');config=state.read('experiment');consumed=state.read('consumed',{});sources=[]
    deadline=dt.datetime.fromisoformat(config['created_at'])+dt.timedelta(hours=config['deadline_hours'])
    for directory in sorted(Path(search_root).glob('.neural-pr*')):
        if directory.resolve()==state.root or not directory.is_dir():continue
        bank_path=directory/'bank.json';experiment_path=directory/'experiment.json'
        if not bank_path.exists() or not experiment_path.exists():continue
        old_bank=json.loads(bank_path.read_text());old_config=json.loads(experiment_path.read_text())
        if old_bank.get('bank_hash')!=bank['bank_hash']:continue
        path=directory/'consumed.json';old_consumed=json.loads(path.read_text()) if path.exists() else {}
        for block,record in old_consumed.items():
            consumed.setdefault(block,dict(record,exposure_imported_from=str(directory.resolve()),ineligible_as_fresh=True))
        old_deadline=dt.datetime.fromisoformat(old_config['created_at'])+dt.timedelta(hours=old_config['deadline_hours'])
        if old_deadline<deadline:
            config['created_at']=old_config['created_at'];config['deadline_hours']=old_config['deadline_hours'];deadline=old_deadline
        if old_consumed:sources.append(dict(state=str(directory.resolve()),blocks=sorted(old_consumed)))
    state.write('consumed',consumed);state.write('experiment',config)
    record=dict(sources=sources,blocks=sorted(consumed),deadline=deadline.isoformat())
    state.write('inherited_exposure',record);return record


def execute(state_root,episodes=30,reuse_preflight=False):
    configure();model=Model();state=State(state_root)
    if model.model!='muse-wonder-1.0' or model.base_url!='https://api.meta.ai/v1':
        raise ValueError('This launcher requires the approved Meta Muse Wonder model/endpoint; remove conflicting shell overrides')
    with lock(state.root/'execution.lock'):
        previous=state.read('learning_execution')
        if previous and previous.get('execution_status')=='completed':
            if previous['model']!=model.identity() or previous['launcher_sha256']!=sha(__file__):raise ValueError('Completed run has a different model/launcher identity; preserve it and use a new state')
            return previous
        record=dict(execution_id=uuid.uuid4().hex,started=now(),model=model.identity(),launcher_sha256=sha(__file__),
                    state_directory=str(state.root),steps=[],execution_status='running',
                    acceptance='Existing neural_pr gate unchanged; strict paired improvement, no task regression, equal budgets and Docker isolation')
        state.emit('learning_execution_started',execution_id=record['execution_id'],model=record['model'],launcher_sha256=record['launcher_sha256'])
        def step(name,status,**details):
            entry=dict(step=name,status=status,time=now(),**details)
            record['steps'].append(entry);state.write('learning_execution',record);state.write('executions/'+record['execution_id'],record)
            state.emit('learning_execution_step',step_name=name,status=status,details=details)
        def finish(status,**details):
            record.update(execution_status=status,finished=now(),heldout_consumed=state.read('consumed',{}),**details)
            state.write('learning_execution',record);state.write('executions/'+record['execution_id'],record);return record
        docker_path=prepare_docker_path()
        step('docker_client_environment',docker_path['status'],configuration=docker_path)
        cached=state.read('doctor') if reuse_preflight else None
        if cached and cached.get('model')!=model.identity():raise ValueError('Recorded preflight is for a different model')
        probe=cached['api'] if cached else model.probe()
        sandbox=Sandbox.doctor()
        step('model_preflight','passed' if probe.get('ready') else 'failed',result=probe,
             provenance='recorded doctor from this execution request' if cached else 'new live API request')
        if sandbox['docker_available'] and sandbox['docker_ready'] and not sandbox['image_ready']:
            directory=state.root/'execution';directory.mkdir(exist_ok=True)
            with (directory/'docker_build.log').open('w') as output:
                env={k:v for k,v in os.environ.items() if not k.endswith(('API_KEY','TOKEN'))}
                try:
                    built=subprocess.run(['docker','build','-f','Dockerfile.worker','-t','neural-pr-worker:0.1','.'],cwd=ROOT,
                                         stdout=output,stderr=output,timeout=600,env=env)
                    code=built.returncode
                except subprocess.TimeoutExpired:code=124
            step('build_worker_image','passed' if code==0 else 'failed',returncode=code,log=str(directory/'docker_build.log'))
            sandbox=Sandbox.doctor()
        else:step('build_worker_image','already_available' if sandbox['image_ready'] else 'blocked',
                  reason='Docker is absent or its daemon is unavailable' if not sandbox['image_ready'] else 'Existing worker image')
        step('enforced_isolation','passed' if sandbox['image_ready'] else 'failed',result=sandbox)
        blockers=[]
        if not probe.get('ready'):blockers.append('Meta Wonder API transport or access unavailable; no agent response obtained')
        if not sandbox['image_ready']:blockers.append('Docker worker image unavailable; existing gate requires enforced isolation')
        if blockers:
            step('coding_and_evaluation','not_run',reason='Prerequisites failed; do not consume protected tasks or invent a policy change')
            return finish('blocked_infrastructure',blockers=blockers,agent_improvement_demonstrated=False)
        controller=Controller(state.root,model=model)
        try:
            if not state.read('experiment'):
                controller.initialize('docker');step('initialize','passed')
                resume=False
            else:
                controller.validate_identity()
                if controller.sandbox.mode!='docker':raise ValueError('Cannot resume an experiment with unenforced isolation')
                step('initialize','resumed_frozen_experiment');resume=True
            exposure=inherit_exposure(state)
            step('prior_evaluation_exposure','retained',**exposure)
            # The existing loop preserves code, proposes from real failures, evaluates fresh blocks,
            # promotes only a passing hash, and stops on repeated failures, outages or its deadline.
            report=controller.run(episodes=episodes,resume=resume)
            state.write('learning_report',report)
            step('coding_and_policy_loop','complete' if report['main_task_complete'] else 'stopped_incomplete',
                 main_task_complete=report['main_task_complete'],counts=report['counts'],active_policy=report['active_agent_version'])
            if not report['main_task_complete']:
                step('final_audit','not_run',reason='Main task unfinished; preserve the final audit')
                return finish('stopped_incomplete',agent_improvement_demonstrated=False,report_path=str(state.root/'learning_report.json'))
            if 'audit' in state.read('consumed',{}) and not state.read('final_acceptance'):
                step('final_audit','not_run_exposed',reason='Audit was consumed by a prior run; a controller fix does not make it fresh')
            elif not state.read('final_acceptance'):
                audit=controller.audit();step('final_audit',audit['decision'])
            else:step('final_audit','previous_result_retained')
            report=controller.report();state.write('learning_report',report)
            return finish('completed',outcome=report['improvement_outcome'],agent_improvement_demonstrated=report['improvement_outcome']=='pilot_validated_improvement',
                          fresh_final_audit_passed=bool(report.get('final_audit',{} ) and report['final_audit']['decision']=='audit_pass'),
                          report_path=str(state.root/'learning_report.json'))
        except (OSError,ValueError,RuntimeError) as exc:
            step('controller','failed',error=str(exc))
            return finish('stopped_error',error=str(exc),agent_improvement_demonstrated=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',default=str(ROOT/'.neural-pr-wonder-v2'))
    parser.add_argument('--episodes',type=int,default=30,choices=range(1,31),metavar='1..30')
    parser.add_argument('--reuse-preflight',action='store_true',help='Use the just-recorded doctor result instead of another API request')
    args=parser.parse_args();result=execute(args.state,args.episodes,args.reuse_preflight)
    print(json.dumps(result,indent=2))
    return 0 if result['execution_status']=='completed' else 2

if __name__=='__main__':sys.exit(main())
