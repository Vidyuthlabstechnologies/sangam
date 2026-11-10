# Backend on Cloud Run + Neon

Runs the FastAPI backend in `backend/` on Google Cloud Run (Mumbai, `asia-south1`) with a free Neon Postgres. Redis is not needed (rate limits stay in-process); Temporal, RabbitMQ, MinIO and Qdrant are not touched at startup.

## Before you run the script (two browser steps)

1. **Link billing to `sangamitra-ai`.** Cloud Run, Cloud Build and Secret Manager need a billing account on the project. Do it at
   https://console.cloud.google.com/billing/linkedaccount?project=sangamitra-ai
   With `--min-instances 0` and low traffic the usage normally stays inside the free tier, but billing must still be linked.
2. **Create a Neon project** at https://console.neon.tech. Pick the closest region (Singapore is nearest to Mumbai). On the project dashboard open **Connect**, turn **Connection pooling off**, and copy the connection string. It is a secret: you will paste it into a hidden prompt, never into chat or a file.

## Run it

From the repo root, in your own terminal (PowerShell 7):

```powershell
pwsh -File .\deploy\cloudrun\deploy.ps1 -DryRun   # lists every step, creates nothing
pwsh -File .\deploy\cloudrun\deploy.ps1
```

The script enables the APIs, stores three secrets in Secret Manager (`sangam-database-url`, `sangam-jwt-secret`, `sangam-revenuecat-webhook-auth`), builds `backend/Dockerfile` with Cloud Build, deploys `sangam-backend`, checks `/health`, and sets the GitHub variable `API_BASE_URL`.

The Neon string is rewritten for the app: `postgresql+asyncpg://` scheme, `sslmode` and `channel_binding` removed, `ssl=require` added. The pooled host (`-pooler`) is refused because asyncpg prepared statements break behind PgBouncer.

## After the first deploy

- **RevenueCat webhook:** URL `<API_BASE_URL>/billing/revenuecat/webhook`, Authorization header value is the secret the script put on your clipboard (new secrets only). Clear the clipboard afterwards. To read it again later, use the Secret Manager page in the Cloud console.
- **Optional keys** (the API returns canned responses without them): `SARVAM_API_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`. Add each as a Secret Manager secret and attach it with `gcloud run services update sangam-backend --update-secrets NAME=secret:latest`. Re-running `deploy.ps1` uses `--update-env-vars` and `--update-secrets`, which change only the variables the script names and keep anything you added by hand. The service runs as its own account, `sangam-backend-run`, which can read only the three secrets the script creates, so grant it `roles/secretmanager.secretAccessor` on any secret you add.
- **Legal postal address:** set `LEGAL_POSTAL_ADDRESS` once you have it (it is also baked into `site/`, see `docs/PLAY_CONSOLE.md`).
- **Logs:** `gcloud run services logs read sangam-backend --region asia-south1 --project sangamitra-ai`.

## Notes

- `--allow-unauthenticated` is intentional: the API verifies Firebase ID tokens itself, and the webhook checks its own Authorization secret.
- `backend/.dockerignore` and `backend/.gcloudignore` keep `.env`, local databases and keys out of the upload.
- IAM: `sangam-backend-run` gets `secretAccessor` on the three secrets only. The default compute account gets `roles/run.builder` so Cloud Build can build from source. If the build fails on a permission error, the error names the missing role (not verified until the first real run).
- Revisit at launch: `REVENUECAT_ACCEPT_SANDBOX=true` credits license-tester purchases (right for closed testing, set it to false for production). `FORWARDED_ALLOW_IPS=*` is needed because Cloud Run's proxy addresses are not fixed, but a client that forges `X-Forwarded-For` can dodge per-IP rate limits. A real fix is to read the last forwarded address in the app.
- A new secret version becomes `:latest` before the deploy finishes, so a failed deploy leaves the old revision reading the new database URL on its next cold start. Re-run the script after fixing the failure.
