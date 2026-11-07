"""Self-contained recorded comparison view; every action remains disabled."""
from pathlib import Path
import json
import sys
import urllib.parse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from ui.server import create_app
from ui.agent_config import configure

configure()
client=TestClient(create_app());data=client.get('/api/research/results').json();html=client.get('/research').text
payload=json.dumps(data).replace('<','\\u003c')
bootstrap='<script>window.RESEARCH_RECORDING=true;const RESEARCH_EVIDENCE='+payload+';window.fetch=async path=>({ok:true,json:async()=>RESEARCH_EVIDENCE});</script>'
html=html.replace('<head>','<head>'+bootstrap).replace('<title>Research episodes','<title>RECORDED · Research episodes')
for name in ('research','research-spec','policy-upgrade'):
    text=client.get('/api/ui/report/'+name).text
    html=html.replace('href="/api/ui/report/'+name+'"','href="data:text/plain;charset=utf-8,'+urllib.parse.quote(text)+'"')
html=html.replace('href="/"','href="../audio_runs/ui/whisper-lab-recorded.html"').replace('href="/research"','href="#"')
destination=Path('research_runs/research-recorded.html');destination.write_text(html);print(destination.resolve())
