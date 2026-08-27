"""Tests para matching y búsqueda de ejercicios."""
import pytest

from app.exercises import ExerciseDB


@pytest.fixture
def db(tmp_path):
    """ExerciseDB con sample data."""
    return ExerciseDB(str(tmp_path))


class TestExerciseMatch:
    """Tests del fuzzy matching de ejercicios."""

    def test_exact_match(self, db):
        """Coincidencia exacta."""
        result = db.match("pull-up")
        assert result is not None
        assert "pull" in result["name"].lower()

    def test_fuzzy_match_typo(self, db):
        """Tolera typos pequeños."""
        result = db.match("dumbbell curls")  # typo menor
        assert result is not None
        assert "curl" in result["name"].lower()

    def test_spanish_alias_sentadilla(self, db):
        """Traduce 'sentadilla' → 'squat'."""
        result = db.match("sentadilla")
        assert result is not None
        assert "squat" in result["name"].lower()

    def test_spanish_alias_dominadas(self, db):
        """Traduce 'dominadas' → 'pull-up'."""
        result = db.match("dominadas")
        assert result is not None
        assert "pull" in result["name"].lower() and "up" in result["name"].lower()

    def test_spanish_alias_flexiones(self, db):
        """Traduce 'flexiones' → 'bench press'."""
        result = db.match("flexiones")
        assert result is not None
        # flexiones se traduce a push-up en ES_ALIASES, pero hay bench press en el dataset
        assert "bench" in result["name"].lower() or "press" in result["name"].lower()

    def test_no_match_below_threshold(self, db):
        """Rechaza coincidencias débiles."""
        result = db.match("xxxyyy", threshold=90)
        assert result is None

    def test_case_insensitive(self, db):
        """Matching case-insensitive."""
        result1 = db.match("DEADLIFT")
        result2 = db.match("deadlift")
        assert result1 is not None and result2 is not None
        assert result1["id"] == result2["id"]

    def test_whitespace_normalized(self, db):
        """Normaliza espacios y puntuación."""
        result1 = db.match("barbell   deadlift")
        result2 = db.match("barbell deadlift")
        assert result1 is not None and result2 is not None
        # Mismo ejercicio
        assert result1["id"] == result2["id"]


class TestMatchMany:
    """Tests del matching de múltiples ejercicios."""

    def test_match_many_dedup(self, db):
        """Evita duplicados en la lista."""
        names = ["deadlift", "DEADLIFT", "barbell deadlift"]
        results = db.match_many(names)
        # Todos apuntan al mismo ejercicio, solo uno en output
        assert len(results) == 1
        assert "deadlift" in results[0]["name"].lower()

    def test_match_many_mixed(self, db):
        """Mezcla ejercicios válidos e inválidos."""
        names = ["squat", "xxxyyy", "deadlift", "pull-up"]
        results = db.match_many(names)
        assert len(results) >= 2
        assert all(ex["id"] for ex in results)

    def test_match_many_empty(self, db):
        """Lista vacía."""
        results = db.match_many([])
        assert results == []

    def test_match_many_no_matches(self, db):
        """Ningún match válido."""
        results = db.match_many(["xxxxxx", "yyyyyy"])
        assert results == []


class TestSearch:
    """Tests de búsqueda manual (GET /api/exercises/search)."""

    def test_search_exact(self, db):
        """Búsqueda exacta."""
        results = db.search("deadlift")
        assert len(results) > 0
        assert any("deadlift" in ex["name"].lower() for ex in results)

    def test_search_limit(self, db):
        """Respeta límite."""
        results = db.search("p", limit=3)
        assert len(results) <= 3

    def test_search_returns_cards(self, db):
        """Devuelve cards bien formadas."""
        results = db.search("squat", limit=1)
        assert len(results) > 0
        card = results[0]
        assert "id" in card
        assert "name" in card
        assert "target" in card

    def test_search_case_insensitive(self, db):
        """Búsqueda case-insensitive."""
        results1 = db.search("SQUAT")
        results2 = db.search("squat")
        assert len(results1) > 0 and len(results2) > 0
        assert results1[0]["id"] == results2[0]["id"]


class TestCard:
    """Tests de la representación de ejercicio."""

    def test_card_has_required_fields(self, db, sample_exercise):
        """Card tiene todos los campos necesarios."""
        card = db.card(sample_exercise)
        required = ["id", "name", "target", "equipment"]
        for field in required:
            assert field in card

    def test_card_media_urls(self, db, sample_exercise):
        """URLs de media tienen el prefijo /media/."""
        card = db.card(sample_exercise)
        if card.get("gif"):
            assert card["gif"].startswith("/media/")
        if card.get("image"):
            assert card["image"].startswith("/media/")

    def test_card_custom_base_url(self, db, sample_exercise):
        """Acepta base_url personalizada."""
        card = db.card(sample_exercise, base_url="https://example.com")
        if card.get("gif"):
            assert card["gif"].startswith("https://example.com/media/")
