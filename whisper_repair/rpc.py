"""Local original-Whisper process; JSONL transport separates model logs from raw results."""
import argparse
import contextlib
import importlib.metadata
import json
import sys

parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--threads',type=int,default=4)
args=parser.parse_args()
try:
    with contextlib.redirect_stdout(sys.stderr):
        from .backend import Backend
        model=Backend(args.checkpoint,'openai',args.threads)
    print(json.dumps({'ready':True,'torch_version':importlib.metadata.version('torch'),
                      'whisper_version':importlib.metadata.version('openai-whisper')}),flush=True)
except Exception as exc:
    print(json.dumps({'ready':False,'error':type(exc).__name__+': '+str(exc)}),flush=True);raise SystemExit(2)
for line in sys.stdin:
    try:
        request=json.loads(line)
        with contextlib.redirect_stdout(sys.stderr):result=model.transcribe(request['path'])
        print(json.dumps({'status':'ok',**result}),flush=True)
    except Exception as exc:
        print(json.dumps({'status':'error','error':type(exc).__name__+': '+str(exc)}),flush=True)
