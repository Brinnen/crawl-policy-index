"""Shared warehouse helpers."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def database_dsn() -> str:
    explicit = os.environ.get("DATABASE_DSN")
    if explicit:
        return explicit
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_DSN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "postgresql://cpi:cpi@127.0.0.1:5432/cpi"
