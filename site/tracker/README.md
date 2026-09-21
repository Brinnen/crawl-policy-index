# Public tracker (Astro)

Static site. It reads `src/data/lab.json` at build time, then refreshes numbers in the browser from `/snapshot/lab.json` (proxied to the droplet). It does not connect to Postgres.

The public site is an explorer, not a data dump. Do not add download routes for JSON or CSV.

Published tables include only `verified AND active` agents. Unverified tokens are stored in the warehouse and stay out of the site.

## Vercel

1. Import the GitHub repo.
2. Set **Root Directory** to `site/tracker`.
3. Framework: Astro. Leave the production domain on the droplet until `/bot` should move.

Do not add environment variables. Postgres stays on the fetch host.

## Refresh numbers

On the droplet, once:

```bash
cd /root/crawl-policy-index && git pull && bash scripts/setup-daily.sh
```

That installs a 02:00 UTC job: fetch → warehouse → export → publish the snapshot. Overview and Explore update from that URL. No manual export or commit.

The daily job uses the 100,000-site panel (`sites100k`). That is a pinned Tranco list, not the web. Totals live in `lab.json`. Website search loads compact `lookup.json` when someone types a name.

Optional: put `GITHUB_TOKEN` in `/root/crawl-policy-index/.env` so the job also commits `lab.json` and Vercel rebuilds.
