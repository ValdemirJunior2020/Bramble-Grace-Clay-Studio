from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Iterable

from .config import DB_PATH, PROJECTS_DIR, CHARACTERS_DIR, SETTINGS_PATH
from .models import Project, ProjectCreate, Character, utc_now

_lock = threading.RLock()

PROJECT_SUBDIRS = ["story", "images", "characters", "voices", "audio", "scenes", "subtitles", "renders/en", "renders/pt-br", "cache", "temp", "logs"]


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, folder TEXT NOT NULL,
            updated_at TEXT NOT NULL, render_status TEXT NOT NULL DEFAULT 'pending'
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, updated_at TEXT NOT NULL
        )""")
        db.commit()


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def create_project(data: ProjectCreate) -> Project:
    with _lock:
        project_id = uuid.uuid4().hex[:12]
        safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in data.title).strip().replace(" ", "-")[:60] or project_id
        folder = PROJECTS_DIR / f"{data.story_number + '-' if data.story_number else ''}{safe}-{project_id}"
        for rel in PROJECT_SUBDIRS:
            (folder / rel).mkdir(parents=True, exist_ok=True)
        project = Project(
            id=project_id, title=data.title, story_number=data.story_number,
            english_title=data.english_title, portuguese_title=data.portuguese_title,
            folder=str(folder),
        )
        project.settings.language = data.language
        project.settings.output_format = data.output_format
        project.settings.width = data.width
        project.settings.height = data.height
        project.settings.mode = data.mode
        save_project(project)
        return project


def save_project(project: Project) -> Project:
    with _lock:
        project.updated_at = utc_now()
        folder = Path(project.folder)
        folder.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(folder / "project.json", project.model_dump())
        with sqlite3.connect(DB_PATH) as db:
            db.execute("INSERT INTO projects(id,title,folder,updated_at,render_status) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,folder=excluded.folder,updated_at=excluded.updated_at,render_status=excluded.render_status",
                       (project.id, project.title, project.folder, project.updated_at, project.render_status))
            db.commit()
        return project


def load_project(project_id: str) -> Project:
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT folder FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        raise FileNotFoundError(project_id)
    payload = json.loads((Path(row[0]) / "project.json").read_text(encoding="utf-8"))
    return Project.model_validate(payload)


def list_projects() -> list[Project]:
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute("SELECT id FROM projects ORDER BY updated_at DESC").fetchall()
    out: list[Project] = []
    for (project_id,) in rows:
        try:
            out.append(load_project(project_id))
        except Exception:
            continue
    return out


def delete_project(project_id: str, delete_files: bool = False) -> None:
    project = load_project(project_id)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        db.commit()
    if delete_files:
        shutil.rmtree(project.folder, ignore_errors=True)


def save_character(character: Character) -> Character:
    with _lock:
        character.updated_at = utc_now()
        folder = CHARACTERS_DIR / character.id
        folder.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(folder / "character.json", character.model_dump())
        with sqlite3.connect(DB_PATH) as db:
            db.execute("INSERT INTO characters(id,name,updated_at) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at", (character.id, character.name, character.updated_at))
            db.commit()
    return character


def list_characters() -> list[Character]:
    out: list[Character] = []
    for path in CHARACTERS_DIR.glob("*/character.json"):
        try:
            out.append(Character.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return sorted(out, key=lambda x: x.name.lower())


def load_character(character_id: str) -> Character:
    path = CHARACTERS_DIR / character_id / "character.json"
    if not path.exists():
        raise FileNotFoundError(character_id)
    return Character.model_validate(json.loads(path.read_text(encoding="utf-8")))


def ensure_default_characters() -> None:
    existing = {c.name.lower() for c in list_characters()}
    defaults = [
        ("grace", "Grace", "Main Bramble & Grace character", "girl"),
        ("bramble", "Bramble", "Gentle bear", "bear"),
        ("pip", "Pip", "Energetic small friend", "animal"),
        ("oliver", "Oliver", "Careful book-loving friend", "bird"),
        ("barnaby", "Barnaby", "Patient thoughtful friend", "turtle"),
        ("narrator", "Narrator", "Story narrator", "voice"),
    ]
    for cid, name, desc, species in defaults:
        if name.lower() not in existing:
            save_character(Character(id=cid, name=name, description=desc, species=species))


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data: dict) -> None:
    _write_json_atomic(SETTINGS_PATH, data)
