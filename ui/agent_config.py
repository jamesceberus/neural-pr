"""Research-only preference; historical coding-controller configuration stays frozen."""
import json
import os
from pathlib import Path
from neural_pr.cli import load_env

ROOT=Path(__file__).resolve().parents[1]


def configure():
    profile=json.loads((Path(__file__).parent/'agent_profile.json').read_text())
    # Explicit caller environment wins; the legacy .env still provides credentials.
    explicit={key:os.environ[key] for key in ('NEURAL_PR_BASE_URL','NEURAL_PR_MODEL','WHISPER_RESEARCH_ROOT') if key in os.environ}
    load_env(ROOT/'.env')
    os.environ['NEURAL_PR_BASE_URL']=explicit.get('NEURAL_PR_BASE_URL',profile['base_url'])
    os.environ['NEURAL_PR_MODEL']=explicit.get('NEURAL_PR_MODEL',profile['model'])
    os.environ['WHISPER_RESEARCH_ROOT']=str(Path(explicit.get('WHISPER_RESEARCH_ROOT',str(ROOT/profile['research_root']))).resolve())
    return profile
