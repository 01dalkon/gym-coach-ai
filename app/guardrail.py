"""Guardrail de dos capas: keyword pre-filter + clasificación LLM ligera."""
import logging
import os
import re
import unicodedata

import httpx

log = logging.getLogger("gymcoach.guardrail")

# Saludos — siempre pasan, el LLM responde presentándose
_GREETINGS = {
    "hola", "hello", "hi", "hey", "buenas", "buenos", "buen", "saludos",
    "que tal", "que hay", "como estas", "como esta", "good morning",
    "good afternoon", "good evening", "sup", "howdy", "greetings",
}

# Términos que garantizan que el mensaje es fitness-related
_FITNESS_ALLOW = {
    # Ejercicios y movimientos
    "squat", "deadlift", "bench", "press", "curl", "row", "pull-up", "pull up", "pushup", "push-up",
    "burpee", "lunge", "plank", "crunch", "dip", "clean", "snatch", "jerk",
    "thruster", "muscle-up", "handstand", "box jump", "double under",
    # Contexto de entrenamiento
    "wod", "amrap", "emom", "for time", "metcon", "workout", "training", "gym",
    "crossfit", "hiit", "cardio", "reps", "sets", "rep", "rm", "1rm", "pr",
    "warm up", "warmup", "cool down", "stretch", "mobility", "routine", "circuit",
    # Músculos y anatomía deportiva
    "muscle", "glute", "quad", "hamstring", "bicep", "tricep", "deltoid",
    "lat", "core", "abs", "chest", "shoulder", "back",
    # Nutrición deportiva
    "protein", "macro", "calorie", "pre-workout", "post-workout", "creatine",
    "whey", "bcaa",
    # Español
    "rutina", "ejercicio", "entrenamiento", "musculo", "repeticion", "serie",
    "sentadilla", "peso muerto", "dominada", "flexion", "fondos", "zancada",
    "plancha", "abdominales", "calentamiento", "estiramientos", "movilidad",
    "proteina", "calorias", "fuerza", "resistencia", "cardio", "gym", "gimnasio",
    "kettlebell", "mancuerna", "barra", "pesa", "tecnica",
}

# Términos que indican claramente que el mensaje NO es fitness
_OFF_TOPIC_DENY = {
    "código", "código fuente", "programa", "javascript", "python", "sql", "html",
    "css", "api", "función", "variable", "loop", "array", "database", "function",
    "política", "presidente", "gobierno", "elecciones", "partido", "politics", "election",
    "receta", "cocina", "ingrediente", "recipe", "cook", "ingredient",  # nutrición no deportiva
    "chiste", "broma", "cuento", "joke", "funny", "story",
    "película", "serie", "musica", "cancion", "movie", "film", "song", "music",
    "write code", "write a function", "debug", "fix my code",
    "what is the capital", "translate", "who is",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", text)


def keyword_check(message: str) -> str:
    """
    Retorna:
      'allow'   — contiene keywords fitness claros → pasar sin LLM
      'deny'    — contiene señales off-topic claras → bloquear sin LLM
      'unclear' — ambiguo → delegar al LLM classifier
    """
    norm = _norm(message)
    words = set(norm.split())

    # Solo match palabras completas (word boundary matching) para evitar falsos positivos
    # ej: "president" NO debe matchear con "press"
    deny_found = any(w in _OFF_TOPIC_DENY for w in words)
    if deny_found:
        return "deny"

    allow_found = any(w in _FITNESS_ALLOW for w in words)
    if allow_found:
        return "allow"

    return "unclear"


_CLASSIFIER_PROMPT = (
    "Answer ONLY with the JSON {\"fitness\": true} or {\"fitness\": false}. "
    "Is the following message related to physical exercise, gym workouts, fitness training, "
    "sports nutrition, or athletic performance? Message: "
)


async def llm_classify(message: str) -> bool:
    """Clasificación binaria con el LLM usando prompt mínimo. Falla abierta (permite el mensaje)."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return True  # sin key no podemos clasificar, dejamos pasar al LLM principal

    model = os.getenv("NVIDIA_MODEL", "google/diffusiongemma-26b-a4b-it")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _CLASSIFIER_PROMPT + message[:300]}],
        "temperature": 0,
        "max_tokens": 20,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions", json=payload, headers=headers
            )
        text = resp.json()["choices"][0]["message"]["content"].lower()
        return '"fitness": true' in text or "'fitness': true" in text
    except Exception as exc:
        log.warning("Guardrail LLM classify falló (%s), dejando pasar.", exc)
        return True  # falla abierta


async def is_fitness_message(message: str, has_image: bool) -> bool:
    """
    True  → el mensaje puede procesarse.
    False → el mensaje es off-topic y debe bloquearse.

    Las imágenes siempre pasan (pueden ser fotos de WODs).
    Primero keyword_check (cero latencia), luego LLM si es ambiguo.
    Mensajes muy cortos (<2 palabras) pasan directo (saludos, errores del usuario).
    """
    if has_image:
        return True

    # Saludos siempre pasan — el LLM se presenta y guía al usuario
    norm = _norm(message)
    words = set(norm.split())
    if any(w in _GREETINGS for w in words):
        return True

    result = keyword_check(message)
    if result == "allow":
        return True
    if result == "deny":
        log.info("Guardrail keyword DENY: %.80s", message)
        return False

    # Ambiguo: si es muy corto, dejar pasar al LLM principal (saludos, "hola", etc.)
    if len(message.split()) < 2:
        return True

    # Clasificación LLM ligera para casos ambiguos
    fitness = await llm_classify(message)
    if not fitness:
        log.info("Guardrail LLM DENY: %.80s", message)
    return fitness
