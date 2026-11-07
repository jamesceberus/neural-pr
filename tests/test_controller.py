from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from neural_pr.controller import Controller
from neural_pr.cli import controls
from neural_pr.sandbox import git
from neural_pr.worker import InfrastructureError

class OfflineModel:
    model='explicit-test-offline'
    def identity(self):return {'model':self.model,'base_url':'http://localhost:1','adapter':'json-chat-v1','temperature':0.2}
    def complete(self,*a,**k):raise InfrastructureError('Labeled offline test control')
    def probe(self):return {'ready':False,'error':'Labeled offline test control'}

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.controller=Controller(Path(self.temp.name)/'state',model=OfflineModel());self.controller.initialize()
    def test_starter_passes_smoke_and_fails_unfinished_work(self):
        report=self.controller.report();self.assertFalse(report['main_task_complete'])
        self.assertEqual(report['application']['verified_milestones'],['smoke'])
    def test_independent_grader_accepts_correct_main_reference(self):
        shutil.copyfile(Path(__file__).parent/'reference_store.py',self.controller.checkout/'jobservice'/'store.py')
        result=self.controller.verifier.main(self.controller.checkout)
        self.assertTrue(result['passed'],result)
    def test_resume_preserves_application_and_agent_identity(self):
        app=self.controller.state.read('application');agent=self.controller.store.active()
        next_controller=Controller(self.controller.state.root,model=OfflineModel())
        result=next_controller.run(episodes=1,resume=True)
        self.assertEqual(result['active_agent_version'],agent)
        self.assertEqual(result['application']['last_verified_commit'],app['last_verified_commit'])
        self.assertEqual(result['counts']['incidents'],1)
    def test_application_rollback_preserves_diagnostics_and_restores_fixture(self):
        checkpoint=self.controller.state.read('application')['last_verified_commit']
        (self.controller.checkout/'evidence.py').write_text('partial work\n')
        (self.controller.checkout/'jobs.sqlite').write_text('fixture')
        self.controller.rollback_application()
        self.assertEqual(git(self.controller.checkout,'rev-parse','HEAD'),checkpoint)
        self.assertFalse((self.controller.checkout/'jobs.sqlite').exists())
        self.assertIn('diagnostic/',git(self.controller.checkout,'branch','--list'))
    def test_recovery_handles_interrupted_attempt(self):
        self.controller.state.write('attempts/pending',{'run_id':'pending','start_time':'now'})
        self.controller.recover()
        self.assertEqual(self.controller.state.read('attempts/pending')['result'],'interrupted')
    def test_controls_are_labeled_and_do_not_promote(self):
        value=controls(self.controller)
        self.assertIn('SYNTHETIC',value['label']);self.assertTrue(value['fixture_removed'])
        self.assertTrue(value['unapproved_activation_rejected']);self.assertEqual(self.controller.report()['counts']['promotions'],0)
    def test_consumed_blocks_cannot_be_reused(self):
        base=self.controller.store.active()
        candidate={'version':self.controller.store.create(dict(self.controller.store.get(base)['content'],skills=['Inspect schema and callers.']),base),'parent':base}
        self.controller.state.write('consumed',{'A':{'evaluation_id':'old'}})
        with self.assertRaisesRegex(ValueError,'consumed'):self.controller.evaluator.evaluate(candidate,'A')
    def test_no_api_does_not_consume_a_holdout(self):
        base=self.controller.store.active()
        candidate={'version':self.controller.store.create(dict(self.controller.store.get(base)['content'],skills=['Inspect schema and callers.']),base),'parent':base}
        result=self.controller.evaluator.evaluate(candidate,'A')
        self.assertEqual(result['decision'],'inconclusive');self.assertEqual(self.controller.state.read('consumed',{}),{})
    def test_agent_rollback_preserves_application_progress(self):
        from neural_pr.state import digest
        base=self.controller.store.active()
        version=self.controller.store.create(dict(self.controller.store.get(base)['content'],skills=['Inspect schema and callers.']),base)
        record={'kind':'promotion','decision':'pass','candidate':version,'incumbent':base};record['record_hash']=digest(record)
        self.controller.state.write('evaluations/control',record)
        self.controller.store.promote(version,'control')
        app_before=git(self.controller.checkout,'rev-parse','HEAD')
        self.controller.rollback_agent()
        self.assertEqual(git(self.controller.checkout,'rev-parse','HEAD'),app_before)
        self.assertEqual(self.controller.store.active(),base)
    def test_environment_identity_change_fails_closed(self):
        record=self.controller.state.read('experiment');record['environment_digest']='changed';self.controller.state.write('experiment',record)
        with self.assertRaises(RuntimeError):self.controller.validate_identity()
    def test_protocol_errors_create_an_incident_without_discarding_verified_progress(self):
        shutil.copyfile(Path(__file__).parent/'reference_store.py',self.controller.checkout/'jobservice'/'store.py')
        result={'result':'submitted','within_budget':True,'error':None,'elapsed':.01,
                'usage':{'model_calls':2,'tool_calls':0,'tokens':20,'protocol_errors':1,'action_recoveries':0}}
        with patch('neural_pr.controller.Worker.run',return_value=result):outcome=self.controller.episode()
        self.assertTrue(outcome['attempt']['objective_passed'])
        self.assertEqual(outcome['incident']['failure_class'],'protocol_failure_with_verified_progress')
        self.assertEqual(self.controller.state.read('application')['unfinished'],[])
