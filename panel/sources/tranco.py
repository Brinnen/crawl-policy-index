"""Tranco top-1M source. Pin a list ID; never fetch 'latest'."""

from __future__ import annotations


def fetch_tranco(list_id: str) -> list[tuple[int, str]]:
    raise NotImplementedError(
        f"Pin Tranco list {list_id} and download its CSV. Never use 'latest'."
    )
