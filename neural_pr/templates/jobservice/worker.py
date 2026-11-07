"""One tick is deliberately restartable; a new process can call tick again."""
import json
import time
from .store import Store

def tick(path, execute, now=None, lease_seconds=30):
    clock = now if now is not None else time.time()
    store = Store(path)
    store.recover(clock)
    job = store.claim(clock, lease_seconds)
    if job is None:
        return None
    try:
        result = execute(json.loads(job['payload']))
    except Exception as exc:
        store.finish(job['id'], job['token'], time.time() if now is None else now, error=str(exc))
    else:
        store.finish(job['id'], job['token'], time.time() if now is None else now, result=result)
    return job['id']
