"""Background adapter for the existing UI job manager; no threshold-changing actions."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from neural_pr.cli import load_env
from whisper_repair.experiment import read,save
from research_eval.core import Research
from research_eval.runner import run_episode
from research_eval.verifier import verify

request=read(sys.argv[1]);directory=Path(sys.argv[1]).parent;load_env();research=Research(request['research_root'])
try:
    params=request['parameters'];kind=request['kind']
    if kind=='research_episode':result=run_episode(research,params['condition'],params['attempt'])
    elif kind=='research_verify':result=verify(research,params['episode_id'])
    elif kind=='research_report':result=research.report()
    else:raise ValueError('Unknown action')
    save(directory/'result.json',dict(status='ok',result=result,result_scope='Research episode evidence; no model or policy promotion'))
except Exception as exc:
    save(directory/'result.json',dict(status='error',error=str(exc)))
    raise
finally:research.report()
