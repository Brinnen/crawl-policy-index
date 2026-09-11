# Lab tracker (Astro)

Static site. It reads `src/data/lab.json` at build time. It does not connect to the droplet.

The public site is an explorer, not a data dump. Do not add download routes for JSON or CSV.

## Vercel

1. Import the GitHub repo.
2. Set **Root Directory** to `site/tracker`.
3. Framework: Astro. Leave the production domain on the droplet until `/bot` should move.

Do not add environment variables. Postgres stays on the fetch host.

## Refresh numbers

On the droplet, after `bash scripts/warehouse-once.sh`:

```bash
python3 warehouse/export_lab.py
```

Commit `site/tracker/src/data/lab.json` so Vercel rebuilds from that snapshot.
