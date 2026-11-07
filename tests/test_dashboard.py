from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from neural_pr.app import create_app
from neural_pr.controller import Controller
from tests.test_controller import OfflineModel

class DashboardTests(unittest.TestCase):
    def test_read_only_dashboard_and_no_private_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            controller=Controller(temp,model=OfflineModel());controller.initialize()
            client=TestClient(create_app(temp))
            response=client.get('/');self.assertEqual(response.status_code,200)
            self.assertIn('Improvement needs evidence',response.text)
            report=client.get('/api/report');self.assertEqual(report.status_code,200)
            text=report.text
            self.assertNotIn('MODEL_API_KEY',text)
            self.assertNotIn('correct',text)
            self.assertEqual(client.post('/api/report',json={}).status_code,405)
            self.assertEqual(client.get('/private/bank/scope.json').status_code,404)
            self.assertEqual(client.get('/api/events').status_code,200)
