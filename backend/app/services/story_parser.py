from __future__ import annotations

import re
import uuid
from pathlib import Path

from docx import Document

from ..models import ScriptBlock, StoryVersions

QUOTE_RE = re.compile(r'[“"]([^”"]+)[”"]')
SPEECH_VERBS = r'(?:said|asked|cried|whispered|answered|replied|called|murmured|announced|added|shouted|laughed|smiled|nodded|grinned|sighed|exclaimed|yelled|called out|continued|disse|perguntou|gritou|sussurrou|respondeu|chamou|murmurou|anunciou|acrescentou|sorriu|concordou|riu|exclamou|continuou)'


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
    english = _slice_between(
        text,
        ["\nEnglish\n", "\r\nEnglish\r\n", "English\n"],
        ["\nHeart Lesson", "\nFor Parents", "\nHistória ", "\nPortuguês Brasileiro"],
    )
    pt = _slice_between(
        text,
        ["\nPortuguês Brasileiro\n", "Português Brasileiro\n"],
        ["\nLição para o Coração", "\nPara os Pais", "\nStory "],
    )
    heart_en = _slice_between(text, ["\nHeart Lesson\n", "Heart Lesson\n"], ["\nFor Parents", "\nHistória ", "\nPortuguês Brasileiro"])
    parents_en = _slice_between(text, ["\nFor Parents: Why This Story Matters\n", "\nFor Parents\n"], ["\nHistória ", "\nPortuguês Brasileiro"])
    heart_pt = _slice_between(text, ["\nLição para o Coração\n", "Lição para o Coração\n"], ["\nPara os Pais", "\nStory "])
    parents_pt = _slice_between(text, ["\nPara os Pais: Por Que Esta História é Importante\n", "\nPara os Pais\n"], ["\nStory "])

    if not english and not pt:
        english = text.strip()

    return StoryVersions(
        english=english,
        portuguese=pt,
        heart_lesson_en=heart_en,
        heart_lesson_pt=heart_pt,
        parents_en=parents_en,
        parents_pt=parents_pt,
    )


def _speaker_from_context(before: str, after: str, character_names: list[str]) -> tuple[str | None, float]:
    for name in character_names:
        before_patterns = [
            rf'\b{re.escape(name)}\b[^.!?\n]{{0,70}}{SPEECH_VERBS}',
            rf'{SPEECH_VERBS}[^.!?\n]{{0,35}}\b{re.escape(name)}\b',
        ]
        after_patterns = [
            rf'^\s*[,;:.!?—-]*\s*\b{re.escape(name)}\b[^.!?\n]{{0,55}}{SPEECH_VERBS}',
            rf'^\s*[,;:.!?—-]*\s*{SPEECH_VERBS}[^.!?\n]{{0,35}}\b{re.escape(name)}\b',
        ]
        if any(re.search(p, before, flags=re.I) for p in before_patterns):
            return name, 0.98
        if any(re.search(p, after, flags=re.I) for p in after_patterns):
            return name, 0.98

    found: list[tuple[int, str]] = []
    low = before.lower()
    for name in character_names:
        idx = low.rfind(name.lower())
        if idx >= 0:
            found.append((idx, name))
    if found:
        found.sort(reverse=True)
        idx, name = found[0]
        if len(before) - idx < 75:
            return name, 0.68
    return None, 0.0


def parse_script_blocks(text: str, character_names: list[str]) -> list[ScriptBlock]:
    blocks: list[ScriptBlock] = []
    if not text.strip():
        return blocks

    paragraphs = [p.strip() for p in re.split(r'\n+', text) if p.strip()]
    for paragraph in paragraphs:
        labeled: tuple[str, str] | None = None
        for name in character_names:
            m = re.match(rf'^\s*{re.escape(name)}\s*[:—-]\s*(.+)$', paragraph, flags=re.I)
            if m and m.group(1).strip():
                labeled = (name, m.group(1).strip())
                break
        if labeled:
            blocks.append(
                ScriptBlock(
                    id=uuid.uuid4().hex[:12],
                    type="dialogue",
                    text=labeled[1],
                    speaker=labeled[0],
                    speaker_confidence=0.99,
                    needs_review=False,
                )
            )
            continue

        matches = list(QUOTE_RE.finditer(paragraph))
        if not matches:
            if paragraph.isupper() and len(paragraph) < 60:
                blocks.append(ScriptBlock(id=uuid.uuid4().hex[:12], type="sound_effect", text=paragraph))
            else:
                blocks.append(
                    ScriptBlock(
                        id=uuid.uuid4().hex[:12],
                        type="narrator",
                        text=paragraph,
                        speaker="Narrator",
                        speaker_confidence=1.0,
                    )
                )
            continue

        cursor = 0
        for match in matches:
            before_text = paragraph[cursor:match.start()].strip()
            if before_text:
                blocks.append(
                    ScriptBlock(
                        id=uuid.uuid4().hex[:12],
                        type="narrator",
                        text=before_text,
                        speaker="Narrator",
                        speaker_confidence=1.0,
                    )
                )

            before_context = paragraph[max(0, match.start() - 160):match.start()]
            after_context = paragraph[match.end():min(len(paragraph), match.end() + 120)]
            speaker, confidence = _speaker_from_context(before_context, after_context, character_names)
            blocks.append(
                ScriptBlock(
                    id=uuid.uuid4().hex[:12],
                    type="dialogue",
                    text=match.group(1).strip(),
                    speaker=speaker,
                    speaker_confidence=confidence,
                    needs_review=speaker is None or confidence < 0.75,
                )
            )
            cursor = match.end()

        after_text = paragraph[cursor:].strip()
        if after_text:
            blocks.append(
                ScriptBlock(
                    id=uuid.uuid4().hex[:12],
                    type="narrator",
                    text=after_text,
                    speaker="Narrator",
                    speaker_confidence=1.0,
                )
            )
    return blocks


def assign_blocks_to_scenes(blocks: list[ScriptBlock], scene_count: int) -> list[list[ScriptBlock]]:
    if scene_count <= 0:
        return []
    result: list[list[ScriptBlock]] = [[] for _ in range(scene_count)]
    if not blocks:
        return result

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
