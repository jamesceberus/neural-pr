import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from jobservice.api import create_app
with tempfile.TemporaryDirectory() as temp:
    api = TestClient(create_app(Path(temp) / 'test.sqlite'))
    assert api.get('/health').json() == {'status': 'ok'}
    headers = {'X-Tenant': 'a', 'Idempotency-Key': 'example'}
    r = api.post('/jobs', headers=headers, json={'payload': {'value': 2}})
    assert r.status_code == 200
    assert api.get('/jobs/' + r.json()['id'], headers=headers).status_code == 200
    assert api.get('/jobs/' + r.json()['id'], headers={'X-Tenant': 'other'}).status_code == 404
print('starter smoke passed')
