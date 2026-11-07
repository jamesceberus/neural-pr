"""Trusted registry, artifact contract and comparison ledger. Reuses existing gates."""
import json
import math
from pathlib import Path
import shutil
import tempfile
import time
import uuid

from neural_pr.state import State, canonical, digest, lock, now
from neural_pr.policy_store import PolicyStore
from whisper_repair.experiment import read, save, sha, rows, DECODE, GATE, OFFICIAL_SMALL_SHA256
from whisper_repair.metrics import compare

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'research_runs'
SCALES = (0, .25, .5, .75, .9, 1, 1.1, 1.25)
BUDGET = dict(seconds=600, model_calls=16, tool_calls=32, tokens=120000,
              output_tokens=4000, whisper_evaluations=160, replay_seconds=60)
ISOLATION = 'local-unenforced; process timeout and sanitized environment; host filesystem secrecy/integrity NOT enforced'
GRID = [dict(id=f'L4H4S{s}-{cohort}', layer=4, head=4, scale=s, cohort=cohort,
             template='first_baseline_lexical_or_first_reference_token_v1')
        for s in (0, .5, 1, 1.25) for cohort in ('unsupported_lexical', 'genuine_speech')]


def confined(directory, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Artifact must be a relative path')
    path = Path(directory) / relative
    if any(p.is_symlink() for p in [path, *path.parents] if p != Path(directory).parent):
        raise ValueError('Artifact symlinks are forbidden')
    if not path.is_file() or Path(directory).resolve() not in path.resolve().parents:
        raise ValueError('Missing or escaping artifact: ' + relative)
    return path


def inventory(directory):
    output = {}
    for path in sorted(Path(directory).rglob('*')):
        if path.is_symlink(): raise ValueError('Symlink in frozen work')
        if path.is_file() and '.git' not in path.parts and '__pycache__' not in path.parts:
            if path.stat().st_size > 12 * 1024 * 1024: raise ValueError('Artifact exceeds 12 MB limit')
            output[str(path.relative_to(directory))] = sha(path)
    return output


def validate_patch(patch, parent=OFFICIAL_SMALL_SHA256):
    required = {'kind', 'layer', 'head', 'scale', 'parent_checkpoint_sha256'}
    if set(patch) != required or patch['kind'] != 'decoder_self_attention_head_scale':
        raise ValueError('Only one declared self-attention head scale is allowed')
    if patch['parent_checkpoint_sha256'] != parent: raise ValueError('Wrong parent checkpoint')
    for k in ('layer', 'head'):
        if type(patch[k]) is not int or not 0 <= patch[k] < 12: raise ValueError('Invalid component index')
    if type(patch['scale']) not in (int, float) or patch['scale'] not in SCALES: raise ValueError('Scale outside frozen protocol')
    return patch


def prediction_score(predictions, measurements, grid=GRID, tolerance=.01):
    """Missing predictions remain in the mandatory-grid denominator; no prose scoring."""
    assigned = {x['id'] for x in grid}
    if set(predictions) - assigned: raise ValueError('Unknown challenge')
    result = []; correct = eligible = missing = 0
    for challenge in grid:
        key = challenge['id']; p = predictions.get(key); m = measurements.get(key)
        if p is None: missing += 1
        if p is not None:
            if not isinstance(p, dict) or set(p) - {'direction', 'magnitude', 'confidence'} or p.get('direction') not in ('decrease', 'none', 'increase'):
                raise ValueError('Invalid frozen prediction')
            for name in ('magnitude', 'confidence'):
                if name in p and (type(p[name]) not in (int, float) or not math.isfinite(p[name])): raise ValueError('Non-finite prediction')
            if 'confidence' in p and not 0 <= p['confidence'] <= 1: raise ValueError('Confidence outside 0..1')
        if not m or m.get('status') != 'ok':
            result.append(dict(id=key, status='not_evaluated', prediction=p)); continue
        delta = m['mean_delta']; direction = 'increase' if delta > tolerance else 'decrease' if delta < -tolerance else 'none'
        eligible += 1; hit = p is not None and p['direction'] == direction; correct += int(hit)
        result.append(dict(id=key, status='scored', prediction=p, observed_direction=direction,
                           mean_delta=delta, correct=hit, magnitude_absolute_error=abs(p['magnitude']-delta) if p and 'magnitude' in p else None,
                           no_effect_correct=direction == 'none'))
    return dict(assigned=len(grid), submitted=len(predictions), missing=missing,
                coverage=len(predictions)/len(grid), evaluated=eligible, correct=correct,
                accuracy=correct/len(grid) if eligible == len(grid) else None,
                partial_accuracy=correct/eligible if eligible else None,
                no_effect_accuracy=sum(x.get('no_effect_correct', False) for x in result)/eligible if eligible else None,
                complete=eligible == len(grid), per_challenge=result)


class Research:
    def __init__(self, root=DEFAULT):
        self.root = Path(root).resolve(); self.state = State(self.root); self.policies = PolicyStore(self.state)

    def task(self):
        package = read(self.root/'task.json')
        if digest(package['public']) != package['version']: raise ValueError('Task hash mismatch')
        if digest(package['private_spec']) != package['private_spec_hash']: raise ValueError('Private spec hash mismatch')
        if sha(ROOT/'audio_models/small.pt') != package['public']['parent_checkpoint_sha256']: raise ValueError('Parent changed')
        for name, value in package['public']['source_hashes'].items():
            if sha(ROOT/name) != value: raise ValueError('Frozen source changed: '+name)
        return package

    def initialize(self, private_manifest=None):
        if (self.root/'task.json').exists(): raise ValueError('Task already frozen; use a new --root for a new task version')
        if sha(ROOT/'audio_models/small.pt') != OFFICIAL_SMALL_SHA256: raise ValueError('Official small checkpoint required')
        exposed = []
        manifests = [ROOT/'whisper_audio_dev/manifest.jsonl', Path('/private/tmp/neural-pr-audio-holdout-quarantine/whisper_audio_holdout/manifest.jsonl')]
        original_groups = read(ROOT/'audio_runs/mechanistic_v1/manifest.json')['source_groups']
        for manifest in manifests:
            if not manifest.exists(): raise ValueError('Need both historical manifests to establish exposure')
            for item in rows(manifest):
                group = item.get('source_recording_id') or original_groups.get(item['id']) or item['id']
                speaker = str(item['id']).split('-')[0] if item['kind'] == 'speech' else None
                exposed.append(dict(id=item['id'], sha256=item['sha256'], source_audio_sha256=item.get('source_audio_sha256'),
                                    source_group=str(group), speaker=speaker, status='exposed_before_comparison',
                                    manifest_sha256=sha(manifest)))
        self.state.write('exposure', dict(recordings=exposed, old_sets_eligible_as_fresh=False))
        private = dict(status='unavailable', reason='No fresh source-independent private recordings registered',
                       manifest_sha256=None, challenge_seed=1729, challenge_case_rule='all eligible; minimum 3 independent groups per cohort',
                       probe_recipe='first lexical token in pristine production window for unsupported output; first reference token after timestamp zero for speech',
                       max_challenge_cases_per_cohort=12)
        if private_manifest:
            path = Path(private_manifest).resolve()
            if ROOT in path.parents: raise ValueError('Private audio must be outside the runtime repository')
            material = rows(path); ids=set(); groups=set(); counts={'speech':0, 'nonspeech':0}
            for item in material:
                for key in ('id', 'source_group', 'sha256', 'label_provenance', 'review_required', 'kind', 'audio_path', 'reference_text'):
                    if key not in item: raise ValueError('Missing private provenance field: '+key)
                if item['id'] in ids: raise ValueError('Duplicate private ID')
                ids.add(item['id']); groups.add(item['source_group']); counts[item['kind']]+=1
                if item['kind']=='speech' and not item['reference_text'].strip(): raise ValueError('Speech reference missing')
                audio=(path.parent/item['audio_path']).resolve()
                if ROOT in audio.parents or sha(audio)!=item['sha256']: raise ValueError('Private file location/hash mismatch')
                if any(item['sha256']==old['sha256'] or item.get('source_audio_sha256') and item.get('source_audio_sha256')==old.get('source_audio_sha256') or item['source_group']==old['source_group'] or item.get('speaker') and str(item['speaker'])==old['speaker'] for old in exposed):
                    raise ValueError('Private data overlaps exposed sources')
            if min(counts.values())<3: raise ValueError('At least three recordings in each cohort required')
            private.update(status='registered', manifest_sha256=sha(path), counts=counts,
                           source_groups_hash=digest(sorted(groups)), review_required=sum(x['review_required'] for x in material))
            self.state.write('private_pointer', dict(manifest=str(path)))
        source = {}
        for directory in ('whisper_repair', 'neural_pr', 'research_eval'):
            for path in sorted((ROOT/directory).rglob('*.py')): source[str(path.relative_to(ROOT))]=sha(path)
        source['scripts/followup_head_strength.py']=sha(ROOT/'scripts/followup_head_strength.py')
        from neural_pr.sandbox import init_repository
        snapshot=self.root/'source';snapshot.mkdir()
        for name in source:
            target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        application_commit=init_repository(snapshot)
        public = dict(task_family='whisper_unsupported_continuation', task_name='Whisper-small research episode v1',
                      parent_checkpoint_sha256=OFFICIAL_SMALL_SHA256, model='multilingual small',
                      runtime=read(ROOT/'audio_runs/mechanistic_v1/installed_source.json'),
                      configuration=DECODE, gate=GATE, lexical_metric='whisper_repair.metrics.words; speech-only corpus WER',
                      development_manifest_sha256=sha(manifests[0]), development_recordings=29,
                      allowed_interventions=dict(kind='decoder_self_attention_head_scale', layers=12, heads=12, scales=SCALES, count=1),
                      budgets=BUDGET, common_challenge_grid=GRID, direction_tolerance_nats=.01,
                      artifact_format='parent-bound single projection NPZ, allow_pickle=False; trusted full-checkpoint reconstruction',
                      source_hashes=source, application_commit=application_commit,
                      application_commit_scope='independent Git source snapshot; frozen trusted application and research tools',
                      evaluation_unit='one complete recording or one diagnostic forward; actual decoder steps vary; arbitrary local Python compute is not enforceably metered',
                      isolation=ISOLATION, exposure_ledger_sha256=sha(self.root/'exposure.json'))
        package = dict(version=digest(public), public=public, private_spec=private, private_spec_hash=digest(private), created=now())
        self.state.write('task', package); self.state.emit('task_frozen', task_version=package['version'], private_spec_hash=package['private_spec_hash'])
        return package

    def freeze_submission(self, episode_id):
        episode = self.state.read('episodes/'+episode_id)
        if not episode: raise ValueError('Unknown episode')
        directory=self.root/'episodes'/episode_id; work=directory/'workspace'; task=self.task()
        if (directory/'frozen.json').exists(): raise ValueError('Submission already frozen')
        s=read(work/'submission.json')
        required={'episode_id','task_version','agent_policy_version','parent_checkpoint_sha256','code_artifact',
                  'patch_manifest','checkpoint_artifact','claims_artifact','experiment_log','decision','reported_limitations', 'reproduction'}
        if set(s)!=required: raise ValueError('Submission schema mismatch')
        for k,v in dict(episode_id=episode_id, task_version=task['version'], agent_policy_version=episode['policy_version'],
                        parent_checkpoint_sha256=OFFICIAL_SMALL_SHA256).items():
            if s[k]!=v: raise ValueError('Submission identity mismatch: '+k)
        if s['decision'] not in ('abstain','submit_patch'): raise ValueError('Explicit submission decision required')
        if not isinstance(s['reported_limitations'], list) or not all(isinstance(x,str) for x in s['reported_limitations']): raise ValueError('Limitations must be text list')
        repro=s['reproduction']
        if not isinstance(repro,dict) or set(repro)!={'entrypoint','dependencies'} or not isinstance(repro['dependencies'],list): raise ValueError('Reproduction entrypoint/dependencies required')
        if repro['entrypoint']!=s['code_artifact'] or not repro['entrypoint'].endswith('.py'): raise ValueError('Executable Python entrypoint required')
        for key in ('code_artifact','claims_artifact','experiment_log'): confined(work,s[key])
        claims=read(work/s['claims_artifact'])
        if set(claims)-{'predictions','repair_prediction','limitations','historical_evidence'}: raise ValueError('Unknown claim fields')
        prediction_score(claims.get('predictions',{}),{})
        if s['decision']=='abstain':
            if s['patch_manifest'] is not None or s['checkpoint_artifact'] is not None: raise ValueError('Abstention cannot submit a patch')
        else:
            validate_patch(read(confined(work,s['patch_manifest'])))
            tensor=confined(work,s['checkpoint_artifact'])
            if tensor.suffix!='.npz': raise ValueError('Agent tensor artifacts must use non-executable NPZ format')
        # The controller journal is authoritative for prospective registration, not an agent file.
        journal=State(directory/'journal'); events=journal.events()
        logs=rows(work/s['experiment_log'])
        if not isinstance(logs,list): raise ValueError('Invalid experiment log')
        if episode.get('kind')=='live_agent' and not events: raise ValueError('Missing controller trajectory')
        if episode.get('kind')=='live_agent':
            completed=[x['data']['id'] for x in events if x['kind']=='experiment_complete']
            if not completed:raise ValueError('No completed executable investigation experiment')
            finished=[x['data']['id'] for x in events if x['kind'] in ('experiment_complete','experiment_failed')]
            if not set(finished).issubset({x.get('id') for x in logs}):raise ValueError('Agent log omitted completed or failed controller experiments')
        frozen_dir=directory/'frozen'; shutil.copytree(work,frozen_dir)
        hashes=inventory(frozen_dir)
        record=dict(submission=s, artifacts=hashes, submission_hash=digest(hashes), frozen_at=now(),
                    journal_sha256=sha(journal.events_path) if journal.events_path.exists() else None,
                    budget_compliant=episode.get('within_budget',False), episode_kind=episode['kind'])
        save(directory/'frozen.json',record); self.state.emit('submission_frozen',episode_id=episode_id,submission_hash=record['submission_hash'])
        return record

    def check_frozen(self, episode_id):
        path=self.root/'episodes'/episode_id; frozen=read(path/'frozen.json')
        if inventory(path/'frozen')!=frozen['artifacts'] or digest(frozen['artifacts'])!=frozen['submission_hash']: raise ValueError('Frozen artifact tampered')
        return frozen

    def freeze_comparison(self):
        task=self.task()
        if (self.root/'comparison.json').exists(): raise ValueError('Comparison already frozen')
        from neural_pr.worker import Model
        common=['Investigate using the frozen task, authentic baseline, aligned probes, matched controls, and all genuine-speech controls. Preserve negative results. Register predictions before cited prospective experiments. Submit executable reproducible work or abstain honestly. Never access private evaluation material.']
        content=dict(skills=common, context_rules=['TASK.md','TASK.json'],tools_version='file-tools-v1',routing_version='fixed-model-v1')
        baseline=self.policies.create(content)
        candidate=self.policies.create(dict(content, skills=common+['For each hypothesis, explicitly register a competing explanation and a falsification criterion; prioritize a matched control, then replication on a reserved source group before refining. Keep the same tools and budgets.']),parent=baseline)
        comparison=dict(task_version=task['version'], private_spec_hash=task['private_spec_hash'], model=Model().identity(),
                        policies={'baseline':baseline,'candidate':candidate}, procedure_diff=self.policies.diff(baseline,candidate),
                        budgets=BUDGET, seeds=[1729,1730], schedule=[dict(condition=c,attempt=i+1,seed=seed) for i,seed in enumerate((1729,1730)) for c in ('baseline','candidate')],
                        created=now(), axis='procedure only; human-written difference', source_snapshot_hash=digest(task['public']['source_hashes']),
                        all_submissions_before_protected_results=True)
        # Simple empirical predictor is frozen from exposed development data only.
        old=read(ROOT/'audio_runs/mechanistic_direction_v2/diagnostic_summary.json');predictions={}
        for challenge in GRID:
            found=next((x for x in old if x['role']=='selected' and x['cohort']==challenge['cohort'] and x['scale']==challenge['scale']),None)
            if found:delta=found['mean_delta']
            else:
                zero=next(x for x in old if x['role']=='selected' and x['cohort']==challenge['cohort'] and x['scale']==0)
                delta=zero['mean_delta']*(1-challenge['scale'])
            predictions[challenge['id']]=dict(direction='increase' if delta>.01 else 'decrease' if delta<-.01 else 'none',magnitude=delta)
        self.state.write('empirical_predictor',dict(predictions=predictions,method='exposed development means; linear interpolation from scale 0 to identity for missing scale .5',
                         source_sha256=sha(ROOT/'audio_runs/mechanistic_direction_v2/diagnostic_summary.json')))
        comparison['empirical_predictor_sha256']=sha(self.root/'empirical_predictor.json')
        self.state.write('comparison',comparison);return comparison

    def seal(self):
        comparison=self.state.read('comparison')
        if not comparison: raise ValueError('Freeze comparison first')
        if self.state.read('comparison_seal'): raise ValueError('Comparison already sealed')
        episodes=self.episodes(); included=[e for e in episodes if e.get('comparison_member')]
        schedule={(x['condition'],x['attempt']) for x in comparison['schedule']}
        if {(x['condition'],x['attempt']) for x in included}!=schedule or len(included)!=len(schedule): raise ValueError('Every scheduled attempt must have a terminal outcome')
        freezes={}
        for episode in included:
            if episode['status']=='running': raise ValueError('Episode still running')
            if (self.root/'episodes'/episode['id']/'frozen.json').exists(): freezes[episode['id']]=self.check_frozen(episode['id'])['submission_hash']
            else: freezes[episode['id']]=None
        record=dict(task_version=comparison['task_version'], comparison_sha256=sha(self.root/'comparison.json'),
                    frozen_submissions=freezes, sealed_at=now())
        self.state.write('comparison_seal',record);return record

    def episodes(self):
        return [read(p) for p in sorted((self.root/'episodes').glob('*.json'))]

    def report(self):
        episodes=[]
        for episode in self.episodes():
            verdict=self.state.read('verdicts/'+episode['id'])
            episodes.append(dict(episode=episode,verdict=verdict))
        live=[x for x in episodes if x['episode'].get('comparison_member')]
        complete=len(live)==4 and all(x['verdict'] and x['verdict'].get('protected_status')=='complete' and x['verdict'].get('reproducibility_status')=='passed' and x['episode']['status']=='submitted' for x in live)
        task=self.state.read('task'); controls=self.state.read('controls')
        report=dict(task_family='Whisper unsupported continuation',task_version=task['version'] if task else None,
                    comparison=self.state.read('comparison'),seal=self.state.read('comparison_seal'),episodes=episodes,controls=controls,
                    comparison_status='complete_pilot' if complete else 'inconclusive',
                    conclusion='No agent demonstrated a qualifying repair; no agent-procedure advantage established.' if not complete else 'See separate outcome dimensions; one task remains pilot evidence.',
                    private_status=task['private_spec']['status'] if task else 'unregistered',isolation=ISOLATION,
                    agent_upgrade_status='not evaluated here; original independent coding-task gate unchanged', generated=now())
        self.state.write('report',report)
        lines=['# Research-agent evaluation results','',report['conclusion'],'',
               'One task family: multilingual Whisper-small unsupported continuation. Historical runs are recorded evidence, not paired agent episodes.','',
               '| Episode | Kind / procedure | Outcome | Repair | Prediction | Reproducibility |',
               '| --- | --- | --- | --- | --- | --- |']
        for item in episodes:
            e=item['episode'];v=item['verdict'] or {}
            lines.append(f"| {e['id']} | {e['kind']} / {e.get('condition','historical')} | {e['status']} | {v.get('repair_status','unrun')} | {v.get('prediction_status','unrun')} | {v.get('reproducibility_status','unrun')} |")
        lines+=['',f"Protected audio: {report['private_status']}. Comparison: {report['comparison_status']}.",
                '',ISOLATION+'. No claim of tamper-proof independent evaluation.',
                '', 'The previously used 29 development and 40 final recordings are exposed. None can establish a new held-out repair. The pristine checkpoint remains active. Coding-policy promotion requires the original independent coding-task gate.',
                '', 'Machine-readable measurements, claims, costs, failed checks, and artifact hashes are in `research_runs/report.json` and each episode/verdict directory.']
        (self.root/'REPORT.md').write_text('\n'.join(lines)+'\n')
        return report
