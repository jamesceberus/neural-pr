"""Task-author utility: deterministic new source selection, never model-performance selection.

Run from an unrestricted terminal. No Whisper inference or agent API call occurs.
Dataset-viewer availability/schema is checked at runtime; failure preserves the author plan.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import urllib.parse
import urllib.request
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper_repair.experiment import read,save,sha,rows
from research_eval.core import ROOT


def get_json(url):
    with urllib.request.urlopen(url,timeout=30) as response:return json.load(response)


def audio_url(value):
    if isinstance(value,list):
        if len(value)!=1:raise ValueError('Expected one source audio object')
        value=value[0]
    if not isinstance(value,dict) or not isinstance(value.get('src'),str) or not value['src'].startswith('https://'):
        raise ValueError('Unsupported dataset-viewer audio schema')
    return value['src']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/private/tmp/whisper-research-private-v1')
    args=parser.parse_args();output=Path(args.output).resolve()
    if ROOT==output or ROOT in output.parents:raise ValueError('Private material must be outside the repository')
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.jsonl').exists():raise ValueError('A completed authoring pack already exists; do not replace it')
    exposure=read(ROOT/'research_runs/exposure.json')['recordings']
    specifications=[dict(dataset='Scicom-intl/Whisper-Hallucination',config='nonspeech',split='test',kind='nonspeech',count=20),
                    dict(dataset='openslr/librispeech_asr',config='clean',split='test',kind='speech',count=20)]
    plan=dict(version='source-independent-author-v1',seed=271828,selection='shuffle row indices >= 1000; skip exposed source/content/speaker groups; one recording per group; no model outcomes consulted',
              specifications=specifications,exposure_ledger_sha256=sha(ROOT/'research_runs/exposure.json'),
              preprocessing='whole recording to mono16k PCM16; no trimming, normalization or denoising',
              non_speech_label_policy='upstream curated nonspeech; review_required remains true without independent listening')
    if (output/'author_plan.json').exists() and read(output/'author_plan.json')!=plan:raise ValueError('Authoring plan changed')
    save(output/'author_plan.json',plan);selected=[];used_groups=set();rng=random.Random(plan['seed'])
    for spec in specifications:
        info_url='https://huggingface.co/api/datasets/'+spec['dataset'];revision=get_json(info_url)['sha']
        query=dict(dataset=spec['dataset'],config=spec['config'],split=spec['split'],offset=0,length=1)
        endpoint='https://datasets-server.huggingface.co/rows?'
        first=get_json(endpoint+urllib.parse.urlencode(query));total=first['num_rows_total']
        indices=list(range(1000,total));rng.shuffle(indices);accepted=0
        if not indices:raise ValueError('Dataset too small for frozen selection rule')
        for index in indices[:400]:
            query['offset']=index;page=get_json(endpoint+urllib.parse.urlencode(query))
            if page.get('dataset_git_revision',revision)!=revision:raise ValueError('Dataset viewer revision differs')
            row=page['rows'][0]['row'];identifier=str(row.get('id') or row.get('audio_id') or '')
            if not identifier:raise ValueError('Stable source identifier absent')
            if spec['kind']=='speech':
                speaker=str(row.get('speaker_id') or identifier.split('-')[0]);group='librispeech-speaker-'+speaker
                reference=row.get('text')
                if not isinstance(reference,str) or not reference.strip():raise ValueError('Speech reference missing')
            else:
                # Curated IDs must name the underlying recording. Do not silently group by row index.
                if not identifier.startswith('noise_'):raise ValueError('Unrecognized non-speech source grouping; task author must inspect provenance')
                speaker=None;group=identifier.removeprefix('noise_');reference=''
            if group in used_groups or any(group==x['source_group'] or speaker and speaker==x['speaker'] or identifier==x['id'] for x in exposure):continue
            source=output/'source'/f"{spec['kind']}-{index}.audio";source.parent.mkdir(exist_ok=True)
            with urllib.request.urlopen(audio_url(row['audio']),timeout=60) as response,source.open('wb') as stream:
                remaining=40*1024*1024
                while True:
                    block=response.read(min(1024*1024,remaining+1))
                    if not block:break
                    remaining-=len(block)
                    if remaining<0:raise ValueError('Source download exceeds 40 MB cap')
                    stream.write(block)
            destination=output/'audio'/f"{spec['kind']}-{index}.wav";destination.parent.mkdir(exist_ok=True)
            subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-ac','1','-ar','16000','-c:a','pcm_s16le',str(destination)],check=True,timeout=30)
            if any(sha(destination)==x['sha256'] or sha(source)==x.get('source_audio_sha256') for x in exposure):continue
            with wave.open(str(destination),'rb') as wav:duration=wav.getnframes()/wav.getframerate()
            if not 0<duration<=60:continue
            if spec['kind']=='speech' and speaker and any(x.get('speaker')==speaker for x in selected):continue
            record=dict(id=f"fresh-{spec['kind']}-{index}",partition='heldout',kind=spec['kind'],source_group=group,speaker=speaker,
                        sha256=sha(destination),source_audio_sha256=sha(source),audio_path=str(destination.relative_to(output)),reference_text=reference,
                        duration_s=duration,source_dataset=spec['dataset'],source_config=spec['config'],source_split=spec['split'],source_row_index=index,
                        source_revision=revision,source_recording_id=identifier,source_row_metadata={k:v for k,v in row.items() if k!='audio'},
                        label_provenance='Upstream LibriSpeech reference' if spec['kind']=='speech' else 'Upstream curated non-speech test split; not independently listened',
                        review_required=spec['kind']!='speech',local_whisper_status='not_run',author_plan_sha256=sha(output/'author_plan.json'))
            selected.append(record);used_groups.add(group);accepted+=1
            save(output/'author_progress.json',dict(completed=len(selected),plan_sha256=sha(output/'author_plan.json')))
            if accepted==spec['count']:break
        if accepted!=spec['count']:raise ValueError('Insufficient eligible independent sources under frozen rule')
        if get_json(info_url)['sha']!=revision:raise ValueError('Dataset changed during authoring')
    temporary=output/'manifest.partial';temporary.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in selected));temporary.replace(output/'manifest.jsonl')
    print(json.dumps(dict(status='authored_not_evaluated',recordings=len(selected),manifest_sha256=sha(output/'manifest.jsonl'),private_manifest=str(output/'manifest.jsonl'),
                         limitations='Network authoring branch must be verified on a reachable host; non-speech labels still require review. Local isolation remains unenforced.')))

if __name__=='__main__':main()
