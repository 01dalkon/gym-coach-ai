"""GymCoach AI — API de chat fitness con visión, GIFs de ejercicios y widget embebible."""
import base64
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .cache import get_cache, make_key as cache_key
from .exercises import ExerciseDB
from .guardrail import is_fitness_message
from .llm import LLMError, ask_llm

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gymcoach")

ROOT = Path(__file__).parent.parent
DATASET_DIR = Path(os.getenv("DATASET_DIR", ROOT / "exercises-dataset"))
MAX_IMAGE_MB = 8

app = FastAPI(title="GymCoach AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

db = ExerciseDB(str(DATASET_DIR))
_cache = get_cache()


@app.get("/health")
def health():
    return {"status": "ok", "exercises": len(db.exercises)}


@app.post("/api/chat")
async def chat(
    message: str = Form(""),
    history: str = Form("[]"),
    image: UploadFile | None = File(None),
):
    if not message and not image:
        raise HTTPException(400, "Envía un mensaje o una imagen.")

    try:
        hist = json.loads(history)
        assert isinstance(hist, list)
    except (json.JSONDecodeError, AssertionError):
        hist = []

    image_b64, mime = None, "image/jpeg"
    if image is not None:
        raw = await image.read()
        if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
            raise HTTPException(413, f"Imagen demasiado grande (máx {MAX_IMAGE_MB} MB).")
        image_b64 = base64.b64encode(raw).decode()
        mime = image.content_type or "image/jpeg"

    if not await is_fitness_message(message, image_b64 is not None):
        return {
            "reply": "Solo puedo ayudarte con rutinas de ejercicio, técnica, programación de entrenamiento o nutrición deportiva. ¡Cuéntame tu WOD o pregúntame sobre algún ejercicio!",
            "exercises": [],
            "off_topic": True,
        }

    ck = cache_key(message) if not image_b64 else None
    out = await _cache.get(ck) if ck else None
    if out is None:
        try:
            out = await ask_llm(message, hist, image_b64, mime)
        except LLMError as e:
            raise HTTPException(502, str(e)) from e
        if ck:
            await _cache.set(ck, out)

    if out.get("off_topic"):
        return {"reply": out["reply"], "exercises": [], "off_topic": True}

    matched = db.match_many([str(n) for n in out["exercises"]])
    return {
        "reply": out["reply"],
        "exercises": [db.card(ex) for ex in matched],
        "off_topic": False,
    }


@app.get("/api/exercises/search")
def search_exercises(q: str, limit: int = 10):
    return [db.card(ex) for ex in db.search(q, limit=min(limit, 25))]


# Media del dataset (GIFs y thumbnails)
if (DATASET_DIR / "videos").exists():
    app.mount("/media/videos", StaticFiles(directory=DATASET_DIR / "videos"), name="videos")
if (DATASET_DIR / "images").exists():
    app.mount("/media/images", StaticFiles(directory=DATASET_DIR / "images"), name="images")

# Widget + demo (al final para no tapar las rutas de API)
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
