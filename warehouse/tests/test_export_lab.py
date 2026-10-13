from pathlib import Path

from export_lab import write_digest, write_lookup

EXPORT = Path(__file__).resolve().parents[1] / "export_lab.py"


def test_published_export_uses_verified_agents_only():
    src = EXPORT.read_text(encoding="utf-8")
    assert "AND a.verified" in src
    assert '"lab": False' in src
    assert '"verified_agents": True' in src
    assert "LOOKUP_NAMED_SQL" in src
    assert "LOOKUP_BLANKET_SQL" in src
    assert "has_wildcard_group" in src
    assert "SITES_SQL" in src
    assert "dl.country" in src
    assert "write_digest" in src
    assert "digest.json" in src
    assert "PREVIEW_HOSTS_SQL" in src
    assert "preview.json" in src
    assert "showcase_hosts" in src
    assert "news_labels" in src
    assert "site_category" in src
    assert "labeled_vertical" in src


def test_write_digest_picks_showcase_changes(tmp_path: Path):
    path = tmp_path / "digest.json"
    write_digest(
        path,
        [
            ["2026-10-13", "nytimes.com", "openai-gptbot", "blocked", "ALLOWED", "BLOCKED"],
            ["2026-10-13", "obscure.test", "openai-gptbot", "blocked", "", "BLOCKED"],
            ["2026-10-13", "svt.se", "anthropic-claudebot", "unblocked", "BLOCKED", "ALLOWED"],
        ],
        ["nytimes.com", "svt.se"],
        "2026-10-13T08:00:00Z",
    )
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert payload["as_of"] == "2026-10-13"
    assert payload["blocked"] == 2
    assert payload["unblocked"] == 1
    assert payload["items"][0]["domain"] == "nytimes.com"


def test_write_lookup_is_compact(tmp_path: Path):
    path = tmp_path / "lookup.json"
    write_lookup(path, [["nytimes.com", "openai-gptbot", "BLOCKED"]], [["example.com", "BLOCKED"]])
    text = path.read_text(encoding="utf-8")
    assert "\n  " not in text
    assert '"named":[["nytimes.com","openai-gptbot","BLOCKED"]]' in text


def test_explorer_loads_lookup_url():
    src = (
        Path(__file__).resolve().parents[2]
        / "site"
        / "tracker"
        / "src"
        / "components"
        / "Explorer.astro"
    ).read_text(encoding="utf-8")
    assert 'LOOKUP_URL = "/snapshot/lookup.json"' in src
    assert "Type a website" in src
    assert "domain-language" in src
    assert "domain-country" in src
    assert "domain-vertical" in src
