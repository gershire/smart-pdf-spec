"""Unit tests for :mod:`smart_pdf_scanner.utils.cache`."""

import json
import time

import pytest

from smart_pdf_scanner.utils.cache import FileCache, make_content_hash


# ---------------------------------------------------------------------------
# make_content_hash
# ---------------------------------------------------------------------------

class TestMakeContentHash:
    def test_returns_64_char_hex(self):
        digest = make_content_hash("hello")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_deterministic(self):
        assert make_content_hash("hello") == make_content_hash("hello")

    def test_different_input_different_hash(self):
        assert make_content_hash("hello") != make_content_hash("world")

    def test_multiple_parts_concatenated(self):
        combined = make_content_hash("ab", "cd")
        single = make_content_hash("abcd")
        assert combined == single

    def test_bytes_input(self):
        digest = make_content_hash(b"\x00\x01\x02")
        assert len(digest) == 64

    def test_mixed_str_and_bytes(self):
        a = make_content_hash("hello", b" world")
        b = make_content_hash("hello world")
        assert a == b

    def test_no_parts_raises(self):
        with pytest.raises(ValueError):
            make_content_hash()


# ---------------------------------------------------------------------------
# FileCache fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cache(tmp_path):
    return FileCache(tmp_path / "cache", ttl=60)


@pytest.fixture
def no_ttl_cache(tmp_path):
    return FileCache(tmp_path / "cache_notl", ttl=None)


# ---------------------------------------------------------------------------
# FileCache.get / set
# ---------------------------------------------------------------------------

class TestFileCacheGetSet:
    def test_miss_returns_none(self, cache):
        assert cache.get("nonexistent") is None

    def test_set_then_get_returns_value(self, cache):
        cache.set("k1", {"result": 42})
        assert cache.get("k1") == {"result": 42}

    def test_stores_various_json_types(self, cache):
        cache.set("str", "text")
        cache.set("num", 3.14)
        cache.set("lst", [1, 2, 3])
        cache.set("none", None)
        assert cache.get("str") == "text"
        assert cache.get("num") == pytest.approx(3.14)
        assert cache.get("lst") == [1, 2, 3]
        assert cache.get("none") is None

    def test_overwrite_replaces_value(self, cache):
        cache.set("k", "first")
        cache.set("k", "second")
        assert cache.get("k") == "second"

    def test_set_non_serialisable_raises(self, cache):
        with pytest.raises(TypeError):
            cache.set("k", object())


# ---------------------------------------------------------------------------
# FileCache TTL expiry
# ---------------------------------------------------------------------------

class TestFileCacheTTL:
    def test_expired_entry_returns_none(self, tmp_path):
        c = FileCache(tmp_path / "c", ttl=0.01)
        c.set("k", "value")
        time.sleep(0.05)
        assert c.get("k") is None

    def test_fresh_entry_returned(self, cache):
        cache.set("k", "value")
        assert cache.get("k") == "value"

    def test_no_ttl_never_expires(self, no_ttl_cache):
        # Write an entry with an ancient timestamp directly.
        key = "old_key"
        no_ttl_cache.set(key, "ancient")
        path = no_ttl_cache._entry_path(key)
        entry = json.loads(path.read_text())
        entry["created_at"] = 0.0  # epoch
        path.write_text(json.dumps(entry))
        assert no_ttl_cache.get(key) == "ancient"


# ---------------------------------------------------------------------------
# FileCache.delete
# ---------------------------------------------------------------------------

class TestFileCacheDelete:
    def test_delete_existing_returns_true(self, cache):
        cache.set("k", "v")
        assert cache.delete("k") is True
        assert cache.get("k") is None

    def test_delete_missing_returns_false(self, cache):
        assert cache.delete("nonexistent") is False

    def test_delete_removes_file(self, cache):
        cache.set("k", "v")
        path = cache._entry_path("k")
        assert path.exists()
        cache.delete("k")
        assert not path.exists()


# ---------------------------------------------------------------------------
# FileCache.clear
# ---------------------------------------------------------------------------

class TestFileCacheClear:
    def test_clear_removes_all_entries(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        count = cache.clear()
        assert count == 2
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_clear_empty_cache_returns_zero(self, cache):
        assert cache.clear() == 0


# ---------------------------------------------------------------------------
# FileCache.cleanup
# ---------------------------------------------------------------------------

class TestFileCacheCleanup:
    def test_cleanup_removes_expired(self, tmp_path):
        c = FileCache(tmp_path / "c", ttl=3600)
        c.set("old", "gone")
        # Manually age the "old" entry so it is expired.
        old_path = c._entry_path("old")
        entry = json.loads(old_path.read_text())
        entry["created_at"] = 0.0
        old_path.write_text(json.dumps(entry))
        c.set("fresh", "here")
        removed = c.cleanup()
        assert removed == 1
        assert c.get("fresh") == "here"

    def test_cleanup_empty_cache(self, cache):
        assert cache.cleanup() == 0

    def test_cleanup_removes_corrupt_file(self, cache):
        cache.set("k", "v")
        path = cache._entry_path("k")
        path.write_text("not json")
        removed = cache.cleanup()
        assert removed == 1
        assert not path.exists()

    def test_cleanup_no_ttl_removes_nothing(self, no_ttl_cache):
        no_ttl_cache.set("k", "v")
        assert no_ttl_cache.cleanup() == 0


# ---------------------------------------------------------------------------
# FileCache.contains
# ---------------------------------------------------------------------------

class TestFileCacheContains:
    def test_present_key(self, cache):
        cache.set("k", "v")
        assert cache.contains("k") is True

    def test_absent_key(self, cache):
        assert cache.contains("missing") is False

    def test_expired_key_not_contained(self, tmp_path):
        c = FileCache(tmp_path / "c", ttl=0.01)
        c.set("k", "v")
        time.sleep(0.05)
        assert c.contains("k") is False


# ---------------------------------------------------------------------------
# FileCache: corrupt entry in get()
# ---------------------------------------------------------------------------

class TestFileCacheCorruptEntry:
    def test_corrupt_file_returns_none(self, cache):
        cache.set("k", "v")
        path = cache._entry_path("k")
        path.write_text("{{bad json")
        assert cache.get("k") is None

    def test_corrupt_file_is_deleted(self, cache):
        cache.set("k", "v")
        path = cache._entry_path("k")
        path.write_text("{{bad json")
        cache.get("k")
        assert not path.exists()


# ---------------------------------------------------------------------------
# FileCache: cache_dir and ttl properties
# ---------------------------------------------------------------------------

class TestFileCacheProperties:
    def test_cache_dir_is_resolved_path(self, tmp_path):
        c = FileCache(tmp_path / "sub")
        assert c.cache_dir == (tmp_path / "sub").resolve()

    def test_ttl_property(self, cache):
        assert cache.ttl == 60

    def test_ttl_none(self, no_ttl_cache):
        assert no_ttl_cache.ttl is None

    def test_creates_directory_automatically(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        c = FileCache(deep)
        assert deep.is_dir()
