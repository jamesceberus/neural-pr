"""Read-only local evidence dashboard. No mutations or private task-bank endpoints."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from .controller import Controller

def create_app(root='.neural-pr'):
    app=FastAPI(title='Neural PR · Evidence console',docs_url=None,redoc_url=None)
    @app.get('/')
    def index():return HTMLResponse((Path(__file__).parent/'web'/'index.html').read_text())
    @app.get('/api/report')
    def report():
        try:return JSONResponse(Controller(root).report(),headers={'Cache-Control':'no-store'})
        except Exception as exc:return JSONResponse({'error':type(exc).__name__},status_code=503)
    @app.get('/api/events')
    def events():
        from .state import State
        public=[]
        for event in State(root).events()[-100:]:
            # Public evidence intentionally excludes prompts, source, hidden fixture definitions and provider headers.
            data={k:v for k,v in event['data'].items() if k in ('run_id','application_commit','agent_version','reason','result','objective_passed','block','candidate_id','decision','version','previous','isolation','disposition','label')}
            public.append({'time':event['time'],'kind':event['kind'],'data':data,'hash':event['hash']})
        return {'events':public}
    return app
