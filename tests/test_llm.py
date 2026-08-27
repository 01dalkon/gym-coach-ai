"""Tests para parsing robusto del LLM."""
import pytest

from app.llm import _extract_json


class TestExtractJson:
    """Tests del parseo robusto de JSON."""

    def test_valid_json_plain(self):
        """JSON válido sin bloques de código."""
        text = '{"reply": "hola", "exercises": ["squat"]}'
        result = _extract_json(text)
        assert result["reply"] == "hola"
        assert result["exercises"] == ["squat"]

    def test_valid_json_with_markdown_json_fence(self):
        """JSON dentro de ```json ... ```."""
        text = '```json\n{"reply": "test", "exercises": []}\n```'
        result = _extract_json(text)
        assert result["reply"] == "test"
        assert result["exercises"] == []

    def test_valid_json_with_generic_fence(self):
        """JSON dentro de ``` ... ```."""
        text = '```\n{"reply": "test", "exercises": []}\n```'
        result = _extract_json(text)
        assert result["reply"] == "test"

    def test_json_with_surrounding_text(self):
        """JSON rodeado de texto."""
        text = 'Aquí está tu respuesta:\n{"reply": "explicación", "exercises": ["burpee"]}\nEso es todo.'
        result = _extract_json(text)
        assert result["reply"] == "explicación"
        assert result["exercises"] == ["burpee"]

    def test_malformed_json_fallback(self):
        """JSON malformado fallback a respuesta plana."""
        text = '{"reply": "hola", exercises: [squat]}'  # falta comillas
        result = _extract_json(text)
        # Falla gracefully, devuelve el texto plano
        assert isinstance(result, dict)
        assert "reply" in result or "exercises" in result or result == {"reply": text, "exercises": []}

    def test_multiline_json(self):
        """JSON con saltos de línea."""
        text = """{
  "reply": "Explicación\\nmulilínea",
  "exercises": ["squat", "deadlift"]
}"""
        result = _extract_json(text)
        assert result["reply"] == "Explicación\nmulilínea"
        assert "squat" in result["exercises"]

    def test_json_with_unicode(self):
        """JSON con caracteres Unicode (español)."""
        text = '{"reply": "Explicación con acentos: técnica, nutrición", "exercises": []}'
        result = _extract_json(text)
        assert "técnica" in result["reply"]
        assert "nutrición" in result["reply"]

    def test_empty_json(self):
        """JSON vacío."""
        text = "{}"
        result = _extract_json(text)
        assert isinstance(result, dict)

    def test_nested_json_in_markdown(self):
        """JSON anidado en markdown (el común en respuestas de LLM)."""
        text = """Aquí te doy tu plan:

```json
{
  "reply": "3 sets x 10 reps de squats",
  "exercises": ["squat"]
}
```

Listo!"""
        result = _extract_json(text)
        assert "squat" in result["exercises"]
        assert "squat" in result["reply"]

    def test_json_with_escaped_quotes(self):
        """JSON con comillas escapadas."""
        text = '{"reply": "Dice \\"hola\\" el entrenador", "exercises": []}'
        result = _extract_json(text)
        assert "hola" in result["reply"]
