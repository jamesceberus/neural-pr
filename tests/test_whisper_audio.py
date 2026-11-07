"""Synthetic metric/guard tests. These are never evidence of Whisper accuracy."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from whisper_repair.metrics import compare,edits,score,words
from whisper_repair.experiment import Experiment,save,identity

MANIFEST=[{'id':'noise','kind':'nonspeech','reference_text':'','review_required':True},
          {'id':'speech','kind':'speech','reference_text':'the real voice speaks','review_required':False},
          {'id':'short','kind':'speech','reference_text':'thanks','review_required':False}]
def predictions(noise='fabricated words',speech='the real voice speaks',short='thanks'):
    return {key:{'id':key,'status':'ok','text':value} for key,value in [('noise',noise),('speech',speech),('short',short)]}

class AudioMetricTests(unittest.TestCase):
    def test_wer_counts_insertions_deletions_and_substitutions(self):
        self.assertEqual(edits('a b c','a x c d')['edits'],2)
        result=edits('a b c','');self.assertEqual(result['deletions'],3);self.assertEqual(result['wer'],1)
    def test_corpus_wer_is_not_average_clip_wer(self):
        result=score(MANIFEST,predictions(speech='',short='thanks'))
        self.assertEqual(result['speech']['wer'],4/5)
    def test_weak_labels_never_become_confirmed_hallucinations(self):
        result=score(MANIFEST,predictions())
        self.assertEqual(result['nonspeech']['weak_label_lexical_output_ids'],['noise'])
        self.assertEqual(result['nonspeech']['strong_label_lexical_output_ids'],[])
    def test_blanket_suppression_fails_retention_gate(self):
        result=compare(MANIFEST,predictions(),predictions('','',''))
        self.assertFalse(result['gate_pass']);self.assertEqual(result['newly_empty_speech_ids'],['speech','short'])
    def test_full_speech_preserving_gain_passes_only_supplied_label_gate(self):
        result=compare(MANIFEST,predictions(),predictions(noise=''))
        self.assertTrue(result['gate_pass']);self.assertIn('weak',result['gate_scope'])
    def test_errors_are_not_silence_and_make_gate_fail(self):
        candidate=predictions(noise='');candidate['short']={'status':'timeout','error':'synthetic test timeout'}
        result=compare(MANIFEST,predictions(),candidate)
        self.assertFalse(result['gate_pass']);self.assertEqual(len(result['candidate']['errors']),1)
        self.assertFalse(result['candidate']['speech']['wer_complete'])
        self.assertNotIn('short',result['candidate']['speech']['empty_ids'])
    def test_every_repair_must_cover_all_speech(self):
        incomplete=predictions();del incomplete['short']
        with self.assertRaises(ValueError):score(MANIFEST,incomplete)
    def test_no_punctuation_only_hallucination(self):self.assertEqual(words('… !!! ♪'),[])

class AudioFreezeTests(unittest.TestCase):
    def test_holdout_not_read_without_frozen_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            experiment=Experiment(temp)
            with patch('whisper_repair.experiment.load_pack',side_effect=AssertionError('Holdout was accessed')) as access:
                with self.assertRaises(FileNotFoundError):experiment.heldout('/heldout-not-accessible','/no-model')
                access.assert_not_called()
    def test_modified_evaluator_blocks_access_before_loading_holdout(self):
        with tempfile.TemporaryDirectory() as temp:
            experiment=Experiment(temp)
            package={'evaluation_code_hash':'wrong'}
            save(Path(temp)/'frozen_candidate.json',{'package':package,'sha256':identity(package)})
            with patch('whisper_repair.experiment.load_pack',side_effect=AssertionError('Holdout was accessed')) as access:
                with self.assertRaises(ValueError):experiment.heldout('/heldout-not-accessible','/no-model')
                access.assert_not_called()
    def test_no_candidate_selected_without_development_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'No development-qualified'):Experiment(temp).freeze()

class StaticWeightTests(unittest.TestCase):
    def test_synthetic_attenuation_changes_only_the_selected_head_columns(self):
        try:import torch
        except ImportError:self.skipTest('Torch is available in the separate audio environment only')
        from whisper_repair.weights import attenuate_head
        key='decoder.blocks.0.cross_attn.out.weight'
        weight=torch.arange(16,dtype=torch.float32).reshape(4,4)
        original=weight.clone();other=torch.ones(3);state={key:weight,'other':other}
        attenuate_head(state,0,1,0.5,n_heads=2)
        self.assertTrue(torch.equal(weight[:,:2],original[:,:2]))
        self.assertTrue(torch.equal(weight[:,2:],original[:,2:]*0.5))
        self.assertTrue(torch.equal(other,torch.ones(3)))
