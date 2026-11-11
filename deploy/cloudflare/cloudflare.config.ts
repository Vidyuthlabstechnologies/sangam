import { defineConfig } from "cf/config";

// Static-assets-only Worker: no code runs, Cloudflare serves the files in ../../site.
// Rebuild those files first with `python -I scripts/build_site.py`, then `npm run deploy`.
export default defineConfig({
  worker: {
    name: "sangamitra-site",
    compatibilityDate: "2026-11-04",
    observability: { enabled: true },
  },
});
