"""Trusted test-only reference. Never copied into runtime starter/evaluation worktrees."""
import contextlib
import json
import sqlite3
import uuid

class Store:
    def __init__(self,path):
        self.path=str(path)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, key TEXT NOT NULL,
                payload TEXT NOT NULL, max_attempts INTEGER NOT NULL,
                state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                token TEXT, lease_until REAL, result TEXT)''')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS tenant_key ON jobs(tenant,key)')

    @contextlib.contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def get(self,tenant,job_id):
        with self.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE tenant=? AND id=?',(tenant,job_id)).fetchone()
            return dict(row) if row else None

    def submit(self,tenant,key,payload,max_attempts=3):
        encoded=json.dumps(payload,sort_keys=True)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM jobs WHERE tenant=? AND key=?',(tenant,key)).fetchone()
            if row:
                if row['payload']!=encoded or row['max_attempts']!=max_attempts:raise ValueError('idempotency_conflict')
                return dict(row)
            identity=uuid.uuid4().hex
            db.execute('INSERT INTO jobs(id,tenant,key,payload,max_attempts,state) VALUES(?,?,?,?,?,?)',
                       (identity,tenant,key,encoded,max_attempts,'queued'))
            return dict(db.execute('SELECT * FROM jobs WHERE id=?',(identity,)).fetchone())

    def claim(self,now,lease_seconds=30):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM jobs WHERE state='queued' AND attempts<max_attempts ORDER BY rowid LIMIT 1").fetchone()
            if row is None:return None
            db.execute("UPDATE jobs SET state='running',attempts=attempts+1,token=?,lease_until=? WHERE id=?",
                       (uuid.uuid4().hex,now+lease_seconds,row['id']))
            return dict(db.execute('SELECT * FROM jobs WHERE id=?',(row['id'],)).fetchone())

    def finish(self,job_id,token,now,result=None,error=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM jobs WHERE id=? AND state='running' AND token=? AND lease_until>?",(job_id,token,now)).fetchone()
            if row is None:return False
            state='succeeded' if error is None else 'queued' if row['attempts']<row['max_attempts'] else 'failed'
            db.execute('UPDATE jobs SET state=?,result=?,token=NULL,lease_until=NULL WHERE id=?',
                       (state,json.dumps(result) if error is None else error,job_id))
            return True

    def recover(self,now):
        with self.connect() as db:
            cursor=db.execute("UPDATE jobs SET state=CASE WHEN attempts<max_attempts THEN 'queued' ELSE 'failed' END,token=NULL,lease_until=NULL WHERE state='running' AND lease_until<=?",(now,))
            return cursor.rowcount

    def cancel(self,tenant,job_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE jobs SET state='cancelled',token=NULL,lease_until=NULL WHERE tenant=? AND id=? AND state IN ('queued','running')",(tenant,job_id))
            row=db.execute('SELECT * FROM jobs WHERE tenant=? AND id=?',(tenant,job_id)).fetchone()
            return dict(row) if row else None
