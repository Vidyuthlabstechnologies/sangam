import { defineWranglerConfig } from "wrangler/experimental-config";

// cf delegates static-site builds to Wrangler; this only tells it where the files are.
// Default html handling serves /legal/privacy from legal/privacy.html.
export default defineWranglerConfig({
  assetsDirectory: "../../site",
});
