import argparse
import json
import os
from pathlib import Path
import sys
from .controller import Controller
from .evaluator import gate
from .sandbox import Sandbox
from .state import lock, now
from .worker import Model

def load_env(path='.env'):
    source=Path(path)
    if source.exists():
        for line in source.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key,value=line.split('=',1)
                if key.strip() in ('MODEL_API_KEY','GEMINI_API_KEY','NEURAL_PR_API_KEY','NEURAL_PR_BASE_URL','NEURAL_PR_MODEL'):
                    os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))

def controls(controller):
    """Synthetic gate control + actual application restore. Never a live model result."""
    state=controller.state
    with lock(state.root/'controller.lock'):
        controller.validate_identity()
        before=controller.store.active()
        version=controller.store.create(dict(controller.store.get(before)['content'],
            skills=controller.store.get(before)['content']['skills']+['Record failed hypotheses before selecting another approach.']),parent=before)
        rejected=False
        try:controller.store.promote(version,'missing-control-evidence')
        except ValueError:rejected=True
        rows=[{'role':role,'task_id':task,'repeat':repeat,'worker':{'result':'submitted','within_budget':True},
               'verification':{'passed':True}} for role in ('incumbent','candidate') for task in ('control-1','control-2','control-3') for repeat in range(2)]
        tied=gate(rows,['control-1','control-2','control-3'])
        record={'label':'SYNTHETIC NEGATIVE CONTROL — not autonomous discovery, not live evaluation',
                'policy_version':version,'diff':controller.store.diff(before,version),'status':'rejected_control',
                'tie_gate':tied,'unapproved_activation_rejected':rejected,'active_unchanged':controller.store.active()==before,'time':now()}
        state.write('controls/rejection',record)
        state.emit('negative_control',label=record['label'],reason='tied score rejected and unevaluated activation denied')
        # Exercise source and ephemeral fixture restoration while preserving prior work on a diagnostic branch.
        (controller.checkout/'DEMO_DIAGNOSTIC.txt').write_text('Labeled demo fixture: preserved on diagnostic branch before rollback.\n')
        (controller.checkout/'demo.sqlite').write_text('disposable fixture')
        restored=controller._rollback_application('labeled demo: actual application rollback')
        recovered=controller.recover()
        record.update(application_rollback_commit=restored,resume_smoke_passed=recovered['milestones']['smoke'],
                      fixture_removed=not (controller.checkout/'demo.sqlite').exists())
        state.write('controls/rejection',record)
        return record

def main(argv=None):
    parser=argparse.ArgumentParser(description='Neural PR: trusted coding and policy-evaluation runner')
    parser.add_argument('--state',default='.neural-pr',help='Private local artifacts; never publish this directory')
    sub=parser.add_subparsers(dest='command',required=True)
    doc=sub.add_parser('doctor');doc.add_argument('--probe-api',action='store_true')
    init=sub.add_parser('init-demo');init.add_argument('--isolation',choices=['docker','local-unenforced'],default='local-unenforced')
    for name in ('run','resume'):
        item=sub.add_parser(name);item.add_argument('--episodes',type=int,default=3)
    evaluate=sub.add_parser('evaluate-candidate');evaluate.add_argument('candidate_id');evaluate.add_argument('--block',choices=['A','B'])
    sub.add_parser('rollback-agent');sub.add_parser('rollback-application')
    sub.add_parser('audit');sub.add_parser('report')
    demo=sub.add_parser('demo');demo.add_argument('--exercise-controls',action='store_true',help='Labeled synthetic rejection plus actual restart/rollback')
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8787)
    args=parser.parse_args(argv);load_env()
    try:
        controller=Controller(args.state)
        if args.command=='doctor':
            model=Model();result={'python':sys.version.split()[0],'git':__import__('shutil').which('git'),
                                 'model':model.identity(),'credential_present':bool(model.key),'sandbox':Sandbox.doctor()}
            if args.probe_api:result['api']=model.probe()
            controller.state.write('doctor',result)
            controller.state.emit('doctor_completed',result='ready' if result.get('api',{}).get('ready') else 'api_not_verified')
        elif args.command=='init-demo':result=controller.initialize(args.isolation)
        elif args.command in ('run','resume'):
            if not 1<=args.episodes<=30:raise ValueError('Episodes must be between 1 and 30')
            result=controller.run(args.episodes,resume=args.command=='resume')
        elif args.command=='evaluate-candidate':
            with lock(controller.state.root/'controller.lock'):
                controller.validate_identity();result=controller.evaluate_candidate(args.candidate_id,args.block)
        elif args.command=='rollback-agent':result={'active':controller.rollback_agent()}
        elif args.command=='rollback-application':result={'application_commit':controller.rollback_application()}
        elif args.command=='audit':result=controller.audit()
        elif args.command=='report':result=controller.report()
        elif args.command=='demo':
            if args.exercise_controls:controls(controller)
            result=controller.report();result['labeled_controls']=controller.state.read('controls/rejection')
        elif args.command=='serve':
            import uvicorn
            from .app import create_app
            uvicorn.run(create_app(args.state),host='127.0.0.1',port=args.port)
            return 0
        print(json.dumps(result,indent=2))
        return 0
    except (ValueError,RuntimeError,OSError) as exc:
        print(json.dumps({'error':str(exc)},indent=2),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
