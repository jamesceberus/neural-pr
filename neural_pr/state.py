"""Durable, hash-chained journal. Hashes detect corruption, not a malicious host owner."""
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.atomic-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(canonical(value) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)

@contextlib.contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another trusted controller is active') from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)

class State:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / 'events.jsonl'

    def read(self, name, default=None):
        path = self.root / (name + '.json')
        return json.loads(path.read_text()) if path.exists() else default

    def write(self, name, value):
        atomic_json(self.root / (name + '.json'), value)

    def events(self):
        if not self.events_path.exists():
            return []
        previous = '0' * 64
        output = []
        for line in self.events_path.read_text().splitlines():
            event = json.loads(line)
            claimed = event.pop('hash')
            if event['previous'] != previous or digest(event) != claimed:
                raise RuntimeError('Journal integrity failure')
            event['hash'] = claimed
            previous = claimed
            output.append(event)
        return output

    def emit(self, kind, **data):
        # A separate journal lock also protects API-tool events if used concurrently.
        with lock(self.root / 'journal.lock'):
            events = self.events()
            event = {'sequence': len(events), 'time': now(), 'kind': kind, 'data': data,
                     'previous': events[-1]['hash'] if events else '0' * 64}
            event['hash'] = digest(event)
            with self.events_path.open('a') as stream:
                stream.write(canonical(event) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            return event
