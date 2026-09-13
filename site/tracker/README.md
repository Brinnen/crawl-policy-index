# Lab tracker (Astro)

Static site. It reads `src/data/lab.json` at build time, then refreshes numbers in the browser from `https://crawlpolicyindex.org/snapshot/lab.json`. It does not connect to Postgres.

The public site is an explorer, not a data dump. Do not add download routes for JSON or CSV.

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

To move the daily job from 1,000 to 100,000 sites:

```bash
cd /root/crawl-policy-index && git pull && bash scripts/setup-sites100k.sh
```

That is still a test list, not the web. Site-by-site explorer rows stay off the public snapshot at that size; totals and the by-bot table update.

Optional: put `GITHUB_TOKEN` in `/root/crawl-policy-index/.env` so the job also commits `lab.json` and Vercel rebuilds.
