import argparse
import json
from pathlib import Path
import sys
from .experiment import Experiment,save,now

parser=argparse.ArgumentParser(description='Whisper audio artifact audit; separate from agent-policy evaluation')
parser.add_argument('--runs',default='audio_runs');parser.add_argument('--dev',default='whisper_audio_dev')
sub=parser.add_subparsers(dest='command',required=True)
sub.add_parser('inspect-dev')
base=sub.add_parser('baseline');base.add_argument('--checkpoint',default='audio_models/small.pt')
edit=sub.add_parser('evaluate-edit');edit.add_argument('--checkpoint',default='audio_models/small.pt')
edit.add_argument('--layer',required=True,type=int);edit.add_argument('--head',required=True,type=int);edit.add_argument('--scale',required=True,type=float)
rank=sub.add_parser('rank-heads');rank.add_argument('--checkpoint',default='audio_models/small.pt')
sub.add_parser('freeze')
holdout=sub.add_parser('heldout');holdout.add_argument('--pack',required=True);holdout.add_argument('--checkpoint',default='audio_models/small.pt');holdout.add_argument('--resume',action='store_true')
args=parser.parse_args()
experiment=Experiment(args.runs,args.dev)
try:
    if args.command=='inspect-dev':result=experiment.inspect()
    elif args.command=='baseline':result=experiment.baseline(args.checkpoint)
    elif args.command=='evaluate-edit':result=experiment.evaluate_edit(args.checkpoint,args.layer,args.head,args.scale)
    elif args.command=='rank-heads':
        from .saliency import rank
        result=rank(experiment,args.checkpoint)
    elif args.command=='freeze':result=experiment.freeze()
    elif args.command=='heldout':result=experiment.heldout(args.pack,args.checkpoint,args.resume)
    print(json.dumps(result,indent=2))
except (OSError,ValueError,RuntimeError,ImportError) as exc:
    failure={'status':'blocked','operation':args.command,'time':now(),'error':type(exc).__name__+': '+str(exc),
             'audio_evidence':'No transcript or reproduction is implied by this infrastructure error.'}
    save(experiment.root/('blocked_'+args.command+'.json'),failure)
    print(json.dumps(failure,indent=2),file=sys.stderr)
    raise SystemExit(2)
