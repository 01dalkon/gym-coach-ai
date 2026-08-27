"""Cliente para NVIDIA NIM (integrate.api.nvidia.com)."""
import json
import logging
import os
import re

import httpx

log = logging.getLogger("gymcoach.llm")

LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = os.getenv("NVIDIA_MODEL", "google/diffusiongemma-26b-a4b-it")

SYSTEM_PROMPT = """Eres GymCoach, un entrenador personal virtual experto en fitness, crossfit y entrenamiento funcional.

El usuario te enviará texto o una FOTO de su rutina del día (WOD, tabla del gym, screenshot de una app).

GUARDRAIL — ANTES de responder, evalúa si el mensaje está relacionado con fitness, ejercicio, entrenamiento, nutrición deportiva o bienestar físico.
- Si es un SALUDO ("hola", "hello", "hi", "buenos días", etc.): responde con off_topic=false, preséntate brevemente y pregunta en qué puedes ayudar (rutina, ejercicio, técnica, etc.).
- Si NO está relacionado con fitness (política, programación, chistes, preguntas generales de conocimiento, etc.): responde con off_topic=true y un mensaje amable pero firme.
- Si SÍ lo está: responde con off_topic=false y sigue los pasos normales.

Tu trabajo (solo cuando off_topic=false):
1. Si hay imagen: lee y transcribe la rutina completa (warm up, fuerza, metcon, series, reps, %RM, etc.).
2. Explica la rutina en español, de forma clara y motivadora: qué se trabaja, en qué orden, técnica clave y errores comunes de cada ejercicio, y cómo escalar si el usuario es principiante.
3. Identifica CADA ejercicio mencionado y devuélvelo con su nombre canónico en INGLÉS (ej: "barbell bench press", "power clean", "push jerk", "toes to bar", "burpee", "sumo deadlift").

Responde SIEMPRE y ÚNICAMENTE con un JSON válido con esta estructura exacta:
{
  "off_topic": false,
  "reply": "tu explicación en español (puedes usar markdown ligero: **negrita**, saltos de línea)",
  "exercises": ["nombre canónico en inglés", "..."]
}

Cuando el mensaje no es de fitness:
{
  "off_topic": true,
  "reply": "Solo puedo ayudarte con rutinas de ejercicio, técnica, programación de entrenamiento o nutrición deportiva. ¡Cuéntame tu WOD o pregúntame sobre algún ejercicio!",
  "exercises": []
}

No agregues texto fuera del JSON. No uses bloques de código."""


class LLMError(Exception):
    pass


def _extract_json(text: str) -> dict:
    """Parseo robusto: maneja markdown fences, prefijos de texto y llaves desbalanceadas."""
    text = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.MULTILINE).strip()

    # Intento 1: parseo directo
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Intento 2: extraer el bloque {...} externo con brace-matching
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        result = json.loads(text[start : i + 1])
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        break

    # Último recurso: texto plano como respuesta
    return {"reply": text, "exercises": []}


async def ask_llm(
    message: str,
    history: list[dict],
    image_b64: str | None = None,
    image_mime: str = "image/jpeg",
    model: str | None = None,
) -> dict:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise LLMError("Falta NVIDIA_API_KEY. Créala gratis en https://build.nvidia.com")

    content: list[dict] | str
    if image_b64:
        content = [
            {"type": "text", "text": message or "Explícame esta rutina paso a paso."},
            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}},
        ]
    else:
        content = message

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-6:]:  # ventana corta para no agotar el free tier
        messages.append({"role": h.get("role", "user"), "content": str(h.get("content", ""))[:2000]})
    messages.append({"role": "user", "content": content }) # type: ignore

    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 1,
        "top_p": 0.95,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": True},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(LLM_URL, json=payload, headers=headers)
    if resp.status_code == 429:
        raise LLMError("Límite de la API NVIDIA alcanzado. Intenta en unos minutos o cambia NVIDIA_MODEL.")
    if resp.status_code != 200:
        log.error("NVIDIA %s: %s", resp.status_code, resp.text[:500])
        raise LLMError(f"Error del proveedor LLM ({resp.status_code}).")

    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError("Respuesta inesperada del LLM.") from e

    out = _extract_json(text)
    out.setdefault("reply", "")
    out.setdefault("exercises", [])
    out.setdefault("off_topic", False)
    if not isinstance(out["exercises"], list):
        out["exercises"] = []
    if not isinstance(out["off_topic"], bool):
        out["off_topic"] = bool(out["off_topic"])
    return out
