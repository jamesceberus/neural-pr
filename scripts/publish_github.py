"""Create and push a PRIVATE source repository. Never uploads local experiment state."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DIRECTORIES=('neural_pr','whisper_repair','research_eval','ui','scripts','tests','docs','.github')
FILES=('.gitignore','.dockerignore','.env.example','README.md','PROGRESS.md','pyproject.toml','requirements-tested.txt','Dockerfile.worker','CODEX_MECH_INTERP_ADDENDUM.md')
SUFFIXES={'.py','.md','.toml','.txt','.json','.html','.css','.js','.command','.yml','.yaml'}
COMMIT_MESSAGE='Add evidence-gated coding agent, Whisper investigation, UI and verified pilot report'


def command(args,cwd=ROOT,check=True):
    result=subprocess.run(args,cwd=cwd,text=True,capture_output=True)
    if check and result.returncode:raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Command failed')
    return result


def source_files(root=ROOT):
    root=Path(root);paths=[]
    for name in FILES:
        path=root/name
        if path.is_file():paths.append(path)
    for name in DIRECTORIES:
        for path in (root/name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and '.git' not in path.parts and path.suffix in SUFFIXES:paths.append(path)
    return sorted(set(paths))


def audit(paths,root=ROOT):
    root=Path(root);secrets=[];env=root/'.env'
    if env.exists():
        for line in env.read_text().splitlines():
            if '=' in line:
                key,value=line.split('=',1);value=value.strip().strip('"').strip("'")
                if key.strip().endswith(('KEY','TOKEN')) and len(value)>12:secrets.append(value)
    hashes={}
    for path in paths:
        name=str(path.relative_to(root))
        if path.is_symlink() or root.resolve() not in path.resolve().parents or path.stat().st_size>2*1024*1024:raise ValueError('Unexpected path, symlink or large file: '+name)
        content=path.read_text()
        if any(value in content for value in secrets):raise ValueError('Local credential value detected in '+name)
        if re.search(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|LLM_[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',content):
            raise ValueError('Credential-like material detected in '+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def verify_index(checkout,hashes):
    tracked=[x for x in command(['git','ls-files','-z'],checkout).stdout.split('\0') if x]
    if set(tracked)!=set(hashes):raise ValueError('Index differs from audited source manifest')
    for name,expected in hashes.items():
        result=subprocess.run(['git','show',':'+name],cwd=checkout,capture_output=True)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest()!=expected:
            raise ValueError('Staged content changed after source audit: '+name)
    return tracked


def prepare(destination=None):
    paths=source_files();hashes=audit(paths)
    checkout=Path(destination or tempfile.mkdtemp(prefix='neural-pr-publish-')).resolve()
    if destination:
        if checkout.exists() and any(checkout.iterdir()):raise ValueError('Preparation directory must be empty')
        checkout.mkdir(parents=True,exist_ok=True)
    for path in paths:
        target=checkout/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    command(['git','init','-b','main'],checkout)
    command(['git','add','--all'],checkout)
    staged=verify_index(checkout,hashes)
    command(['git','commit','-m',COMMIT_MESSAGE],checkout)
    return dict(status='prepared_not_pushed',checkout=str(checkout),commit=command(['git','rev-parse','HEAD'],checkout).stdout.strip(),
                files=len(staged),total_bytes=sum((checkout/x).stat().st_size for x in staged),private=True,source_hashes=hashes)


def publish(repo):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',repo) or repo in ('.','..'):raise ValueError('Use a repository name without owner or slashes')
    files=source_files();hashes=audit(files)
    login=command(['gh','api','user','--jq','.login']).stdout.strip()
    if not re.fullmatch(r'[A-Za-z0-9-]+',login):raise ValueError('Could not identify authenticated GitHub owner')
    full_name=login+'/'+repo
    existing=command(['gh','repo','view',full_name,'--json','nameWithOwner,isPrivate'],check=False)
    origin=command(['git','remote','get-url','origin'],check=False) if (ROOT/'.git').exists() else None
    if existing.returncode==0:
        metadata=json.loads(existing.stdout)
        if not metadata['isPrivate']:raise ValueError('Existing repository is public; this publisher only supports private repositories')
        valid_origins={f'https://github.com/{full_name}',f'https://github.com/{full_name}.git',f'git@github.com:{full_name}.git',f'ssh://git@github.com/{full_name}.git'}
        if not origin or origin.returncode or origin.stdout.strip() not in valid_origins:
            raise ValueError('Repository already exists but is not this checkout origin; choose another --repo name')
    if not (ROOT/'.git').exists():command(['git','init','-b','main'])
    already_tracked=command(['git','ls-files','-z']).stdout.split('\0')
    if set(x for x in already_tracked if x)-set(hashes):raise ValueError('Tracked files outside the audited source set; inspect before publishing')
    command(['git','add','--',*hashes.keys()])
    verify_index(ROOT,hashes)
    staged=command(['git','diff','--cached','--name-only','-z']).stdout
    if staged:command(['git','commit','-m',COMMIT_MESSAGE])
    if existing.returncode==0:command(['git','push','-u','origin','main'])
    else:
        if origin and origin.returncode==0:raise ValueError('This checkout already has an origin; refusing to replace it')
        command(['gh','repo','create',full_name,'--private','--description','Evidence-gated autonomous coding and Whisper research with independent verification','--source',str(ROOT),'--remote','origin','--push'])
    url=command(['gh','repo','view',full_name,'--json','url','--jq','.url']).stdout.strip()
    return dict(status='pushed',repository=url,private=True,commit=command(['git','rev-parse','HEAD']).stdout.strip())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',default='neural-pr')
    parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--output')
    args=parser.parse_args()
    try:result=prepare(args.output) if args.prepare_only else publish(args.repo)
    except (ValueError,RuntimeError,OSError) as exc:
        print(json.dumps(dict(status='blocked',error=str(exc)),indent=2));sys.exit(2)
    print(json.dumps(result,indent=2))
