# Runbook

## Alerts

| Alert | Meaning | Recover |
|---|---|---|
| Fetch run not `complete: true` by 09:00 UTC | Invariant 1 at risk | Resume the binary; do not restart. Inspect the run manifest for the last recorded `(domain, resource)`. |
| `unexplained_failure_rate` > 0.5% or > 2× 7-day median | Network, DNS, or politeness misconfig | Check egress, TLS, and the global rate limit. 404s are explained and do not count. |
| Derive past 30 minutes / failed | Warehouse pipeline | Re-run load+derive. It is idempotent per `(blob, parse_version)`. |
| Detect-gate distribution shifted > 3pp day over day | Parser-corruption canary | Stop publication. Diff a sample of newly `robots` vs `not_robots_html` blobs. Do not refresh rollups until classified. |
| `blobs_written` > 5% of panel | Real event or hashing bug | Compare a handful of "new" blobs to yesterday's. If they are identical, stop and fix hashing. |
| Site build failed | WP5 | The site reads only materialised views. Check the export job, not the fetcher. |

## Honouring exclusion

Requests to be removed from the panel are honoured within 24 hours. Record domain, requester, time, and the panel version that will omit them. Do not delete historical blobs; stop fetching and exclude from new panel versions.

## Wayback

1 req/s, single worker. Do not raise this. On 429/503 back off from 60 s to 30 min. Resume from the per-domain checkpoint; never restart the backlog.
