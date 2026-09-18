from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np

from ..models import Character


def _orb_score(scene: np.ndarray, ref: np.ndarray) -> float:
    gray1 = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=1000)
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)
    if des1 is None or des2 is None or len(kp1) < 8 or len(kp2) < 8:
        return 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des1, des2)
    if not matches:
        return 0.0
    good = [m for m in matches if m.distance < 55]
    return min(1.0, len(good) / max(12.0, min(len(kp1), len(kp2)) * 0.2))


def suggest_characters(scene_path: Path, characters: list[Character]) -> list[dict]:
    scene = cv2.imread(str(scene_path))
    if scene is None:
        return []
    suggestions: list[dict] = []
    for character in characters:
        scores: list[float] = []
        for ref_path in character.reference_images[:8]:
            ref = cv2.imread(str(ref_path))
            if ref is not None:
                scores.append(_orb_score(scene, ref))
        if scores:
            score = max(scores)
            if score >= 0.18:
                suggestions.append({"character_id": character.id, "name": character.name, "confidence": round(score, 3), "needs_review": score < 0.55})
    return sorted(suggestions, key=lambda x: x["confidence"], reverse=True)
