"""Local UI on top of the existing read-only evidence application and bounded workers."""
import base64
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time
import uuid

from fastapi import HTTPException,Request
from fastapi.responses import HTMLResponse,FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from neural_pr.state import State
from whisper_repair.experiment import read,rows,save,sha,now,identity,DECODE
from whisper_repair.mechanistic.dashboard import create_app as evidence_app

ROOT=Path(__file__).resolve().parents[1]

def safe_read(path,default=None):
    try:return read(path)
    except (FileNotFoundError,json.JSONDecodeError):return default

class Jobs:
    def __init__(self,root,research_root=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.research_root=Path(research_root or ROOT/'research_runs').resolve()
        self.guard=threading.Lock();self.process=None
    def list(self):
        output=[]
        for path in sorted(self.root.glob('*/job.json'),key=lambda x:x.stat().st_mtime,reverse=True):
            data=safe_read(path,{})
            if not data:continue
            result=safe_read(path.parent/'result.json')
            owned=self.process is not None and self.process.pid==data.get('pid')
            if result and data['status']=='running' and not owned:
                data['status']='complete' if result.get('status')=='ok' else 'failed';save(path,data)
            data['progress']=safe_read(path.parent/'progress.json')
            data['result']=result;output.append(data)
        return output[:30]
    def start(self,kind,parameters):
        with self.guard:
            if self.process is not None and self.process.poll() is None:raise ValueError('An experiment is already running. Wait or stop it before starting another.')
            if kind not in ('setup_model','research_connection') and not (ROOT/'.audio-venv/bin/python').exists():raise ValueError('Audio runtime is missing. Use Prepare model & runtime in Setup first.')
            job_id=uuid.uuid4().hex;directory=self.root/job_id;directory.mkdir()
            request={'kind':kind,'parameters':parameters,'created':now(),'provenance':{'application_commit':safe_read(ROOT/'audio_runs/mechanistic_v1/manifest.json',{}).get('application_commit'),'agent_policy_version':read(ROOT/'.neural-pr/active.json')['version'],'configuration_hash':identity(DECODE),'ui_server_source_sha256':sha(__file__)}};save(directory/'request.json',request)
            if kind.startswith('research_'):
                request['research_root']=str(self.research_root);save(directory/'request.json',request)
            job={'id':job_id,'kind':kind,'parameters':parameters,'status':'running','started':now(),'request_sha256':sha(directory/'request.json')}
            save(directory/'job.json',job)
            env={key:value for key,value in os.environ.items() if not key.endswith(('API_KEY','TOKEN'))}
            if kind in ('research_connection','research_episode'):
                # These trusted coordinators call the provider; their public Python checks still receive sanitized environments.
                for key in ('MODEL_API_KEY','GEMINI_API_KEY','NEURAL_PR_API_KEY'):
                    if key in os.environ:env[key]=os.environ[key]
            log=(directory/'worker.log').open('w')
            worker=ROOT/'scripts/check_research_api.py' if kind=='research_connection' else ROOT/'scripts/research_ui_worker.py' if kind.startswith('research_') else ROOT/'scripts/setup_whisper_runtime.py' if kind=='setup_model' else ROOT/'scripts/ui_worker.py'
            interpreter=sys.executable if kind=='setup_model' or kind.startswith('research_') else str(ROOT/'.audio-venv/bin/python')
            self.process=subprocess.Popen([interpreter,str(worker),str(directory/'request.json')],
                 cwd=ROOT,stdout=log,stderr=log,env=env,start_new_session=True)
            job['pid']=self.process.pid;save(directory/'job.json',job)
            process=self.process
            def monitor():
                timeout=45 if kind=='research_connection' else 660 if kind.startswith('research_') else 600 if kind=='setup_model' else 180 if kind=='full_development' else 90
                try:code=process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait();code=124
                finally:log.close()
                with self.guard:
                    current=read(directory/'job.json')
                    if current['status']!='cancelled':current['status']='complete' if code==0 else 'failed'
                    if code and not (directory/'result.json').exists():save(directory/'result.json',{'status':'error','error':'Hard process timeout' if code==124 else 'Worker exited; see its local log','inference_error_is_not_silence':True})
                    current.update(finished=now(),returncode=code);save(directory/'job.json',current)
            threading.Thread(target=monitor,daemon=True).start()
            return job
    def stop(self,job_id):
        with self.guard:
            path=self.root/job_id/'job.json'
            if not path.exists():raise ValueError('Unknown job')
            job=read(path)
            if job['status']!='running':return job
            if self.process is None or self.process.pid!=job['pid']:raise ValueError('Job belongs to a previous server session; inspect its recorded result first')
            try:os.killpg(job['pid'],signal.SIGKILL)
            except ProcessLookupError:pass
            job.update(status='cancelled',finished=now());save(path,job);return job

def create_app(job_root=None,research_root=None):
    app=evidence_app();app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])
    app.router.routes=[route for route in app.router.routes if getattr(route,'path',None)!='/']
    research_root=Path(research_root or os.environ.get('WHISPER_RESEARCH_ROOT',ROOT/'research_runs')).resolve()
    session=secrets.token_urlsafe(32);jobs=Jobs(job_root or ROOT/'audio_runs/ui/jobs',research_root)
    @app.get('/')
    def index():return HTMLResponse((ROOT/'ui/static/index.html').read_text())
    @app.get('/research')
    def research_index():return HTMLResponse((ROOT/'ui/static/research.html').read_text())
    @app.get('/api/research/results')
    def research_results():
        result=safe_read(research_root/'report.json',{'episodes':[],'comparison_status':'not_initialized','conclusion':'Initialize a frozen research task with the documented CLI first.'})
        return dict(result,coding_policy=safe_read(ROOT/'research_runs/policy_upgrade_verified/summary.json'))
    @app.get('/api/ui/session')
    def session_info():return {'token':session}
    @app.get('/api/ui/results')
    def results():
        main=ROOT/'audio_runs/mechanistic_v1';follow=ROOT/'audio_runs/mechanistic_direction_v2'
        cases=[]
        for path in sorted((main/'cases').glob('*.json')):
            value=read(path);cases.append({'id':value['case_id'],'cohort':value['cohort'],'target_token':value['target_token_text'],
                'former_partition':value['partition'],'window_seconds':value['window']['bounds_seconds']})
        transcripts=[]
        for path in sorted((main/'baseline').glob('*.json')):
            before=read(path);after=safe_read(main/'application/selected'/path.name,{})
            transcripts.append({'id':before['id'],'baseline':before['text'],'rejected_edit':after.get('text'),
                               'audio_url':'/api/mechanistic/audio/'+before['id']})
        return {'mechanistic':safe_read(main/'summary.json',{}),'followup':safe_read(follow/'summary.json',{}),
                'interpretation':safe_read(follow/'interpretation.json',{}),'stratified':safe_read(follow/'stratified_diagnostics.json',[]),
                'original_transitions':safe_read(follow/'original_paired_transitions.json',{}),
                'manifest':safe_read(follow/'manifest.json',{}),'cases':cases,'transcripts':transcripts,
                'setup':{'checkpoint_exists':(ROOT/'audio_models/small.pt').exists(),'runtime_exists':(ROOT/'.audio-venv/bin/python').exists(),
                         'checkpoint':'multilingual small','device':'CPU','heldout_status':'Consumed · fresh recordings required for new validation'},
                'recorded':True,'time':now()}
    @app.get('/api/ui/jobs')
    def list_jobs():return {'jobs':jobs.list()}
    @app.post('/api/ui/jobs')
    async def start(request:Request):
        if request.headers.get('X-Whisper-Session')!=session:raise HTTPException(403,'Local session required')
        data=await request.json()
        if not isinstance(data,dict) or set(data)-{'kind','parameters'}:raise HTTPException(422,'Unknown request fields')
        kind=data.get('kind');parameters=data.get('parameters',{})
        if kind not in ('setup_model','verify_setup','diagnostic','full_development','research_episode','research_verify','research_report','research_connection'):raise HTTPException(422,'Unknown experiment action')
        if kind.startswith('research_'):
            if not isinstance(parameters,dict):raise HTTPException(422,'Parameters must be an object')
            if kind=='research_episode' and (set(parameters)!={'condition','attempt'} or parameters['condition'] not in ('baseline','candidate') or type(parameters['attempt'])!=int or parameters['attempt'] not in (1,2)):raise HTTPException(422,'Choose a frozen procedure and attempt')
            if kind=='research_verify' and (set(parameters)!={'episode_id'} or parameters['episode_id'] not in {read(p)['id'] for p in (research_root/'episodes').glob('*.json')}):raise HTTPException(422,'Choose a recorded episode; no private-input or gate arguments accepted')
            if kind in ('research_report','research_connection') and parameters!={}:raise HTTPException(422,'Action takes no parameters; credentials stay in the server environment')
            if kind!='research_connection' and not (research_root/'task.json').exists():raise HTTPException(409,'Initialize the trusted task registry first; see docs/RESEARCH_EVAL_RESULTS.md')
            try:return jobs.start(kind,parameters)
            except ValueError as exc:raise HTTPException(409,str(exc)) from exc
        if kind in ('setup_model','verify_setup') and parameters!={}:raise HTTPException(422,'Setup verification accepts no custom fields')
        if kind not in ('setup_model','verify_setup'):
            allowed={'layer','head','scale','hypothesis'}|({'case_id'} if kind=='diagnostic' else set())
            if not isinstance(parameters,dict) or set(parameters)!=allowed:raise HTTPException(422,'Use the declared hypothesis and parameters')
            if type(parameters['layer'])!=int or type(parameters['head'])!=int or not 0<=parameters['layer']<12 or not 0<=parameters['head']<12:raise HTTPException(422,'Layer/head must be 0–11')
            if isinstance(parameters['scale'],bool) or parameters['scale'] not in (0,.9,1,1.1,1.25):raise HTTPException(422,'Scale outside protocol v2')
            if not isinstance(parameters['hypothesis'],str) or not 10<=len(parameters['hypothesis'])<=2000:raise HTTPException(422,'State a testable hypothesis first')
            if kind=='diagnostic' and parameters['case_id'] not in {p.stem for p in (ROOT/'audio_runs/mechanistic_v1/cases').glob('*.json')}:raise HTTPException(422,'Choose an available development probe')
        try:return jobs.start(kind,parameters)
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    @app.post('/api/ui/jobs/{job_id}/stop')
    def stop(job_id:str,request:Request):
        if request.headers.get('X-Whisper-Session')!=session:raise HTTPException(403,'Local session required')
        if len(job_id)!=32 or any(x not in '0123456789abcdef' for x in job_id):raise HTTPException(422,'Invalid job ID')
        try:return jobs.stop(job_id)
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    @app.get('/api/ui/report/{name}')
    def report(name:str):
        paths={'mechanistic':ROOT/'docs/MECHANISTIC_RESULTS.md','followup':ROOT/'docs/HEAD_STRENGTH_FOLLOWUP.md',
               'audio':ROOT/'docs/AUDIO_RESULTS.md','agent':ROOT/'docs/AGENT_POLICY_RESULTS.md','specification':ROOT/'docs/mechanistic_interpretability.md',
               'research':ROOT/'docs/RESEARCH_EVAL_RESULTS.md','research-spec':ROOT/'docs/research_agent_evaluation.md',
               'policy-upgrade':ROOT/'docs/VERIFIED_POLICY_UPGRADE.md'}
        if name not in paths or not paths[name].exists():raise HTTPException(404,'Report unavailable')
        return FileResponse(paths[name],media_type='text/markdown')
    return app
