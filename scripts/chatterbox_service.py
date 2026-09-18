from __future__ import annotations
import inspect
import os
from pathlib import Path
from threading import Lock

import torch
import torchaudio as ta
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

app = FastAPI(title="Bramble Chatterbox Local Service")
_lock = Lock()
_models = {}
OUT = Path(os.getenv("BRAMBLE_TTS_TEMP", "data/temp/tts-service"))
OUT.mkdir(parents=True, exist_ok=True)

class Req(BaseModel):
    text: str
    language: str = "en"
    reference_audio: str | None = None
    exaggeration: float = .5
    cfg: float = .5
    seed: int = 0
    model: str | None = None

def _load_model(device: str, model_name: str | None):
    loader = ChatterboxMultilingualTTS.from_pretrained
    params = inspect.signature(loader).parameters
    kwargs = {"device": device}
    if model_name and "t3_model" in params:
        kwargs["t3_model"] = model_name
    return loader(**kwargs)

def get_model(model_name: str | None):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    key = (device, model_name or "default")
    with _lock:
        if key not in _models:
            _models[key] = _load_model(device, model_name)
    return _models[key]

@app.get("/health")
def health():
    return {"ok": True, "device": "cuda" if torch.cuda.is_available() else "cpu"}

@app.post("/generate")
def generate(r: Req):
    try:
        if r.seed:
            torch.manual_seed(r.seed)
        model = get_model(r.model)
        kwargs = {
            "language_id": "pt" if r.language == "pt-br" else "en",
            "exaggeration": r.exaggeration,
            "cfg_weight": r.cfg,
        }
        if r.reference_audio and Path(r.reference_audio).exists():
            kwargs["audio_prompt_path"] = r.reference_audio
        wav = model.generate(r.text, **kwargs)
        out = OUT / f"{os.getpid()}-{abs(hash((r.text, r.language, r.seed))) % 10**10}.wav"
        ta.save(str(out), wav, model.sr)
        return FileResponse(out, media_type="audio/wav", filename="speech.wav")
    except Exception as exc:
        raise HTTPException(500, str(exc))
