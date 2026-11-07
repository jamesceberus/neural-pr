import json
import sys
import unittest
from unittest.mock import patch
from neural_pr.sandbox import execute
from neural_pr.worker import Model,InfrastructureError

class TransportTests(unittest.TestCase):
    def test_http_errors_are_sanitized_and_key_never_enters_argv(self):
        model=Model('https://api.example.test/v1','fixed-model','secret-control')
        with patch('neural_pr.sandbox.execute',return_value={'code':0,'stdout':'{"error":"Model API returned HTTP 401"}'}) as transport:
            with self.assertRaisesRegex(InfrastructureError,'HTTP 401'):model.complete([{'role':'user','content':'hello'}])
            args,kwargs=transport.call_args
            self.assertNotIn('secret-control',str(args))
            payload=json.loads(kwargs['input']);self.assertEqual(payload['key'],'secret-control')
            self.assertEqual(payload['payload']['model'],'fixed-model')
    def test_transport_has_hard_timeout_and_cleans_descendants(self):
        result=execute([sys.executable,'-c','import time;time.sleep(5)'],timeout=0.05)
        self.assertEqual(result['code'],124)
    def test_malformed_response_is_not_coding_failure(self):
        model=Model('https://api.example.test/v1','fixed-model','secret-control')
        with patch('neural_pr.sandbox.execute',return_value={'code':0,'stdout':'not-json'}):
            with self.assertRaises(InfrastructureError):model.complete([])
    def test_usage_preserved(self):
        model=Model('https://api.example.test/v1','fixed-model','secret-control')
        with patch('neural_pr.sandbox.execute',return_value={'code':0,'stdout':json.dumps({'content':'{}','usage':{'total_tokens':17}})}):
            content,usage=model.complete([])
            self.assertEqual(usage['total_tokens'],17)
