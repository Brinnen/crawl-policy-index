from cpi_parser.html_country import country_from_html


def test_jsonld_address_country():
    html = b'<script type="application/ld+json">{"addressCountry":"SE"}</script>'
    assert country_from_html(html) == "SE"


def test_named_country():
    html = b'<script type="application/ld+json">{"addressCountry":"United States"}</script>'
    assert country_from_html(html) == "US"


def test_not_from_html_lang_or_locale():
    html = b'<html lang="sv-SE"><head><meta property="og:locale" content="sv_SE"></head>'
    assert country_from_html(html) == ""


def test_rejects_language_looking_code():
    html = b'<script type="application/ld+json">{"addressCountry":"EN"}</script>'
    assert country_from_html(html) == ""
