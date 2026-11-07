import json
from pathlib import Path
import tempfile
import time
import unittest
from fastapi.testclient import TestClient
from ui.server import create_app

class WhisperUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.client=TestClient(create_app(job_root=self.temp.name))
        self.token=self.client.get('/api/ui/session').json()['token']
    def test_actual_results_and_setup_are_visible(self):
        self.assertIn('Run an experiment',self.client.get('/').text)
        data=self.client.get('/api/ui/results').json()
        self.assertEqual(len(data['cases']),20);self.assertEqual(len(data['transcripts']),29)
        self.assertEqual(data['followup']['repair_status'],'rejected')
        self.assertTrue(data['setup']['checkpoint_exists'])
        self.assertEqual(self.client.get('/api/ui/report/followup').status_code,200)
    def test_untrusted_actions_cannot_mutate_gates_or_select_holdout(self):
        self.assertEqual(self.client.post('/api/ui/jobs',json={'kind':'verify_setup'}).status_code,403)
        headers={'X-Whisper-Session':self.token}
        params={'layer':4,'head':4,'scale':1.1,'case_id':'one_minute_silence','hypothesis':'A legitimate exploratory hypothesis'}
        self.assertEqual(self.client.post('/api/ui/jobs',headers=headers,json={'kind':'diagnostic','parameters':dict(params,case_id='noise_101509')}).status_code,422)
        self.assertEqual(self.client.post('/api/ui/jobs',headers=headers,json={'kind':'diagnostic','parameters':dict(params,gate_pass=True)}).status_code,422)
        self.assertEqual(self.client.post('/api/ui/jobs',headers=headers,json={'kind':'diagnostic','parameters':dict(params,scale=1.2)}).status_code,422)
        self.assertEqual(self.client.post('/api/ui/jobs',headers=headers,json={'kind':'verify_setup','parameters':{'api_key':'not-allowed'}}).status_code,422)
    def wait_for_result(self,job_id,timeout=120):
        started=time.monotonic()
        while time.monotonic()-started<timeout:
            jobs=self.client.get('/api/ui/jobs').json()['jobs']
            job=next(x for x in jobs if x['id']==job_id)
            if job['result'] is not None and job['status']!='running':return job
            time.sleep(.2)
        self.fail('UI worker did not finish within test timeout')
    def test_live_diagnostic_runs_from_pristine_and_returns_measured_scores(self):
        parameters={'layer':4,'head':4,'scale':1.1,'case_id':'one_minute_silence',
                    'hypothesis':'On this reused development input, amplification may reduce the fixed target probability.'}
        response=self.client.post('/api/ui/jobs',headers={'X-Whisper-Session':self.token},json={'kind':'diagnostic','parameters':parameters})
        self.assertEqual(response.status_code,200,response.text)
        job=self.wait_for_result(response.json()['id']);result=job['result']
        self.assertEqual(job['status'],'complete',result)
        self.assertTrue(result['hook_weight_equivalence_passed']);self.assertTrue(result['pristine_projection_restored'])
        self.assertTrue(isinstance(result['target_logprob_delta'],float))
        self.assertEqual(result['case_id'],'one_minute_silence')
        self.assertIn('not final transcription',result['result_scope'])
    def test_live_full_development_evaluates_all_genuine_speech(self):
        parameters={'layer':4,'head':4,'scale':1.1,'hypothesis':'A full development check tests whether amplification is a useful repair while retaining speech.'}
        response=self.client.post('/api/ui/jobs',headers={'X-Whisper-Session':self.token},json={'kind':'full_development','parameters':parameters})
        self.assertEqual(response.status_code,200,response.text)
        job=self.wait_for_result(response.json()['id']);result=job['result']
        self.assertEqual(job['status'],'complete',result)
        comparison=result['comparison'];self.assertEqual(comparison['candidate']['recordings'],29)
        self.assertEqual(comparison['candidate']['speech']['recordings'],12)
        self.assertEqual(len(comparison['candidate']['errors']),0)
        self.assertTrue(result['pristine_projection_restored'])
        self.assertFalse(comparison['gate_pass'])
    def test_cancelled_job_cannot_become_completed_and_original_is_preserved(self):
        parameters={'layer':4,'head':4,'scale':1.1,'case_id':'one_minute_silence','hypothesis':'Cancellation test of a controlled development probe.'}
        response=self.client.post('/api/ui/jobs',headers={'X-Whisper-Session':self.token},json={'kind':'diagnostic','parameters':parameters})
        self.assertEqual(response.status_code,200)
        job_id=response.json()['id']
        stopped=self.client.post('/api/ui/jobs/'+job_id+'/stop',headers={'X-Whisper-Session':self.token})
        self.assertEqual(stopped.status_code,200)
        self.assertEqual(stopped.json()['status'],'cancelled')
        # Wait for the monitor to process SIGKILL; it must preserve the terminal cancellation.
        for _ in range(30):
            job=next(x for x in self.client.get('/api/ui/jobs').json()['jobs'] if x['id']==job_id)
            if 'returncode' in job:break
            time.sleep(.1)
        self.assertEqual(job['status'],'cancelled')
