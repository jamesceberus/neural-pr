import argparse
import json
from pathlib import Path
import sys
from neural_pr.state import lock
from whisper_repair.experiment import read,save,now

parser=argparse.ArgumentParser(description='Aligned, controlled Whisper self-attention investigation')
parser.add_argument('--root',default='audio_runs/mechanistic_v1')
parser.add_argument('--checkpoint',default='audio_models/small.pt')
sub=parser.add_subparsers(dest='command',required=True)
for name in ('prepare','investigate','verify-export','report','evaluate-heldout','snapshot'):sub.add_parser(name)
serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8787)
args=parser.parse_args()
try:
    if args.command=='serve':
        import uvicorn
        from .dashboard import create_app
        uvicorn.run(create_app(mi_root=args.root),host='127.0.0.1',port=args.port);raise SystemExit(0)
    if args.command=='snapshot':
        from .dashboard import snapshot
        print(snapshot(args.root));raise SystemExit(0)
    if args.command=='report':
        from .evidence import render
        render(args.root);print(str(Path(args.root)/'REPORT.md'));raise SystemExit(0)
    if args.command=='evaluate-heldout':
        # The supplied original set was already consumed in the preceding experiment. No new caller-selected paths allowed.
        if Path('audio_runs/holdout_consulted.json').exists():raise ValueError('Original audio holdout already consumed. A new independently supplied set and frozen evaluator are required; no fresh comparison was run.')
        raise ValueError('No new held-out dataset is configured. Freeze a new dataset with the trusted evaluator before running it.')
    from .controller import Investigation
    investigation=Investigation(args.root,args.checkpoint)
    with lock(Path(args.root)/'controller.lock'):
        if args.command=='prepare':result=investigation.prepare()
        elif args.command=='investigate':result=investigation.investigate()
        elif args.command=='verify-export':result=investigation.verify_export()
    print(json.dumps(result,indent=2))
except Exception as exc:
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    save(root/('failed_'+args.command+'.json'),{'time':now(),'status':'error','error':type(exc).__name__+': '+str(exc)})
    print(json.dumps({'status':'error','error':str(exc)}),file=sys.stderr);raise SystemExit(2)
