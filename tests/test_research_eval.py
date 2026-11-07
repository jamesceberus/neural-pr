"""Focused verifier boundaries; synthetic fixtures are not Whisper research evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from neural_pr.state import digest,State
from whisper_repair.experiment import save,OFFICIAL_SMALL_SHA256
from research_eval.core import Research,validate_patch,prediction_score,GRID,confined,inventory
from research_eval.verifier import controls,verify


class ResearchContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.research=Research(self.temp.name)

    def test_allowlist_and_parent_cannot_be_overridden(self):
        p=dict(kind='decoder_self_attention_head_scale',layer=4,head=4,scale=1.25,parent_checkpoint_sha256=OFFICIAL_SMALL_SHA256)
        self.assertEqual(validate_patch(p),p)
        for update in ({'head':12},{'layer':True},{'scale':1.2},{'parent_checkpoint_sha256':'fake'},{'gate':{}}):
            with self.assertRaises(ValueError):validate_patch(dict(p,**update))

    def test_complete_prediction_grid_and_no_effect_comparator(self):
        predictions={x['id']:{'direction':'none'} for x in GRID};measurements={x['id']:{'status':'ok','mean_delta':0.} for x in GRID}
        result=prediction_score(predictions,measurements);self.assertEqual(result['accuracy'],1);self.assertEqual(result['no_effect_accuracy'],1)
        predictions.pop(GRID[0]['id']);result=prediction_score(predictions,measurements)
        self.assertEqual(result['missing'],1);self.assertEqual(result['accuracy'],7/8)
        measurements.pop(GRID[1]['id']);self.assertIsNone(prediction_score(predictions,measurements)['accuracy'])
        with self.assertRaises(ValueError):prediction_score({'private_case':{'direction':'none'}},{})
        with self.assertRaises(ValueError):prediction_score({GRID[0]['id']:{'direction':'none','confidence':float('nan')}},{})

    def test_paths_and_frozen_tampering_fail_closed(self):
        work=Path(self.temp.name)/'episodes/id/frozen';work.mkdir(parents=True);(work/'replay.py').write_text('pass')
        hashes=inventory(work);save(work.parent/'frozen.json',dict(artifacts=hashes,submission_hash=digest(hashes)))
        self.research.check_frozen('id');(work/'replay.py').write_text('changed')
        with self.assertRaises(ValueError):self.research.check_frozen('id')
        for path in ('../task.json','/etc/passwd','missing'):
            with self.assertRaises(ValueError):confined(work,path)
        (work/'link').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):inventory(work)

    def test_calibrated_correct_wrong_and_silence_controls(self):
        try:import numpy
        except ImportError:self.skipTest('numpy requires audio runtime')
        result=controls(self.research);self.assertTrue(result['all_passed'])
        self.assertFalse(result['cases']['accumulated_edit']['observed_valid'])
        self.assertFalse(result['cases']['stale_load']['observed_valid'])
        self.assertTrue(result['cases']['correct_slice']['observed_valid'])

    def test_abstention_and_missing_infrastructure_are_distinct(self):
        self.research.state.write('episodes/missing',dict(id='missing',status='missing_submission'))
        self.research.state.write('episodes/infra',dict(id='infra',status='infrastructure_failure',error='network'))
        with patch.object(Research,'task',return_value={'version':'fixture'}):
            self.assertEqual(verify(self.research,'missing')['submission_status'],'missing_submission')
            self.assertEqual(verify(self.research,'infra')['submission_status'],'infrastructure_failure')

    def test_seal_requires_all_scheduled_outcomes_and_blocks_running(self):
        self.research.state.write('comparison',dict(task_version='v',schedule=[dict(condition=c,attempt=i) for c in ('baseline','candidate') for i in (1,2)]))
        with self.assertRaises(ValueError):self.research.seal()
        for c in ('baseline','candidate'):
            for i in (1,2):self.research.state.write(f'episodes/{c}{i}',dict(id=c+str(i),condition=c,attempt=i,status='infrastructure_failure',comparison_member=True))
        seal=self.research.seal();self.assertEqual(len(seal['frozen_submissions']),4)
        with self.assertRaises(ValueError):self.research.seal()

    def test_safe_npz_rejects_nonfinite_unrelated_and_accumulated_values(self):
        try:import numpy as np
        except ImportError:self.skipTest('numpy requires audio runtime')
        from research_eval.artifacts import validate_projection
        expected=np.ones((4,4),dtype=np.float32);validate_projection(expected.copy(),expected)
        for change in (np.zeros((4,4),dtype=np.float32),np.full((4,4),np.nan,dtype=np.float32),expected.astype(np.float64),np.ones((3,4),dtype=np.float32)):
            with self.assertRaises(ValueError):validate_projection(change,expected)

    def test_executable_abstention_skips_candidate_loading(self):
        """A labeled software fixture, not an agent's research discovery."""
        episode_id='abstention-control';directory=self.research.root/'episodes'/episode_id;work=directory/'workspace';work.mkdir(parents=True)
        episode=dict(id=episode_id,kind='synthetic_verifier_control',policy_version='fixture',within_budget=True,status='submitted')
        self.research.state.write('episodes/'+episode_id,episode)
        (work/'replay.py').write_text("import json\nassert 2+2==4\njson.dump({'decision':'abstain','patch':None,'checks':[{'name':'synthetic arithmetic fixture','passed':True}]},open('replay_result.json','w'))\n")
        save(work/'claims.json',{'predictions':{}});(work/'experiments.jsonl').write_text('{"kind":"synthetic_fixture"}\n')
        submission=dict(episode_id=episode_id,task_version='fixture',agent_policy_version='fixture',parent_checkpoint_sha256=OFFICIAL_SMALL_SHA256,
                        code_artifact='replay.py',patch_manifest=None,checkpoint_artifact=None,claims_artifact='claims.json',experiment_log='experiments.jsonl',
                        decision='abstain',reported_limitations=['synthetic software control only'],reproduction={'entrypoint':'replay.py','dependencies':[]})
        save(work/'submission.json',submission)
        task={'version':'fixture','public':{'budgets':{'replay_seconds':20}}}
        with patch.object(Research,'task',return_value=task),patch('research_eval.verifier.invoke',side_effect=AssertionError('Must skip candidate loader')):
            self.research.freeze_submission(episode_id);result=verify(self.research,episode_id)
        self.assertEqual(result['reproducibility_status'],'passed',result)
        self.assertEqual(result['submission_status'],'valid_abstention')
        self.assertEqual(result['repair_status'],'abstained_no_credit')
        self.assertFalse(result['repair_improvement_credit'])


if __name__=='__main__':unittest.main()
