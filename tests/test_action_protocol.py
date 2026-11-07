"""Regression and boundary fixtures for the original worker's response handling."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from neural_pr.worker import parse_action,parse_json_object,Worker,Budget,Model
from neural_pr.state import State
from neural_pr.sandbox import Sandbox
from neural_pr.policy_store import BASELINE,PolicyStore
from neural_pr.improver import Improver


class RawModel:
    model='synthetic-response-fixture'
    def __init__(self,responses):self.responses=iter(responses)
    def complete(self,*args,**kwargs):return next(self.responses),{'total_tokens':20,'prompt_tokens':10,'completion_tokens':10}


class ActionProtocolTests(unittest.TestCase):
    def test_observed_preamble_and_fenced_single_action_are_supported(self):
        obj={'tool':'read','arguments':{'path':'TASK.md'}}
        for raw,mode in [(json.dumps(obj),'strict'),('Implementing the contract. '+json.dumps(obj),'preamble'),('```json\n'+json.dumps(obj)+'\n```','fenced')]:
            action,actual=parse_action(raw);self.assertEqual(action,obj);self.assertEqual(actual,mode)

    def test_braces_and_escaped_quotes_in_written_code_are_not_extra_actions(self):
        obj={'tool':'write','arguments':{'path':'fixture.py','content':'print({"quoted": "{value}"})\n'}}
        self.assertEqual(parse_action('Saving the file. '+json.dumps(obj))[0],obj)

    def test_ambiguous_truncated_duplicate_or_unknown_actions_are_rejected(self):
        action='{"tool":"list","arguments":{}}'
        invalid=[action+action,action+' Done.', 'An example: {} then '+action,'['+action+']',
                 'Progress. {"tool":"write",','{"tool":"list","tool":"write"}',
                 '{"tool":"write","arguments":{"path":"x","path":"y","content":"bad"}}',
                 '{"tool":"shell","arguments":{"cmd":"bad"}}','{"done":true,"tool":"list"}',
                 '{"done":1}','{"tool":"read","arguments":[]}',
                 '{"tool":"write","arguments":{"path":"x","content":"y","overwrite":true}}',
                 '{"tool":"list","arguments":{"value":NaN}}','```json\n'+action+'\n```\n'+action,
                 'x'*1025+action]
        for raw in invalid:
            with self.subTest(raw=raw[:80]),self.assertRaises(ValueError):parse_action(raw)

    def test_worker_executes_in_same_call_and_keeps_raw_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);task=root/'task';task.mkdir();state=State(root/'state')
            raw='Implementing the change. '+json.dumps({'tool':'write','arguments':{'path':'result.txt','content':'written'}})
            model=RawModel([raw,'All set. {"done":true,"summary":"saved"}'])
            result=Worker(model,Sandbox(),state).run('fixture',task,{'content':BASELINE},'Synthetic fixture',Budget(model_calls=2))
            self.assertEqual(result['result'],'submitted');self.assertEqual(result['usage']['model_calls'],2)
            self.assertEqual(result['usage']['action_recoveries'],2);self.assertEqual(result['usage']['protocol_errors'],0)
            self.assertEqual((task/'result.txt').read_text(),'written')
            trace=state.read('traces/fixture');self.assertEqual(trace['model_responses'][0]['raw_content'],raw)
            self.assertTrue(trace['messages'][2]['content'].startswith('{'))

    def test_multiple_actions_never_write_files_and_path_boundary_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);task=root/'task';task.mkdir();state=State(root/'state')
            write=json.dumps({'tool':'write','arguments':{'path':'bad.txt','content':'bad'}})
            model=RawModel([write+write,'{"done":true}'])
            result=Worker(model,Sandbox(),state).run('ambiguous',task,{'content':BASELINE},'fixture',Budget(model_calls=2))
            self.assertFalse((task/'bad.txt').exists());self.assertEqual(result['usage']['protocol_errors'],1)
            self.assertEqual(result['usage']['tool_calls'],0)
            model=RawModel(['Writing now. '+json.dumps({'tool':'write','arguments':{'path':'../escape.txt','content':'bad'}}),'Perhaps done. {"done":true}'])
            Worker(model,Sandbox(),state).run('boundary',task,{'content':BASELINE},'fixture',Budget(model_calls=2))
            self.assertFalse((root/'escape.txt').exists())

    def test_original_proposer_accepts_one_object_without_promoting_itself(self):
        with tempfile.TemporaryDirectory() as temp:
            state=State(temp);store=PolicyStore(state);baseline=store.initialize()
            proposal={'hypothesis':'Pure JSON actions reduce lost calls','scope':'Action formatting only',
                      'skills':BASELINE['skills']+['Emit the JSON object directly without a progress preface.'],
                      'context_rules':BASELINE['context_rules']}
            raw='One reusable change. '+json.dumps(proposal)
            improver=Improver(state,store,RawModel([raw]))
            incident=improver.incident('fixture','fixture',baseline,{'checks':{'protocol':{'passed':False}}},'fixture','Synthetic fixture')
            candidate=improver.propose(incident)
            self.assertEqual(candidate['status'],'development_checked');self.assertEqual(candidate['response_format'],'preamble')
            self.assertEqual(store.active(),baseline)
            self.assertEqual(state.read('traces/proposals/'+candidate['id'])['raw_content'],raw)

    def test_original_readiness_probe_has_sufficient_budget_and_validates_json(self):
        model=Model('https://api.example.test/v1','fixture','fixture')
        with patch.object(model,'complete',return_value=('{"ready":true}',{})) as complete:
            self.assertTrue(model.probe()['ready']);self.assertGreaterEqual(complete.call_args.kwargs['max_tokens'],1024)
        for response in ('{}','{"ready":1}','not JSON'):
            with patch.object(model,'complete',return_value=(response,{})):self.assertFalse(model.probe()['ready'])

if __name__=='__main__':unittest.main()
