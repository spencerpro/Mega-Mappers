import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
THEMES_DIR = DATA_DIR / "themes"
DB_PATH = DATA_DIR / "codex.db"
MAPS_DIR = DATA_DIR / "maps"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
THEMES_DIR.mkdir(parents=True, exist_ok=True)
MAPS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_THEME = "fantasy"
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 840
SIDEBAR_WIDTH = 320  # Increased from 260

