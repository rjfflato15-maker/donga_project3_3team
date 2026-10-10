"""Bounded process-local display evidence cache; no fields or user responses.

Callers must verify the current source hash before using this cache. Raw text
changes and different storage roots have separate keys. Nothing is persisted.
"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
from threading import Lock

_entries = OrderedDict()
_lock = Lock()
_loads = [Lock() for _ in range(16)]
_characters = 0
MAX_CHARACTERS = 2_000_000
MAX_ENTRIES = 16


def invalidate_source_pages(path, raw, verified_sha256):
    global _characters
    key = (str(path.resolve()), verified_sha256, hashlib.sha256(raw.encode('utf-8')).hexdigest())
    with _lock:
        entry = _entries.pop(key, None)
        if entry:
            _characters -= entry[1]


def cached_source_pages(path, raw, verified_sha256, loader):
    global _characters
    key = (str(path.resolve()), verified_sha256, hashlib.sha256(raw.encode('utf-8')).hexdigest())
    # Concurrent requests for the same document perform only one extraction.
    with _loads[hash(key) % len(_loads)]:
        with _lock:
            if key in _entries:
                pages, _ = _entries[key]
                _entries.move_to_end(key)
                return deepcopy(pages)
        pages = loader(path, raw)
        size = sum(len(page.get('text', '')) for page in pages)
        # Empty/failed extraction is retryable. SOURCE_TEXT_CHANGED is a
        # deterministic comparison with this raw-text version; retain its
        # incomplete flag rather than promote it to verified extraction.
        if pages and 0 < size <= MAX_CHARACTERS and all(
                page.get('evidence_complete', True) or
                set(page.get('extraction_warnings', [])) == {'SOURCE_TEXT_CHANGED'} for page in pages):
            with _lock:
                while _entries and (len(_entries) >= MAX_ENTRIES or _characters + size > MAX_CHARACTERS):
                    _, (_, removed) = _entries.popitem(last=False)
                    _characters -= removed
                _entries[key] = (deepcopy(pages), size)
                _characters += size
        return pages
