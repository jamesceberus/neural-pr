"""Run this test on a Docker host; never infer enforcement from local path-tool tests."""
from pathlib import Path
import tempfile
import unittest
from neural_pr.sandbox import Sandbox

class DockerIsolationTests(unittest.TestCase):
    @unittest.skipUnless(Sandbox.doctor()['image_ready'],'Docker worker image is unavailable')
    def test_host_controller_and_grader_are_inaccessible(self):
        with tempfile.TemporaryDirectory() as root:
            parent=Path(root);private=parent/'controller-secret';private.write_text('private')
            checkout=parent/'checkout';checkout.mkdir();checkout.chmod(0o777);(checkout/'TASK.md').write_text('frozen')
            result=Sandbox('docker').run(['python','-c',
                'from pathlib import Path; import socket; assert not Path('+repr(str(private))+').exists(); assert not Path("/task/../controller-secret").exists(); Path("/task/probe").write_text("task only"); print("isolated")'],checkout)
            self.assertEqual(result['code'],0,result)
            self.assertEqual(private.read_text(),'private')
