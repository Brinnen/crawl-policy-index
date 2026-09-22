from cctld import category_from_domain, country_from_domain


def test_sweden_and_uk():
    assert country_from_domain("svt.se") == "SE"
    assert country_from_domain("bbc.co.uk") == "GB"
    assert country_from_domain("amazon.com") == ""
    assert country_from_domain("nytimes.com") == ""


def test_gov_edu():
    assert category_from_domain("harvard.edu") == "edu"
    assert category_from_domain("irs.gov") == "gov"
    assert category_from_domain("svt.se", "news") == "news"
    assert category_from_domain("example.com") == "other"
