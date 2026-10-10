"""Short-lived, bounded PNG reuse after per-request auth/source/version checks."""
from collections import OrderedDict
from threading import Lock
from time import monotonic

_entries = OrderedDict()
_lock = Lock()
_loads = [Lock() for _ in range(16)]
_bytes = 0
MAX_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 16
TTL_SECONDS = 120


def invalidate_preview(key):
    global _bytes
    with _lock:
        entry = _entries.pop(key, None)
        if entry:
            _bytes -= len(entry[1])


def cached_preview(key, render):
    global _bytes
    with _loads[hash(key) % len(_loads)]:
        with _lock:
            expired = [item for item, (expires, _) in _entries.items() if expires <= monotonic()]
            for item in expired:
                _, content = _entries.pop(item)
                _bytes -= len(content)
            if key in _entries:
                _entries.move_to_end(key)
                return _entries[key][1]
        content = render()  # Exceptions never create a cache entry.
        if content.startswith(b'\x89PNG\r\n\x1a\n') and len(content) <= MAX_BYTES:
            with _lock:
                while _entries and (len(_entries) >= MAX_ENTRIES or _bytes + len(content) > MAX_BYTES):
                    _, (_, removed) = _entries.popitem(last=False)
                    _bytes -= len(removed)
                _entries[key] = (monotonic() + TTL_SECONDS, content)
                _bytes += len(content)
        return content
