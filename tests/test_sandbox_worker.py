from pathlib import Path
import tempfile
import unittest
from neural_pr.sandbox import Files,Sandbox
from neural_pr.state import State
from neural_pr.worker import Worker,Budget,InfrastructureError
from neural_pr.policy_store import BASELINE

class ScriptedModel:
    model='explicit-test-control'
    def __init__(self,actions):self.actions=iter(actions)
    def complete(self,*args,**kwargs):
        import json
        return json.dumps(next(self.actions)),{'total_tokens':20,'prompt_tokens':10,'completion_tokens':10}

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.task=self.root/'task';self.task.mkdir();self.state=State(self.root/'controller')
    def test_path_traversal_and_symlink_denied(self):
        files=Files(self.task,Sandbox());(self.task/'escape').symlink_to(self.root/'controller',target_is_directory=True)
        for path in ('TASK.md','../controller/active.json','/etc/passwd','.git/config','escape/active.json'):
            with self.assertRaises(ValueError):files.call('write',{'path':path,'content':'bad'})
        self.assertFalse((self.root/'controller'/'active.json').exists())
    def test_runtime_worker_edits_and_checks(self):
        model=ScriptedModel([{'tool':'write','arguments':{'path':'smoke.py','content':'assert 2+2 == 4\nprint("checked")\n'}},
                             {'tool':'check','arguments':{'path':'smoke.py'}},{'done':True}])
        result=Worker(model,Sandbox(),self.state).run('control',self.task,{'content':BASELINE},'Development test control',Budget())
        self.assertEqual(result['result'],'submitted');self.assertEqual(result['usage']['tool_calls'],2)
        self.assertIn('checked',str(self.state.events()))
    def test_tool_budget_enforced(self):
        model=ScriptedModel([{'tool':'list'},{'tool':'list'},{'tool':'list'}])
        result=Worker(model,Sandbox(),self.state).run('control',self.task,{'content':BASELINE},'control',Budget(tool_calls=1))
        self.assertEqual(result['usage']['tool_calls'],1)
    def test_missing_key_is_infrastructure_failure(self):
        class Missing:
            def complete(self,*a,**k):raise InfrastructureError('missing key')
        result=Worker(Missing(),Sandbox(),self.state).run('control',self.task,{'content':BASELINE},'control',Budget())
        self.assertEqual(result['result'],'infrastructure_failure')
    def test_context_reconstruction_uses_trusted_frozen_contract(self):
        from neural_pr.evaluator import build_context
        (self.task/'TASK.md').write_text('modified checkout instructions')
        text=build_context(self.task,{'content':BASELINE},{'objective':'test'},contract='trusted frozen contract')
        self.assertIn('trusted frozen contract',text)
        self.assertNotIn('modified checkout instructions',text)
