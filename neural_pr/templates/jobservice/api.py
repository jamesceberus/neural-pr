import os
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from .store import Store

class Submission(BaseModel):
    payload: dict
    max_attempts: int = Field(default=3, ge=1, le=10)

def create_app(path=None):
    store = Store(path or os.environ.get('JOB_DB', 'jobs.sqlite'))
    app = FastAPI(title='Controlled durable job runner starter')
    app.state.store = store

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/jobs')
    def submit(body: Submission, x_tenant: str = Header(..., min_length=1),
               idempotency_key: str = Header(..., min_length=1)):
        try:
            return store.submit(x_tenant, idempotency_key, body.payload, body.max_attempts)
        except ValueError as exc:
            raise HTTPException(409, detail='idempotency_conflict') from exc

    @app.get('/jobs/{job_id}')
    def get(job_id: str, x_tenant: str = Header(..., min_length=1)):
        job = store.get(x_tenant, job_id)
        if job is None:
            raise HTTPException(404, detail='job_not_found')
        return job

    @app.post('/jobs/{job_id}/cancel')
    def cancel(job_id: str, x_tenant: str = Header(..., min_length=1)):
        job = store.cancel(x_tenant, job_id)
        if job is None:
            raise HTTPException(404, detail='job_not_found')
        return job
    return app
