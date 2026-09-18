from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from docx import Document

from ..models import ScriptBlock, StoryVersions

QUOTE_RE = re.compile(r'[“"]([^”"]+)[”"]')
SPEECH_VERBS = r'(?:said|asked|cried|whispered|answered|replied|called|murmured|announced|added|shouted|laughed|smiled|nodded|grinned|sighed|disse|perguntou|gritou|sussurrou|respondeu|chamou|murmurou|anunciou|acrescentou|sorriu|concordou|riu)'


def read_story_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8-sig")
    raise ValueError(f"Unsupported story file: {suffix}")


def _slice_between(text: str, starts: list[str], ends: list[str]) -> str:
    lower = text.lower()
    positions = [(lower.find(s.lower()), s) for s in starts if lower.find(s.lower()) >= 0]
    if not positions:
        return ""
    start_pos, marker = min(positions, key=lambda x: x[0])
    start = start_pos + len(marker)
    end_positions = [lower.find(e.lower(), start) for e in ends if lower.find(e.lower(), start) >= 0]
    end = min(end_positions) if end_positions else len(text)
    return text[start:end].strip()


def split_bilingual(text: str) -> StoryVersions:
    # Keeps source wording untouched; only sections are separated.
    english = _slice_between(
        text,
        ["\nEnglish\n", "\r\nEnglish\r\n", "English\n"],
        ["\nHeart Lesson", "\nFor Parents", "\nHistória ", "\nPortuguês Brasileiro"]
    )
    pt = _slice_between(
        text,
        ["\nPortuguês Brasileiro\n", "Português Brasileiro\n"],
        ["\nLição para o Coração", "\nPara os Pais", "\nStory "]
    )
    heart_en = _slice_between(text, ["\nHeart Lesson\n", "Heart Lesson\n"], ["\nFor Parents", "\nHistória ", "\nPortuguês Brasileiro"])
    parents_en = _slice_between(text, ["\nFor Parents: Why This Story Matters\n", "\nFor Parents\n"], ["\nHistória ", "\nPortuguês Brasileiro"])
    heart_pt = _slice_between(text, ["\nLição para o Coração\n", "Lição para o Coração\n"], ["\nPara os Pais", "\nStory "])
    parents_pt = _slice_between(text, ["\nPara os Pais: Por Que Esta História é Importante\n", "\nPara os Pais\n"], ["\nStory "])

    if not english and not pt:
        # Single-language source. Keep it in English slot by default; user can change it later.
        english = text.strip()

    return StoryVersions(
        english=english,
        portuguese=pt,
        heart_lesson_en=heart_en,
        heart_lesson_pt=heart_pt,
        parents_en=parents_en,
        parents_pt=parents_pt,
    )


def _speaker_from_context(context: str, character_names: list[str]) -> tuple[str | None, float]:
    # Strong pattern: Name + speech verb close to quote.
    for name in character_names:
        patterns = [
            rf'\b{re.escape(name)}\b[^.!?\n]{{0,60}}{SPEECH_VERBS}',
            rf'{SPEECH_VERBS}[^.!?\n]{{0,30}}\b{re.escape(name)}\b',
        ]
        if any(re.search(p, context, flags=re.I) for p in patterns):
            return name, 0.94
    # Weaker pattern: nearest named character in the preceding clause.
    found: list[tuple[int, str]] = []
    low = context.lower()
    for name in character_names:
        idx = low.rfind(name.lower())
        if idx >= 0:
            found.append((idx, name))
    if found:
        found.sort(reverse=True)
        idx, name = found[0]
        if len(context) - idx < 90:
            return name, 0.64
    return None, 0.0


def parse_script_blocks(text: str, character_names: list[str]) -> list[ScriptBlock]:
    blocks: list[ScriptBlock] = []
    if not text.strip():
        return blocks

    # Process paragraph-by-paragraph to preserve source order.
    paragraphs = [p.strip() for p in re.split(r'\n+', text) if p.strip()]
    last_speaker: str | None = None
    for paragraph in paragraphs:
        matches = list(QUOTE_RE.finditer(paragraph))
        if not matches:
            if paragraph.isupper() and len(paragraph) < 60:
                blocks.append(ScriptBlock(id=uuid.uuid4().hex[:12], type="sound_effect", text=paragraph))
            else:
                blocks.append(ScriptBlock(id=uuid.uuid4().hex[:12], type="narrator", text=paragraph, speaker="Narrator", speaker_confidence=1.0))
            continue

        cursor = 0
        for match in matches:
            before = paragraph[cursor:match.start()].strip()
            if before:
                blocks.append(ScriptBlock(id=uuid.uuid4().hex[:12], type="narrator", text=before, speaker="Narrator", speaker_confidence=1.0))
            context_start = max(0, match.start() - 140)
            context = paragraph[context_start:match.start()]
            speaker, confidence = _speaker_from_context(context, character_names)
            # If a quote follows immediately after another quote and no clear cue is present, never blindly alternate.
            needs_review = speaker is None or confidence < 0.75
            if speaker:
                last_speaker = speaker
            blocks.append(ScriptBlock(
                id=uuid.uuid4().hex[:12], type="dialogue", text=match.group(1).strip(),
                speaker=speaker, speaker_confidence=confidence, needs_review=needs_review,
            ))
            cursor = match.end()
        after = paragraph[cursor:].strip()
        if after:
            blocks.append(ScriptBlock(id=uuid.uuid4().hex[:12], type="narrator", text=after, speaker="Narrator", speaker_confidence=1.0))
    return blocks


def assign_blocks_to_scenes(blocks: list[ScriptBlock], scene_count: int) -> list[list[ScriptBlock]]:
    if scene_count <= 0:
        return []
    result: list[list[ScriptBlock]] = [[] for _ in range(scene_count)]
    if not blocks:
        return result
    # Evenly distribute by text weight. This is a suggestion only and is reviewed before rendering.
    weights = [max(1, len(b.text)) for b in blocks]
    total = sum(weights)
    target = total / scene_count
    scene_index = 0
    acc = 0.0
    for block, weight in zip(blocks, weights):
        if scene_index < scene_count - 1 and acc >= target:
            scene_index += 1
            acc = 0.0
        result[scene_index].append(block)
        acc += weight
    return result
