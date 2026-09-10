"""Differential harness vs protego.

Every disagreement must become a ticket (bug or documented deviation).
Skipped until protego is installed; the acceptance bar is zero unexplained
disagreements on a 10k sample.
"""

from __future__ import annotations

import pytest

pytest.importorskip("protego")


def test_differential_harness_placeholder():
    pytest.skip("10k-sample differential run is WP2 acceptance, not a unit test")
