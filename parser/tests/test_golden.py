from __future__ import annotations

import json
from pathlib import Path

import pytest

from cpi_parser.detect import classify
from cpi_parser.registry import load_agents
from cpi_parser.robots import parse
from cpi_parser.state import derive_agent, derive_wildcard

SKIP_NAMES = {"README", ".gitkeep"}


def _cases(corpus_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in corpus_dir.iterdir()
        if p.suffix == ".txt" and p.stem not in SKIP_NAMES
    )


def test_corpus_not_empty(corpus_dir: Path):
    assert len(_cases(corpus_dir)) >= 20


def pytest_generate_tests(metafunc):
    if "case_txt" in metafunc.fixturenames:
        corpus = Path(__file__).parent / "corpus"
        cases = _cases(corpus)
        metafunc.parametrize("case_txt", cases, ids=[p.stem for p in cases])


def test_golden_case(case_txt: Path, registry_path: Path):
    expected_path = case_txt.with_suffix(".expected.json")
    assert expected_path.exists(), f"missing {expected_path.name}"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    body = case_txt.read_bytes()
    content_type = expected.get("content_type")
    verdict = classify(body, content_type)
    assert str(verdict) == expected["detect"]

    if expected["detect"] != "robots":
        return

    parsed = parse(body)
    if "truncated_for_parse" in expected:
        assert parsed.truncated_for_parse is expected["truncated_for_parse"]
    if "sitemaps" in expected:
        assert parsed.sitemaps == expected["sitemaps"]
    if "wildcard" in expected:
        state, has_wc = derive_wildcard(parsed)
        assert str(state) == expected["wildcard"]["state"]
        assert has_wc is expected["wildcard"]["has_wildcard_group"]
    if "agents" in expected:
        agents = {a.slug: a for a in load_agents(registry_path)}
        for slug, want in expected["agents"].items():
            policy = derive_agent(parsed, agents[slug].ua_token)
            assert str(policy.state) == want["state"], slug
            assert str(policy.rule_source) == want["rule_source"], slug
