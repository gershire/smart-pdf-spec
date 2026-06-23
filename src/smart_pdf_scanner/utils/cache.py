"""File-based caching for OCR results and layout detections.

Implements a simple disk-backed cache keyed by a SHA-256 hash of the content
being cached. Cache entries are stored as JSON files and can be configured
with a maximum age (TTL) for automatic expiration.

The cache is thread-safe: all reads and writes acquire a per-instance lock
so that multiple threads processing PDF pages concurrently do not corrupt
entries.

References
----------
- Requirement 10: Configuration Management (caching sub-requirement)
- Design Document: Performance Optimization
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, Optional, Union

__all__ = [
    "FileCache",
    "make_content_hash",
]

# Default time-to-live in seconds (24 hours).
_DEFAULT_TTL = 86_400


def make_content_hash(*parts: Union[str, bytes]) -> str:
    """Produce a stable SHA-256 hex digest from one or more content parts.

    Useful for generating deterministic cache keys from page images, PDF
    page numbers, or configuration fingerprints.

    Args:
        *parts: Strings or bytes objects whose concatenated content should be
            hashed. Each string is encoded as UTF-8 before hashing.

    Returns:
        64-character lowercase hex digest.

    Raises:
        ValueError: If no parts are supplied.
    """
    if not parts:
        raise ValueError("At least one content part is required")
    h = hashlib.sha256()
    for part in parts:
        if isinstance(part, str):
            h.update(part.encode("utf-8"))
        else:
            h.update(part)
    return h.hexdigest()


class FileCache:
    """A persistent, file-backed key-value cache with TTL expiry.

    Each cache entry is stored as a JSON file under ``cache_dir`` named after
    the entry's key (the first 16 hex characters of the SHA-256 hash are used
    as a subdirectory prefix to avoid large flat directories). The file
    contains a JSON object with ``created_at`` (UNIX timestamp) and ``value``
    fields.

    Args:
        cache_dir: Root directory for cache storage. Created automatically if
            it does not exist.
        ttl: Maximum age (seconds) of a cache entry before it is considered
            expired. ``None`` disables expiry (entries live forever).

    Example::

        cache = FileCache(Path(".cache/ocr"), ttl=3600)
        key = make_content_hash(page_bytes)
        if (result := cache.get(key)) is None:
            result = run_ocr(page_bytes)
            cache.set(key, result)
    """

    def __init__(self, cache_dir: Union[str, Path], *, ttl: Optional[float] = _DEFAULT_TTL) -> None:
        self._root = Path(cache_dir).resolve()
        self._ttl = ttl
        self._lock = threading.Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value.

        Args:
            key: Cache key (typically produced by :func:`make_content_hash`).

        Returns:
            The stored value, or ``None`` if the key is absent or expired.
        """
        with self._lock:
            path = self._entry_path(key)
            if not path.exists():
                return None
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                path.unlink(missing_ok=True)
                return None
            if self._is_expired(entry.get("created_at", 0)):
                path.unlink(missing_ok=True)
                return None
            return entry.get("value")

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache.

        The value must be JSON-serialisable (dicts, lists, strings, numbers,
        ``None``, booleans).

        Args:
            key: Cache key.
            value: JSON-serialisable value to store.

        Raises:
            TypeError: If ``value`` is not JSON-serialisable.
        """
        with self._lock:
            path = self._entry_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            entry = {"created_at": time.time(), "value": value}
            path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")

    def delete(self, key: str) -> bool:
        """Remove a single cache entry.

        Args:
            key: Cache key to delete.

        Returns:
            ``True`` if the entry existed and was deleted, ``False`` otherwise.
        """
        with self._lock:
            path = self._entry_path(key)
            if path.exists():
                path.unlink()
                return True
            return False

    def clear(self) -> int:
        """Remove all entries from the cache.

        Returns:
            The number of entries deleted.
        """
        with self._lock:
            count = 0
            for json_file in self._root.rglob("*.json"):
                json_file.unlink(missing_ok=True)
                count += 1
            return count

    def cleanup(self) -> int:
        """Remove only expired cache entries.

        Returns:
            The number of expired entries deleted.
        """
        with self._lock:
            count = 0
            for json_file in self._root.rglob("*.json"):
                try:
                    entry = json.loads(json_file.read_text(encoding="utf-8"))
                    if self._is_expired(entry.get("created_at", 0)):
                        json_file.unlink(missing_ok=True)
                        count += 1
                except (json.JSONDecodeError, OSError):
                    json_file.unlink(missing_ok=True)
                    count += 1
            return count

    def contains(self, key: str) -> bool:
        """Return ``True`` if ``key`` has a non-expired entry in the cache.

        Args:
            key: Cache key to check.
        """
        return self.get(key) is not None

    @property
    def cache_dir(self) -> Path:
        """The resolved root directory of the cache."""
        return self._root

    @property
    def ttl(self) -> Optional[float]:
        """The configured time-to-live in seconds, or ``None`` for no expiry."""
        return self._ttl

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _entry_path(self, key: str) -> Path:
        """Compute the file path for a cache entry key."""
        # Use the first two hex chars as a shard prefix to keep the directory
        # tree shallow (at most 256 subdirectories).
        prefix = key[:2] if len(key) >= 2 else "00"
        return self._root / prefix / f"{key}.json"

    def _is_expired(self, created_at: float) -> bool:
        """Return ``True`` if the entry age exceeds the configured TTL."""
        if self._ttl is None:
            return False
        return (time.time() - created_at) > self._ttl
