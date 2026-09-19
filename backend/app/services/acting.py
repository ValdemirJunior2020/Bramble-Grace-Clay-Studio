from __future__ import annotations

import re
from typing import Iterable
from ..models import ActingBeat, ScriptBlock

ACTION_RULES = [
    (r'\b(run|running|ran|sprint|raced|dash|dashed|correr|correu)\b', 'run', 0.95),
    (r'\b(walk|walked|walking|step|stepped|approach|approached|caminh|andou)\b', 'walk', 0.72),
    (r'\b(pull|pulled|pulling|tug|tugged|puxou|puxar)\b', 'pull', 0.88),
    (r'\b(push|pushed|empurrou)\b', 'push', 0.82),
    (r'\b(reach|reached|grab|grabbed|take|took|pegou|alcançou)\b', 'reach', 0.78),
    (r'\b(point|pointed|apontou)\b', 'point', 0.72),
    (r'\b(fall|fell|tumble|tumbled|stumble|stumbled|caiu|tropeçou)\b', 'stumble', 0.9),
    (r'\b(turn|turned|looked at|look toward|olhou|virou)\b', 'turn_head', 0.7),
    (r'\b(nod|nodded|assentiu)\b', 'nod', 0.6),
    (r'\b(shake|shook)\b.*\b(head)\b', 'shake_head', 0.65),
    (r'\b(hug|hugged|abraçou)\b', 'hug', 0.82),
    (r'\b(jump|jumped|hop|hopped|pulou)\b', 'jump', 0.78),
    (r'\b(sit|sat|kneel|knelt|ajoelhou|sentou)\b', 'lower_body', 0.72),
]

EMOTION_RULES = [
    (r'\b(surpris|startl|gasp|shocked|wide eyes|surpres|espant)\w*', 'surprised'),
    (r'\b(worr|afraid|scared|nervous|anxious|preocup|assust)\w*', 'worried'),
    (r'\b(smile|smiled|happy|joy|grin|grinned|sorri|feliz|alegr)\w*', 'happy'),
    (r'\b(laugh|laughed|giggle|riu|risada)\w*', 'laughing'),
    (r'\b(sad|frown|cried|crying|triste|chor)\w*', 'sad'),
    (r'\b(angry|frustrat|annoyed|mad|irritad|frustrad)\w*', 'frustrated'),
    (r'\b(calm|gentle|softly|calmamente|gentil)\w*', 'calm'),
]

REACTION_WORDS = re.compile(r'\b(react|watch|watched|noticed|notice|stared|stare|gasped|blinked|looked|viu|notou|encarou)\b', re.I)


def _characters_in_text(text: str, names: Iterable[str]) -> list[str]:
    low=text.lower()
    return [n for n in names if re.search(rf'\b{re.escape(n.lower())}\b', low)]


def _emotion(text: str) -> str:
    for pattern, emotion in EMOTION_RULES:
        if re.search(pattern, text, re.I):
            return emotion
    return 'engaged'


def _action(text: str) -> tuple[str,float]:
    for pattern, action, intensity in ACTION_RULES:
        if re.search(pattern, text, re.I):
            return action,intensity
    if REACTION_WORDS.search(text):
        return 'react',0.62
    return 'perform_dialogue',0.55


def build_acting_plan(blocks: list[ScriptBlock], character_names: list[str]) -> list[ActingBeat]:
    spoken=[b for b in blocks if b.text.strip()]
    if not spoken:
        return []
    weights=[max(1,len(b.text.strip())) for b in spoken]
    total=max(1,sum(weights))
    cursor=0.0
    beats:list[ActingBeat]=[]
    last_character: str|None=None

    for block,weight in zip(spoken,weights):
        start=cursor/total
        cursor+=weight
        end=min(1.0,cursor/total)
        text=block.text.strip()
        named=_characters_in_text(text,character_names)
        actor=(block.speaker if block.type=='dialogue' and block.speaker and block.speaker!='Narrator' else None)
        actor=actor or (named[0] if named else last_character)
        action,intensity=_action(text)
        emotion=_emotion(text)
        target=next((n for n in named if n!=actor),None)

        if actor:
            beats.append(ActingBeat(character=actor,action=action,emotion=emotion,target=target,intensity=intensity,start=start,end=end,source_text=text))
            last_character=actor

        if block.type=='dialogue' and actor:
            # Visible co-characters should not freeze while somebody speaks.
            for other in named:
                if other!=actor:
                    beats.append(ActingBeat(character=other,action='react',emotion='engaged',target=actor,intensity=0.42,start=start,end=end,source_text=text))

    return beats


def acting_prompt(beats: list[ActingBeat]) -> str:
    if not beats:
        return 'Expressive clay character performance with natural body acting, head movement, facial expression, and reactions.'
    parts=[]
    for b in beats:
        target=f' toward {b.target}' if b.target else ''
        parts.append(f'{b.character}: {b.action}{target}, {b.emotion} expression, intensity {b.intensity:.2f}')
    return 'Story-driven clay puppet performance. ' + '; '.join(parts)
