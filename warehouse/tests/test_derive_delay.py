from warehouse.derive.derive_robots import _crawl_delay_column


def test_crawl_delay_fits_numeric_8_2():
    assert _crawl_delay_column(10) == 10.0
    assert _crawl_delay_column(10.456) == 10.46
    assert _crawl_delay_column(None) is None
    assert _crawl_delay_column(-1) is None
    assert _crawl_delay_column(float("nan")) is None
    assert _crawl_delay_column(float("inf")) is None
    assert _crawl_delay_column(1_000_000) is None
    assert _crawl_delay_column(999_999.99) == 999_999.99
