"""Trusted audio subprocess; requests originate from the coordinator, not shell commands."""
import contextlib
import gc
import json
from pathlib import Path
import subprocess
import sys
import time

from .core import ROOT, validate_patch, GRID
from .artifacts import export_npz,reconstruct
from whisper_repair.experiment import read, save, sha, rows, OFFICIAL_SMALL_SHA256, DECODE


def construct(request):
    patch=validate_patch(request['patch']);destination=Path(request['directory']);destination.mkdir(parents=True,exist_ok=True)
    tensor=Path(request.get('tensor') or destination/'candidate.npz')
    if not request.get('tensor'):export_npz(ROOT/'audio_models/small.pt',patch,tensor)
    info=reconstruct(ROOT/'audio_models/small.pt',patch,tensor,destination/'candidate.pt')
    smoke=request.get('fixtures',[])
    command=[sys.executable,'-m','whisper_repair.mechanistic.export_rpc']
    fresh=subprocess.run(command,input=json.dumps(dict(checkpoint=str(destination/'candidate.pt'),expected_sha256=info['checkpoint_sha256'],
                   layer=patch['layer'],fixtures=smoke)),capture_output=True,text=True,cwd=ROOT,timeout=120)
    if fresh.returncode: raise ValueError('Fresh-process load failed: '+fresh.stderr[-1000:])
    loaded=json.loads(fresh.stdout)
    if loaded['loaded_checkpoint_sha256']!=info['checkpoint_sha256'] or loaded['loaded_projection_sha256']!=info['loaded_projection_sha256'] or loaded['hooks_at_load']!=0:
        raise ValueError('Stale or mismatched checkpoint reached inference')
    matches=[]
    for fixture,result in zip(smoke,loaded['fixtures']):
        matches.append(dict(id=fixture['case_id'],passed=result['status']=='ok' and ('expected_text' not in fixture or fixture['expected_text']==result['text']),actual=result))
    if not all(x['passed'] for x in matches): raise ValueError('Reload smoke behavior differs')
    return dict(reconstruction=info,fresh_process=loaded,smoke_checks=matches)


def development(request):
    from whisper_repair.backend import Backend
    from whisper_repair.mechanistic.probes import ProbeEngine, trace_decoding
    from whisper_repair.mechanistic.interventions import head_mode
    import importlib.util
    spec=importlib.util.spec_from_file_location('strength_protocol',ROOT/'scripts/followup_head_strength.py')
    protocol=importlib.util.module_from_spec(spec);spec.loader.exec_module(protocol)
    # Local extension only, preserving the previous measured protocol files.
    import whisper_repair.mechanistic.interventions as iv
    iv.SCALES=tuple(sorted(set(iv.SCALES)|{.9,1.1,1.25}))
    backend=Backend(ROOT/'audio_models/small.pt');output=Path(request['directory']);output.mkdir(parents=True,exist_ok=True)
    if request['operation']=='probe':
        case=read(ROOT/'audio_runs/mechanistic_v1/cases'/f"{request['case_id']}.json")
        patch=validate_patch(request['patch']);engine=ProbeEngine(backend)
        before=engine.forward(case)
        after=engine.forward(case,dict(layer=patch['layer'],head=patch['head'],scale=patch['scale'],mode='hook'))
        return dict(case_id=case['case_id'],before=before,after=after,delta=after['target_logprob']-before['target_logprob'],
                    prefix_token_ids=case['prefix_token_ids'],target_position=case['target_position'],input_sha256=sha(ROOT/'audio_runs/mechanistic_v1/cases'/f"{request['case_id']}.json"))
    manifest=rows(ROOT/'whisper_audio_dev/manifest.jsonl');selected=manifest if request['operation']=='full_development' else [x for x in manifest if x['id']==request['case_id']]
    if not selected: raise ValueError('Unknown development recording')
    patch=request.get('patch');results={}
    for item in selected:
        try:
            with contextlib.ExitStack() as stack:
                if patch:
                    validate_patch(patch);stack.enter_context(head_mode(backend.model,patch['layer'],patch['head'],patch['scale'],'hook'))
                traces=stack.enter_context(trace_decoding(backend.model))
                value=backend.transcribe(ROOT/'whisper_audio_dev'/item['audio_path'])
            results[item['id']]=dict(id=item['id'],status='ok',text=value['text'],raw=value['raw'],windows=traces)
        except Exception as exc:results[item['id']]=dict(id=item['id'],status='error',error=str(exc))
        save(output/(item['id']+'.json'),results[item['id']])
    from whisper_repair.metrics import score,compare
    report=dict(results=results,score=score(selected,results))
    if request['operation']=='full_development':
        baseline={x['id']:read(ROOT/'audio_runs/mechanistic_v1/baseline'/(x['id']+'.json')) for x in manifest}
        report['comparison']=compare(manifest,baseline,results)
    return report


def protected(request):
    """All complete recordings, then a predeclared grid; never executed by a runtime agent."""
    from whisper_repair.backend import Backend
    from whisper_repair.metrics import compare,words
    from whisper_repair.mechanistic.probes import ProbeEngine,trace_decoding,build_case
    import whisper_repair.mechanistic.interventions as iv
    iv.SCALES=tuple(sorted(set(iv.SCALES)|{1.25}))
    path=Path(request['manifest']);manifest=rows(path);output=Path(request['directory']);output.mkdir(parents=True,exist_ok=True)
    results={};cases=[];attestations={}
    for condition,checkpoint in [('baseline',ROOT/'audio_models/small.pt')]+([('candidate',Path(request['candidate']))] if request.get('candidate') else []):
        backend=Backend(checkpoint);predictions={}
        from whisper_repair.mechanistic.interventions import tensor_hash
        if condition=='candidate':
            expected=request['expected_candidate']
            actual=dict(checkpoint_sha256=sha(backend.path),projection_sha256=tensor_hash(backend.model.decoder.blocks[request['patch']['layer']].attn.out.weight))
            if actual['checkpoint_sha256']!=expected['checkpoint_sha256'] or actual['projection_sha256']!=expected['loaded_projection_sha256']:raise ValueError('Protected inference loaded a stale candidate')
            attestations[condition]=actual
        else:
            if sha(backend.path)!=OFFICIAL_SMALL_SHA256:raise ValueError('Protected inference parent changed')
            attestations[condition]=dict(checkpoint_sha256=sha(backend.path))
        for item in manifest:
            try:
                with trace_decoding(backend.model,output/condition/'windows'/item['id']) as windows:
                    value=backend.transcribe(path.parent/item['audio_path'])
                predictions[item['id']]=dict(id=item['id'],status='ok',text=value['text'],raw=value['raw'],windows=windows)
                if condition=='baseline' and request.get('run_challenges',True):
                    cohort='genuine_speech' if item['kind']=='speech' else 'unsupported_lexical' if words(value['text']) else None
                    if cohort: cases.append(build_case(item,windows,backend.model,cohort,'private'))
            except Exception as exc:predictions[item['id']]=dict(id=item['id'],status='error',error=str(exc))
            save(output/condition/(item['id']+'.json'),predictions[item['id']])
        results[condition]=predictions
        del backend;gc.collect()
    measurements={}
    if request.get('run_challenges',True):backend=Backend(ROOT/'audio_models/small.pt');engine=ProbeEngine(backend)
    import random
    rng=random.Random(1729);rng.shuffle(cases)
    for challenge in (GRID if request.get('run_challenges',True) else []):
        cohort=[x for x in cases if x['cohort']==challenge['cohort']][:12]
        groups={x['manifest_record']['source_group'] for x in cohort}
        if len(groups)<3:
            measurements[challenge['id']]=dict(status='insufficient_independent_cases',groups=len(groups));continue
        values=[]
        for case in cohort:
            before=engine.forward(case);after=engine.forward(case,dict(layer=challenge['layer'],head=challenge['head'],scale=challenge['scale'],mode='hook'))
            values.append(dict(id=case['case_id'],delta=after['target_logprob']-before['target_logprob'],before=before,after=after,
                               prefix_token_ids=case['prefix_token_ids'],target_position=case['target_position']))
        measurements[challenge['id']]=dict(status='ok',mean_delta=sum(x['delta'] for x in values)/len(values),per_case=values,groups=len(groups))
        save(output/'challenges.json',measurements)
    comparison=compare(manifest,results['baseline'],results['candidate']) if 'candidate' in results else None
    transitions=[dict(id=x['id'],kind=x['kind'],baseline=results['baseline'][x['id']],candidate=results['candidate'][x['id']]) for x in manifest] if 'candidate' in results else []
    return dict(comparison=comparison,challenges=measurements,manifest_sha256=sha(path),paired_transitions=transitions,loaded_artifacts=attestations,
                complete_baseline=all(x['status']=='ok' for x in results['baseline'].values()),
                protected_recordings=len(manifest),newly_exposed_ids=[x['id'] for x in manifest])


def main():
    request=read(sys.argv[1]);started=time.monotonic()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result=construct(request) if request['operation']=='construct' else protected(request) if request['operation'] in ('protected','paired_regression') else development(request)
        import importlib.metadata
        runtime={name:importlib.metadata.version(name) for name in ('openai-whisper','torch','numpy')}
        save(sys.argv[2],dict(status='ok',result=result,elapsed=time.monotonic()-started,runtime=runtime))
    except Exception as exc:
        save(sys.argv[2],dict(status='error',error=type(exc).__name__+': '+str(exc),elapsed=time.monotonic()-started));raise

if __name__=='__main__': main()
