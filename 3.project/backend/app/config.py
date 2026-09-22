import os
from pathlib import Path

# Root directory: c:\project
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

STORAGE_DIR = PROJECT_ROOT / "storage"
RAW_STORAGE_DIR = STORAGE_DIR / "raw"
MASKED_STORAGE_DIR = STORAGE_DIR / "masked"
SAMPLE_DIR = PROJECT_ROOT / "sample-data"
DB_PATH = PROJECT_ROOT / "evidence_manager.db"

RAW_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MASKED_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
