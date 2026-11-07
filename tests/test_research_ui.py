import tempfile
import unittest
import time
from pathlib import Path
from fastapi.testclient import TestClient
from ui.server import create_app


class ResearchUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.client=TestClient(create_app(job_root=Path(self.temp.name)/'jobs',research_root=Path(self.temp.name)/'research'))
        self.headers={'X-Whisper-Session':self.client.get('/api/ui/session').json()['token']}

    def test_viewer_uses_existing_server_and_discloses_missing_task(self):
        response=self.client.get('/research');self.assertEqual(response.status_code,200)
        self.assertIn('Repairs, causal predictions',response.text)
        self.assertEqual(self.client.get('/api/research/results').json()['comparison_status'],'not_initialized')
        self.assertIn('/research',self.client.get('/').text)

    def test_ui_cannot_choose_private_inputs_or_override_gate(self):
        for parameters in ({'condition':'baseline','attempt':1,'private_manifest':'/tmp/secret'},
                           {'condition':'candidate','attempt':1,'gate':{'pass':True}},
                           {'condition':'baseline','attempt':True}):
            response=self.client.post('/api/ui/jobs',headers=self.headers,json={'kind':'research_episode','parameters':parameters})
            self.assertEqual(response.status_code,422)
        self.assertEqual(self.client.post('/api/ui/jobs',headers=self.headers,json={'kind':'research_verify','parameters':{'episode_id':'arbitrary','protected':True}}).status_code,422)
        self.assertEqual(self.client.post('/api/ui/jobs',json={'kind':'research_report','parameters':{}}).status_code,403)

    def test_controller_task_required_before_running_episode(self):
        response=self.client.post('/api/ui/jobs',headers=self.headers,json={'kind':'research_episode','parameters':{'condition':'baseline','attempt':1}})
        self.assertEqual(response.status_code,409)

    def test_connection_preflight_does_not_consume_an_episode(self):
        response=self.client.post('/api/ui/jobs',headers=self.headers,json={'kind':'research_connection','parameters':{}})
        self.assertEqual(response.status_code,200,response.text)
        for _ in range(150):
            job=self.client.get('/api/ui/jobs').json()['jobs'][0]
            if job['status']!='running':break
            time.sleep(.2)
        self.assertEqual(job['status'],'complete',job)
        result=job['result']['connection'];self.assertIn('failure_stage',result)
        self.assertNotIn('key',result);self.assertNotIn('api_key',result)
        self.assertFalse((Path(self.temp.name)/'research/episodes').exists())
        self.assertEqual(self.client.post('/api/ui/jobs',headers=self.headers,json={'kind':'research_connection','parameters':{'api_key':'forbidden'}}).status_code,422)

if __name__=='__main__':unittest.main()
