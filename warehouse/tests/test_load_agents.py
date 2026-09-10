from __future__ import annotations

from pathlib import Path

from load_agents import rows_from_yaml

ROOT = Path(__file__).resolve().parents[2]


def test_registry_loads_and_is_unverified():
    rows = rows_from_yaml(ROOT / "registry" / "agents.yml")
    assert len(rows) >= 30
    assert all(r["verified"] is False for r in rows)
    slugs = [r["slug"] for r in rows]
    assert len(slugs) == len(set(slugs))
    tokens = [r["ua_token"].casefold() for r in rows]
    assert len(tokens) == len(set(tokens))
    assert any(r["purpose"] == "opt_out_token" and r["ua_token"] == "Google-Extended" for r in rows)
    assert any(r["slug"] == "openai-gptbot" for r in rows)
