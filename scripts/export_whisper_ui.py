"""A clearly labeled read-only UI recording for hosts that deny localhost binding."""
from pathlib import Path
import base64
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from ui.server import create_app
client=TestClient(create_app())
results=client.get('/api/ui/results').json();jobs=client.get('/api/ui/jobs').json()
for row in results['transcripts']:
    audio=client.get(row['audio_url']);row['audio_url']='data:audio/wav;base64,'+base64.b64encode(audio.content).decode()
reports={name:client.get('/api/ui/report/'+name).text for name in ('mechanistic','followup','audio','agent','specification')}
html=client.get('/').text
payload=json.dumps({'/api/ui/results':results,'/api/ui/jobs':jobs}).replace('<','\\u003c')
bootstrap='<script>window.WHISPER_RECORDING=true;const UI_RECORDING='+payload+';window.fetch=async path=>path in UI_RECORDING?({ok:true,json:async()=>UI_RECORDING[path]}):({ok:false,json:async()=>({detail:"Start the local server to run experiments"})});</script>'
html=html.replace('<head>','<head>'+bootstrap)
html=html.replace('<title>Whisper lab · Experiments & evidence</title>','<title>RECORDED · Whisper lab</title>')
for name,text in reports.items():
    import urllib.parse
    html=html.replace('href="/api/ui/report/'+name+'"','href="data:text/plain;charset=utf-8,'+urllib.parse.quote(text)+'"')
html=html.replace('Read local evidence · ','Recorded evidence · ')
html=html.replace('href="/research"','href="../../research_runs/research-recorded.html"')
output=Path('audio_runs/ui/whisper-lab-recorded.html');output.parent.mkdir(parents=True,exist_ok=True);output.write_text(html)
print(output.resolve())
