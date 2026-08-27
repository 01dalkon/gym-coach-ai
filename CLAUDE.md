# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Levantar la app

**Con Docker (recomendado):**
```bash
docker compose up --build
```

**Sin Docker (desarrollo local):**
```bash
pip install -r requirements.txt
export NVIDIA_API_KEY=nvapi-...
uvicorn app.main:app --reload
```

**Imagen ligera sin dataset (pruebas rápidas):**
```bash
docker build --build-arg INCLUDE_DATASET=false .
```

La app queda en `http://localhost:8000`. El chat directo en `/chat.html`.

## Variables de entorno

Copiar `.env.example` → `.env` y setear `NVIDIA_API_KEY`. El resto tiene defaults razonables.

| Variable | Default | Descripción |
|---|---|---|
| `NVIDIA_API_KEY` | — | Requerida. Gratis en build.nvidia.com |
| `NVIDIA_MODEL` | `google/diffusiongemma-26b-a4b-it` | Modelo LLM; cambiarlo no requiere tocar código |
| `DATASET_DIR` | `./exercises-dataset` | Path al repo clonado del dataset |
| `CORS_ORIGINS` | `*` | Orígenes embebibles del widget |
| `PORT` | `8000` | Puerto del servidor (Hugging Face Spaces usa 7860) |

## Arquitectura

```
POST /api/chat (multipart: message, history, image)
  │
  ├─ llm.py :: ask_llm()  →  NVIDIA NIM (visión opcional)
  │     Devuelve JSON: { reply: str, exercises: [nombre EN] }
  │
  └─ exercises.py :: ExerciseDB.match_many()  →  fuzzy-match contra dataset
        Devuelve cards con URLs /media/... servidas por FastAPI StaticFiles
```

**`app/llm.py`** — cliente async httpx para NVIDIA NIM. El system prompt fuerza que el LLM devuelva siempre JSON `{reply, exercises}`. `_extract_json()` parsea de forma robusta porque los modelos gratuitos a veces envuelven la respuesta en \`\`\`json...\`\`\`.

**`app/exercises.py`** — `ExerciseDB` carga `exercises-dataset/data/exercises.json` (1,324 ejercicios) o el fallback `data/sample_exercises.json` (8 ejercicios) si el dataset no está clonado. El matching usa `rapidfuzz.token_set_ratio` con threshold 72 para chat y 55 para búsqueda manual. `ES_ALIASES` traduce nombres comunes en español antes del fuzzy-match.

**`app/main.py`** — FastAPI. El orden de los `app.mount()` importa: los mounts de `/media/videos` y `/media/images` se registran antes del mount raíz `/` (static), o FastAPI los taparía.

**`static/`** — frontend vanilla JS sin dependencias. `widget.js` inyecta un botón flotante embebible con `<script src="...">`. `chat.html` es la UI standalone usable también en iframe.

## Tests

**Correr todos los tests:**
```bash
pytest                           # 60 tests, ~75% coverage
pytest -v                        # verbose
pytest --cov=app --cov-report=html  # coverage report
pytest tests/test_guardrail.py -v   # single file
pytest tests/test_exercises.py::TestExerciseMatch -v  # single class
```

**Test suites (60 tests, 75% coverage):**
- **`test_guardrail.py`** — keyword detection, off-topic classification (pre-filter sin LLM)
  - 16 tests: case insensitivity, Spanish aliases, deny/allow lists
- **`test_exercises.py`** — fuzzy matching, búsqueda, cards (core matching engine)
  - 18 tests: exact/fuzzy matching, dedup, Spanish aliases, card formatting
- **`test_llm.py`** — JSON parsing robusto de respuestas del LLM
  - 11 tests: plain JSON, markdown blocks, nested JSON, Unicode, malformed fallback
- **`test_main.py`** — endpoints HTTP, guardrail integration, límites
  - 15 tests: health, search, chat guardrail, off-topic detection, image size limits

## Dataset

El dataset `exercises-dataset` está incluido en el repo vía Git LFS. Cada ejercicio tiene `gif_url` e `image` que son paths relativos dentro del dataset; `ExerciseDB.card()` los convierte a URLs `/media/...` que FastAPI sirve como archivos estáticos.

Si el dataset no existe en `DATASET_DIR`, la app arranca igual usando los 8 ejercicios de `data/sample_exercises.json` (útil para desarrollo).
