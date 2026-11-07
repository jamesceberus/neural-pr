"""Boundary checks; synthetic controls are labeled independently of real Whisper checks."""
import copy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from whisper_repair.mechanistic.interventions import validate,head_mode,tensor_hash,assert_uncached
from whisper_repair.mechanistic.evidence import qualify,CRITERIA
from whisper_repair.mechanistic.investigator import Investigator

class ProposalTests(unittest.TestCase):
    def test_allowlist_rejects_gate_override_and_invalid_indices(self):
        dimensions={'n_text_layer':12,'n_text_head':12}
        for args in [dict(layer=99,head=0,scale=.5,claim='x',predicted_direction='decrease_target_logprob_when_attenuated',would_weaken_claim='x'),
                     dict(layer=0,head=0,scale=.5,claim='x',predicted_direction='decrease_target_logprob_when_attenuated',would_weaken_claim='x',gate_pass=True)]:
            class MaliciousControl:
                def complete(self,*a,**k):
                    import json
                    return json.dumps({'tool':'propose_intervention','arguments':args}),{}
            with tempfile.TemporaryDirectory() as temp:
                result=Investigator(Path(temp),MaliciousControl()).ask('synthetic',dimensions,{})
                self.assertIsNone(result['proposal']);self.assertEqual(result['status'],'budget_exhausted')
    def test_runtime_next_proposal_uses_observed_results(self):
        class TestModel:
            def __init__(self):self.calls=0
            def complete(self,messages,*a,**k):
                import json
                self.calls+=1
                if self.calls==1:return '{"tool":"read_results"}',{}
                return json.dumps({'tool':'propose_intervention','arguments':{'layer':1,'head':2,'scale':.5,'claim':'Synthetic test hypothesis',
                       'predicted_direction':'decrease_target_logprob_when_attenuated','would_weaken_claim':'Speech and control-head effects are comparable'}}),{}
        with tempfile.TemporaryDirectory() as temp:
            result=Investigator(Path(temp),TestModel()).ask('synthetic',{'n_text_layer':12,'n_text_head':12},{},results={'observed_delta':-.1})
            self.assertEqual(result['status'],'proposed');self.assertEqual(result['trace'][0]['result'],{'observed_delta':-.1})
            self.assertFalse(result['approval_authority'])
    def test_shape_range_checks(self):
        model=SimpleNamespace(dims=SimpleNamespace(n_text_layer=12,n_text_head=12,n_text_state=768))
        for values in [(True,1,.5),(0,99,.5),(0,1,.1),(0,1,float('nan'))]:
            with self.assertRaises(ValueError):validate(model,*values)
    def test_prose_cannot_award_strong_mechanism(self):
        rows=[{'cohort':'unsupported_lexical','status':'ok','target_logprob_delta':-.5}]*3
        result=qualify(rows,[],CRITERIA,0,True,3,False)
        self.assertEqual(result['mechanism_status'],'causal_localization')
        self.assertFalse(result['predicates']['five_matched_controls_available'])
        self.assertFalse(result['predicates']['nonspeech_labels_verified'])

class RealWhisperChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import whisper,torch
        except ImportError:raise unittest.SkipTest('Original Whisper is available in .audio-venv only')
        if not Path('audio_models/small.pt').exists():raise unittest.SkipTest('Original small.pt unavailable')
        from whisper_repair.backend import Backend
        from whisper_repair.mechanistic.probes import ProbeEngine,trace_decoding,build_case
        from whisper_repair.experiment import rows
        cls.temp=tempfile.TemporaryDirectory()
        cls.backend=Backend('audio_models/small.pt');cls.model=cls.backend.model;cls.engine=ProbeEngine(cls.backend)
        cls.item=next(x for x in rows('whisper_audio_dev/manifest.jsonl') if x['id']=='one_minute_silence')
        with trace_decoding(cls.model,cls.temp.name) as traces:
            cls.output=cls.backend.transcribe(Path('whisper_audio_dev')/cls.item['audio_path'])
        cls.traces=traces;cls.case=build_case(cls.item,traces,cls.model,'unsupported_lexical','software_test')
    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'temp'):cls.temp.cleanup();del cls.engine,cls.backend,cls.model
    def test_actual_failure_window_and_token_alignment(self):
        import torch
        result=self.engine.forward(self.case,return_logits=True);logits=result.pop('_logits')
        self.assertEqual(self.case['target_position'],len(self.case['prefix_token_ids'])-1)
        self.assertIn('you',self.case['target_token_text'])
        self.assertAlmostEqual(result['target_logit'],logits[0,self.case['target_position'],self.case['target_token_id']].item())
        tokenizer=self.engine.task(self.case).tokenizer
        self.assertAlmostEqual(result['no_speech_probability_at_sot'],logits[0,self.case['sot_position']].softmax(-1)[tokenizer.no_speech].item())
        self.assertIsNone(result['kv_cache'])
    def test_capture_clones_identity_and_all_position_equivalence(self):
        import torch
        baseline=self.engine.forward(self.case,return_logits=True)['_logits']
        captured=[]
        with head_mode(self.model,0,0,1,mode='capture',capture=captured):
            observed=self.engine.forward(self.case,return_logits=True)['_logits']
        self.assertTrue(torch.equal(baseline,observed));self.assertFalse(captured[0].requires_grad)
        self.assertEqual(captured[0].shape[-1],64)
        hook=self.engine.forward(self.case,{'layer':0,'head':0,'scale':.5,'mode':'hook'},return_logits=True)['_logits']
        weight=self.engine.forward(self.case,{'layer':0,'head':0,'scale':.5,'mode':'weight'},return_logits=True)['_logits']
        self.assertTrue(torch.allclose(hook,weight,atol=CRITERIA['logits_atol'],rtol=CRITERIA['logits_rtol']))
    def test_exception_removes_hooks_and_restores_pristine_state(self):
        module=self.model.decoder.blocks[0].attn.out;original=tensor_hash(module.weight)
        for mode in ('hook','weight'):
            with self.assertRaisesRegex(RuntimeError,'synthetic fault'):
                with head_mode(self.model,0,0,.25,mode=mode):raise RuntimeError('synthetic fault injection')
            self.assertEqual(tensor_hash(module.weight),original);self.assertEqual(len(module._forward_pre_hooks),0)
        with self.assertRaises(ValueError):
            with head_mode(self.model,0,0,.5,mode='weight'):
                with head_mode(self.model,0,0,.5,mode='hook'):pass
        self.assertEqual(tensor_hash(module.weight),original)
        assert_uncached(self.model)
    def test_rejects_shifted_prefix_positions_and_ragged_inputs(self):
        for mutate in [lambda x:x.update(target_position=0),lambda x:x.update(prefix_token_ids=[[1,2],[1]]),
                       lambda x:x.update(prefix_token_ids=[1]+x['prefix_token_ids'][1:]),lambda x:x.update(sot_position=1)]:
            case=copy.deepcopy(self.case);mutate(case)
            with self.assertRaises(ValueError):self.engine.forward(case)
    def test_trace_matches_exact_production_skip_predicate(self):
        for window in self.traces:
            expected=window['no_speech_prob']>.6 and not window['avg_logprob']>-1
            self.assertEqual(window['skip_decision'],expected)
            self.assertEqual(window['sot_position'],window['initial_token_ids'].index(50258))
        self.assertEqual(self.output['text'],' you you you')
    def test_rejects_leftover_decoder_cache_hooks(self):
        module=self.model.decoder.blocks[0].attn.key
        handle=module.register_forward_hook(lambda module,inputs,output:None)
        try:
            with self.assertRaisesRegex(ValueError,'KV cache'):self.engine.forward(self.case)
        finally:handle.remove()
        assert_uncached(self.model)
