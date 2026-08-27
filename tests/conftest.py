"""Fixtures compartidas para tests."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_exercises():
    """Carga ejercicios de ejemplo."""
    data_file = Path(__file__).parent.parent / "data" / "sample_exercises.json"
    with open(data_file, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_exercise(sample_exercises):
    """Primer ejercicio del dataset."""
    return sample_exercises[0]
