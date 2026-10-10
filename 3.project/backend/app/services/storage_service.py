import hashlib
import ntpath
import os
import threading
import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile
from ..config import STORAGE_DIR, PROJECT_ROOT, MAX_UPLOAD_BYTES

# Serialize short database publication / revision checks in the single worker.
# Unique immutable file writes, OCR and preview rendering do not use this lock.
STORAGE_LOCK = threading.RLock()
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif",
                      ".txt", ".md", ".json", ".csv", ".doc", ".docx", ".hwp", ".hwpx", ".xls", ".xlsx"}


def clean_name(name: str) -> str:
    name = ntpath.basename(name or "document.txt")
    name = "".join(c for c in name if c >= " " and c not in '<>:"/\\|?*').strip().strip(".")
    if not name:
        raise HTTPException(400, "파일 이름을 확인하세요.")
    suffix = Path(name).suffix
    return name if len(name) <= 240 else name[:240 - len(suffix)] + suffix


def validate_upload(name: str, data: bytes):
    ext = Path(clean_name(name)).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "지원하지 않는 파일 형식입니다.")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"파일당 최대 {MAX_UPLOAD_BYTES // 1048576}MB까지 가능하며 빈 파일은 등록할 수 없습니다.")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(400, "PDF 파일의 실제 형식이 올바르지 않습니다.")
    if ext in {".doc", ".xls", ".hwp"} and not data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise HTTPException(400, "문서 파일의 실제 형식이 올바르지 않습니다.")
    from ..ai.input_safety import check_container, UnsafeDocument
    try:
        check_container(data, ext)
    except UnsafeDocument as error:
        raise HTTPException(400, str(error)) from error


def read_upload(file: UploadFile) -> bytes:
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    validate_upload(file.filename or "document.txt", data)
    return data


def store_original(contract_id: int, name: str, data: bytes):
    name = clean_name(name)
    validate_upload(name, data)
    key = f"raw/{contract_id}/{uuid.uuid4().hex}{Path(name).suffix.lower()}"
    target = STORAGE_DIR / key
    _write_immutable(target, data)
    return key, target, hashlib.sha256(data).hexdigest()


def _write_immutable(target: Path, data: bytes):
    """Publish complete UUID files atomically; never rewrite a referenced file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".pending-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
        if target.exists():
            raise FileExistsError(f"Storage key already exists: {target.name}")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def resolve_path(key: str):
    if not key:
        return None
    roots = [STORAGE_DIR, (PROJECT_ROOT / "storage").resolve()]
    candidates = [Path(key)] if Path(key).is_absolute() else [STORAGE_DIR / key]
    base = ntpath.basename(key)
    # Legacy absolute paths can move with a restored company inbox. Keep their
    # namespace: a privacy sidecar must never stand in for a missing original
    # (or an original for a missing privacy sidecar).
    parts = ntpath.normpath(key).replace("\\", "/").split("/")
    namespace_index = next((i for i in range(len(parts) - 2, -1, -1)
                            if parts[i].lower() in {"raw", "masked", "text"}), None)
    if namespace_index is not None:
        namespace = parts[namespace_index].lower()
        portable = Path(namespace, *parts[namespace_index + 1:])
        candidates += [root / portable for root in roots]
        candidates += [root / namespace / base for root in roots]
    else:
        candidates += [root / sub / base for root in roots for sub in ("raw", "masked")]
    for candidate in candidates:
        resolved = candidate.resolve()
        if any(resolved.is_relative_to(root) for root in roots) and resolved.is_file():
            return resolved
    return None


def store_text(raw_key: str, raw_text: str, masked_text: str):
    stem = Path(raw_key).stem
    raw_text_key = f"text/{stem}.txt"
    masked_key = f"masked/{stem}.txt"
    for key, text in ((raw_text_key, raw_text), (masked_key, masked_text)):
        target = STORAGE_DIR / key
        _write_immutable(target, text.encode("utf-8"))
    return masked_key


def read_texts(doc):
    raw = ""
    masked = ""
    source = resolve_path(doc.storage_path)
    if source:
        for path in (STORAGE_DIR / "text" / f"{source.stem}.txt", source.parent / f"extracted_raw_{source.name}.txt"):
            if path.is_file():
                raw = path.read_text(encoding="utf-8", errors="replace")
                break
        if not raw and source.suffix.lower() in {".txt", ".md", ".json", ".csv"}:
            raw = source.read_text(encoding="utf-8", errors="replace")
    # Recompute the protected view with the current rules. Immutable sidecars
    # may have been generated before a masking omission was fixed; never
    # prefer an old sidecar over raw text or overwrite originals/extractions.
    if not raw:
        masked_path = resolve_path(doc.masking.masked_file_path) if doc.masking else None
        if masked_path:
            masked = masked_path.read_text(encoding="utf-8", errors="replace")
    if raw or masked:
        from ..ai.masking import mask_sensitive_information
        try:
            masked = mask_sensitive_information(raw or masked)[0]
        except Exception:
            masked = "자동 마스킹을 완료하지 못했습니다. 권한이 있는 사용자가 원본을 확인하세요."
    return raw, masked
