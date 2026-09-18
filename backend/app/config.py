from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Bramble & Grace Clay Studio"
ROOT_DIR = Path(os.getenv("BRAMBLE_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = Path(os.getenv("BRAMBLE_DATA_DIR", ROOT_DIR / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
CHARACTERS_DIR = DATA_DIR / "characters"
VOICES_DIR = DATA_DIR / "voices"
MODELS_DIR = DATA_DIR / "models"
CACHE_DIR = DATA_DIR / "cache"
TEMP_DIR = DATA_DIR / "temp"
LOGS_DIR = ROOT_DIR / "logs"
DB_PATH = DATA_DIR / "studio.sqlite3"
SETTINGS_PATH = DATA_DIR / "settings.json"
WORKFLOWS_DIR = ROOT_DIR / "workflows"

DEFAULT_BACKEND_HOST = os.getenv("BRAMBLE_BACKEND_HOST", "127.0.0.1")
DEFAULT_BACKEND_PORT = int(os.getenv("BRAMBLE_BACKEND_PORT", "8765"))
DEFAULT_COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

for path in [DATA_DIR, PROJECTS_DIR, CHARACTERS_DIR, VOICES_DIR, MODELS_DIR, CACHE_DIR, TEMP_DIR, LOGS_DIR, WORKFLOWS_DIR]:
    path.mkdir(parents=True, exist_ok=True)
