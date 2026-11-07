import copy
import unittest
from neural_pr.evaluator import gate

class GateTests(unittest.TestCase):
    def rows(self,inc=(0,1,0),cand=(1,1,1)):
        return [{'role':role,'task_id':task,'repeat':repeat,
                 'worker':{'result':'submitted','within_budget':True},'verification':{'passed':repeat<n}}
                for role,counts in [('incumbent',inc),('candidate',cand)] for task,n in zip(('a','b','c'),counts) for repeat in range(2)]
    def test_strict_improvement_passes(self):self.assertEqual(gate(self.rows(),['a','b','c'])['decision'],'pass')
    def test_ties_rejected(self):self.assertEqual(gate(self.rows(cand=(0,1,0)),['a','b','c'])['reason'],'tie_or_no_improvement')
    def test_regression_rejected_despite_aggregate_gain(self):self.assertEqual(gate(self.rows(inc=(1,0,0),cand=(0,2,2)),['a','b','c'])['reason'],'per_task_regression')
    def test_unbalanced_inconclusive(self):self.assertEqual(gate(self.rows()[:-1],['a','b','c'])['decision'],'inconclusive')
    def test_infrastructure_inconclusive(self):
        rows=self.rows();rows[0]['worker']['result']='infrastructure_failure'
        self.assertEqual(gate(rows,['a','b','c'])['decision'],'inconclusive')
    def test_budget_violation_rejects(self):
        rows=self.rows();rows[0]['worker']['within_budget']=False
        self.assertEqual(gate(rows,['a','b','c'])['decision'],'reject')
    def test_unenforced_integrity_cannot_pass(self):self.assertEqual(gate(self.rows(),['a','b','c'],integrity=False)['decision'],'inconclusive')
    def test_duplicate_rows_inconclusive(self):
        rows=self.rows();rows[-1]=copy.deepcopy(rows[0])
        self.assertEqual(gate(rows,['a','b','c'])['decision'],'inconclusive')
