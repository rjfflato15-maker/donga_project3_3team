import os
from pathlib import Path
from dotenv import load_dotenv

# Root directory: c:\project
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env file
ENV_PATH = PROJECT_ROOT / "backend" / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

STORAGE_DIR = PROJECT_ROOT / "storage"
RAW_STORAGE_DIR = STORAGE_DIR / "raw"
MASKED_STORAGE_DIR = STORAGE_DIR / "masked"
SAMPLE_DIR = PROJECT_ROOT / "sample-data"
DB_PATH = PROJECT_ROOT / "evidence_manager.db"

RAW_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MASKED_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT", "6543")
dbname = os.getenv("DB_NAME", "postgres")

DEFAULT_PG_URL = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}" if (user and password and host) else f"sqlite:///{DB_PATH}"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_PG_URL)

