"""The current model adapter with a bounded capability allowlist; it cannot approve claims."""
import json
import uuid
from neural_pr.worker import Model,InfrastructureError
from neural_pr.cli import load_env
from whisper_repair.experiment import save,now
from .interventions import validate

ALLOWED_TOOLS=('inspect_dimensions','development_summary','run_probe','read_results','propose_intervention')

class Investigator:
    def __init__(self,root,model=None):
        self.root=root
        if model is None:load_env();model=Model()
        self.model=model
    def ask(self,phase,dimensions,summary,run_probe=None,results=None):
        prompt='''You are the runtime mechanistic investigator. Propose a testable next decoder SELF-attention experiment using only the supplied development evidence.
Respond with one JSON action per turn: {"tool":"inspect_dimensions"}, {"tool":"development_summary"}, {"tool":"read_results"},
{"tool":"run_probe","arguments":{"case_id":"declared discovery ID","layer":0,"head":0,"scale":0.5}}, or
{"tool":"propose_intervention","arguments":{"layer":0,"head":0,"scale":0.5,"claim":"...","predicted_direction":"decrease_target_logprob_when_attenuated","would_weaken_claim":"..."}}.
Tools accept only declared discovery IDs and scales 0,.25,.5,.75,1. Do not choose confirmation/holdout inputs, thresholds, metrics, or approval statuses.
Select an experiment based on the observed evidence and state its predicted result. You cannot award a mechanism or repair label.
'''
        messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'phase':phase,'development':summary,'observed_results':results})}]
        trace=[];status='budget_exhausted';proposal=None;usage=[]
        for index in range(6):
            try:
                raw,call_usage=self.model.complete(messages,max_tokens=1200,timeout=15);usage.append(call_usage)
                action=json.loads(raw)
                if set(action)-{'tool','arguments'} or action.get('tool') not in ALLOWED_TOOLS:raise ValueError('Action outside allowlist')
                args=action.get('arguments',{});tool=action['tool']
                if tool=='inspect_dimensions':reply=dimensions
                elif tool=='development_summary':reply=summary
                elif tool=='read_results':reply=results
                elif tool=='run_probe':
                    if set(args)!={'case_id','layer','head','scale'} or not run_probe:raise ValueError('Invalid probe request')
                    reply=run_probe(**args)
                else:
                    if set(args)!={'layer','head','scale','claim','predicted_direction','would_weaken_claim'}:raise ValueError('Invalid proposal fields')
                    if not all(isinstance(args[k],str) and 0<len(args[k])<3000 for k in ('claim','predicted_direction','would_weaken_claim')):raise ValueError('Invalid hypothesis strings')
                    if args['predicted_direction']!='decrease_target_logprob_when_attenuated':raise ValueError('Unsupported primary prediction')
                    if (type(args['layer'])!=int or type(args['head'])!=int or not 0<=args['layer']<dimensions['n_text_layer'] or not 0<=args['head']<dimensions['n_text_head'] or isinstance(args['scale'],bool) or args['scale'] not in (0,.25,.5,.75,1)):
                        raise ValueError('Component indices or scale outside declared model dimensions')
                    proposal=args;status='proposed';trace.append({'action':action});break
                trace.append({'action':action,'result':reply})
                messages.extend([{'role':'assistant','content':raw},{'role':'user','content':json.dumps(reply)}])
            except InfrastructureError as exc:status='infrastructure_unavailable';trace.append({'error':str(exc)});break
            except (ValueError,KeyError,TypeError) as exc:
                trace.append({'error':type(exc).__name__+': '+str(exc)});messages.append({'role':'user','content':str(exc)})
        record={'phase':phase,'time':now(),'status':status,'proposal':proposal,'trace':trace,'usage':usage,
                'model':self.model.identity() if hasattr(self.model,'identity') else {'model':'synthetic_test_control'},
                'origin':'runtime_model_adapter','approval_authority':False}
        save(self.root/f'agent_{phase}.json',record)
        return record
