import tempfile
import unittest
from fastapi.testclient import TestClient
from whisper_repair.mechanistic.dashboard import create_app

class MechanisticDashboardTests(unittest.TestCase):
    def test_existing_dashboard_extended_with_four_read_only_statuses(self):
        with tempfile.TemporaryDirectory() as temp:
            client=TestClient(create_app(mi_root=temp))
            self.assertIn('Whisper mechanistic evidence',client.get('/').text)
            report=client.get('/api/mechanistic').json()
            for key in ('implementation_status','mechanism_status','repair_status','agent_upgrade_status'):self.assertIn(key,report)
            self.assertEqual(client.post('/api/mechanistic',json={}).status_code,405)
            self.assertEqual(client.get('/api/mechanistic/audio/unknown-private-file').status_code,404)
            self.assertNotIn('API_KEY',str(report))
            self.assertEqual(client.get('/api/report').status_code,200)
