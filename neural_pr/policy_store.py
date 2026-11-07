"""Immutable content-addressed policies; only controller calls activation."""
import difflib
import json
from .state import atomic_json, canonical, digest, lock, now

BASELINE = {
    'skills': ['Read the task contract. Inspect relevant code, implement the requested behavior, and run development checks.'],
    'context_rules': ['TASK.md', 'jobservice/store.py', 'jobservice/api.py', 'jobservice/worker.py', 'jobservice/client.py'],
    'tools_version': 'file-tools-v1', 'routing_version': 'fixed-model-v1',
}

class PolicyStore:
    def __init__(self, state):
        self.state = state
        self.directory = state.root / 'policies'
        self.directory.mkdir(exist_ok=True)

    def create(self, content, parent=None):
        if set(content) != set(BASELINE):
            raise ValueError('Policy keys must exactly match the permitted manifest')
        if not all(isinstance(content[k], list) and all(isinstance(x, str) and 0 < len(x) <= 8000 for x in content[k])
                   for k in ('skills', 'context_rules')):
            raise ValueError('skills and context_rules must contain bounded strings')
        from pathlib import Path
        if any(Path(rule).is_absolute() or '..' in Path(rule).parts or '.git' in Path(rule).parts for rule in content['context_rules']):
            raise ValueError('Context rules must stay within the task checkout')
        if len(canonical(content)) > 24000:
            raise ValueError('Policy exceeds size limit')
        if parent:
            old = self.get(parent)['content']
            if any(content[k] != old[k] for k in ('tools_version', 'routing_version')):
                raise ValueError('Tool and routing changes are outside MVP permitted surfaces')
        elif any(content[k] != BASELINE[k] for k in ('tools_version', 'routing_version')):
            raise ValueError('Unknown tool/routing identity')
        package = {'parent': parent, 'content': content}
        version = digest(package)
        path = self.directory / (version + '.json')
        if path.exists():
            self.get(version)
        else:
            atomic_json(path, package)
            path.chmod(0o444)
        return version

    def get(self, version):
        if len(version) != 64 or any(x not in '0123456789abcdef' for x in version):
            raise ValueError('Invalid policy identifier')
        package = json.loads((self.directory / (version + '.json')).read_text())
        if digest(package) != version:
            raise RuntimeError('Policy hash mismatch')
        return package

    def active(self):
        value = self.state.read('active')
        if not value:
            raise RuntimeError('Run init-demo first')
        self.get(value['version'])
        return value['version']

    def initialize(self):
        version = self.create(BASELINE)
        if not self.state.read('active'):
            self.state.write('active', {'version': version, 'previous': None, 'time': now()})
        return version

    def diff(self, parent, version):
        return ''.join(difflib.unified_diff(
            json.dumps(self.get(parent)['content'], indent=2).splitlines(True),
            json.dumps(self.get(version)['content'], indent=2).splitlines(True),
            fromfile=parent, tofile=version))

    def promote(self, version, evaluation_id):
        with lock(self.state.root / 'activation.lock'):
            package = self.get(version)
            current = self.active()
            evaluation = self.state.read('evaluations/' + evaluation_id)
            if not evaluation or evaluation.get('decision') != 'pass' or evaluation.get('kind') != 'promotion':
                raise ValueError('A passing promotion evaluation is required')
            if evaluation.get('candidate') != version or evaluation.get('incumbent') != current or package['parent'] != current:
                raise ValueError('Evaluated hash or active parent is stale')
            if evaluation.get('record_hash') != digest({k: v for k, v in evaluation.items() if k != 'record_hash'}):
                raise ValueError('Evaluation record integrity failure')
            if self.state.read('quarantine/' + version):
                raise ValueError('Quarantined policy cannot be promoted')
            # Write-ahead: recovery can identify an activation interrupted after its intent.
            self.state.emit('policy_promotion_intent', candidate=version, parent=current, evaluation_id=evaluation_id)
            self.state.write('active', {'version': version, 'previous': current, 'time': now(), 'evaluation_id': evaluation_id})
            self.state.emit('policy_promoted', version=version, previous=current, evaluation_id=evaluation_id)

    def rollback(self, reason='operator'):
        with lock(self.state.root / 'activation.lock'):
            active = self.state.read('active')
            if not active or not active.get('previous'):
                raise ValueError('No previous accepted policy')
            previous = active['previous']
            self.get(previous)
            self.state.write('quarantine/' + active['version'], {'reason': reason, 'time': now()})
            self.state.write('active', {'version': previous, 'previous': self.get(previous)['parent'], 'time': now()})
            self.state.emit('policy_rolled_back', previous=active['version'], version=previous, reason=reason)
            return previous
