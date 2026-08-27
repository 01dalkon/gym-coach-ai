"""Carga y búsqueda del dataset de ejercicios (hasaneyldrm/exercises-dataset)."""
import json
import logging
import os
import re
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz, process

log = logging.getLogger("gymcoach.exercises")

# Alias comunes ES -> EN para mejorar el matching cuando la rutina viene en español
ES_ALIASES = {
    "sentadilla": "squat",
    "peso muerto": "deadlift",
    "press de banca": "bench press",
    "press banca": "bench press",
    "dominadas": "pull-up",
    "flexiones": "bench press",
    "fondos": "dips",
    "remo": "row",
    "zancadas": "lunge",
    "estocadas": "lunge",
    "curl de biceps": "biceps curl",
    "elevaciones laterales": "lateral raise",
    "press militar": "overhead press",
    "abdominales": "sit-up",
    "plancha": "plank",
    "hip thrust": "hip thrust",
    "burpees": "burpee",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", text).strip()


class ExerciseDB:
    def __init__(self, dataset_dir: str):
        self.dataset_dir = Path(dataset_dir)
        data_file = self.dataset_dir / "data" / "exercises.json"
        if not data_file.exists():
            # Fallback para desarrollo sin el dataset clonado
            data_file = Path(__file__).parent.parent / "data" / "sample_exercises.json"
            log.warning(
                "Dataset completo no encontrado en %s. Usando dataset de ejemplo (%s). "
                "Clona https://github.com/hasaneyldrm/exercises-dataset para los 1,324 ejercicios.",
                self.dataset_dir, data_file,
            )
        with open(data_file, encoding="utf-8") as f:
            self.exercises: list[dict] = json.load(f)
        self._names = [_norm(ex["name"]) for ex in self.exercises]
        log.info("Cargados %d ejercicios", len(self.exercises))

    def match(self, name: str, threshold: int = 72) -> dict | None:
        """Fuzzy-match de un nombre de ejercicio (EN o ES) contra el dataset."""
        query = _norm(name)
        for es, en in ES_ALIASES.items():
            if es in query:
                query = _norm(en)
                break
        result = process.extractOne(query, self._names, scorer=fuzz.token_set_ratio)
        if result and result[1] >= threshold:
            return self.exercises[result[2]]
        return None

    def match_many(self, names: list[str]) -> list[dict]:
        seen, out = set(), []
        for n in names:
            ex = self.match(n)
            if ex and ex["id"] not in seen:
                seen.add(ex["id"])
                out.append(ex)
        return out

    def search(self, q: str, limit: int = 10) -> list[dict]:
        query = _norm(q)
        results = process.extract(query, self._names, scorer=fuzz.token_set_ratio, limit=limit)
        return [self.exercises[r[2]] for r in results if r[1] >= 55]

    def card(self, ex: dict, base_url: str = "", lang: str = "es") -> dict:
        """Representación para el frontend, con URLs servidas por esta API."""
        instructions = ex.get("instructions") or {}
        return {
            "id": ex["id"],
            "name": ex["name"],
            "target": ex.get("target"),
            "equipment": ex.get("equipment"),
            "category": ex.get("category"),
            "secondary_muscles": ex.get("secondary_muscles", []),
            "instructions": instructions.get(lang) or instructions.get("es", ""),
            "gif": f"{base_url}/media/{ex['gif_url']}" if ex.get("gif_url") else None,
            "image": f"{base_url}/media/{ex['image']}" if ex.get("image") else None,
        }
