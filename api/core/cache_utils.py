"""
TTL Cache — Thread-safe in-memory cache with prefix-based invalidation.
"""
import time
import threading
from typing import Any, Optional

_cache: dict[str, tuple[Any, float]] = {}
_lock = threading.Lock()


def cache_get(key: str) -> Optional[Any]:
    """Get value from cache if not expired."""
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del _cache[key]
            return None
        return value


def cache_set(key: str, value: Any, ttl: int = 60):
    """Set value in cache with TTL in seconds."""
    with _lock:
        _cache[key] = (value, time.time() + ttl)


def cache_invalidate(prefix: str = ""):
    """Invalidate all cache entries matching prefix. Empty prefix clears all."""
    with _lock:
        if not prefix:
            _cache.clear()
        else:
            keys_to_delete = [k for k in _cache if k.startswith(prefix)]
            for k in keys_to_delete:
                del _cache[k]
