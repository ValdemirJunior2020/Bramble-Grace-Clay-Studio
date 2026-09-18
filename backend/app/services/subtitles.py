from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _vtt_time(seconds: float) -> str:
    return _srt_time(seconds).replace(",", ".")


def write_srt(cues: list[tuple[float, float, str]], path: Path) -> Path:
    lines: list[str] = []
    for idx, (start, end, text) in enumerate(cues, 1):
        lines.extend([str(idx), f"{_srt_time(start)} --> {_srt_time(end)}", text, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_vtt(cues: list[tuple[float, float, str]], path: Path) -> Path:
    lines = ["WEBVTT", ""]
    for start, end, text in cues:
        lines.extend([f"{_vtt_time(start)} --> {_vtt_time(end)}", text, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
