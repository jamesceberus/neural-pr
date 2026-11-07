import json
from pathlib import Path
import tempfile
import unittest
from neural_pr.controller import Controller
from neural_pr.policy_store import BASELINE
from neural_pr.worker import InfrastructureError
from tests.test_controller import OfflineModel

class ReadyControl(OfflineModel):
    def probe(self):return {'ready':True,'label':'SCRIPTED TEST CONTROL'}
    def complete(self,*args,**kwargs):return '{"done":true,"summary":"scripted test control; no implementation"}',{'total_tokens':12}

class EvaluationTests(unittest.TestCase):
    def test_all_paired_rollouts_are_recorded_with_identical_snapshots_and_budgets(self):
        with tempfile.TemporaryDirectory() as temp:
            c=Controller(temp,model=ReadyControl());c.initialize()
            base=c.store.active()
            version=c.store.create(dict(BASELINE,skills=BASELINE['skills']+['Check interface callers.']),base)
            record=c.evaluator.evaluate({'version':version,'parent':base},'A')
            self.assertEqual(len(record['rows']),12)
            self.assertEqual(record['decision'],'inconclusive') # no Docker on the local test host
            self.assertEqual(record['reason'],'isolation_integrity_unenforced')
            for task in ('scope','fencing','client-errors'):
                attempts=[c.state.read('attempts/'+r['run_id']) for r in record['rows'] if r['task_id']==task]
                self.assertEqual(len({a['application_base_commit'] for a in attempts}),1)
                self.assertTrue(all(a['budget']==record['budget'] for a in attempts))
                self.assertTrue(all(a['verification']['passed'] is False for a in attempts))
            self.assertEqual(set(c.state.read('consumed')),{'A'})
            with self.assertRaises(ValueError):c.evaluator.evaluate({'version':version,'parent':base},'A')
            self.assertEqual(c.store.active(),base)
    def test_runtime_proposal_has_exact_parent_diff_and_no_self_activation(self):
        class Proposer(OfflineModel):
            def complete(self,*args,**kwargs):
                return json.dumps({'hypothesis':'Reading callers prevents incomplete interface updates.',
                    'scope':'Interface changes','skills':BASELINE['skills']+['Inspect callers and schemas before changing an interface.'],
                    'context_rules':BASELINE['context_rules']}),{'total_tokens':42}
        with tempfile.TemporaryDirectory() as temp:
            c=Controller(temp,model=Proposer());c.initialize();base=c.store.active()
            incident=c.improver.incident('execution','commit',base,{'checks':{'slice':{'passed':False}}},'no_verified_progress','Test control')
            candidate=c.improver.propose(incident)
            self.assertEqual(candidate['status'],'development_checked')
            self.assertEqual(candidate['parent'],base);self.assertIn('+',candidate['diff'])
            self.assertEqual(c.store.active(),base)
            again=c.improver.incident('execution','new-commit',base,{'checks':{'slice':{'passed':False}}},'no_verified_progress','Test control')
            self.assertEqual(again['id'],incident['id']);self.assertEqual(again['occurrences'],2)
            repeated=c.improver.propose(incident);self.assertEqual(repeated['disposition'],'deduplicated')
            self.assertIsNone(c.improver.propose(incident))
