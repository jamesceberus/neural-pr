"""Launch the local UI from the project root; use an unrestricted Terminal on this host."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from ui.server import create_app
from ui.agent_config import configure
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8787)
parser.add_argument('--prepare-only',action='store_true',help='Freeze a new research comparison without starting a server')
parser.add_argument('--check-agent',action='store_true',help='Test the selected agent connection without consuming an episode')
parser.add_argument('--research-root',help='Trusted comparison directory; defaults to the selected research profile')
args=parser.parse_args()
if args.research_root:os.environ['WHISPER_RESEARCH_ROOT']=str(Path(args.research_root).resolve())
configure()
if args.check_agent:
    from scripts.check_research_api import check
    result=check();print(json.dumps(result,indent=2));sys.exit(0 if result['ready'] else 2)
from research_eval.core import Research
from neural_pr.worker import Model
research=Research(os.environ['WHISPER_RESEARCH_ROOT'])
if not research.state.read('task'):research.initialize()
if not research.state.read('comparison'):research.freeze_comparison()
if research.state.read('comparison')['model']!=Model().identity():
    raise SystemExit('This comparison is frozen for another agent model. Select a new --research-root; old attempts are retained.')
research.report()
print('Research agent: '+Model().model+' · '+str(research.root),flush=True)
print('Fresh private audio: '+research.task()['private_spec']['status'],flush=True)
if args.prepare_only:sys.exit(0)
print(f'Whisper lab: http://127.0.0.1:{args.port}/research',flush=True)
uvicorn.run(create_app(),host='127.0.0.1',port=args.port)
