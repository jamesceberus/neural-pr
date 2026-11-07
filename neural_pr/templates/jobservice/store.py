"""SQLite persistence. Complete the frozen contract in TASK.md."""
import json
import sqlite3
import uuid

class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, key TEXT NOT NULL,
                payload TEXT NOT NULL, max_attempts INTEGER NOT NULL,
                state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                token TEXT, lease_until REAL, result TEXT)''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def get(self, tenant, job_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=? AND tenant=?', (job_id, tenant)).fetchone()
            return dict(row) if row else None

    def submit(self, tenant, key, payload, max_attempts=3):
        # Starter supports creation; idempotency and conflicts are unfinished.
        job_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO jobs(id,tenant,key,payload,max_attempts,state) VALUES(?,?,?,?,?,?)',
                       (job_id, tenant, key, json.dumps(payload, sort_keys=True), max_attempts, 'queued'))
        return self.get(tenant, job_id)

    def claim(self, now, lease_seconds=30):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            db.execute("UPDATE jobs SET state='running',attempts=attempts+1,token=?,lease_until=? WHERE id=?",
                       (token, now + lease_seconds, row['id']))
            return dict(db.execute('SELECT * FROM jobs WHERE id=?', (row['id'],)).fetchone())

    def finish(self, job_id, token, now, result=None, error=None):
        # Starter completion lacks fencing, retry bounds and cancellation protection.
        with self.connect() as db:
            db.execute('UPDATE jobs SET state=?,result=? WHERE id=?',
                       ('queued' if error else 'succeeded', json.dumps(result), job_id))
            return True

    def cancel(self, tenant, job_id):
        return self.get(tenant, job_id)

    def recover(self, now):
        return 0
