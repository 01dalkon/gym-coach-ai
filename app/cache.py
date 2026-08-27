"""Cache de respuestas LLM — backend en memoria (default) o Redis opcional."""
import asyncio
import hashlib
import json
import logging
import os
import time

log = logging.getLogger("gymcoach.cache")

TTL = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
_KEY_PREFIX = "gymcoach:llm:"


def make_key(message: str) -> str:
    normalized = " ".join(message.lower().split())
    return _KEY_PREFIX + hashlib.sha256(normalized.encode()).hexdigest()


class InMemoryCache:
    def __init__(self, ttl: int = TTL):
        self._ttl = ttl
        self._store: dict[str, tuple[dict, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> dict | None:
        async with self._lock:
            entry = self._store.get(key)
        if entry is None:
            return None
        data, expires_at = entry
        if time.monotonic() > expires_at:
            async with self._lock:
                self._store.pop(key, None)
            return None
        return data

    async def set(self, key: str, value: dict) -> None:
        async with self._lock:
            self._store[key] = (value, time.monotonic() + self._ttl)

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)


class RedisCache:
    def __init__(self, url: str, ttl: int = TTL):
        self._url = url
        self._ttl = ttl
        self._client = None

    async def _connect(self):
        if self._client is not None:
            return self._client
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(self._url, decode_responses=False)
            await client.ping()
            self._client = client
            log.info("Cache: Redis conectado (%s)", self._url)
        except Exception as e:
            log.warning("Cache: Redis no disponible (%s), usando memoria", e)
            self._client = None
        return self._client

    async def get(self, key: str) -> dict | None:
        client = await self._connect()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            log.warning("Cache Redis GET error: %s", e)
            return None

    async def set(self, key: str, value: dict) -> None:
        client = await self._connect()
        if client is None:
            return
        try:
            await client.setex(key, self._ttl, json.dumps(value))
        except Exception as e:
            log.warning("Cache Redis SET error: %s", e)

    async def invalidate(self, key: str) -> None:
        client = await self._connect()
        if client is None:
            return
        try:
            await client.delete(key)
        except Exception as e:
            log.warning("Cache Redis DEL error: %s", e)


def get_cache() -> InMemoryCache | RedisCache:
    backend = os.getenv("CACHE_BACKEND", "memory").lower()
    if backend == "redis":
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return RedisCache(url=url, ttl=TTL)
    return InMemoryCache(ttl=TTL)
