import os
import unittest
from unittest.mock import patch
from ui.agent_config import configure,ROOT
from whisper_repair.experiment import sha


class ResearchAgentProfileTests(unittest.TestCase):
    def test_wonder_selected_without_mutating_legacy_credentials(self):
        original=sha(ROOT/'.env')
        with patch.dict(os.environ,{},clear=True),patch('ui.agent_config.load_env'):
            profile=configure()
            self.assertEqual(os.environ['NEURAL_PR_MODEL'],'muse-wonder-1.0')
            self.assertEqual(os.environ['NEURAL_PR_BASE_URL'],'https://api.meta.ai/v1')
            self.assertEqual(os.environ['WHISPER_RESEARCH_ROOT'],str(ROOT/'research_runs/wonder-v2'))
            self.assertNotIn('MODEL_API_KEY',os.environ)
        self.assertEqual(sha(ROOT/'.env'),original)

    def test_explicit_environment_and_comparison_selection_win(self):
        with patch.dict(os.environ,{'NEURAL_PR_MODEL':'explicit-model','NEURAL_PR_BASE_URL':'https://example.test/v1','WHISPER_RESEARCH_ROOT':'/private/tmp/explicit-comparison'},clear=True),patch('ui.agent_config.load_env'):
            configure()
            self.assertEqual(os.environ['NEURAL_PR_MODEL'],'explicit-model')
            self.assertEqual(os.environ['NEURAL_PR_BASE_URL'],'https://example.test/v1')
            self.assertEqual(os.environ['WHISPER_RESEARCH_ROOT'],'/private/tmp/explicit-comparison')

if __name__=='__main__':unittest.main()
