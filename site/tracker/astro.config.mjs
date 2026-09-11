import { defineConfig } from "astro/config";

export default defineConfig({
  output: "static",
  site: "https://crawlpolicyindex.org",
  redirects: {
    "/data/lab.json": "/data",
    "/data/gptbot-named.csv": "/data",
    "/data/gptbot-named-grouped.csv": "/data",
  },
});

