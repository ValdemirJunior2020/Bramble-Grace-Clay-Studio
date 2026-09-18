from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def available() -> bool:
    return bool(shutil.which("rhubarb"))


def analyze(audio: Path, output_json: Path, language: str = "en") -> list[dict]:
    exe = shutil.which("rhubarb")
    if not exe:
        raise RuntimeError("Rhubarb Lip Sync is not installed.")
    recognizer = "phonetic" if language == "pt-br" else "pocketSphinx"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    args = [exe, "-f", "json", "-r", recognizer, "-o", str(output_json), str(audio)]
    subprocess.run(args, check=True, capture_output=True, text=True)
    data = json.loads(output_json.read_text(encoding="utf-8"))
    return data.get("mouthCues", [])
