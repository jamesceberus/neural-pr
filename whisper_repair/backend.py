"""Real local inference only. Missing weights/dependencies are errors, never empty transcripts."""
from array import array
import math
from pathlib import Path
import sys
import wave

def load_audio(path):
    with wave.open(str(path),'rb') as wav:
        if (wav.getnchannels(),wav.getframerate(),wav.getsampwidth())!=(1,16000,2):
            raise ValueError('Expected untouched mono 16kHz PCM16 WAV; no implicit resampling')
        pcm=array('h',wav.readframes(wav.getnframes()))
    if sys.byteorder!='little':pcm.byteswap()
    if not pcm:raise ValueError('Empty audio file')
    rms=math.sqrt(sum((sample/32768)**2 for sample in pcm)/len(pcm))
    return pcm,{'frames':len(pcm),'duration_s':len(pcm)/16000,'rms':rms,
                'rms_dbfs':20*math.log10(rms) if rms else None,'exact_digital_silence':not any(pcm)}

class Backend:
    def __init__(self,checkpoint,backend='openai',threads=4):
        import torch
        self.torch=torch
        torch.set_num_threads(threads);torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        self.backend=backend;self.path=Path(checkpoint).resolve()
        if not self.path.exists():raise FileNotFoundError('Local untouched checkpoint is absent: '+str(self.path))
        if backend!='openai':raise ValueError('This experiment requires original openai-whisper')
        import whisper
        self.model=whisper.load_model(str(self.path),device='cpu').float().eval()
        dims=self.model.dims
        if (dims.n_text_layer,dims.n_text_head,dims.n_audio_layer,dims.n_vocab)!=(12,12,12,51865):
            raise ValueError('Expected multilingual small; switching models requires a new baseline')

    def transcribe(self,path):
        import numpy as np
        pcm,stats=load_audio(path);audio=np.asarray(pcm,dtype=np.float32)/32768.0
        with self.torch.inference_mode():
            output=self.model.transcribe(audio,language='en',task='transcribe',fp16=False,temperature=0.0,
                beam_size=1,condition_on_previous_text=True,compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,no_speech_threshold=0.6,verbose=None)
        return {'text':output['text'],'raw':output,'audio_stats':stats}
