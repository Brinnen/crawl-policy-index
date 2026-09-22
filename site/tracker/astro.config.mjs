import clerk from "@clerk/astro";
import vercel from "@astrojs/vercel";
import { defineConfig } from "astro/config";

export default defineConfig({
  integrations: [
    clerk({
      signInUrl: "/sign-in",
      signUpUrl: "/sign-up",
      signInFallbackRedirectUrl: "/app",
      signUpFallbackRedirectUrl: "/pricing",
      enableEnvSchema: false,
    }),
  ],
  adapter: vercel(),
  output: "server",
  site: "https://crawlpolicyindex.org",
  redirects: {
    "/data/lab.json": "/data",
    "/data/gptbot-named.csv": "/data",
    "/data/gptbot-named-grouped.csv": "/data",
  },
});
