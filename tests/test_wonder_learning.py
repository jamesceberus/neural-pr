"""Synthetic launcher checks; no simulated result is research evidence."""
import tempfile
import os
import shutil
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock,patch
from neural_pr.state import State
from scripts.run_wonder_learning import execute,prepare_docker_path,inherit_exposure


class WonderLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.model=MagicMock();self.model.model='muse-wonder-1.0';self.model.base_url='https://api.meta.ai/v1'
        self.model.identity.return_value=dict(model='muse-wonder-1.0',base_url=self.model.base_url,adapter='json-chat-v1',temperature=.2)
        self.root=Path(self.temp.name)/'run'
        self.prepare=patch('scripts.run_wonder_learning.prepare_docker_path',return_value={'status':'fixture'})
        self.prepare.start();self.addCleanup(self.prepare.stop)
        self.exposure=patch('scripts.run_wonder_learning.inherit_exposure',return_value={'sources':[],'blocks':[],'deadline':'fixture'})
        self.exposure.start();self.addCleanup(self.exposure.stop)

    def run_fixture(self,ready=True,docker=True,complete=True):
        self.model.probe.return_value={'ready':ready}
        sandbox=dict(docker_available=docker,docker_ready=docker,image_ready=docker)
        report=dict(main_task_complete=complete,counts={'attempts':1,'promotions':0},active_agent_version='fixture',improvement_outcome='no_validated_improvement')
        with patch('scripts.run_wonder_learning.configure'),patch('scripts.run_wonder_learning.Model',return_value=self.model),patch('scripts.run_wonder_learning.Sandbox.doctor',return_value=sandbox),patch('scripts.run_wonder_learning.Controller') as constructor:
            controller=constructor.return_value;controller.run.return_value=report;controller.report.return_value=report
            controller.audit.return_value={'decision':'audit_passed'}
            result=execute(self.root,episodes=3)
            return result,constructor,controller

    def test_blocked_infrastructure_does_not_initialize_or_consume(self):
        result,constructor,_=self.run_fixture(ready=False,docker=False)
        self.assertEqual(result['execution_status'],'blocked_infrastructure');self.assertEqual(len(result['blockers']),2)
        constructor.assert_not_called();self.assertEqual(State(self.root).read('consumed',{}),{})
        self.assertFalse((self.root/'bank.json').exists())

    def test_real_loop_is_delegated_and_incomplete_work_preserves_audit(self):
        result,_,controller=self.run_fixture(complete=False)
        controller.initialize.assert_called_once_with('docker');controller.run.assert_called_once_with(episodes=3,resume=False)
        controller.audit.assert_not_called();self.assertEqual(result['execution_status'],'stopped_incomplete')

    def test_complete_without_improvement_is_not_reported_as_upgrade(self):
        result,_,controller=self.run_fixture()
        controller.audit.assert_called_once();self.assertEqual(result['execution_status'],'completed')
        self.assertFalse(result['agent_improvement_demonstrated'])

    def test_existing_local_experiment_cannot_resume_as_enforced(self):
        State(self.root).write('experiment',{'fixture':True})
        self.model.probe.return_value={'ready':True}
        with patch('scripts.run_wonder_learning.configure'),patch('scripts.run_wonder_learning.Model',return_value=self.model),patch('scripts.run_wonder_learning.Sandbox.doctor',return_value=dict(docker_available=True,docker_ready=True,image_ready=True)),patch('scripts.run_wonder_learning.Controller') as constructor:
            constructor.return_value.sandbox.mode='local-unenforced'
            result=execute(self.root)
            self.assertEqual(result['execution_status'],'stopped_error')
            constructor.return_value.run.assert_not_called()

class DockerHelperPathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def binary(self,directory,name):
        directory.mkdir(exist_ok=True);path=directory/name;path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o755);return path

    def test_missing_helper_becomes_visible_in_child_without_replacing_docker(self):
        original=self.root/'original';desktop=self.root/'desktop'
        docker=self.binary(original,'docker');helper=self.binary(desktop,'docker-credential-desktop')
        with patch.dict(os.environ,{'PATH':str(original)}):
            result=prepare_docker_path([desktop]);self.assertEqual(result['status'],'added_to_process_path')
            self.assertEqual(shutil.which('docker'),str(docker))
            child=subprocess.run([sys.executable,'-c','import shutil;print(shutil.which("docker-credential-desktop"))'],capture_output=True,text=True,check=True)
            self.assertEqual(child.stdout.strip(),str(helper))
            self.assertEqual(prepare_docker_path([desktop])['status'],'already_available')

    def test_existing_helper_and_nonexecutable_candidates_leave_path_alone(self):
        existing=self.root/'existing';self.binary(existing,'docker-credential-desktop')
        with patch.dict(os.environ,{'PATH':str(existing)}):
            self.assertEqual(prepare_docker_path([])['status'],'already_available');self.assertEqual(os.environ['PATH'],str(existing))
        bad=self.root/'bad';bad.mkdir();(bad/'docker-credential-desktop').write_text('not executable')
        with patch.dict(os.environ,{'PATH':str(self.root/'missing')}):
            before=os.environ['PATH'];self.assertEqual(prepare_docker_path([bad])['status'],'helper_not_found');self.assertEqual(os.environ['PATH'],before)


class ExposureInheritanceTests(unittest.TestCase):
    def test_parser_fix_preserves_consumed_blocks_and_original_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);old=State(root/'.neural-pr-old');new=State(root/'.neural-pr-new')
            old.write('bank',{'bank_hash':'same'});new.write('bank',{'bank_hash':'same'})
            old.write('experiment',{'created_at':'2026-11-07T10:00:00+00:00','deadline_hours':7})
            new.write('experiment',{'created_at':'2026-11-07T11:00:00+00:00','deadline_hours':7})
            old.write('consumed',{'audit':{'evaluation_id':'original'},'A':{'evaluation_id':'original-A'}})
            result=inherit_exposure(new,root)
            self.assertEqual(result['blocks'],['A','audit'])
            self.assertTrue(new.read('consumed')['audit']['ineligible_as_fresh'])
            self.assertEqual(new.read('experiment')['created_at'],'2026-11-07T10:00:00+00:00')
            self.assertEqual(old.read('consumed')['audit'],{'evaluation_id':'original'})

if __name__=='__main__':unittest.main()
