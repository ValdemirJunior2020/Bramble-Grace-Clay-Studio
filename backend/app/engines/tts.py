from __future__ import annotations

import inspect
import os
import re
import shutil
import subprocess
import tempfile
import threading
import httpx
from pathlib import Path

from ..models import VoiceSettings

_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, object] = {}
CHATTERBOX_SERVICE_URL = os.getenv("CHATTERBOX_SERVICE_URL", "http://127.0.0.1:8766").rstrip("/")


def validate_voice_file(path: Path) -> bool:
    """Reject empty, near-silent, or malformed WAV files before they enter a movie."""
    if not path.exists() or path.stat().st_size < 2048:
        return False
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        return True
    try:
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=20
        )
        duration = float((probe.stdout or "0").strip() or 0)
        if duration < 0.08:
            return False
        check = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=30
        )
        text = (check.stderr or "") + (check.stdout or "")
        m = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", text)
        if m and float(m.group(1)) < -45.0:
            return False
        return True
    except Exception:
        return False


def split_text(text: str, limit: int = 260) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= limit:
        return [text] if text else []
    parts = re.split(r"(?<=[.!?…])\s+", text)
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) + 1 <= limit:
            current = (current + " " + part).strip()
        else:
            if current:
                chunks.append(current)
            if len(part) <= limit:
                current = part
            else:
                words = part.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 > limit:
                        if current:
                            chunks.append(current)
                        current = word
                    else:
                        current = (current + " " + word).strip()
    if current:
        chunks.append(current)
    return chunks


def _ffmpeg_speed(infile: Path, outfile: Path, speed: float, volume_db: float = 0.0) -> None:
    if not shutil.which("ffmpeg"):
        if infile != outfile:
            shutil.copy2(infile, outfile)
        return
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(infile),
        "-filter:a", f"atempo={speed:.4f},volume={volume_db:.2f}dB,loudnorm=I=-16:LRA=7:TP=-1.5",
        "-ar", "48000", "-ac", "2", str(outfile)
    ], check=True)


def _generate_sapi(text: str, outfile: Path, language: str, settings: VoiceSettings) -> Path:
    if os.name != "nt":
        raise RuntimeError("Windows SAPI fallback is only available on Windows.")
    rate = max(-10, min(10, round((settings.speed - 1.0) * 10)))
    script = r'''
param([string]$Text,[string]$Out,[int]$Rate,[string]$Lang)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = $Rate
$voices = $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo }
if ($Lang -eq "pt-br") {
  $v = $voices | Where-Object { $_.Culture.Name -match "^pt-BR" } | Select-Object -First 1
  if ($v) { $s.SelectVoice($v.Name) }
}
$s.SetOutputToWaveFile($Out)
$s.Speak($Text)
$s.Dispose()
'''
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as f:
        f.write(script)
        ps1 = f.name
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, "-Text", text, "-Out", str(outfile), "-Rate", str(rate), "-Lang", language], check=True, capture_output=True, text=True)
    finally:
        Path(ps1).unlink(missing_ok=True)
    return outfile


def _load_chatterbox(language: str, settings: VoiceSettings):
    try:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    except Exception as exc:
        raise RuntimeError("Chatterbox is not installed in the local Python environment.") from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    custom_pt = os.getenv("CHATTERBOX_PT_BR_T3_MODEL") if language == "pt-br" else None
    requested_model = settings.model or custom_pt or os.getenv("CHATTERBOX_MULTILINGUAL_T3_MODEL", "v2")
    loader = ChatterboxMultilingualTTS.from_pretrained
    params = inspect.signature(loader).parameters
    supports_t3 = "t3_model" in params
    key = f"{device}:{requested_model if supports_t3 else 'default'}"

    with _MODEL_LOCK:
        if key not in _MODEL_CACHE:
            kwargs = {"device": device}
            if supports_t3:
                kwargs["t3_model"] = requested_model
            _MODEL_CACHE[key] = loader(**kwargs)
    return _MODEL_CACHE[key]


def chatterbox_available() -> bool:
    try:
        if httpx.get(f"{CHATTERBOX_SERVICE_URL}/health", timeout=0.5).status_code == 200:
            return True
    except Exception:
        pass
    try:
        import chatterbox.mtl_tts  # noqa: F401
        return True
    except Exception:
        return False


def _generate_chatterbox_service(text: str, outfile: Path, language: str, settings: VoiceSettings) -> bool:
    try:
        payload = {
            "text": text,
            "language": language,
            "reference_audio": settings.reference_audio,
            "exaggeration": settings.exaggeration,
            "cfg": settings.cfg,
            "seed": settings.seed,
            "model": settings.model,
        }
        r = httpx.post(f"{CHATTERBOX_SERVICE_URL}/generate", json=payload, timeout=600.0)
        if r.status_code != 200:
            raise RuntimeError(r.text[:500])
        outfile.write_bytes(r.content)
        return True
    except httpx.ConnectError:
        return False


def generate_chatterbox(text: str, outfile: Path, language: str, settings: VoiceSettings) -> Path:
    try:
        import torchaudio as ta
        import torch
    except Exception as exc:
        raise RuntimeError("Chatterbox dependencies (torch/torchaudio) are not installed.") from exc
    model = _load_chatterbox(language, settings)
    language_id = "pt" if language == "pt-br" else "en"
    kwargs = {
        "language_id": language_id,
        "exaggeration": settings.exaggeration,
        "cfg_weight": settings.cfg,
    }
    if settings.reference_audio and Path(settings.reference_audio).exists():
        kwargs["audio_prompt_path"] = settings.reference_audio
    if settings.seed:
        torch.manual_seed(settings.seed)
    wav = model.generate(text, **kwargs)
    ta.save(str(outfile), wav, model.sr)
    return outfile


def generate_voice(text: str, outfile: Path, language: str, settings: VoiceSettings, global_speed: float = 1.0) -> tuple[Path, str]:
    outfile.parent.mkdir(parents=True, exist_ok=True)
    engine = settings.engine
    if engine == "auto":
        engine = "chatterbox" if chatterbox_available() else "sapi"
    chunks = split_text(text)
    if not chunks:
        raise ValueError("No text to speak")

    chunk_files: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="bramble-tts-") as td:
        td_path = Path(td)
        for i, chunk in enumerate(chunks):
            raw = td_path / f"chunk-{i:03}.wav"
            used_engine = engine
            if engine == "chatterbox":
                try:
                    if not _generate_chatterbox_service(chunk, raw, language, settings):
                        generate_chatterbox(chunk, raw, language, settings)
                except Exception:
                    used_engine = "sapi"
                    _generate_sapi(chunk, raw, language, VoiceSettings(**{**settings.model_dump(), "speed": 1.0, "engine": "sapi"}))
            elif engine == "sapi":
                _generate_sapi(chunk, raw, language, VoiceSettings(**{**settings.model_dump(), "speed": 1.0}))
            else:
                raise RuntimeError(f"Unknown TTS engine: {engine}")

            norm = td_path / f"chunk-{i:03}-norm.wav"
            if shutil.which("ffmpeg"):
                subprocess.run([
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                    "-af", "loudnorm=I=-16:LRA=7:TP=-1.5", "-ar", "48000", "-ac", "2", str(norm)
                ], check=True)
            else:
                shutil.copy2(raw, norm)

            if not validate_voice_file(norm):
                if used_engine != "sapi":
                    raw.unlink(missing_ok=True)
                    norm.unlink(missing_ok=True)
                    _generate_sapi(chunk, raw, language, VoiceSettings(**{**settings.model_dump(), "speed": 1.0, "engine": "sapi"}))
                    if shutil.which("ffmpeg"):
                        subprocess.run([
                            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                            "-af", "loudnorm=I=-16:LRA=7:TP=-1.5", "-ar", "48000", "-ac", "2", str(norm)
                        ], check=True)
                    else:
                        shutil.copy2(raw, norm)
                if not validate_voice_file(norm):
                    raise RuntimeError("Generated voice audio is invalid or near-silent.")
            chunk_files.append(norm)

        joined = td_path / "joined.wav"
        if len(chunk_files) == 1:
            shutil.copy2(chunk_files[0], joined)
        else:
            if not shutil.which("ffmpeg"):
                raise RuntimeError("FFmpeg is required to join long narration chunks.")
            concat = td_path / "concat.txt"
            concat.write_text(
                "\n".join("file '" + str(p).replace("'", "'\\''") + "'" for p in chunk_files),
                encoding="utf-8",
            )
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                "-i", str(concat), "-c:a", "pcm_s16le", joined
            ], check=True)

        speed = max(0.5, min(2.0, settings.speed * global_speed))
        _ffmpeg_speed(joined, outfile, speed, settings.volume_db)
    return outfile, engine
