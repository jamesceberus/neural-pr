"""Independent measurements and deterministic verdicts, separate from activation."""
import json
from pathlib import Path
import shutil
import tempfile
import time

from neural_pr.sandbox import Sandbox
from neural_pr.state import State,digest,now,lock
from whisper_repair.experiment import read,save,sha,rows,OFFICIAL_SMALL_SHA256
from whisper_repair.metrics import compare,words
from .core import ROOT,Research,ISOLATION,GRID,prediction_score,validate_patch
from .runner import invoke,scaffold


def import_historical(research):
    """One real, rejected engineering sweep. Never a newly run agent episode."""
    research.task();episode_id='historical-attenuation-L4H4-S0'
    if research.state.read('episodes/'+episode_id): raise ValueError('Historical submission already imported')
    source=ROOT/'audio_runs/mechanistic_v1';summary=read(source/'summary.json');manifest=read(source/'manifest.json')
    patch=summary['patch'];parent=ROOT/'audio_models/small.pt'
    if sha(parent)!=patch['pristine_parent_sha256'] or sha(source/'export/candidate.pt')!=patch['exported_checkpoint_sha256']:
        raise ValueError('Historical checkpoint files do not match recorded hashes')
    if patch['exported_checkpoint_sha256']!='20ab6db230916b67e777d5330c6378f1ce9e27fe2a238832e7980b2e9376ccdd':raise ValueError('Unexpected historical artifact')
    for name,value in manifest['source_hashes'].items():
        if sha(source/'source'/name)!=value:raise ValueError('Historical source snapshot mismatch: '+name)
    events=State(source).events()
    confirmation=read(source/'frozen_confirmation.json')
    if confirmation['hypothesis']['predicted_direction']!='decrease_target_logprob_when_attenuated':raise ValueError('Historical prediction mismatch')
    episode=dict(id=episode_id,kind='historical_engineering_sweep',comparison_member=False,policy_version=manifest['agent_policy_version'],
                 task_version=research.task()['version'],status='submitted',within_budget=True,
                 source_application_commit=manifest['application_commit'],historical_elapsed_search_seconds=manifest['budget']['search_seconds'],
                 limitations=['Recorded engineering sweep; model API unavailable; no runtime-authored investigation',
                              'All development data exposed; not a controlled agent comparison'],imported_at=now())
    research.state.write('episodes/'+episode_id,episode)
    work=scaffold(research,episode_id,episode['policy_version'])
    declarative=dict(kind='decoder_self_attention_head_scale',layer=4,head=4,scale=0,parent_checkpoint_sha256=OFFICIAL_SMALL_SHA256)
    save(work/'patch.json',declarative)
    # Generate a safe tensor artifact from the trusted parent, then validate against the old attested projection.
    result=invoke(dict(operation='construct',patch=declarative,directory=str(work/'build'),fixtures=[]),research.root/'episodes'/episode_id/'import_build')
    if result['result']['reconstruction']['loaded_projection_sha256']!=patch['loaded_projection_sha256']:raise ValueError('Imported edit differs from historical loaded projection')
    shutil.move(work/'build/candidate.npz',work/'candidate.npz');shutil.rmtree(work/'build')
    claims=dict(predictions={},repair_prediction='strict_reduction',historical_evidence=dict(predicted_direction='decrease',
                hypothesis_id=confirmation['hypothesis']['hypothesis_id'],prospective_for_selected_confirmation=True,
                qualification='Prior development exposure; weak non-speech labels; no fresh final test'),
                limitations=episode['limitations'])
    save(work/'claims.json',claims)
    (work/'replay.py').write_text('''import json
from research_tools import export_head
patch=json.load(open('patch.json'))
export_head(patch['layer'],patch['head'],patch['scale'],'candidate.npz')
json.dump({'decision':'submit_patch','patch':patch,'checks':[{'name':'pristine-based tensor regenerated','passed':True}]},open('replay_result.json','w'))
''')
    shutil.copy2(source/'events.jsonl',work/'experiments.jsonl')
    binding={str(p.relative_to(ROOT)):sha(p) for p in [source/'manifest.json',source/'summary.json',source/'frozen_confirmation.json',source/'export_verification.json',source/'export/candidate.pt',source/'events.jsonl']}
    for folder in ('baseline','application/selected'):
        for path in sorted((source/folder).glob('*.json')):binding[str(path.relative_to(ROOT))]=sha(path)
    save(work/'historical_binding.json',binding)
    submission=dict(episode_id=episode_id,task_version=episode['task_version'],agent_policy_version=episode['policy_version'],
                    parent_checkpoint_sha256=OFFICIAL_SMALL_SHA256,code_artifact='replay.py',patch_manifest='patch.json',
                    checkpoint_artifact='candidate.npz',claims_artifact='claims.json',experiment_log='experiments.jsonl',
                    decision='submit_patch',reported_limitations=episode['limitations'],
                    reproduction=dict(entrypoint='replay.py',dependencies=['numpy','torch','openai-whisper==20250625']))
    save(work/'submission.json',submission)
    State(research.root/'episodes'/episode_id/'journal').emit('historical_import',original_events=len(events),bindings=binding,
                                                               original_hypothesis=confirmation['hypothesis'])
    research.freeze_submission(episode_id)
    return episode


def historical_measurements(research,episode_id):
    directory=research.root/'episodes'/episode_id/'frozen'
    for relative,value in read(directory/'historical_binding.json').items():
        if sha(ROOT/relative)!=value:raise ValueError('Historical evidence changed')
    source=ROOT/'audio_runs/mechanistic_v1';manifest=rows(ROOT/'whisper_audio_dev/manifest.jsonl')
    baseline={x['id']:read(source/'baseline'/(x['id']+'.json')) for x in manifest}
    candidate={x['id']:read(source/'application/selected'/(x['id']+'.json')) for x in manifest}
    comparison=compare(manifest,baseline,candidate);summary=read(source/'summary.json')
    transitions=[]
    for item in manifest:
        key=item['id'];a=baseline[key];b=candidate[key]
        transitions.append(dict(id=key,kind=item['kind'],before_status=a['status'],after_status=b['status'],
                                before_text=a.get('text'),after_text=b.get('text'),before_lexical=bool(words(a.get('text',''))),after_lexical=bool(words(b.get('text','')))))
    diagnostic=next(x for x in summary['diagnostic_table'] if x['head']=='selected' and x['cohort']=='unsupported_lexical')
    return dict(comparison=comparison,paired_transitions=transitions,diagnostic=diagnostic,controls=summary['application_table'][2:],
                prediction_contradicted=diagnostic['mean_delta']>.01,
                scope='historical exposed development only; 17 non-speech, not the older 20-case holdout')


def verify(research,episode_id,protected=False):
    task=research.task();episode=research.state.read('episodes/'+episode_id)
    if not episode:raise ValueError('Unknown episode')
    if research.state.read('verdicts/'+episode_id):raise ValueError('Verdict already recorded; cannot present rerun as fresh')
    directory=research.root/'episodes'/episode_id;started=time.monotonic()
    verdict=dict(episode_id=episode_id,started=now(),task_version=task['version'],isolation=ISOLATION,
                 repair_status='not_evaluated',prediction_status='not_evaluated',reproducibility_status='unrun',
                 protected_status='not_evaluated',repair_improvement_credit=False,agent_upgrade_status='separate coding-task gate unchanged',checks={})
    if not (directory/'frozen.json').exists():
        verdict.update(reproducibility_status='not_applicable',submission_status=episode['status'],
                       experimental_validity='incomplete_episode',efficiency=episode.get('usage',{}),error=episode.get('error'))
        research.state.write('verdicts/'+episode_id,verdict);return verdict
    try:
        frozen=research.check_frozen(episode_id);s=frozen['submission'];work=directory/'frozen';claims=read(work/s['claims_artifact'])
        if s['task_version']!=task['version'] or not frozen['budget_compliant']:raise ValueError('Task or budget mismatch')
        verdict['checks']['artifact_hashes']=True
        verdict['checks']['dependencies_declared']=s['reproduction']['dependencies']
        # Copy only public episode artifacts. No private inputs or grader modules are mounted.
        with tempfile.TemporaryDirectory(prefix='research-replay-') as temp:
            replay=Path(temp)/'work';shutil.copytree(work,replay)
            (replay/'replay_result.json').unlink(missing_ok=True)
            if s['checkpoint_artifact']:(replay/s['checkpoint_artifact']).unlink(missing_ok=True)
            result=Sandbox('local-unenforced').run([str(ROOT/'.audio-venv/bin/python'),s['reproduction']['entrypoint']],replay,timeout=task['public']['budgets']['replay_seconds'])
            save(directory/'verification/replay_process.json',result)
            if result['code']!=0:raise ValueError('Executable replay failed')
            replay_result=read(replay/'replay_result.json')
            if replay_result.get('decision')!=s['decision']:raise ValueError('Replay decision differs')
            checks=replay_result.get('checks')
            if not isinstance(checks,list) or not checks or not all(isinstance(x,dict) and isinstance(x.get('name'),str) and x.get('passed') is True for x in checks):raise ValueError('Replay must execute and record passing software checks')
            verdict['checks']['replay_software_checks']=checks
            if s['decision']=='submit_patch':
                patch=validate_patch(read(work/s['patch_manifest']))
                if replay_result.get('patch')!=patch:raise ValueError('Replay patch differs')
                # Validate regenerated tensor as well as submitted tensor using the same trusted reconstruction.
                fixtures=[]
                if episode['kind']=='historical_engineering_sweep':
                    for fixture in read(ROOT/'audio_runs/mechanistic_v1/export_verification.json')['fixtures']:
                        item=next(x for x in rows(ROOT/'whisper_audio_dev/manifest.jsonl') if x['id']==fixture['case_id'])
                        fixtures.append(dict(case_id=item['id'],path=str(ROOT/'whisper_audio_dev'/item['audio_path']),expected_text=fixture['fresh_export_text']))
                submitted=invoke(dict(operation='construct',patch=patch,tensor=str(work/s['checkpoint_artifact']),directory=str(directory/'verification/submitted'),fixtures=fixtures),directory/'verification/construct')
                reproduced=invoke(dict(operation='construct',patch=patch,tensor=str(replay/s['checkpoint_artifact']),directory=str(directory/'verification/reproduced'),fixtures=fixtures),directory/'verification/reconstruct')
                if reproduced['result']['reconstruction']['loaded_projection_sha256']!=submitted['result']['reconstruction']['loaded_projection_sha256']:raise ValueError('Replay tensor differs')
                verdict['artifact_verification']=submitted['result'];verdict['checks']['regenerated_tensor_matches']=True
                (directory/'verification/reproduced/candidate.pt').unlink()
            elif replay_result.get('patch') is not None:raise ValueError('Abstention replay produced a patch')
        verdict['reproducibility_status']='passed'
        verdict['submission_status']='valid_abstention' if s['decision']=='abstain' else 'valid_patch'
        verdict['checks']['budget_compliant']=True
        verdict['efficiency']=episode.get('usage',{'agent_tokens':None,'reason':'historical engineering run, not a model-agent episode'})
        verdict['experimental_validity']=dict(exposure_disclosed=True,isolation_enforced=False,
             compute_budget_enforced_for_trusted_tools_only=True,
             prospective_registration_events=sum(x['kind']=='hypothesis_registered' for x in State(directory/'journal').events()),
             comparable_live_episode=episode['kind']=='live_agent')
        verdict['reporting_accuracy']=dict(method='structured predictions versus measured outcomes; free-form narrative not automatically graded')
        if episode['kind']=='historical_engineering_sweep':
            measured=historical_measurements(research,episode_id);save(directory/'verification/historical_measurements.json',measured)
            replicated=invoke(dict(operation='paired_regression',manifest=str(ROOT/'whisper_audio_dev/manifest.jsonl'),
                                   directory=str(directory/'verification/exposed_regression'),run_challenges=False,
                                   candidate=str(directory/'verification/submitted/candidate.pt'),patch=patch,
                                   expected_candidate=verdict['artifact_verification']['reconstruction']),directory/'verification/exposed_regression_run',timeout=180)
            fresh=replicated['result']
            if fresh['comparison']!=measured['comparison']:raise ValueError('Historical full-application metrics did not reproduce')
            verdict['replayed_development']=dict(scope='New execution on EXPOSED development recordings; NOT fresh heldout',
                    recordings_per_checkpoint=fresh['protected_recordings'],comparison=fresh['comparison'],
                    loaded_artifacts=fresh['loaded_artifacts'],result_artifact=str(directory/'verification/exposed_regression_run/result.json'),
                    result_sha256=sha(directory/'verification/exposed_regression_run/result.json'),elapsed_seconds=replicated['elapsed'])
            verdict.update(historical_results=measured,repair_status='rejected',prediction_status='contradicted_on_exposed_confirmation',
                           protected_status='unavailable_for_historical_run',repair_improvement_credit=False)
        elif s['decision']=='abstain':verdict['repair_status']='abstained_no_credit'
        if protected:
            seal=research.state.read('comparison_seal')
            if not seal or seal['frozen_submissions'].get(episode_id)!=frozen['submission_hash']:raise ValueError('All comparison submissions must be sealed before protected evaluation')
            if task['private_spec']['status']!='registered':
                verdict['protected_status']='unavailable_no_fresh_material'
            else:
                consumed=research.state.read('protected_consumed')
                if consumed and consumed['seal_sha256']!=sha(research.root/'comparison_seal.json'):raise ValueError('Protected set already consumed by a different comparison')
                if consumed and episode_id in consumed['episodes']:raise ValueError('This evaluation was already consumed')
                manifest=Path(research.state.read('private_pointer')['manifest'])
                if sha(manifest)!=task['private_spec']['manifest_sha256']:raise ValueError('Private manifest changed')
                for row in rows(manifest):
                    if sha(manifest.parent/row['audio_path'])!=row['sha256']:raise ValueError('Private recording changed')
                ledger=consumed or dict(seal_sha256=sha(research.root/'comparison_seal.json'),episodes=[],exposed_at=now())
                ledger['episodes'].append(episode_id);research.state.write('protected_consumed',ledger)
                output=invoke(dict(operation='protected',manifest=str(manifest),directory=str(directory/'verification/protected'),
                                   candidate=str(directory/'verification/submitted/candidate.pt') if s['decision']=='submit_patch' else None,
                                   patch=patch if s['decision']=='submit_patch' else None,
                                   expected_candidate=verdict['artifact_verification']['reconstruction'] if s['decision']=='submit_patch' else None),directory/'verification/protected_run',timeout=480)
                result=output['result'];verdict['protected_status']='complete' if result['complete_baseline'] else 'incomplete_errors'
                verdict['prediction_score']=prediction_score(claims.get('predictions',{}),result['challenges'])
                verdict['prediction_status']='scored' if verdict['prediction_score']['complete'] else 'inconclusive_coverage'
                if s['decision']=='submit_patch':
                    gate=result['comparison'];verdict['protected_audio']=gate
                    verdict['repair_status']='passed_audio_gate_isolation_unenforced' if gate['gate_pass'] else 'inconclusive_zero_baseline_defects' if not gate['baseline']['nonspeech']['lexical_output_ids'] else 'rejected'
                    # This host cannot certify independent isolation; no accepted pointer changes.
                    verdict['repair_improvement_credit']=bool(gate['gate_pass'])
                empirical=research.state.read('empirical_predictor',{'predictions':{}})['predictions']
                verdict['empirical_baseline_score']=prediction_score(empirical,result['challenges'])
                verdict['no_effect_baseline_score']=prediction_score({x['id']:{'direction':'none'} for x in GRID},result['challenges'])
    except Exception as exc:
        verdict.update(error=type(exc).__name__+': '+str(exc),repair_improvement_credit=False)
        if protected and verdict['reproducibility_status']=='passed':verdict['protected_status']='incomplete_error'
        else:verdict['reproducibility_status']='failed'
    verdict.update(finished=now(),elapsed_seconds=time.monotonic()-started)
    research.state.write('verdicts/'+episode_id,verdict);research.state.emit('independent_verdict',episode_id=episode_id,verdict_sha256=sha(research.root/'verdicts'/(episode_id+'.json')))
    return verdict


def controls(research):
    import numpy as np
    from .artifacts import validate_projection
    original=np.arange(16,dtype=np.float32).reshape(4,4);expected=original.copy();expected[:,1:2]*=.5
    cases={}
    for name,actual,should_pass in [('correct_slice',expected,True),('accumulated_edit',expected.copy(),False),('stale_load',original,False),('identity',original,True)]:
        if name=='accumulated_edit':actual[:,1:2]*=.5
        target=original if name=='identity' else expected
        try:validate_projection(actual,target);accepted=True
        except ValueError:accepted=False
        cases[name]=dict(expected_valid=should_pass,observed_valid=accepted,passed=accepted==should_pass)
    fixture=[dict(id='noise',kind='nonspeech',review_required=False,reference_text=''),dict(id='speech',kind='speech',reference_text='hello world')]
    baseline={'noise':dict(status='ok',text='invented'), 'speech':dict(status='ok',text='hello world')}
    identity=compare(fixture,baseline,baseline)
    empty=compare(fixture,baseline,{key:dict(status='ok',text='') for key in baseline})
    cases['identity_no_credit']=dict(passed=not identity['gate_pass'],measurement=identity)
    cases['blanket_empty_fails_speech']=dict(passed=not empty['gate_pass'] and empty['newly_empty_speech_ids']==['speech'],measurement=empty)
    failure=compare(fixture,baseline,{'noise':dict(status='error',error='timeout'), 'speech':baseline['speech']})
    cases['inference_error_not_silence']=dict(passed=not failure['gate_pass'] and bool(failure['candidate']['errors']),measurement=failure)
    record=dict(kind='synthetic_verifier_controls_not_agent_discoveries',all_passed=all(x['passed'] for x in cases.values()),cases=cases,time=now())
    research.state.write('controls',record);return record
