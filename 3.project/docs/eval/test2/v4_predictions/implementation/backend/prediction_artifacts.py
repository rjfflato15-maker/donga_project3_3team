"""Artifact IO only; safe to import after the live extractor has changed."""
import json
import os
from hashlib import sha256
from pathlib import Path
from uuid import uuid4


class ArtifactError(ValueError):
    pass


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def write_json(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            # An atomic hard link publishes the complete file without overwriting.
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_checkpoint(path, value):
    write_json(path, {"sha256": digest(value), "payload": value}, exclusive=True)


def load_checkpoint(path):
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    if body.get("sha256") != digest(body.get("payload")):
        raise ArtifactError("CHECKPOINT_CHANGED")
    return body["payload"]


def verify_package(output):
    output = Path(output).resolve()
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    required = {"manifest.json", "source_manifest.json", "release.json", "predictions.json", "traces.json",
                "implementation/backend/evaluation_core.py", "implementation/backend/prediction_scoring.py"}
    if receipt.get("format") != "heldout-predictions-v1" or not required <= set(receipt.get("files_sha256", {})):
        raise ArtifactError("INCOMPLETE_FROZEN_PACKAGE")
    for relative, expected in receipt["files_sha256"].items():
        path = (output / relative).resolve()
        if not path.is_relative_to(output) or not path.is_file() or file_hash(path) != expected:
            raise ArtifactError("FROZEN_PACKAGE_CHANGED")
    return receipt
