import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from ..config import STORAGE_DIR
from .storage_service import STORAGE_LOCK


def create_backup(archive: Path):
    """Snapshot committed rows briefly, then ZIP immutable files without blocking readers."""
    handle, temporary_file = tempfile.mkstemp(prefix="c-pilot-db-", suffix=".db")
    os.close(handle)
    copy = Path(temporary_file)
    try:
        with STORAGE_LOCK:
            with closing(sqlite3.connect(str(STORAGE_DIR / "pilot.db"))) as source, closing(sqlite3.connect(str(copy))) as target:
                source.backup(target)
        _write_bundle(archive, copy)
    finally:
        copy.unlink(missing_ok=True)


def _write_bundle(archive, copy):
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(copy, "pilot.db")
        for folder in ("raw", "masked", "text"):
            root = STORAGE_DIR / folder
            if root.exists():
                for file in root.rglob("*"):
                    resolved = file.resolve()
                    if (file.is_file() and not file.is_symlink() and resolved.is_relative_to(STORAGE_DIR)
                            and not file.name.startswith(".pending-")):
                        bundle.write(file, file.relative_to(STORAGE_DIR).as_posix())
        bundle.writestr("manifest.json", json.dumps({"format": "c-pilot-v1", "created_at": datetime.utcnow().isoformat(),
                                                     "database": "pilot.db", "storage": ["raw", "masked", "text"]}))
