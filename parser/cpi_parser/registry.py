"""Load registry/agents.yml. Never treat unverified tokens as publishable."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Agent:
    slug: str
    ua_token: str
    display_name: str
    operator: str
    purpose: str
    documented_url: str | None
    verified: bool
    active: bool
    notes: str | None
    confidence: str | None = None


def load_agents(path: str | Path) -> list[Agent]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    defaults: dict[str, Any] = raw.get("defaults") or {}
    default_verified = bool(defaults.get("verified", False))
    default_active = bool(defaults.get("active", True))
    agents: list[Agent] = []
    for row in raw.get("agents") or []:
        agents.append(
            Agent(
                slug=row["slug"],
                ua_token=row["ua_token"],
                display_name=row["display_name"],
                operator=row["operator"],
                purpose=row["purpose"],
                documented_url=row.get("documented_url"),
                verified=bool(row.get("verified", default_verified)),
                active=bool(row.get("active", default_active)),
                notes=_notes(row.get("notes")),
                confidence=row.get("confidence"),
            )
        )
    return agents


def _notes(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None
