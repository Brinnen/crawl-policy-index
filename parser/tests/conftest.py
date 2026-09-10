from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def registry_path() -> Path:
    return REPO / "registry" / "agents.yml"


@pytest.fixture(scope="session")
def corpus_dir() -> Path:
    return Path(__file__).parent / "corpus"
