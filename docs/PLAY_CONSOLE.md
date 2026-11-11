# Google Play Console: ready-to-paste content for Sangam

This file holds the answers and text to enter in Play Console. Every claim was
taken from the repo (`android/`, `backend/`). Where the repo does not decide
something, the line says **TO CONFIRM**. Do not put real reviewer credentials,
keystore passwords or API keys in this file.

If a data flow changes, change it here, in
`backend/app/core/legal_content.py` and in the Play Data safety form together.

- Package name (applicationId): `com.mldynamic.sangamitra` (`com.sangam.app` is taken on Google Play; the Kotlin namespace stays `com.sangam.app`)
- Target SDK: 35 (`android/app/build.gradle.kts`)
- Firebase project: `sangamitra-ai`
- Legal pages (live on Cloudflare Workers; move to a custom domain later and update the three GitHub variables):
  - Privacy policy: `https://sangamitra-site.cbvarshini1.workers.dev/legal/privacy`
  - Terms of use: `https://sangamitra-site.cbvarshini1.workers.dev/legal/terms`
  - Account deletion: `https://sangamitra-site.cbvarshini1.workers.dev/legal/delete-account`

## 1. Store listing

| Field | Value |
|---|---|
| App name (max 30) | `Sangamitra AI` (13 characters). **TO CONFIRM:** the launcher label in the manifest is `Sangam`; decide whether to match it. |
| Default language | English (India) |
| App or game | App |
| Free or paid | Free (plans and top-ups are in-app purchases) |
| Category | Business |
| Tags (pick up to 5 that Play offers) | Business, Productivity, Communication, Finance, Artificial intelligence (use the nearest tags Play lists) |
| Contact email | `info@mldynamic.com` (**TO CONFIRM:** the mailbox must exist and be monitored) |
| Contact phone | `<PHONE>` (optional) |
| Website | `<WEBSITE_URL>` (optional) |
| Privacy policy URL | `https://sangamitra-site.cbvarshini1.workers.dev/legal/privacy` |

### Short description (max 80, this one is 72)

```
AI voice assistant that answers your business calls in Indian languages.
```

### Full description (max 4000, this one is 1430)

```
Sangamitra AI gives your business a voice assistant that picks up the phone when you cannot.

Set it up by speaking or typing what your business does. The assistant answers incoming calls, tells callers it is an AI, answers common questions, takes callback requests and passes the details to you.

WHAT YOU CAN DO
- Get an AI assistant that answers calls for your business, with Hindi and Tamil among the supported Indian languages
- Record a short voice instruction and have it turned into a workflow
- Read call summaries and callback requests in the Call Inbox
- Keep your vendors and their documents in one place
- Approve actions the assistant wants to take before they happen
- Get notifications for calls, payments and service alerts
- Connect your everyday tools from inside the app

PLANS AND WALLET
Pick a plan from inside the app. Plans and top-ups are bought through Google Play, and call usage is deducted from your wallet at the rate shown in the app before you pay. GST is shown before you confirm.

YOUR DATA
Sign in with Google or with your email and password. You can delete your account and its data from inside the app at any time. The app shows no ads and does not sell your personal data. Read the full policy at the link on this page.

Made for small and medium businesses in India. The assistant can make mistakes, so check call summaries before you rely on them for legal, medical or financial decisions.
```

**TO CONFIRM before publishing:** the list of supported languages (the app text
names Hindi and Tamil only), and that "Approve actions" and "Connect your
everyday tools" match what a reviewer will see in the build you upload. Do not
add performance numbers (such as pickup rates) unless you can back them up.

### Graphics

| Asset | Spec | File |
|---|---|---|
| App icon | 512 x 512 px, PNG, 32-bit, max 1 MB | `brand/play-icon-512.png` |
| Feature graphic | 1024 x 500 px, JPG or 24-bit PNG | `brand/play-feature-1024x500.png` |
| Phone screenshots | at least 2, up to 8; JPG or PNG; 16:9 or 9:16; each side 320 to 3840 px | **you take these** from a real device (see section 12) |

The assistant generates the icon and the feature graphic into `brand/`. They
are not in the repo until that step has run, so check the files exist before
uploading. The screenshots must come from the installed release candidate.

## 2. App content declarations

| Form | Answer |
|---|---|
| Privacy policy | `https://sangamitra-site.cbvarshini1.workers.dev/legal/privacy` |
| Ads | **No**, the app contains no ads |
| App access | Some functionality is restricted (sign-in needed). See section 3. |
| Target audience and content | **18 and over** only. Not designed for children. |
| News app | No |
| Government app | No |
| COVID-19 contact tracing or status | No |
| Data safety | Section 4 |
| Advertising ID | **No**, the app does not use it. The manifest removes `com.google.android.gms.permission.AD_ID`. |
| Health apps / health features | No |
| Financial features | Section 6 |
| Account deletion | Section 7 |

### Content rating questionnaire

Category: select **Utility, Productivity, Communication, or Other non-game**.
Answers:

| Question | Answer |
|---|---|
| Violence, blood, gore | No |
| Sexual content or nudity | No |
| Profanity or crude humor | No |
| Controlled substances (drugs, alcohol, tobacco) | No |
| Gambling or simulated gambling | No |
| User-generated content shared with other users | No (call summaries are shown only to the business owner) |
| Users can interact or exchange content with each other | No |
| Shares the user's location with others | No |
| Allows purchases of digital goods | Yes (subscriptions, a one-time pilot pass, top-ups) |
| Unrestricted internet access or web browsing | No |

**TO CONFIRM:** re-answer honestly from the questionnaire as Play words it on
the day. Expect a low rating such as "Everyone", but the rating is assigned by
Play from your answers.

## 3. App access (reviewer sign-in)

Play reviewers must be able to open every part of the app. The app signs in
with Google or email and password through Firebase.

Paste into the App access form, replacing the placeholders. Create a dedicated
test account for this and never reuse a real person's account.

```
All functionality requires signing in.

Sign-in method: email and password on the sign-in screen.
Email: <REVIEWER_EMAIL>
Password: <REVIEWER_PASSWORD>

After sign-in: the Home screen opens. Tap "Voice Agent" in the bottom bar to
set up the assistant. Plans and top-ups are in the Voice Agent screen.
Purchases are made with Google Play test cards on a license-tester account.

Microphone permission is requested only when you tap the record button on the
voice instruction screen.
```

- `<REVIEWER_EMAIL>` and `<REVIEWER_PASSWORD>`: **supplied by you, never written
  in this repo or in chat.** Create the account in the Firebase console
  (Authentication, Users) for project `sangamitra-ai`, or sign up in the app.
- If the account is new, the app opens the setup wizard first. **TO CONFIRM**
  the exact first-run flow on a device.
- The test account needs wallet credit or a license-tester purchase so the
  reviewer can exercise paid features. Keep `REVENUECAT_ACCEPT_SANDBOX=true`
  until review ends (section 9).
- The Home screen no longer shows invented call counts. Check it on a device
  before taking screenshots, because Play reviewers read it as real data.

## 4. Data safety form

Answer the top-level questions:

| Question | Answer |
|---|---|
| Does the app collect or share any of the required user data types? | Yes |
| Is all of the user data collected by the app encrypted in transit? | Yes (HTTPS only: `usesCleartextTraffic="false"` and a system-trust network security config) |
| Do you provide a way for users to request that their data is deleted? | Yes (in-app, and `https://sangamitra-site.cbvarshini1.workers.dev/legal/delete-account`) |
| Data sold | **No data is sold** |
| Ads | No ads, no advertising ID |

Service providers that process data only on our behalf (Firebase, Sarvam AI,
RevenueCat, Razorpay) are, under Google's definitions, **not "sharing"**.
**TO CONFIRM** this reading with whoever owns compliance; if you decide they
count as sharing, change the "Shared" column to Yes for those rows.

"Optional" means the user can use the app without providing it.

| Data type (Play category) | What it is here | Collected | Shared | Optional | Purpose | Processed ephemerally | Deletable |
|---|---|---|---|---|---|---|---|
| Personal info: Email address | Firebase sign-in email; stored in the backend actor record and a Firestore `users/{uid}` document | Yes | No | No | App functionality, Account management | No | Yes |
| Personal info: Name | Display name from Google or entered at sign-up; stored in the same records | Yes | No | Yes | App functionality, Account management | No | Yes |
| Personal info: User IDs | Firebase uid, backend actor id, auth provider, last-login time | Yes | No | No | App functionality, Account management, Fraud prevention, security | No | Yes |
| Personal info: Phone number | Phone numbers of callers in callback requests and call records, and the number assigned to the business. **TO CONFIRM** against what the call records store. | Yes | No | No | App functionality | No | Yes (kept ledger rows are detached from the business name) |
| Audio: Voice or sound recordings | Only while the user records a voice instruction; the file is saved in the app cache and sent to the backend for speech-to-text | Yes | No | Yes (the feature is optional) | App functionality | **TO CONFIRM** whether the backend keeps the audio or only the transcript | Yes |
| App activity: App interactions | **TO CONFIRM.** No analytics SDK was found in the repo. Tick this only if call summaries, workflow runs or similar usage records count as "app interactions" for you; the safe answer is to include them. | Yes (workflow and call records) | No | No | App functionality | No | Yes |
| Financial info: Purchase history | Plan, amount and Google Play order id, held in the wallet ledger | Yes | No | No | App functionality, Account management | No | Partly. Ledger rows are kept at least 6 years because Indian GST law requires it; they are detached from the business name and GSTIN. |
| Device or other IDs | Firebase Cloud Messaging token, used for push notifications | Yes | No | Yes (user can deny the notification permission) | App functionality | No | Yes |

Not collected: precise or approximate location, contacts, photos and videos,
files and docs from the device, calendar, SMS, call logs, health data,
web browsing history, advertising ID.

Security practices block:

- Data is encrypted in transit: **Yes**
- Users can request data deletion: **Yes**
- Committed to the Play Families Policy: **No** (not a children's app)
- Independent security review: **No** (unless you commission one)

## 5. Permission declarations

The app's own manifest requests only these: `INTERNET`, `BILLING`,
`RECORD_AUDIO`, `POST_NOTIFICATIONS`. Libraries merge in
`ACCESS_NETWORK_STATE`, `WAKE_LOCK`, `RECEIVE_BOOT_COMPLETED` and
`FOREGROUND_SERVICE` (the app's own manifest does not declare them, so they come
from bundled libraries; which library is **TO CONFIRM** from the merged
manifest). The manifest removes `AD_ID`, `READ_BASIC_PHONE_STATE` and `NFC`.
**TO CONFIRM** by reading the merged release manifest of the build you upload.

### RECORD_AUDIO

Play shows this to users as a sensitive permission. Justification text:

```
The app records audio only while the user taps the record button on the voice
instruction screen, to turn a spoken instruction into text and a workflow. The
permission prompt appears the first time the user taps that button. Nothing is
recorded in the background and nothing is recorded when the app is closed.
```

If Play asks for a video of the permission in use, record the voice instruction
screen on a device: tap record, speak, stop, see the resulting workflow.

### POST_NOTIFICATIONS

```
The app sends notifications about calls the assistant handled, payments and
service alerts through Firebase Cloud Messaging. The permission is requested at
runtime on Android 13 and above and the app works without it.
```

**TO CONFIRM:** the repo has no code that asks for the permission at a chosen
moment; check on a device that the prompt appears and that denying it does not
break the app.

### Foreground service and other merged permissions

The app's code starts no foreground service of its own (no `startForeground`
call, no `foregroundServiceType` in the manifest). If Play's pre-launch report
or the merged manifest shows a `FOREGROUND_SERVICE_*` type declaration is
required, answer it from the merged manifest, not from this file. `WAKE_LOCK`
and `RECEIVE_BOOT_COMPLETED` come from libraries and need no declaration form.

## 6. Financial features declaration

Select **"My app doesn't provide any financial features"** only if that is true
for you. Check the options as Play words them:

| Feature | Answer |
|---|---|
| Personal loans, credit, lending | No |
| Banking, money transfer, payments between people | No |
| Investment, trading, crypto | No |
| In-app wallet | **TO CONFIRM.** The wallet holds prepaid call credit with no cash value and is not transferable, and it is topped up with Google Play purchases. Read Play's wallet wording and declare it if it applies. |

The app sells digital goods only, through Google Play Billing. The Razorpay SDK
is bundled for builds that are **not** distributed through Google Play. **TO
CONFIRM** that the Play build never shows a card or UPI payment path, because
Play requires Google Play Billing for in-app digital goods.

## 7. Account deletion

| Field | Value |
|---|---|
| Account deletion URL | `https://sangamitra-site.cbvarshini1.workers.dev/legal/delete-account` |
| Delete data without deleting the account | Not offered |

Steps a user takes inside the app (read from the code):

1. Sign in. The Home screen opens.
2. Tap **Voice Agent** in the bottom bar (this opens the setup wizard screen).
3. Scroll to the bottom to the panel headed "GOOGLE PLAY STORE 2026 AI & DPDP
   ACT 2023 SAFETY" and tap **Delete Account**.
4. Read the dialog "Delete Account & All Voice Data?" and tap
   **Delete Permanently**.

The app then calls `DELETE /onboarding/compliance/account/{id}` (the older
`DELETE /onboarding/delete-account/{id}` route also exists), deletes the
Firestore `users/{uid}` profile, and tries to delete the Firebase login. Firebase
can refuse that last step with "requires recent login". The public delete page
says so and asks the user to email in that case, so watch the mailbox for it.

The public delete page (`backend/app/core/legal_content.py`) uses the same
labels as the app, and a test pins them.

Also **TO CONFIRM**: the page promises completion of deletion by email within
30 days, and the contact mailbox must exist before you publish that.

## 8. Monetisation setup

All prices below are the backend's price **before GST** (GST 18%). They are
from `backend/app/core/pricing.py`. **Play prices are your decision.** India
Play prices are normally entered GST-inclusive, so decide whether Play will
show the ex-GST figure or a GST-inclusive one, and make the backend plan table
match what you charge. The "GST-inclusive" column is the arithmetic at 18%.

Use the same product ids in Play Console and RevenueCat. The webhook credits a
top-up from the product id (`topup_` followed by 2 to 6 digits).

| Product id | Type | Name in app | Backend price (ex-GST) | If GST-inclusive | Billing |
|---|---|---|---|---|---|
| `personal` | Subscription, base plan `monthly` | Mitra Personal | Rs 999 | about Rs 1,178.82 | Monthly auto-renew (30 days) |
| `vyapar` | Subscription, base plan `monthly` | Vyapar Starter | Rs 2,499 | about Rs 2,948.82 | Monthly auto-renew |
| `udyog` | Subscription, base plan `monthly` | Udyog B2B Pro | Rs 4,999 | about Rs 5,898.82 | Monthly auto-renew |
| `enterprise` | Subscription, base plan `monthly` | Enterprise | Rs 11,999 | about Rs 14,158.82 | Monthly auto-renew |
| `pilot` | One-time product | 7-day pilot | Rs 799 | about Rs 942.82 | One-time, 7 days |
| `topup_500` | Consumable one-time product | Wallet top-up Rs 500 | credits Rs 500 | **TO CONFIRM** whether Rs 500 is the credit or the paid amount | Consumable |

Notes:

- Call usage is charged at Rs 7.50 per minute (retail) from the wallet. Keep
  the in-app text and the store description consistent with this.
- Play rounds to the price points it offers; if you want a clean figure such as
  Rs 1,179, accept that the backend ledger records the Play price.
- Top-up limits in the backend: minimum Rs 100, maximum Rs 50,000 per top-up.
  The webhook accepts `topup_<digits>` only.
- After creating products in Play, activate them, then link the Play app to
  RevenueCat and create matching products, an entitlement and an offering.

## 9. RevenueCat setup

1. Create a RevenueCat project and add the Android app `com.mldynamic.sangamitra`.
2. Upload a Play service account JSON in RevenueCat (this is a RevenueCat
   credential, not a repo secret). Grant it the Play permissions RevenueCat
   lists for subscriptions.
3. Copy the **public Android SDK key**. It starts with `goog_`. Store it as the
   GitHub secret `REVENUECAT_ANDROID_KEY` (environment `play-store`). The CI
   release job fails if it does not start with `goog_`.
4. Webhook: RevenueCat, Integrations, Webhooks, add:
   - URL: `https://<API_HOST>/billing/revenuecat/webhook`
   - Authorization header value: any long random string that you also set in
     the backend as `REVENUECAT_WEBHOOK_AUTH`. The backend accepts the webhook
     only when the header equals that value exactly, and rejects everything
     when it is unset.
5. The app logs in to RevenueCat with the backend actor id
   (`Purchases.logIn(actorId)`), so `app_user_id` in each event is that actor.
6. Credited events: `INITIAL_PURCHASE`, `RENEWAL`, `NON_RENEWING_PURCHASE`.
   Credits are idempotent on the store transaction id.
7. Sandbox: the backend credits license-tester purchases while
   `REVENUECAT_ACCEPT_SANDBOX` is true (the default). Set it to `false` at
   launch if test purchases should not grant real call minutes.

## 10. Backend environment

Set these where the API runs. Do not commit values.

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `FIREBASE_PROJECT_ID` | `sangamitra-ai` |
| `REVENUECAT_WEBHOOK_AUTH` | the shared secret from section 9 |
| `REVENUECAT_ACCEPT_SANDBOX` | `true` through closed testing, then your call |
| `LEGAL_CONTACT_EMAIL` | a monitored mailbox |
| `LEGAL_OPERATOR_NAME` | the legal name of the operator |
| `LEGAL_POSTAL_ADDRESS` | the postal address (the grievance contact should include one) |
| `DATABASE_URL`, `JWT_SECRET` | real values, not the defaults. Production start-up refuses the default database password. |

`validate_production_settings` also refuses to start in production when
`USE_FIXTURES` or `DEBUG` is true, or when neither `FIREBASE_PROJECT_ID` nor
`ZITADEL_ISSUER` is set. It only logs a warning (it does not refuse) when
`LEGAL_CONTACT_EMAIL` is still the old placeholder `dpo@sangamitra.in` or
`LEGAL_POSTAL_ADDRESS` is empty, so check the logs on first boot.

The same `LEGAL_*` values are baked into the static site. Before every deploy to
Cloudflare set them in your shell, then run `python -I scripts/build_site.py`
(it needs `pydantic-settings` from `backend/requirements`) and commit nothing
secret. The pages under `site/legal/` must not still show `dpo@sangamitra.in`.

GitHub variables used by the CI release job: `API_BASE_URL` (https, required),
and optional `GOOGLE_WEB_CLIENT_ID`, `PRIVACY_POLICY_URL`, `TERMS_URL`,
`ACCOUNT_DELETION_URL`, `UPLOAD_KEY_SHA1`. Set the three URL variables to the
`https://sangamitra-site.cbvarshini1.workers.dev` pages once they are deployed.

## 11. Signing, Play App Signing and Firebase

1. Create the upload key with `scripts/create-upload-key.ps1` in your own
   terminal. It never prints or stores a password in the repo, sets the GitHub
   secrets, and registers the upload key fingerprints in Firebase.
2. The first release upload enrols the app in **Play App Signing** (Play keeps
   the app signing key; you keep the upload key).
3. After the first upload, open Play Console, Test and release, App integrity,
   App signing. Copy the SHA-1 and SHA-256 of the **App signing key
   certificate**. Google sign-in on installs from Play uses those, not your
   upload key.
4. Register them in Firebase (`<APP_ID>` is
   `1:1056144800596:android:f259b348ae2a97edb0e6c1`):

```powershell
firebase apps:android:sha:list 1:1056144800596:android:f259b348ae2a97edb0e6c1 --project sangamitra-ai
firebase apps:android:sha:create 1:1056144800596:android:f259b348ae2a97edb0e6c1 <PLAY_APP_SIGNING_SHA1> --project sangamitra-ai
firebase apps:android:sha:create 1:1056144800596:android:f259b348ae2a97edb0e6c1 <PLAY_APP_SIGNING_SHA256> --project sangamitra-ai
```

5. Download the refreshed `google-services.json` to a **new scratch path**,
   because the CLI will not overwrite an existing file, then compare and copy:

```powershell
firebase apps:sdkconfig ANDROID 1:1056144800596:android:f259b348ae2a97edb0e6c1 --project sangamitra-ai --out "$env:TEMP\google-services.new.json"
# compare with android/app/google-services.json, then copy it over and commit
```

   If the CI build gets `google-services.json` from the optional
   `GOOGLE_SERVICES_JSON_BASE64` secret, update that secret from the new file.
   Set the `UPLOAD_KEY_SHA1` variable to the upload key's SHA-1 (the script does
   this).
6. If the Play-signed install still cannot sign in with Google, the usual cause
   is a missing SHA in step 4 or an old `google-services.json`.

## 12. Testing requirement and release checklist

**Closed testing for new personal developer accounts.** As last known, a
personal developer account created after November 2023 must run a closed test
with about **12 testers opted in for 14 continuous days** before it can apply
for production access. **Verify the current rule in Play Console**, because
Google changes these numbers. Organisation accounts are exempt, **TO CONFIRM**
which account type you have.

Checklist, in order:

- [ ] Developer account created and identity verified; app created with package `com.mldynamic.sangamitra`
- [ ] Legal pages deployed at `https://sangamitra-site.cbvarshini1.workers.dev`; `LEGAL_*` values set to real ones, `site/` rebuilt with them, and the delete page URL entered in the Console's data-deletion field (section 7)
- [ ] Mailbox for `LEGAL_CONTACT_EMAIL` exists and is monitored
- [ ] Backend deployed over https; `API_BASE_URL` set in GitHub
- [ ] `play-store` GitHub environment exists; `scripts/create-upload-key.ps1` run
- [ ] RevenueCat project, `goog_` key, webhook and products created (sections 8 and 9)
- [ ] `launch-readiness` workflow run and shows nothing MISSING
- [ ] Release job produced a signed AAB (uploaded to the **internal** track as a draft)
- [ ] Play App Signing SHA-1 and SHA-256 registered in Firebase; `google-services.json` refreshed (section 11)
- [ ] Release build tested on a **physical device**: sign-in with Google and with email, record a voice instruction, notification prompt, purchase with a license tester, account deletion
- [ ] Screenshots taken from that device; icon and feature graphic uploaded
- [ ] Store listing, App content forms, Data safety, content rating completed (sections 1 to 6)
- [ ] Closed test started with enough testers for the required period
- [ ] Production access requested; release promoted; PR #5 taken out of draft and merged only after the device test

Things a reviewer will open: the privacy and deletion URLs, the sign-in with
your reviewer account, and any permission prompt. Make sure all of them work on
the exact build you submit.
