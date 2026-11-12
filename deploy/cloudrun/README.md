# Backend on Cloud Run + Neon

Runs the FastAPI backend in `backend/` on Google Cloud Run (Mumbai, `asia-south1`) with a free Neon Postgres. Redis is not needed (rate limits stay in-process); Temporal, RabbitMQ, MinIO and Qdrant are not touched at startup.

## Before you run the script (two browser steps)

1. **Billing** is already linked to `vidyuthlabs-514315`, the hosting project (the Firebase project `sangamitra-ai` stays as it is: it holds sign-in, and the backend only uses its id to verify tokens). Run `gcloud auth list` first and make sure the active account is the one that owns `vidyuthlabs-514315`.
   With `--min-instances 0` and low traffic the usage normally stays inside the free tier or the trial credit.
2. **Create a Neon project.** `neon init --org-id <org> --region-id aws-ap-southeast-1 --project-name sangam --no-config` (Singapore is nearest to Mumbai) writes `DATABASE_URL_UNPOOLED` to the git-ignored `.env.local`, and the script offers to use it. Otherwise open the project at https://console.neon.tech, go to **Connect**, turn **Connection pooling off**, copy the string, and paste it into the script's hidden prompt, never into chat or a file.

## Run it

From the repo root, in your own terminal (PowerShell 7):

```powershell
pwsh -File .\deploy\cloudrun\deploy.ps1 -DryRun   # lists every step, creates nothing
pwsh -File .\deploy\cloudrun\deploy.ps1
pwsh -File .\deploy\cloudrun\deploy.ps1 -Launch   # at the public launch: sandbox purchases stop crediting
pwsh -File .\deploy\cloudrun\deploy.ps1 -SamvaadOrgId <org> -SamvaadWorkspaceId <workspace>   # once, for Voice Agents
```

The script enables the APIs, stores three secrets in Secret Manager (`sangam-database-url`, `sangam-jwt-secret`, `sangam-revenuecat-webhook-auth`), asks for `SARVAM_API_KEY` and `SARVAM_SAMVAAD_API_KEY` (the separate Voice Agents key) if they are not stored yet (Razorpay is not used; the app sells through Google Play Billing), builds `backend/Dockerfile` with Cloud Build, deploys `sangam-backend`, checks `/health`, and sets the GitHub variable `API_BASE_URL`.

The Neon string is rewritten for the app: `postgresql+asyncpg://` scheme, `sslmode` and `channel_binding` removed, `ssl=require` added. The pooled host (`-pooler`) is refused because asyncpg prepared statements break behind PgBouncer.

## After the first deploy

- **RevenueCat webhook:** URL `<API_BASE_URL>/billing/revenuecat/webhook`, Authorization header value is the secret the script put on your clipboard (new secrets only). Clear the clipboard afterwards. To read it again later, use the Secret Manager page in the Cloud console.
- **Provider keys:** without `SARVAM_API_KEY` voice agents answer with canned fixture replies, and the startup log says so. Skipped it? Run the script again; it asks only while the key is missing. Re-running uses `--update-env-vars` and `--update-secrets`, which change only the variables the script names. The service account `sangam-backend-run` can read only the secrets the script stores.
- **Voice Agents (Samvaad):** the GitHub secret `SARVAM_SAMVAAD_API_KEY` does not reach Cloud Run by itself (this script runs on your machine, not in Actions). Paste the same key at the script's prompt; it goes to Secret Manager as `sangam-sarvam-samvaad-api-key`. Pass `-SamvaadOrgId` and `-SamvaadWorkspaceId` once (from the Samvaad dashboard URL or Settings); they stay on the service. Then give a business an agent with `PUT /voice-agents/bindings` as an admin. Outbound-call results come back to `<API_BASE_URL>/voice-agents/webhooks/outbound/<per-call secret>`, built automatically from the request URL, so nothing needs configuring in Samvaad. The `Samvaad key check` workflow (Actions tab) confirms the GitHub copy of the key works.
- **Legal postal address:** set `LEGAL_POSTAL_ADDRESS` once you have it (it is also baked into `site/`, see `docs/PLAY_CONSOLE.md`).
- **Logs:** `gcloud run services logs read sangam-backend --region asia-south1 --project vidyuthlabs-514315`.

## Notes

- The org policy `iam.disableServiceAccountKeyCreation` is enforced on `vidyuthlabs-514315`, so no service-account keys can be made there. The deploy does not need any.
- `--allow-unauthenticated` is intentional: the API verifies Firebase ID tokens itself, and the webhook checks its own Authorization secret.
- `backend/.dockerignore` and `backend/.gcloudignore` keep `.env`, local databases and keys out of the upload.
- IAM: `sangam-backend-run` gets `secretAccessor` on the three secrets plus the provider keys it stored, nothing else. The default compute account gets `roles/run.builder` so Cloud Build can build from source. If the build fails on a permission error, the error names the missing role (not verified until the first real run).
- Sandbox purchases: without `-Launch`, `REVENUECAT_ACCEPT_SANDBOX=true` credits license-tester purchases (right for closed testing). Run with `-Launch` for the public release.
- Email accounts must verify their address (`FIREBASE_REQUIRE_VERIFIED_EMAIL=true`); the app sends the link and asks the user to sign in after opening it.
- Client IP: `CLIENT_IP_FORWARDED_HOP=1` makes rate limits use the address Cloud Run appends to `X-Forwarded-For`, so a forged header cannot dodge them. Limits are still per instance (up to 3), so the effective ceiling is up to 3x the configured rate; set `REDIS_URL` to share one counter.
- A new secret version becomes `:latest` before the deploy finishes, so a failed deploy leaves the old revision reading the new database URL on its next cold start. Re-run the script after fixing the failure.
