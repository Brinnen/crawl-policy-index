from __future__ import annotations

import hashlib
from pathlib import Path

from build_panel import main


def test_dev_sample_is_deterministic(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert main(["--version", "dev", "--sample", "50", "--seed", "42", "--out-dir", str(a)]) == 0
    assert main(["--version", "dev", "--sample", "50", "--seed", "42", "--out-dir", str(b)]) == 0
    fa = (a / "panel-dev.csv").read_bytes()
    fb = (b / "panel-dev.csv").read_bytes()
    assert fa == fb
    assert hashlib.sha256(fa).hexdigest() == hashlib.sha256(fb).hexdigest()


def test_sample_size_and_labels(tmp_path: Path):
    assert main(["--version", "dev", "--sample", "20", "--seed", "1", "--out-dir", str(tmp_path)]) == 0
    lines = (tmp_path / "panel-dev.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 21
    assert lines[0].startswith("domain,")
    domains = [ln.split(",")[0] for ln in lines[1:]]
    assert len(set(domains)) == 20
    assert all(d.endswith(".example") for d in domains)
