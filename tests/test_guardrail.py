"""Tests para el guardrail de off-topic detection."""
import pytest

from app.guardrail import keyword_check


class TestKeywordCheck:
    """Tests del pre-filter de keywords."""

    def test_fitness_allow_squat(self):
        """Detecta 'squat' como fitness."""
        assert keyword_check("How do squat properly?") == "allow"

    def test_fitness_allow_deadlift(self):
        """Detecta 'deadlift' como fitness."""
        assert keyword_check("My deadlift is weak") == "allow"

    def test_fitness_allow_sentadilla_es(self):
        """Detecta 'sentadilla' (español) como fitness."""
        assert keyword_check("Quiero mejorar mi sentadilla") == "allow"

    def test_fitness_allow_wod(self):
        """Detecta 'WOD' como fitness."""
        assert keyword_check("Today wod looks hard") == "allow"

    def test_fitness_allow_routine(self):
        """Detecta 'routine' como fitness."""
        assert keyword_check("Give me a routine for beginners") == "allow"

    def test_fitness_allow_protein(self):
        """Detecta 'protein' como nutrición deportiva."""
        assert keyword_check("How much protein daily") == "allow"

    def test_off_topic_deny_election(self):
        """Bloquea pregunta sobre política."""
        assert keyword_check("Who won the election") == "deny"

    def test_off_topic_deny_code(self):
        """Bloquea pregunta sobre programación."""
        assert keyword_check("Write a function please") == "deny"

    def test_off_topic_deny_recipe(self):
        """Bloquea pregunta sobre recetas (nutrición no deportiva)."""
        assert keyword_check("How do I make a recipe") == "deny"

    def test_off_topic_deny_joke(self):
        """Bloquea pedido de chiste."""
        assert keyword_check("Tell me a funny joke") == "deny"

    def test_unclear_short_message(self):
        """Mensaje ambiguo corto → unclear."""
        assert keyword_check("hello") == "unclear"

    def test_unclear_ambiguous(self):
        """Mensaje que podría ser fitness o no."""
        assert keyword_check("I need help") == "unclear"

    def test_case_insensitive(self):
        """Keywords funcionan case-insensitive."""
        assert keyword_check("SQUAT EVERY DAY") == "allow"
        assert keyword_check("TELL ME JOKE") == "deny"

    def test_diacritics_normalized(self):
        """Maneja acentos y caracteres especiales."""
        assert keyword_check("Mejorar la técnica fitness") == "allow"  # tiene "tecnica"
        assert keyword_check("Dieta con proteína") == "allow"  # proteina
