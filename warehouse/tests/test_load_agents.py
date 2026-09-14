from __future__ import annotations

from pathlib import Path

from load_agents import rows_from_yaml

ROOT = Path(__file__).resolve().parents[2]


def test_registry_loads_unique_and_mixed_verified():
    rows = rows_from_yaml(ROOT / "registry" / "agents.yml")
    by_slug = {r["slug"]: r for r in rows}
    assert len(rows) >= 30
    slugs = [r["slug"] for r in rows]
    assert len(slugs) == len(set(slugs))
    tokens = [r["ua_token"].casefold() for r in rows]
    assert len(tokens) == len(set(tokens))
    assert any(r["purpose"] == "opt_out_token" and r["ua_token"] == "Google-Extended" for r in rows)
    assert by_slug["openai-gptbot"]["verified"] is True
    assert by_slug["google-googlebot"]["verified"] is True
    assert by_slug["anthropic-claudebot"]["verified"] is True
    # Operator page does not publish these tokens (or the page was unreachable).
    assert by_slug["meta-facebookbot"]["verified"] is False
    assert by_slug["anthropic-ai-legacy"]["verified"] is False
    assert by_slug["cohere-ai"]["verified"] is False
    assert by_slug["amazon-amazonbot"]["verified"] is False
