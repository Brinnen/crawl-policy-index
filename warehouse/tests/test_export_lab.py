from pathlib import Path

EXPORT = Path(__file__).resolve().parents[1] / "export_lab.py"


def test_published_export_uses_verified_agents_only():
    src = EXPORT.read_text(encoding="utf-8")
    assert "AND a.verified" in src
    assert '"lab": False' in src
    assert '"verified_agents": True' in src
