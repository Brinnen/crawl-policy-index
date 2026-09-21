from labels import apply_labels


def test_news_label_merges_and_adds():
    rows = [
        {
            "domain": "svt.se",
            "strata": "head",
            "tranco_rank": "10",
            "country": "",
            "vertical": "other",
            "psl_version": "dev-unpinned",
            "added_on": "2026-09-21",
        },
        {
            "domain": "example.com",
            "strata": "head",
            "tranco_rank": "1",
            "country": "",
            "vertical": "other",
            "psl_version": "dev-unpinned",
            "added_on": "2026-09-21",
        },
    ]
    out = apply_labels(rows, {"news": {"svt.se": "SE", "dn.se": "SE"}})
    by_domain = {r["domain"]: r for r in out}
    assert by_domain["svt.se"]["vertical"] == "news"
    assert by_domain["svt.se"]["country"] == "SE"
    assert by_domain["svt.se"]["strata"] == "head|news"
    assert by_domain["dn.se"]["strata"] == "news"
    assert by_domain["dn.se"]["country"] == "SE"
    assert by_domain["example.com"]["vertical"] == "other"
    assert by_domain["example.com"]["country"] == ""


def test_sample_still_deterministic(tmp_path):
    from build_panel import main

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert main(["--version", "dev", "--sample", "20", "--seed", "7", "--out-dir", str(a)]) == 0
    assert main(["--version", "dev", "--sample", "20", "--seed", "7", "--out-dir", str(b)]) == 0
    assert (a / "panel-dev.csv").read_bytes() == (b / "panel-dev.csv").read_bytes()
