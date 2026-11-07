"""Synthetic exposure/trace fixtures, not live agent evaluation outcomes."""
from pathlib import Path
import tempfile
import unittest
import copy
from unittest.mock import MagicMock,patch
from neural_pr.state import State,lock,now
from scripts.run_policy_followup import development_evidence,freeze_protocol,execute


class PolicyFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'source';self.old=State(self.source)
        self.old.write('experiment',{'model':{'model':'synthetic'}})
        self.old.write('consumed',{'audit':{'evaluation_id':'synthetic-exposed-audit'}})
        self.old.write('attempts/main',{'run_id':'main','task_id':'main:synthetic','objective_passed':True,
                        'source_commit':'synthetic','agent_version':'synthetic','worker':{'within_budget':True,'result':'budget_exhausted'}})
        self.old.write('traces/main',{'messages':[{'role':'assistant','content':'Progress. {"tool":"list","arguments":{}}'},
                        {'role':'assistant','content':'{"tool":"list","arguments":{}}'}]})
        self.old.write('attempts/audit',{'run_id':'audit','task_id':'audit:synthetic','objective_passed':False,'worker':{'within_budget':True}})
        self.old.write('traces/audit',{'messages':[{'role':'assistant','content':'private-audit-marker'}]})

    def test_only_development_protocol_errors_enter_proposal_evidence(self):
        evidence=development_evidence(self.source)
        self.assertEqual(evidence['checks']['strict_action_json']['invalid_responses'],1)
        self.assertEqual(evidence['checks']['strict_action_json']['total_responses'],2)
        self.assertNotIn('private-audit-marker',str(evidence))

    def test_exposed_promotion_block_cannot_be_presented_as_fresh(self):
        self.old.write('consumed',{'A':{'evaluation_id':'synthetic-exposed'}})
        with self.assertRaisesRegex(ValueError,'consumed'):development_evidence(self.source)

    def test_single_registered_followup_preserves_audit_exposure(self):
        target=self.root/'followup';protocol=freeze_protocol(self.source,target)
        self.assertIn('audit',protocol['original_consumed_blocks'])
        self.assertEqual(freeze_protocol(self.source,target),protocol)
        with self.assertRaisesRegex(ValueError,'already registered'):freeze_protocol(self.source,self.root/'other')

    def test_a_successful_clean_trace_does_not_manufacture_a_failure(self):
        self.old.write('traces/main',{'messages':[{'role':'assistant','content':'{"done":true}'}]})
        with self.assertRaisesRegex(ValueError,'No observed'):development_evidence(self.source)

    def test_followup_delegates_one_paired_gate_and_never_reopens_audit(self):
        """Synthetic orchestration only; the real gate has its own independent tests."""
        config=dict(model={'model':'synthetic'},gate={'fixture':True},main_budget={'fixture':True},evaluation_budget={'seconds':1},
                    controller_digest='synthetic',environment_digest='synthetic',bank_hash='synthetic',
                    calibration={'run_id':'main'},created_at=now(),deadline_hours=7)
        self.old.write('experiment',config)
        self.old.write('application',{'application_base_commit':'base','last_verified_commit':'tip','verified_milestones':['smoke'],'unfinished':[]})
        target=self.root/'followup';state=State(target);original=MagicMock();original.state=self.old;original.checkout=self.source/'application'
        controller=MagicMock();controller.state=state;controller.checkout=target/'application';controller.store.active.return_value='synthetic'
        def initialize(mode):
            # A real nested controller lock would fail here, catching accidental recursive locking.
            with lock(target/'controller.lock'):state.write('experiment',copy.deepcopy(config))
        controller.initialize.side_effect=initialize;controller.verifier.main.return_value={'passed':True}
        candidate={'id':'candidate','status':'development_checked','version':'new-policy'}
        def propose(_):state.write('candidates/candidate',candidate);return candidate
        controller.improver.propose.side_effect=propose
        def evaluate(identifier,block):
            self.assertIn('audit',state.read('consumed'))
            updated=dict(candidate,status='promoted',evaluation_id='evaluation');state.write('candidates/candidate',updated)
            return {'id':'evaluation','decision':'pass','counts':{'synthetic':True}}
        controller.evaluate_candidate.side_effect=evaluate;controller.report.return_value={'fixture':'synthetic'}
        model=MagicMock();model.identity.return_value=config['model'];model.probe.return_value={'ready':True}
        with patch('scripts.run_policy_followup.configure'),patch('scripts.run_policy_followup.prepare_docker_path'),patch('scripts.run_policy_followup.WonderModel',return_value=model),patch('scripts.run_policy_followup.Sandbox.doctor',return_value={'image_ready':True}),patch('scripts.run_policy_followup.Controller',side_effect=[original,controller]),patch('scripts.run_policy_followup.git',side_effect=lambda checkout,*args:'base' if args[0]=='rev-list' else ''):
            result=execute(self.source,target)
        controller.evaluate_candidate.assert_called_once_with('candidate',block='A')
        controller.audit.assert_not_called()
        self.assertEqual(result['decision'],'pass')
        self.assertIn('Unavailable',result['final_audit'])

if __name__=='__main__':unittest.main()
