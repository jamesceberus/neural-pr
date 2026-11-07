"""Docker supports process/filesystem isolation. Local fallback is explicitly unenforced."""
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

IMAGE = 'neural-pr-worker:0.1'

def execute(command, cwd=None, timeout=30, input=None, env=None, output_limit=20000):
    # Child output lands in bounded regular files, preventing an untrusted stream from filling controller RAM.
    import resource
    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE,(2*1024*1024,2*1024*1024))
    with tempfile.TemporaryFile(mode='w+') as stdout_file, tempfile.TemporaryFile(mode='w+') as stderr_file:
        proc = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=stdout_file,
                                stderr=stderr_file, text=True, start_new_session=True, env=env,preexec_fn=limits)
        expired=False
        try:
            proc.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired:
            expired=True
            try:os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:pass
            proc.communicate()
        # Successful programs must not leave background descendants running between attempts.
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        stdout_file.seek(0);stderr_file.seek(0)
        stdout=stdout_file.read()[-output_limit:];stderr=stderr_file.read()[-12000:]
        return {'code':124 if expired else proc.returncode,'stdout':stdout,'stderr':stderr+('\ntimeout' if expired else '')}

class Sandbox:
    def __init__(self, mode='local-unenforced'):
        if mode not in ('docker', 'local-unenforced'):
            raise ValueError('Unknown isolation mode')
        self.mode = mode

    @staticmethod
    def doctor():
        docker = shutil.which('docker')
        ready = False
        image = False
        if docker:
            ready = execute([docker, 'info', '--format', '{{.ServerVersion}}'], timeout=8)['code'] == 0
            image = ready and execute([docker, 'image', 'inspect', IMAGE], timeout=8)['code'] == 0
        return {'docker_available': bool(docker), 'docker_ready': ready, 'image_ready': image,
                'supported_isolation': 'docker' if image else None,
                'local_limitation': 'Local fallback does not enforce process/filesystem secrecy or integrity. Never use adversarial code.'}

    def run(self, command, checkout, timeout=30, input=None):
        checkout = Path(checkout).resolve()
        if self.mode == 'docker':
            import uuid
            container_name='neural-pr-'+uuid.uuid4().hex
            command = ['docker', 'run', '--name',container_name,'--rm', '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                       '--pids-limit=64', '--memory=512m', '--cpus=1', '--read-only', '--tmpfs=/tmp:rw,nosuid,size=128m',
                       '--user=65534:65534', '-i', '--mount', 'type=bind,src=' + str(checkout) + ',dst=/task',
                       '--workdir=/task'] + (['--mount','type=bind,src='+str(checkout/'TASK.md')+',dst=/task/TASK.md,readonly'] if (checkout/'TASK.md').exists() else []) + [IMAGE] + command
            try:return execute(command, timeout=timeout, input=input)
            finally:execute(['docker','rm','-f',container_name],timeout=8)
        env = {'PATH': os.environ.get('PATH', ''), 'HOME': '/tmp', 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONHASHSEED': '0', 'PYTHONUNBUFFERED': '1'}
        command = [sys.executable if x == 'python' and i == 0 else x for i, x in enumerate(command)]
        return execute(command, cwd=checkout, timeout=timeout, input=input, env=env)

    def environment_digest(self):
        from importlib.metadata import version
        identity = {'mode': self.mode, 'python': sys.version, 'tool_version': 'file-tools-v1',
                    'dependencies':{name:version(name) for name in ('fastapi','httpx','uvicorn','pydantic','starlette')}}
        if self.mode == 'docker':
            identity['image'] = execute(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'])['stdout'].strip()
        from .state import digest
        return digest(identity)

class Files:
    """No arbitrary shell. Resolve every tool path; never follow checkout escape links."""
    def __init__(self, root, sandbox):
        self.root = Path(root).resolve()
        self.sandbox = sandbox

    def path(self, name):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
            raise ValueError('Path outside task surface')
        path = (self.root / relative).resolve()
        if self.root != path and self.root not in path.parents:
            raise ValueError('Symlink escapes checkout')
        return path

    def call(self, name, arguments, timeout=20):
        if name == 'list':
            return sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')
                          if p.is_file() and not p.is_symlink() and '.git' not in p.parts and '__pycache__' not in p.parts)[:300]
        if name == 'read':
            return self.path(arguments['path']).read_text()[:30000]
        if name == 'write':
            if arguments.get('path') == 'TASK.md' or self.path(arguments.get('path','')) == self.root/'TASK.md':
                raise ValueError('Frozen task manifest is read-only')
            content = arguments['content']
            if not isinstance(content, str) or len(content) > 100000:
                raise ValueError('Write exceeds file budget')
            path = self.path(arguments['path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return 'written'
        if name == 'check':
            target = arguments.get('path', 'smoke.py')
            self.path(target)
            return self.sandbox.run(['python', target], self.root, timeout=timeout)
        raise ValueError('Unsupported tool')

def git(checkout, *arguments, timestamp=None):
    env = dict(os.environ, GIT_AUTHOR_DATE=timestamp, GIT_COMMITTER_DATE=timestamp) if timestamp else None
    result = execute(['git', '-c', 'user.name=Neural PR', '-c', 'user.email=neural-pr@localhost', *arguments], cwd=checkout, env=env)
    if result['code']:
        raise RuntimeError(result['stderr'])
    return result['stdout'].strip()

def init_repository(checkout):
    git(checkout, 'init', '-q')
    git(checkout, 'add', '.')
    git(checkout, 'commit', '-qm', 'Controlled starter: frozen task scaffold', timestamp='2000-01-01T00:00:00Z')
    return git(checkout, 'rev-parse', 'HEAD')

def commit(checkout, message):
    # Persist all source edits, including unsuccessful work; runtime databases are ignored.
    git(checkout, 'add', '.')
    git(checkout, 'commit', '--allow-empty', '-qm', message)
    return git(checkout, 'rev-parse', 'HEAD')
