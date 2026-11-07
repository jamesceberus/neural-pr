"""Bounded dev-only search. Never opens or scores the held-out pack."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper_repair.experiment import Experiment,read,save,now

experiment=Experiment()
if (experiment.root/'holdout_consulted.json').exists():raise SystemExit('Holdout consumed: no tuning permitted')
ranking=read(experiment.root/'head_ranking.json')['ranking'][:4]
plan={'created':now(),'basis':'development-only head-scale gradients with all genuine-speech controls',
      'order':[{'layer':head['layer'],'head':head['head'],'scale':scale} for scale in (0.75,0.5) for head in ranking],
      'max_candidates':8,'stop':'first full-development gate pass; otherwise retain baseline',
      'no_holdout_access':True}
path=experiment.root/'search_plan.json'
if path.exists():plan=read(path)
else:save(path,plan)
results=[]
for proposal in plan['order']:
    result=experiment.evaluate_edit('audio_models/small.pt',**proposal)
    comparison=result['comparison']
    row={'id':result['id'],**proposal,'gate_pass':comparison['gate_pass'],
         'nonspeech_lexical_outputs':len(comparison['candidate']['nonspeech']['lexical_output_ids']),
         'speech_wer':comparison['candidate']['speech']['wer'],
         'newly_empty_speech':comparison['newly_empty_speech_ids'],'errors':comparison['candidate']['errors']}
    results.append(row);save(experiment.root/'search_results.json',results)
    print(row,flush=True)
    if comparison['gate_pass']:
        print('Frozen candidate:',experiment.freeze()['sha256'],flush=True)
        break
else:print('No development-qualified candidate; baseline retained, holdout untouched.',flush=True)
