import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from scripts.publish_github import audit,source_files,publish,verify_index


class PublishSafetyTests(unittest.TestCase):
    def test_source_selection_excludes_credentials_models_and_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ['.env','audio_models/small.pt','.neural-pr-private/events.jsonl','audio_runs/result.json','scripts/__pycache__/cache.pyc','scripts/source.py','docs/evidence/summary.json']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            self.assertEqual({str(p.relative_to(root)) for p in source_files(root)},{'scripts/source.py','docs/evidence/summary.json'})

    def test_known_local_key_is_blocked_without_printing_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);key='private-test-value-123456789'
            (root/'.env').write_text('MODEL_API_KEY='+key)
            code=root/'source.py';code.write_text('value='+repr(key))
            with self.assertRaisesRegex(ValueError,'credential value') as caught:audit([code],root)
            self.assertNotIn(key,str(caught.exception))

    def test_public_existing_repository_is_refused_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            def fake(args,*a,**kw):
                if args[:3]==['gh','api','user']:return subprocess.CompletedProcess(args,0,'owner\n','')
                if args[:3]==['gh','repo','view']:return subprocess.CompletedProcess(args,0,'{"isPrivate":false}','')
                raise AssertionError('Unexpected mutation '+str(args))
            with patch('scripts.publish_github.ROOT',Path(temp)),patch('scripts.publish_github.source_files',return_value=[]),patch('scripts.publish_github.audit',return_value={}),patch('scripts.publish_github.command',side_effect=fake):
                with self.assertRaisesRegex(ValueError,'public'):publish('fixture')

    def test_staged_content_is_checked_again_before_commit(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);subprocess.run(['git','init','-q'],cwd=root,check=True)
            code=root/'source.py';code.write_text('audited')
            hashes={'source.py':hashlib.sha256(code.read_bytes()).hexdigest()}
            subprocess.run(['git','add','source.py'],cwd=root,check=True);verify_index(root,hashes)
            code.write_text('changed after audit');subprocess.run(['git','add','source.py'],cwd=root,check=True)
            with self.assertRaisesRegex(ValueError,'Staged content changed'):verify_index(root,hashes)

if __name__=='__main__':unittest.main()
