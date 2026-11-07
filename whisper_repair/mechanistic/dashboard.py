"""Extend the existing read-only dashboard, leaving its trusted controller/gate source intact."""
from pathlib import Path
import json
from neural_pr.app import create_app as original_app
from whisper_repair.experiment import read,rows
from .evidence import summary

PANEL='''<section class="card" id="mechanistic"><div class="cardhead"><h2>Whisper mechanistic evidence</h2><span class="badge neutral">RECORDED EXPERIMENT</span></div>
<p>Fixed-prefix diagnostics, application behavior, and policy evidence have separate outcomes.</p><div id="mi-status" class="stats" style="margin-top:15px"></div>
<div id="mi-provenance" class="identities"></div><div id="mi-diagnostic"></div><div id="mi-application"></div><div id="mi-examples"></div>
<p id="mi-gaps" style="font-size:11px;margin-top:12px"></p><p style="font-size:12px;margin-top:12px"><a href="/mechanistic/report">Open complete recorded report ↗</a></p></section>'''
SCRIPT='''<script>
(async function(){const miEsc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
try{const res=await fetch('/api/mechanistic');if(!res.ok)return;const d=await res.json();
document.getElementById('mi-status').innerHTML=['implementation_status','mechanism_status','repair_status','agent_upgrade_status'].map(k=>'<div class="identity"><div class="eyebrow">'+miEsc(k.replaceAll('_',' '))+'</div><strong style="font-size:12px">'+miEsc(d[k])+'</strong></div>').join('');
document.getElementById('mi-provenance').innerHTML=Object.entries(d.provenance||{}).map(([k,v])=>'<div class="identity"><div class="eyebrow">'+miEsc(k)+'</div><code>'+miEsc(v)+'</code></div>').join('');
function table(headers,values){return '<table><thead><tr>'+headers.map(x=>'<th>'+miEsc(x)+'</th>').join('')+'</tr></thead><tbody>'+values.map(row=>'<tr>'+row.map(x=>'<td>'+miEsc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}
document.getElementById('mi-diagnostic').innerHTML='<div class="sectionlabel">Confirmation: fixed-prefix diagnostic changes</div>'+table(['Head','Cohort','N','Δ log p(token)'],(d.diagnostic_table||[]).map(x=>[x.head,x.cohort,x.n,x.mean_delta.toFixed(5)]));
document.getElementById('mi-application').innerHTML='<div class="sectionlabel">Full development transcription and speech retention</div>'+table(['Condition','NS words /17','Speech errors / words','Empty speech','Errors'],(d.application_table||[]).map(x=>[x.condition,x.nonspeech_lexical_outputs,x.speech_edits+' / '+x.speech_words,x.empty_speech,x.errors]));
document.getElementById('mi-examples').innerHTML=(d.examples||[]).map(x=>'<div class="policy"><strong>'+miEsc(x.id)+'</strong><audio controls preload="none" style="display:block;width:100%;margin:8px 0" src="'+miEsc(x.audio_url)+'"></audio><div class="eyebrow">Pristine → selected head intervention</div><pre>'+miEsc(x.before)+String.fromCharCode(10)+'→ '+miEsc(x.after)+'</pre></div>').join('');
document.getElementById('mi-gaps').textContent=d.limitations||d.note||'';
}catch(error){document.getElementById('mi-gaps').textContent='Evidence not yet available: '+error.message}})();
</script>'''

def create_app(root='.neural-pr',mi_root='audio_runs/mechanistic_v1'):
    from fastapi.responses import HTMLResponse,JSONResponse,FileResponse,PlainTextResponse
    from fastapi import HTTPException
    app=original_app(root);mi_root=Path(mi_root).resolve()
    app.router.routes=[route for route in app.router.routes if getattr(route,'path',None)!='/']
    @app.get('/')
    def index():
        html=(Path(__file__).resolve().parents[2]/'neural_pr'/'web'/'index.html').read_text()
        return HTMLResponse(html.replace('<div class="stats">',PANEL+'<div class="stats">',1).replace('</body>',SCRIPT+'</body>'))
    @app.get('/api/mechanistic')
    def report():
        result=summary(mi_root)
        manifest=read(mi_root/'manifest.json') if (mi_root/'manifest.json').exists() else {}
        result['provenance']={key:manifest.get(key) for key in ('application_commit','agent_policy_version','checkpoint_sha256')}
        result['examples']=[]
        if (mi_root/'baseline').exists():
            for case_id in ('one_minute_silence','audioset_audioset_0000893','2277-149896-0000'):
                before=mi_root/'baseline'/f'{case_id}.json';after=mi_root/'application'/'selected'/f'{case_id}.json'
                if before.exists() and after.exists():result['examples'].append({'id':case_id,'before':read(before)['text'],
                    'after':read(after).get('text','<inference error>'),'audio_url':'/api/mechanistic/audio/'+case_id})
        return JSONResponse(result,headers={'Cache-Control':'no-store'})
    @app.get('/mechanistic/report')
    def text_report():
        path=mi_root/'REPORT.md'
        if not path.exists():raise HTTPException(404,'Recorded report not yet generated')
        return PlainTextResponse(path.read_text())
    @app.get('/api/mechanistic/audio/{case_id}')
    def audio(case_id:str):
        # ID allowlist, not user-selected paths. The runtime never gets holdout routes.
        manifest={item['id']:item for item in rows('whisper_audio_dev/manifest.jsonl')}
        if case_id not in manifest:raise HTTPException(404,'Unknown development recording')
        path=(Path('whisper_audio_dev')/manifest[case_id]['audio_path']).resolve()
        return FileResponse(path,media_type='audio/wav')
    return app

def snapshot(mi_root):
    import base64
    from fastapi.testclient import TestClient
    client=TestClient(create_app(mi_root=mi_root))
    data={path:client.get(path).json() for path in ('/api/report','/api/events','/api/mechanistic')}
    for example in data['/api/mechanistic'].get('examples',[]):
        response=client.get(example['audio_url']);example['audio_url']='data:audio/wav;base64,'+base64.b64encode(response.content).decode()
    payload=json.dumps(data).replace('<','\\u003c')
    bootstrap='<script>const MI_RECORDING='+payload+';const originalFetch=window.fetch;window.fetch=async url=>url in MI_RECORDING?({ok:true,json:async()=>MI_RECORDING[url]}):originalFetch(url);</script>'
    html=client.get('/').text.replace('<head>','<head>'+bootstrap).replace('Experiment / controlled durable job runner','RECORDED / mechanistic investigation')
    html=html.replace('href="/mechanistic/report"','href="REPORT.md"')
    html=html.replace('↻ Refresh','↻ Reload recording').replace("'Read from disk · '","'Recorded local snapshot · '")
    path=Path(mi_root)/'dashboard-recorded.html';path.write_text(html)
    return str(path.resolve())
