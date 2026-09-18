from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
from pathlib import Path
import psutil


def _run(args: list[str], timeout: int = 5) -> str:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return (p.stdout or p.stderr or "").strip()
    except Exception:
        return ""


def detect_gpu() -> dict:
    info = {"vendor": "Unknown", "name": "Unknown", "vram_mb": None, "cuda": False, "rocm": False}
    if platform.system() == "Windows":
        script = r'''
$g=Get-CimInstance Win32_VideoController | Where-Object {$_.Name -and $_.Name -notmatch 'Microsoft'} | Sort-Object AdapterRAM -Descending | Select-Object -First 1
$mem=[uint64]0
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Video' -ErrorAction SilentlyContinue | ForEach-Object { Get-ChildItem $_.PSPath -ErrorAction SilentlyContinue | ForEach-Object { try { $v=(Get-ItemProperty $_.PSPath -Name 'HardwareInformation.qwMemorySize' -ErrorAction Stop).'HardwareInformation.qwMemorySize'; if([uint64]$v -gt $mem){$mem=[uint64]$v} } catch {} } }
[pscustomobject]@{Name=$g.Name;AdapterRAM=$g.AdapterRAM;RegistryVRAM=$mem} | ConvertTo-Json -Compress
'''
        out = _run(["powershell", "-NoProfile", "-Command", script])
        try:
            best = json.loads(out)
            name = str(best.get("Name") or "Unknown")
            info["name"] = name
            raw_vram = int(best.get("RegistryVRAM") or best.get("AdapterRAM") or 0)
            info["vram_mb"] = raw_vram // (1024*1024) or None
            low = name.lower()
            info["vendor"] = "AMD" if "amd" in low or "radeon" in low else "NVIDIA" if "nvidia" in low or "geforce" in low else "Intel" if "intel" in low else "Unknown"
        except Exception:
            pass
    else:
        smi = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        if smi:
            first = smi.splitlines()[0].split(",")
            info.update(vendor="NVIDIA", name=first[0].strip(), vram_mb=int(first[1].strip()), cuda=True)
    info["cuda"] = bool(shutil.which("nvidia-smi")) or info["vendor"] == "NVIDIA"
    info["rocm"] = bool(shutil.which("rocminfo")) or bool(shutil.which("hipinfo"))
    return info


def system_status() -> dict:
    gpu = detect_gpu()
    disk = shutil.disk_usage(Path.cwd())
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or "Unknown",
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "disk_free_gb": round(disk.free / (1024**3), 1),
        "gpu": gpu,
        "python": platform.python_version(),
        "node": _run(["node", "--version"]) if shutil.which("node") else None,
        "npm": _run(["npm", "--version"]) if shutil.which("npm") else None,
        "git": _run(["git", "--version"]) if shutil.which("git") else None,
        "ffmpeg": _run(["ffmpeg", "-version"]).splitlines()[0] if shutil.which("ffmpeg") else None,
        "rhubarb": shutil.which("rhubarb"),
    }


def mode_recommendations(status: dict) -> list[dict]:
    gpu = status.get("gpu", {})
    vram = gpu.get("vram_mb") or 0
    vendor = gpu.get("vendor")
    rows = [
        {"mode": "Clay Motion", "state": "Recommended", "reason": "Deterministic local renderer; works without a large video model."},
        {"mode": "Rhubarb Mouth Shapes", "state": "Recommended" if status.get("rhubarb") else "Not Installed", "reason": "Lightweight local phoneme-to-mouth cue engine."},
    ]
    if vram >= 12000:
        rows.append({"mode": "Quantized ComfyUI video workflows", "state": "Available but verify workflow", "reason": f"Detected about {round(vram/1024,1)} GB VRAM. Model/workflow requirements vary."})
    else:
        rows.append({"mode": "Large ComfyUI video workflows", "state": "Not recommended", "reason": "VRAM is below the default 12 GB safety threshold."})
    if vendor == "AMD":
        rows.append({"mode": "AMD acceleration", "state": "Available when ROCm/PyTorch build supports this GPU" if gpu.get("rocm") else "Needs ROCm-compatible runtime", "reason": "The app never assumes CUDA-only execution."})
    return rows
