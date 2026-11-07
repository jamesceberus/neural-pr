"""Export a PRIVATE, self-contained dashboard snapshot. No live/replayed trace ambiguity."""
import argparse
import datetime
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from neural_pr.app import create_app

parser=argparse.ArgumentParser()
parser.add_argument('--state',default='.neural-pr')
args=parser.parse_args()
root=Path(args.state).resolve()
client=TestClient(create_app(root))
report=client.get('/api/report').json()
events=client.get('/api/events').json()
recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
data=json.dumps({'report':report,'events':events}).replace('<','\\u003c')
bootstrap='<script>const RECORDED='+data+';window.fetch=async url=>({ok:true,json:async()=>url==="/api/events"?RECORDED.events:RECORDED.report});</script>'
html=client.get('/').text
html=html.replace('<title>Neural PR — Evidence console</title>','<title>RECORDED · Neural PR evidence</title>')
html=html.replace('Experiment / controlled durable job runner','RECORDED SNAPSHOT / '+recorded_at)
html=html.replace('↻ Refresh','↻ Reload recording')
html=html.replace("'Read from disk · '+new Date().toLocaleTimeString()",json.dumps('Recorded at '+recorded_at))
html=html.replace('<script>\nconst $=',bootstrap+'<script>\nconst $=')
html=html.replace('href="/api/report" download="neural-pr-report.json"','href="data:application/json;charset=utf-8,'+__import__('urllib.parse',fromlist=['quote']).quote(json.dumps(report))+'" download="neural-pr-recorded-report.json"')
output=root/'dashboard-recorded.html'
output.write_text(html)
print(output)
