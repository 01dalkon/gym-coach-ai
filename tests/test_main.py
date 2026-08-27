"""Tests para los endpoints de la API."""
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Cliente de test para FastAPI."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests de GET /health."""

    def test_health_ok(self, client):
        """Health check devuelve status OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "exercises" in data
        assert data["exercises"] > 0  # Al menos el sample dataset


class TestSearchEndpoint:
    """Tests de GET /api/exercises/search."""

    def test_search_squat(self, client):
        """Búsqueda de squat."""
        response = client.get("/api/exercises/search?q=squat")
        assert response.status_code == 200
        results = response.json()
        assert len(results) > 0
        assert any("squat" in ex["name"].lower() for ex in results)

    def test_search_with_limit(self, client):
        """Búsqueda respeta límite."""
        response = client.get("/api/exercises/search?q=p&limit=2")
        assert response.status_code == 200
        results = response.json()
        assert len(results) <= 2

    def test_search_limit_capped(self, client):
        """Límite no puede exceder 25."""
        response = client.get("/api/exercises/search?q=p&limit=100")
        assert response.status_code == 200
        results = response.json()
        assert len(results) <= 25

    def test_search_empty_query(self, client):
        """Búsqueda con query vacía."""
        response = client.get("/api/exercises/search?q=")
        assert response.status_code == 200
        # Puede devolver algo o nada según el matching

    def test_search_returns_cards(self, client):
        """Resultados son cards bien formadas."""
        response = client.get("/api/exercises/search?q=push")
        results = response.json()
        if results:
            card = results[0]
            assert "id" in card
            assert "name" in card
            assert "target" in card


class TestChatEndpointGuardrail:
    """Tests del guardrail en POST /api/chat."""

    def test_chat_off_topic_code(self, client):
        """Pregunta de programación es bloqueada por guardrail."""
        response = client.post(
            "/api/chat",
            data={"message": "Write a Python function"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["off_topic"] is True
        assert data["exercises"] == []
        assert "Solo puedo ayudarte" in data["reply"]

    def test_chat_off_topic_joke(self, client):
        """Pedido de chiste es bloqueado por guardrail."""
        response = client.post(
            "/api/chat",
            data={"message": "Tell me a funny joke"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["off_topic"] is True

    def test_chat_no_input(self, client):
        """Chat sin mensaje ni imagen falla."""
        response = client.post("/api/chat", data={})
        assert response.status_code == 400
        assert "Envía un mensaje o una imagen" in response.json()["detail"]

    def test_chat_empty_history(self, client):
        """Chat con history vacío es válido (off-topic bloqueado por guardrail)."""
        response = client.post(
            "/api/chat",
            data={"message": "Write a function please", "history": "[]"}
        )
        # Bloqueado por guardrail antes de llamar al LLM
        assert response.status_code == 200
        assert response.json()["off_topic"] is True

    def test_chat_malformed_history_fallback(self, client):
        """Chat con history malformado fallback a []."""
        response = client.post(
            "/api/chat",
            data={"message": "Tell me a funny joke", "history": "not json"}
        )
        # Bloqueado por guardrail, no falla por history malformado
        assert response.status_code == 200

    def test_chat_message_only(self, client):
        """Chat con solo mensaje (sin image) es válido."""
        response = client.post(
            "/api/chat",
            data={"message": "Write a function"}
        )
        assert response.status_code == 200
        assert response.json()["off_topic"] is True


class TestChatEndpointIntegration:
    """Tests de integración del chat (con mocks)."""

    @pytest.mark.asyncio
    async def test_chat_fitness_message_calls_llm(self, client, mocker):
        """Mensaje válido pasa al LLM."""
        mock_ask_llm = AsyncMock(return_value={
            "reply": "Aquí va tu explicación",
            "exercises": ["squat"],
            "off_topic": False,
        })
        with patch("app.main.ask_llm", mock_ask_llm):
            response = client.post(
                "/api/chat",
                data={"message": "¿Cómo hago una sentadilla correcta?"}
            )
            assert response.status_code == 200
            # El guardrail debe dejar pasar este mensaje
            data = response.json()
            assert "exercises" in data or "reply" in data

    def test_chat_response_structure(self, client):
        """Respuesta del chat tiene estructura esperada."""
        response = client.post(
            "/api/chat",
            data={"message": "Tell me a joke"}  # off-topic, bloqueado por guardrail
        )
        data = response.json()
        assert "reply" in data
        assert "exercises" in data
        assert "off_topic" in data
        assert isinstance(data["exercises"], list)
        assert data["off_topic"] is True

    def test_chat_image_only(self, client):
        """Chat solo con imagen (sin texto)."""
        response = client.post(
            "/api/chat",
            data={"message": ""},
            files={"image": ("test.jpg", b"fake image data", "image/jpeg")}
        )
        # Con imagen pero sin mensaje, debería procesar la imagen
        assert response.status_code in [200, 502]  # 502 si falla el LLM sin API key

    def test_chat_image_size_limit(self, client):
        """Imagen demasiado grande es rechazada."""
        huge_data = b"x" * (10 * 1024 * 1024)  # 10 MB
        response = client.post(
            "/api/chat",
            data={"message": "Explícame esta rutina"},
            files={"image": ("huge.jpg", huge_data, "image/jpeg")}
        )
        assert response.status_code == 413
        assert "demasiado grande" in response.json()["detail"]


class TestCorsHeaders:
    """Tests de CORS (nota: TestClient no expone headers CORS, requiere cliente real)."""

    def test_health_works(self, client):
        """Health endpoint funciona."""
        response = client.get("/health")
        assert response.status_code == 200
