from __future__ import annotations

from sources.infra import is_infrastructure, load_suffixes

from build_panel import _from_tranco


def test_corporate_sites_are_not_infra():
    for host in (
        "google.com",
        "amazon.com",
        "cloudflare.com",
        "akamai.com",
        "microsoft.com",
        "apple.com",
        "facebook.com",
        "tiktok.com",
    ):
        assert not is_infrastructure(host), host


def test_cdn_apex_and_subdomain_are_infra():
    for host in (
        "cloudfront.net",
        "d111111abcdef8.cloudfront.net",
        "akamai.net",
        "e1234.akamaiedge.net",
        "gvt1.com",
        "ytimg.com",
        "root-servers.net",
        "azurefd.net",
        "tiktokcdn-eu.com",
        "b-cdn.net",
        "ax-msedge.net",
        "tm-azurefd.net",
        "namebrightdns.com",
    ):
        assert is_infrastructure(host), host


def test_denylist_has_no_single_label_suffixes():
    for suffix in load_suffixes():
        assert "." in suffix, suffix
        assert suffix == suffix.lower()


def test_from_tranco_drops_infra_and_keeps_n():
    ranked = [
        (1, "google.com"),
        (2, "cloudfront.net"),
        (3, "amazon.com"),
        (4, "akamai.net"),
        (5, "wikipedia.org"),
        (6, "gvt1.com"),
        (7, "bbc.com"),
    ]
    rows, skipped = _from_tranco(ranked, "2026-09-10", drop_infra=True, keep=3)
    assert skipped == 2
    assert [r["domain"] for r in rows] == ["google.com", "amazon.com", "wikipedia.org"]
    assert [r["tranco_rank"] for r in rows] == ["1", "3", "5"]


def test_keep_without_enough_sites_raises():
    ranked = [(1, "cloudfront.net"), (2, "akamai.net")]
    try:
        _from_tranco(ranked, "2026-09-10", drop_infra=True, keep=2)
    except RuntimeError as exc:
        assert "raise --tranco-top" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
