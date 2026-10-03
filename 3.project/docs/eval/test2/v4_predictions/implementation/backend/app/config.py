import os
from pathlib import Path

from dotenv import load_dotenv

# Application project directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env or env file
for p in [PROJECT_ROOT / "backend" / ".env", PROJECT_ROOT / "backend" / "env", PROJECT_ROOT / ".env"]:
    if p.exists():
        load_dotenv(dotenv_path=p, override=False)

DEPLOYMENT_MODE = os.getenv("APP_DEPLOYMENT_MODE", "development")
IS_PILOT = DEPLOYMENT_MODE == "pilot"
STORAGE_DIR = Path(os.getenv("APP_STORAGE_ROOT", str(PROJECT_ROOT / "storage" / "pilot" if IS_PILOT else PROJECT_ROOT / "storage"))).resolve()
RAW_STORAGE_DIR = STORAGE_DIR / "raw"
MASKED_STORAGE_DIR = STORAGE_DIR / "masked"
SAMPLE_DIR = PROJECT_ROOT / "sample-data"
DB_PATH = STORAGE_DIR / "pilot.db" if IS_PILOT else PROJECT_ROOT / "evidence_manager.db"
MAX_UPLOAD_BYTES = int(os.getenv("APP_MAX_UPLOAD_MB", "20")) * 1024 * 1024
SESSION_HOURS = int(os.getenv("APP_SESSION_HOURS", "8"))
COOKIE_SECURE = os.getenv("APP_COOKIE_SECURE", "false").lower() == "true"
NTS_MODE = os.getenv("APP_NTS_MODE", "disabled" if IS_PILOT else "demo").lower()
ALLOWED_ORIGINS = [v.strip() for v in os.getenv("APP_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000").split(",") if v.strip()]

RAW_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MASKED_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT", "6543")
dbname = os.getenv("DB_NAME", "postgres")

DEFAULT_PG_URL = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}" if (user and password and host) else f"sqlite:///{DB_PATH}"

DATABASE_URL = f"sqlite:///{DB_PATH}" if IS_PILOT else os.getenv("DATABASE_URL", DEFAULT_PG_URL)

# Fail clearly when a selected PostgreSQL driver is unavailable.
if DATABASE_URL.startswith("postgresql"):
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("PostgreSQL 드라이버가 없습니다. DB 설정을 확인하세요.") from exc
