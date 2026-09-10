# ADR 0001 — Store policy as SCD-2 intervals, explicit rules only

**Status:** accepted
**Date:** 2026-09-08

## Context

A daily snapshot of `(domain, agent)` state for ~1.08M domains and ~60 agents is ~23 billion rows per year.

## Decision

1. Store validity intervals, writing a row only when state changes (`valid_to IS NULL` means current).
2. Materialise `policy_interval` only for agents a file names explicitly.
3. Store one `wildcard_interval` per domain per `*`-group change.
4. Resolve point-in-time state exclusively through `effective_policy()`.

## Consequences

Total stored policy rows land in the low millions. Re-parse is triggered only by a `content_sha256` change. Every published figure must read a named view over `effective_policy`, never the base tables.
