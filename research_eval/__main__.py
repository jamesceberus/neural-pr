"""CLI for trusted task authoring, episodes, independent verification and comparison."""
import argparse
import json
from .core import Research,DEFAULT


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',default=str(DEFAULT))
    sub=parser.add_subparsers(dest='command',required=True)
    initialize=sub.add_parser('init');initialize.add_argument('--private-manifest')
    sub.add_parser('import-historical');sub.add_parser('controls');sub.add_parser('freeze-comparison')
    run=sub.add_parser('run-episode');run.add_argument('condition',choices=['baseline','candidate']);run.add_argument('--attempt',type=int,choices=[1,2],required=True)
    sub.add_parser('seal');verify=sub.add_parser('verify');verify.add_argument('episode_id');verify.add_argument('--protected',action='store_true')
    sub.add_parser('compare');sub.add_parser('report')
    args=parser.parse_args()
    from neural_pr.cli import load_env
    load_env();research=Research(args.root)
    if args.command=='init':
        result=research.initialize(args.private_manifest);output={'task_version':result['version'],'private_status':result['private_spec']['status']}
    elif args.command=='import-historical':
        from .verifier import import_historical
        output=import_historical(research)
    elif args.command=='controls':
        from .verifier import controls
        output=controls(research)
    elif args.command=='freeze-comparison': output=research.freeze_comparison()
    elif args.command=='run-episode':
        from .runner import run_episode
        output=run_episode(research,args.condition,args.attempt)
    elif args.command=='seal': output=research.seal()
    elif args.command=='verify':
        from .verifier import verify
        output=verify(research,args.episode_id,args.protected)
    else:
        result=research.report();output=dict(report=str(research.root/'REPORT.md'),comparison_status=result['comparison_status'],conclusion=result['conclusion'])
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
