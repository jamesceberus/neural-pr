"""Synthetic provider envelopes; no inference improvement is implied."""
import json
import unittest
from unittest.mock import patch
from neural_pr.worker import InfrastructureError
from ui.meta_model import WonderModel,decode_response


class MetaModelTests(unittest.TestCase):
    def model(self):return WonderModel('https://api.meta.ai/v1','muse-wonder-1.0','private-fixture-key')
    def response(self,content='{"ready":true}',finish='stop'):
        return {'choices':[{'message':{'content':content},'finish_reason':finish}], 'usage':{'total_tokens':99,'completion_tokens':90}}
    def envelope(self,response):return {'code':0,'stdout':json.dumps(decode_response(response))}

    def test_final_text_and_usage_are_preserved(self):
        result=decode_response(self.response());self.assertEqual(result['content'],'{"ready":true}');self.assertEqual(result['usage']['total_tokens'],99)

    def test_reasoning_only_length_response_is_specific_and_not_exposed(self):
        response=self.response(None,'length');response['choices'][0]['message']['reasoning_content']='private reasoning fixture'
        result=decode_response(response)
        self.assertIn('budget exhausted',result['error']);self.assertTrue(result['metadata']['reasoning_present'])
        self.assertNotIn('private reasoning fixture',json.dumps(result))

    def test_truncated_final_text_is_not_an_action(self):
        result=decode_response(self.response('{"tool":','length'));self.assertNotIn('content',result)

    def test_probe_has_reasoning_budget_and_checks_actual_json(self):
        model=self.model()
        with patch('ui.meta_model.execute',return_value=self.envelope(self.response())) as transport:
            result=model.probe();self.assertTrue(result['ready'])
            args,kwargs=transport.call_args;request=json.loads(kwargs['input'])
            self.assertEqual(request['payload']['max_completion_tokens'],1024)
            self.assertEqual(request['payload']['reasoning_effort'],'minimal')
            self.assertNotIn('private-fixture-key',str(args))
        with patch('ui.meta_model.execute',return_value=self.envelope(self.response('{}'))):
            self.assertFalse(model.probe()['ready'])
        with patch('ui.meta_model.execute',return_value=self.envelope(self.response('{"ready":1}'))):
            self.assertFalse(model.probe()['ready'])

    def test_agent_requests_have_same_versioned_effort_and_cap(self):
        model=self.model()
        with patch('ui.meta_model.execute',return_value=self.envelope(self.response('{}'))) as transport:
            model.complete([{'role':'user','content':'fixture'}],max_tokens=5000)
            request=json.loads(transport.call_args.kwargs['input'])
            self.assertEqual(request['payload']['reasoning_effort'],'low');self.assertEqual(request['payload']['max_completion_tokens'],5000)
            self.assertEqual(model.identity()['adapter'],'meta-wonder-json-chat-v2')
            self.assertEqual(len(model.identity()['adapter_source_sha256']),64)

    def test_error_response_preserves_diagnostic_without_provider_body(self):
        model=self.model();response=self.response(None,'length')
        with patch('ui.meta_model.execute',return_value=self.envelope(response)):
            result=model.probe();self.assertFalse(result['ready']);self.assertEqual(result['metadata']['finish_reason'],'length')
            self.assertIn('budget exhausted',result['error'])
        result=decode_response({'error':{'message':'private-fixture-key'}})
        self.assertNotIn('private-fixture-key',json.dumps(result))

    def test_non_wonder_configuration_rejected(self):
        with self.assertRaises(ValueError):WonderModel('https://api.meta.ai/v1','different','fixture')

if __name__=='__main__':unittest.main()
