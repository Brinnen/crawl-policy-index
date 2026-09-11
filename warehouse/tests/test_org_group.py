from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "load"))
from org_group import group_key


def test_amazon_cctlds_collapse():
    assert group_key("amazon.com") == "amazon.com"
    assert group_key("amazon.de") == "amazon.com"
    assert group_key("amazon.co.uk") == "amazon.com"
    assert group_key("amazon.com.au") == "amazon.com"


def test_other_sites_stay_themselves():
    assert group_key("bbc.com") == "bbc.com"
    assert group_key("alibaba.com") == "alibaba.com"
