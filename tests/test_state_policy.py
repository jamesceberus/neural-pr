import copy
import json
from pathlib import Path
import tempfile
import unittest
from neural_pr.policy_store import PolicyStore,BASELINE
from neural_pr.state import State,digest,lock

class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.state=State(self.temp.name);self.store=PolicyStore(self.state);self.base=self.store.initialize()
    def candidate(self):
        content=copy.deepcopy(BASELINE);content['skills'].append('Inspect callers before changing an interface.')
        return self.store.create(content,self.base)
    def evaluation(self,version,**changes):
        record=dict(id='e',kind='promotion',decision='pass',candidate=version,incumbent=self.base)
        record.update(changes);record['record_hash']=digest(record);self.state.write('evaluations/e',record)
    def test_journal_survives_restart(self):
        self.state.emit('one',value=2);self.state.emit('two')
        self.assertEqual([x['kind'] for x in State(self.temp.name).events()],['one','two'])
    def test_corruption_is_detected(self):
        self.state.emit('one');p=self.state.events_path;p.write_text(p.read_text().replace('one','two'))
        with self.assertRaises(RuntimeError):self.state.events()
    def test_exclusive_controller(self):
        with lock(self.state.root/'controller.lock'):
            with self.assertRaises(RuntimeError):
                with lock(self.state.root/'controller.lock'):pass
    def test_unevaluated_candidate_cannot_activate(self):
        candidate=self.candidate()
        with self.assertRaises(ValueError):self.store.promote(candidate,'missing')
        self.assertEqual(self.store.active(),self.base)
    def test_rejected_candidate_cannot_activate(self):
        candidate=self.candidate();self.evaluation(candidate,decision='reject')
        with self.assertRaises(ValueError):self.store.promote(candidate,'e')
    def test_exact_hash_parent_and_atomic_pointer(self):
        candidate=self.candidate();self.evaluation(candidate)
        self.store.promote(candidate,'e');self.assertEqual(self.store.active(),candidate)
        with self.assertRaises(ValueError):self.store.promote(candidate,'e')
        self.assertEqual(self.store.rollback(),self.base)
        with self.assertRaises(ValueError):self.store.promote(candidate,'e')
    def test_result_record_tamper_rejected(self):
        candidate=self.candidate();self.evaluation(candidate)
        record=self.state.read('evaluations/e');record['candidate']=self.base
        self.state.write('evaluations/e',record)
        with self.assertRaises(ValueError):self.store.promote(candidate,'e')
    def test_package_tamper_rejected(self):
        candidate=self.candidate();path=self.store.directory/(candidate+'.json');path.chmod(0o600)
        package=json.loads(path.read_text());package['content']['skills'].append('changed');path.write_text(json.dumps(package))
        with self.assertRaises(RuntimeError):self.store.get(candidate)
    def test_tool_or_routing_changes_rejected(self):
        for key in ('tools_version','routing_version'):
            content=copy.deepcopy(BASELINE);content[key]='permission-escalation'
            with self.assertRaises(ValueError):self.store.create(content,self.base)
    def test_control_record_cannot_promote(self):
        candidate=self.candidate();self.evaluation(candidate,kind='control')
        with self.assertRaises(ValueError):self.store.promote(candidate,'e')
