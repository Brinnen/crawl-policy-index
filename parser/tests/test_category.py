from cpi_parser.category import category_from_html


def test_news_from_jsonld():
    html = b'<script type="application/ld+json">{"@type":"NewsMediaOrganization"}</script>'
    assert category_from_html(html) == "news"


def test_other_when_empty():
    assert category_from_html(b"<html><body>hello</body></html>") == "other"


def test_product_schema_is_not_a_shop():
    html = b'<script type="application/ld+json">{"@type":"Product","name":"Chair"}</script>'
    assert category_from_html(html) == "other"


def test_shopify_is_a_shop():
    html = b'<script src="https://cdn.shopify.com/s/files/1/theme.js"></script>'
    assert category_from_html(html) == "ecommerce"


def test_hotel_schema_is_travel():
    html = b'<script type="application/ld+json">{"@type":"LodgingBusiness"}</script>'
    assert category_from_html(html) == "travel"
