"""Explicit UI setup action, confined to the project venv and model directory."""
from pathlib import Path
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper_repair.experiment import save,sha,OFFICIAL_SMALL_SHA256,now
root=Path(__file__).resolve().parents[1];directory=Path(sys.argv[1]).parent

def progress(phase,done,total=3):save(directory/'progress.json',{'phase':phase,'done':done,'total':total,'time':now()})
try:
    interpreter=root/'.audio-venv/bin/python';checkpoint=root/'audio_models/small.pt'
    progress('Checking the dedicated audio environment',0)
    if not interpreter.exists():subprocess.run([sys.executable,'-m','venv',str(root/'.audio-venv')],check=True,timeout=60)
    probe=subprocess.run([str(interpreter),'-c','import whisper,torch'],capture_output=True,text=True,timeout=30)
    if probe.returncode:
        progress('Installing original openai-whisper in the project environment',1)
        subprocess.run([str(interpreter),'-m','pip','install','--disable-pip-version-check','--retries','1','--timeout','15','openai-whisper==20250625'],check=True,timeout=360)
    if checkpoint.exists() and sha(checkpoint)!=OFFICIAL_SMALL_SHA256:raise ValueError('Existing small.pt does not match the official checkpoint. It was preserved; provide the pristine file before proceeding.')
    if not checkpoint.exists():
        progress('Downloading multilingual small; this can take a few minutes',2)
        subprocess.run([str(interpreter),'-c','import whisper;whisper.load_model("small",device="cpu",download_root="audio_models")'],cwd=root,check=True,timeout=300)
    if sha(checkpoint)!=OFFICIAL_SMALL_SHA256:raise ValueError('Downloaded checkpoint hash differs from official multilingual small')
    versions=subprocess.run([str(interpreter),'-c','import whisper,torch,importlib.metadata,json;print(json.dumps({x:importlib.metadata.version(x) for x in ("openai-whisper","torch","numpy")}))'],check=True,capture_output=True,text=True,timeout=30)
    progress('Setup verified; pristine checkpoint ready',3)
    save(directory/'result.json',{'status':'ok','time':now(),'checkpoint':'multilingual small','official_checkpoint_verified':True,'checkpoint_sha256':sha(checkpoint),
                                  'runtime':json.loads(versions.stdout),'scope':'project-local environment; no agent-policy or model promotion'})
except Exception as exc:
    save(directory/'result.json',{'status':'error','time':now(),'error':type(exc).__name__+': '+str(exc),'accepted_checkpoint_not_modified':True})
    raise
