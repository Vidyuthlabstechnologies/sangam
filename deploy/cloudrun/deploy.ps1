<#
.SYNOPSIS
  Deploy the Sangam backend to Cloud Run (Mumbai) with a Neon Postgres.

.DESCRIPTION
  RUN THIS YOURSELF in your own terminal. The Neon connection string is typed
  at a hidden prompt and goes straight into Secret Manager. It is never echoed
  or put on a command line. It passes through a short-lived temp file (gcloud
  --data-file) that is overwritten and deleted right after the upload.

  In order:
    1. Checks gcloud and gh, and that billing is linked to the project.
    2. Enables Cloud Run, Cloud Build, Artifact Registry and Secret Manager.
    3. Stores the Neon URL (converted for asyncpg), a fresh JWT secret and a
       fresh RevenueCat webhook secret in Secret Manager. Existing secrets are
       kept unless you choose to replace the database URL.
    4. Lets the Cloud Run service account read those three secrets only.
    5. Builds backend/Dockerfile with Cloud Build and deploys it.
    6. Checks /health, then sets the GitHub variable API_BASE_URL.
    7. Copies the RevenueCat webhook secret to your clipboard (new secrets only).

  Use the DIRECT Neon connection string (host without "-pooler"). The pooled
  endpoint breaks asyncpg prepared statements.

.PARAMETER DryRun
  Print every step without creating anything or asking for secrets.

.PARAMETER UseLocalNeon
  Take the direct Neon string from .env.local (written by `neon init`) without asking.

.EXAMPLE
  pwsh -File .\deploy\cloudrun\deploy.ps1 -DryRun
  pwsh -File .\deploy\cloudrun\deploy.ps1
#>
#requires -Version 7
[CmdletBinding()]
param(
    # Hosting project (has the billing account). Firebase Auth stays in sangamitra-ai;
    # the backend only needs that id to verify tokens (FIREBASE_PROJECT_ID below).
    [string]$ProjectId = 'vidyuthlabs-514315',
    [string]$Region = 'asia-south1',
    [string]$Service = 'sangam-backend',
    [string]$RuntimeAccountName = 'sangam-backend-run',
    [string]$Repo = 'Vidyuthlabstechnologies/sangam',
    [switch]$DryRun,
    # Use DATABASE_URL_UNPOOLED from .env.local without asking (for unattended runs).
    [switch]$UseLocalNeon
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$DbSecret = 'sangam-database-url'
$JwtSecret = 'sangam-jwt-secret'
$WebhookSecret = 'sangam-revenuecat-webhook-auth'
$ApiServices = 'run.googleapis.com', 'cloudbuild.googleapis.com', 'artifactregistry.googleapis.com', 'secretmanager.googleapis.com'

function Step([string]$Title) { Write-Host "==> $Title" -ForegroundColor Cyan }

function Invoke-Cloud([string]$Label, [scriptblock]$Block) {
    Write-Host "  $Label"
    if ($DryRun) { return }
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit $LASTEXITCODE)." }
}

function Test-Secret([string]$Name) {
    if ($DryRun) { return $false }
    gcloud secrets describe $Name --project $ProjectId *> $null
    return $LASTEXITCODE -eq 0
}

function New-RandomToken {
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function ConvertFrom-Secure([securestring]$Secure) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringUni($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($ptr) }
}

# Neon gives postgresql://user:pw@host/db?sslmode=require&channel_binding=require.
# SQLAlchemy needs the +asyncpg scheme, and asyncpg wants ssl=require instead.
function ConvertTo-AsyncpgUrl([string]$Raw) {
    $text = $Raw.Trim()
    if ($text -notmatch '^postgres(ql)?://') { throw 'That is not a postgresql:// connection string.' }
    $rest = $text -replace '^postgres(ql)?://', ''
    $base, $query = $rest -split '\?', 2
    if ($base -match '-pooler') { throw 'Use the DIRECT connection string (turn off "Connection pooling" in Neon).' }
    $kept = @()
    if ($query) { $kept = @($query -split '&' | Where-Object { $_ -and $_ -notmatch '^(sslmode|channel_binding|ssl)=' }) }
    $kept += 'ssl=require'
    return 'postgresql+asyncpg://' + $base + '?' + ($kept -join '&')
}

function Get-LocalNeonUrl {
    $file = Join-Path $RepoRoot '.env.local'
    if (-not (Test-Path -LiteralPath $file)) { return $null }
    $line = Get-Content -LiteralPath $file | Where-Object { $_ -match '^DATABASE_URL_UNPOOLED=' } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -replace '^DATABASE_URL_UNPOOLED=', '').Trim().Trim('"').Trim("'")
}

function Set-SecretValue([string]$Name, [string]$Value) {
    $dir = Join-Path ([IO.Path]::GetTempPath()) ('sangam-' + [Guid]::NewGuid().ToString('N'))
    $file = Join-Path $dir 'value'
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        [IO.File]::WriteAllText($file, $Value, [Text.UTF8Encoding]::new($false))
        if (Test-Secret $Name) {
            gcloud secrets versions add $Name --data-file=$file --project $ProjectId *> $null
        } else {
            gcloud secrets create $Name --replication-policy=automatic --data-file=$file --project $ProjectId *> $null
        }
        if ($LASTEXITCODE -ne 0) { throw "Could not store secret $Name." }
    } finally {
        [IO.File]::WriteAllBytes($file, (New-Object byte[] 256))
        Remove-Item -LiteralPath $dir -Recurse -Force
    }
}

Step 'Checking tools and billing'
foreach ($tool in 'gcloud', 'gh') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not on PATH." }
}
if (-not $DryRun) {
    $billing = gcloud billing projects describe $ProjectId --format='value(billingEnabled)' 2>$null
    if ($billing -ne 'True') {
        throw "Billing is not linked to $ProjectId. Link it at https://console.cloud.google.com/billing/linkedaccount?project=$ProjectId and run this again."
    }
}

Step 'Enabling Google Cloud APIs'
Invoke-Cloud "gcloud services enable $($ApiServices -join ' ')" {
    gcloud services enable @ApiServices --project $ProjectId
}

Step 'Storing secrets in Secret Manager'
$replaceDb = $true
if (Test-Secret $DbSecret) {
    $replaceDb = (Read-Host "$DbSecret already exists. Replace it? (y/N)") -match '^[yY]'
}
if ($replaceDb -and -not $DryRun) {
    # `neon init` writes DATABASE_URL_UNPOOLED (the direct string) to .env.local, which git ignores.
    $neon = Get-LocalNeonUrl
    if ($neon -and -not $UseLocalNeon -and (Read-Host 'Use the direct Neon URL from .env.local? (Y/n)') -match '^[nN]') { $neon = $null }
    if (-not $neon) {
        $neon = ConvertFrom-Secure (Read-Host -AsSecureString 'Paste the DIRECT Neon connection string (hidden)')
    }
    Set-SecretValue $DbSecret (ConvertTo-AsyncpgUrl $neon)
    $neon = $null
    Write-Host "  stored $DbSecret"
} elseif ($DryRun) {
    Write-Host "  ${DbSecret}: would prompt for the Neon string (or keep the existing one)"
} else {
    Write-Host "  kept existing ${DbSecret}"
}
if (-not (Test-Secret $JwtSecret)) {
    Invoke-Cloud "create $JwtSecret (random, not shown)" { Set-SecretValue $JwtSecret (New-RandomToken) }
}
if (-not (Test-Secret $WebhookSecret)) {
    $newWebhookToken = New-RandomToken
    Invoke-Cloud "create $WebhookSecret (random, not shown)" { Set-SecretValue $WebhookSecret $newWebhookToken }
    if (-not $DryRun) {
        # Copy it now, not after the deploy: a later failure must not lose the only copy.
        Set-Clipboard $newWebhookToken
        Write-Host '  The RevenueCat webhook secret is on your clipboard. Paste it into RevenueCat as the Authorization header value, then clear the clipboard (Win+V history too).' -ForegroundColor Yellow
    }
}

Step 'Creating the runtime identity and granting access'
# The service runs as its own account that can read only these three secrets.
# The default compute account is used for the build only (source deploys need it).
$runtimeEmail = "$RuntimeAccountName@$ProjectId.iam.gserviceaccount.com"
$runtimeAccount = "serviceAccount:$runtimeEmail"
$accountExists = $false
if (-not $DryRun) {
    gcloud iam service-accounts describe $runtimeEmail --project $ProjectId *> $null
    $accountExists = $LASTEXITCODE -eq 0
}
if (-not $accountExists) {
    Invoke-Cloud "create service account $runtimeEmail" {
        gcloud iam service-accounts create $RuntimeAccountName --display-name 'Sangam backend runtime' --project $ProjectId *> $null
    }
    if (-not $DryRun) { Start-Sleep -Seconds 15 }  # let IAM see the new account before binding it
}
foreach ($name in $DbSecret, $JwtSecret, $WebhookSecret) {
    Invoke-Cloud "secretAccessor on $name" {
        gcloud secrets add-iam-policy-binding $name --member $runtimeAccount --role roles/secretmanager.secretAccessor --project $ProjectId *> $null
    }
}
$projectNumber = if ($DryRun) { '<PROJECT_NUMBER>' } else { gcloud projects describe $ProjectId --format='value(projectNumber)' }
$buildAccount = "serviceAccount:$projectNumber-compute@developer.gserviceaccount.com"
Invoke-Cloud 'roles/run.builder for the build account (needed to build from source)' {
    gcloud projects add-iam-policy-binding $ProjectId --member $buildAccount --role roles/run.builder --condition=None *> $null
}

Step "Building and deploying $Service to $Region (takes a few minutes)"
# Deliberate choices, revisit at launch:
#  REVENUECAT_ACCEPT_SANDBOX=true   credits license-tester purchases during closed testing (set false at launch)
#  FIREBASE_REQUIRE_VERIFIED_EMAIL=false   email sign-up works before the address is verified
#  FORWARDED_ALLOW_IPS=*   Cloud Run's proxy addresses are not fixed; the client IP comes from X-Forwarded-For,
#                          so a client that forges that header can dodge per-IP rate limits
$envVars = 'ENVIRONMENT=production,FIREBASE_PROJECT_ID=sangamitra-ai,FIREBASE_REQUIRE_VERIFIED_EMAIL=false,REVENUECAT_ACCEPT_SANDBOX=true,FORWARDED_ALLOW_IPS=*'
$secretRefs = "DATABASE_URL=${DbSecret}:latest,JWT_SECRET=${JwtSecret}:latest,REVENUECAT_WEBHOOK_AUTH=${WebhookSecret}:latest"
Invoke-Cloud "gcloud run deploy $Service --source backend --port 8000 --min-instances 0 --max-instances 3" {
    gcloud run deploy $Service --source (Join-Path $RepoRoot 'backend') --project $ProjectId --region $Region `
        --port 8000 --allow-unauthenticated --min-instances 0 --max-instances 3 --memory 512Mi `
        --service-account $runtimeEmail `
        --update-env-vars $envVars --update-secrets $secretRefs
}

Step 'Checking the service'
if (-not $DryRun) {
    $url = gcloud run services describe $Service --project $ProjectId --region $Region --format='value(status.url)'
    $health = Invoke-WebRequest -Uri "$url/health" -UseBasicParsing -TimeoutSec 60
    Write-Host "  $url/health -> HTTP $($health.StatusCode)"
    Write-Host "  setting GitHub variable API_BASE_URL"
    gh variable set API_BASE_URL --body $url -R $Repo
    if ($LASTEXITCODE -ne 0) { throw 'Could not set API_BASE_URL.' }
    Write-Host "`nBackend URL: $url" -ForegroundColor Green
}
Write-Host "`nNot set yet (the API uses canned responses without them): SARVAM_API_KEY, RAZORPAY_KEY_ID/SECRET." -ForegroundColor Yellow
