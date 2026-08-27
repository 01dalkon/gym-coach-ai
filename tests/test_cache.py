"""Tests para el módulo de cache."""
import asyncio
import pytest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.cache import InMemoryCache, make_key
from app.main import app


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def cache():
    return InMemoryCache(ttl=3600)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_main_cache(monkeypatch):
    """Aísla el singleton _cache de main.py entre tests."""
    import app.main as main_module
    fresh = InMemoryCache(ttl=3600)
    monkeypatch.setattr(main_module, "_cache", fresh)
    return fresh


# ── TestCacheKey ──────────────────────────────────────────────────────────────

class TestCacheKey:
    def test_normalizes_whitespace(self):
        assert make_key("  squat  ") == make_key("squat")

    def test_case_insensitive(self):
        assert make_key("Squat") == make_key("squat")

    def test_different_messages_differ(self):
        assert make_key("squat") != make_key("deadlift")

    def test_has_prefix(self):
        assert make_key("squat").startswith("gymcoach:llm:")

    def test_collapse_inner_spaces(self):
        assert make_key("como  hacer  sentadillas") == make_key("como hacer sentadillas")


# ── TestInMemoryCache ─────────────────────────────────────────────────────────

class TestInMemoryCache:
    @pytest.mark.asyncio
    async def test_miss_returns_none(self, cache):
        assert await cache.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_set_then_get(self, cache):
        value = {"reply": "hola", "exercises": [], "off_topic": False}
        await cache.set("key1", value)
        assert await cache.get("key1") == value

    @pytest.mark.asyncio
    async def test_expired_returns_none(self):
        fast_cache = InMemoryCache(ttl=0)
        await fast_cache.set("k", {"reply": "x", "exercises": [], "off_topic": False})
        # TTL=0 expira inmediatamente
        await asyncio.sleep(0.01)
        assert await fast_cache.get("k") is None

    @pytest.mark.asyncio
    async def test_invalidate_removes_key(self, cache):
        await cache.set("k2", {"reply": "y", "exercises": [], "off_topic": False})
        await cache.invalidate("k2")
        assert await cache.get("k2") is None

    @pytest.mark.asyncio
    async def test_concurrent_writes_no_race(self, cache):
        async def write(i):
            await cache.set(f"key_{i}", {"reply": str(i), "exercises": [], "off_topic": False})

        await asyncio.gather(*[write(i) for i in range(50)])
        for i in range(50):
            result = await cache.get(f"key_{i}")
            assert result is not None


# ── TestChatCacheIntegration ──────────────────────────────────────────────────

class TestChatCacheIntegration:
    LLM_RESPONSE = {"reply": "El squat es el rey.", "exercises": ["squat"], "off_topic": False}

    def test_cache_miss_calls_ask_llm(self, client, mocker):
        mock_llm = mocker.patch("app.main.ask_llm", new_callable=AsyncMock)
        mock_llm.return_value = self.LLM_RESPONSE
        mocker.patch("app.main.is_fitness_message", new_callable=AsyncMock, return_value=True)
        mocker.patch("app.main.db.match_many", return_value=[])

        client.post("/api/chat", data={"message": "como hacer squat"})
        mock_llm.assert_called_once()

    def test_cache_hit_skips_ask_llm(self, client, mocker):
        mock_llm = mocker.patch("app.main.ask_llm", new_callable=AsyncMock)
        mock_llm.return_value = self.LLM_RESPONSE
        mocker.patch("app.main.is_fitness_message", new_callable=AsyncMock, return_value=True)
        mocker.patch("app.main.db.match_many", return_value=[])

        # Primera llamada → miss → llama LLM
        client.post("/api/chat", data={"message": "como hacer squat"})
        # Segunda llamada → hit → no llama LLM
        client.post("/api/chat", data={"message": "como hacer squat"})

        mock_llm.assert_called_once()

    def test_image_request_skips_cache(self, client, mocker):
        mock_llm = mocker.patch("app.main.ask_llm", new_callable=AsyncMock)
        mock_llm.return_value = self.LLM_RESPONSE
        mocker.patch("app.main.is_fitness_message", new_callable=AsyncMock, return_value=True)
        mocker.patch("app.main.db.match_many", return_value=[])

        img = b"GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;"
        files = {"image": ("test.gif", img, "image/gif")}

        client.post("/api/chat", data={"message": ""}, files=files)
        client.post("/api/chat", data={"message": ""}, files=files)

        # Las imágenes siempre llaman al LLM (no se cachean)
        assert mock_llm.call_count == 2

    def test_cache_key_normalized(self, client, mocker):
        mock_llm = mocker.patch("app.main.ask_llm", new_callable=AsyncMock)
        mock_llm.return_value = self.LLM_RESPONSE
        mocker.patch("app.main.is_fitness_message", new_callable=AsyncMock, return_value=True)
        mocker.patch("app.main.db.match_many", return_value=[])

        client.post("/api/chat", data={"message": "como hacer squat"})
        client.post("/api/chat", data={"message": "COMO HACER SQUAT"})

        # Mismo mensaje normalizado → hit en el segundo
        mock_llm.assert_called_once()
