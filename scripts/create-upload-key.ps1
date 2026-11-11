<#
.SYNOPSIS
  Create the Sangam Play upload key and wire it into GitHub and Firebase.

.DESCRIPTION
  RUN THIS YOURSELF in your own terminal. Do not paste its prompts or passwords
  anywhere else.

  What it does, in order:
    1. Checks keytool, gh and firebase are available and the GitHub environment exists.
    2. Prompts for a keystore password (hidden, typed twice) and a backup folder.
    3. Creates a PKCS12 keystore in a temp folder OUTSIDE this repo.
    4. Copies it to your backup folder and verifies the copy by hash.
    5. Prints only the SHA-1 and SHA-256 fingerprints.
    6. Sets the GitHub environment secrets ANDROID_KEYSTORE_BASE64,
       ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_PASSWORD, ANDROID_KEY_ALIAS and the
       repository variable UPLOAD_KEY_SHA1. Secret values go to gh on stdin,
       never on a command line, and the base64 is never written to disk.
    7. Registers both fingerprints in Firebase (skipping ones already listed).
    8. Overwrites and deletes the temp copy (only after the backup is verified).

  Passwords are read with Read-Host -AsSecureString. They are never accepted as
  parameters, never echoed, and only handed to keytool through a process-scoped
  environment variable that is removed afterwards.

  Prerequisites: JDK keytool on PATH, `gh auth login` done with admin on the
  repo, `firebase login` done with an account that can edit project
  sangamitra-ai, and the GitHub environment `play-store` already created.

.PARAMETER DryRun
  Print every step and command without creating, changing or deleting anything,
  and without asking for passwords.

.EXAMPLE
  pwsh -File .\scripts\create-upload-key.ps1 -DryRun
  pwsh -File .\scripts\create-upload-key.ps1
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$Repo = 'Vidyuthlabstechnologies/sangam',
    [string]$Environment = 'play-store',
    [string]$KeyAlias = 'sangamitra',
    [string]$FirebaseAppId = '1:1056144800596:android:f259b348ae2a97edb0e6c1',
    [string]$FirebaseProject = 'sangamitra-ai',
    [string]$DistinguishedName = 'CN=Sangamitra AI, O=Sangamitra AI, C=IN'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$PasswordEnvVar = 'SANGAM_UPLOAD_KS_PW'
$MinPasswordLength = 12
$ValidityDays = 10000
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-DryRun([string]$Text) { Write-Host "[dry-run] $Text" -ForegroundColor Yellow }

function Test-InsideRepo([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $root = $RepoRoot.TrimEnd('\', '/')
    return $full.Equals($root, 'OrdinalIgnoreCase') -or
        $full.StartsWith($root + [IO.Path]::DirectorySeparatorChar, 'OrdinalIgnoreCase') -or
        $full.StartsWith($root + [IO.Path]::AltDirectorySeparatorChar, 'OrdinalIgnoreCase')
}

function ConvertFrom-Secure([securestring]$Secure) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function Assert-NativeOk([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)." }
}

function Read-NewPassword {
    while ($true) {
        $first = Read-Host -AsSecureString 'Choose a keystore password (hidden)'
        $second = Read-Host -AsSecureString 'Type it again (hidden)'
        $plainFirst = ConvertFrom-Secure $first
        $entriesMatch = $plainFirst -ceq (ConvertFrom-Secure $second)
        $longEnough = $plainFirst.Length -ge $MinPasswordLength
        if ($entriesMatch -and $longEnough) { return $plainFirst }
        if (-not $entriesMatch) { Write-Warning 'The two entries differ. Try again.' }
        else { Write-Warning "Use at least $MinPasswordLength characters. Try again." }
    }
}

function Set-GhSecret([string]$Name, [string]$Value, [string]$GhPath) {
    # The value goes to gh on stdin with no trailing newline. Nothing secret is
    # placed on a command line.
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $GhPath
    $psi.Arguments = "secret set $Name --repo $Repo --env $Environment"
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $proc = [Diagnostics.Process]::Start($psi)
    $proc.StandardInput.Write($Value)
    $proc.StandardInput.Close()
    $null = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) { throw "gh secret set $Name failed: $stderr" }
    Write-Host "  set secret $Name"
}

function Get-Fingerprint([string[]]$KeytoolOutput, [string]$Label) {
    $line = $KeytoolOutput | Where-Object { $_ -match "^\s*$Label\s*:" } | Select-Object -First 1
    if (-not $line) { throw "Could not find $Label in keytool output." }
    return ($line -replace "^\s*$Label\s*:\s*", '').Trim()
}

function Remove-Securely([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    # Best effort: overwrite then delete. SSD wear levelling means this cannot
    # guarantee the old blocks are gone; the folder is in your user temp area.
    $length = (Get-Item -LiteralPath $Path).Length
    $noise = New-Object byte[] $length
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($noise) } finally { $rng.Dispose() }
    [IO.File]::WriteAllBytes($Path, $noise)
    Remove-Item -LiteralPath $Path -Force
}

# ---------------------------------------------------------------- dry run

if ($DryRun) {
    Write-Step 'Dry run: nothing will be created, changed or deleted.'
    Write-DryRun 'check tools: keytool, gh, firebase'
    Write-DryRun "gh api repos/$Repo/environments/$Environment   (must exist)"
    Write-DryRun "gh secret list --repo $Repo --env $Environment   (warn before overwriting)"
    Write-DryRun 'prompt: keystore password twice (hidden), backup folder (outside the repo)'
    Write-DryRun "keytool -genkeypair -keystore <TEMP>\sangamitra-upload.p12 -alias $KeyAlias -keyalg RSA -keysize 2048 -validity $ValidityDays -storetype PKCS12 -dname `"$DistinguishedName`" -storepass:env $PasswordEnvVar -keypass:env $PasswordEnvVar"
    Write-DryRun 'copy keystore to <BACKUP_FOLDER>\sangamitra-upload.p12 and compare SHA-256 hashes'
    Write-DryRun "keytool -list -v -keystore <TEMP>\sangamitra-upload.p12 -alias $KeyAlias -storepass:env $PasswordEnvVar   (print only SHA1 and SHA256)"
    foreach ($name in 'ANDROID_KEYSTORE_BASE64', 'ANDROID_KEYSTORE_PASSWORD', 'ANDROID_KEY_PASSWORD', 'ANDROID_KEY_ALIAS') {
        Write-DryRun "<value on stdin> | gh secret set $name --repo $Repo --env $Environment"
    }
    Write-DryRun "gh variable set UPLOAD_KEY_SHA1 --repo $Repo --body <SHA1>"
    Write-DryRun "firebase apps:android:sha:list $FirebaseAppId --project $FirebaseProject"
    Write-DryRun "firebase apps:android:sha:create $FirebaseAppId <SHA1> --project $FirebaseProject   (if not listed)"
    Write-DryRun "firebase apps:android:sha:create $FirebaseAppId <SHA256> --project $FirebaseProject   (if not listed)"
    Write-DryRun 'overwrite and delete the temp keystore after the backup is verified'
    return
}

# --------------------------------------------------------------- preflight

Write-Step 'Checking tools'
foreach ($tool in 'keytool', 'gh', 'firebase') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "'$tool' was not found on PATH. Install it and run again."
    }
}
$ghPath = (Get-Command gh).Source

Write-Step "Checking GitHub environment '$Environment' on $Repo"
& gh api "repos/$Repo/environments/$Environment" --silent
if ($LASTEXITCODE -ne 0) {
    throw ("Environment '$Environment' does not exist or you lack access. Create it first:`n" +
        "  gh api -X PUT repos/$Repo/environments/$Environment")
}

$existing = & gh secret list --repo $Repo --env $Environment --json name --jq '.[].name'
Assert-NativeOk 'gh secret list'
$writtenSecrets = 'ANDROID_KEYSTORE_BASE64', 'ANDROID_KEYSTORE_PASSWORD', 'ANDROID_KEY_PASSWORD', 'ANDROID_KEY_ALIAS'
$alreadySet = @($writtenSecrets | Where-Object { $existing -contains $_ })
$existingVariables = & gh variable list --repo $Repo --json name --jq '.[].name'
Assert-NativeOk 'gh variable list'
if ($existingVariables -contains 'UPLOAD_KEY_SHA1') { $alreadySet += 'UPLOAD_KEY_SHA1 (variable)' }
if ($alreadySet.Count -gt 0) {
    Write-Warning ("These already exist and would be overwritten: " + ($alreadySet -join ', ') +
        ". Replacing them changes the upload key CI signs with.")
    $answer = Read-Host "Type REPLACE to continue, anything else to stop"
    if ($answer -cne 'REPLACE') { Write-Host 'Stopped. Nothing was changed.'; return }
}

# ------------------------------------------------------------ user input

$backupFolder = Read-Host 'Folder for the keystore backup (outside this repo, e.g. a USB drive or synced vault folder)'
if ([string]::IsNullOrWhiteSpace($backupFolder)) { throw 'A backup folder is required.' }
$backupFolder = [IO.Path]::GetFullPath($backupFolder)
if (Test-InsideRepo $backupFolder) { throw "Backup folder must be outside the repo ($RepoRoot)." }
if (-not (Test-Path -LiteralPath $backupFolder -PathType Container)) { throw "Backup folder does not exist: $backupFolder" }
$backupFile = Join-Path $backupFolder 'sangamitra-upload.p12'
if (Test-Path -LiteralPath $backupFile) { throw "Refusing to overwrite an existing file: $backupFile" }

$tempDir = Join-Path ([IO.Path]::GetTempPath()) ("sangam-upload-" + [Guid]::NewGuid().ToString('N'))
if (Test-InsideRepo $tempDir) { throw 'Temp folder resolves inside the repo. Aborting.' }

$password = Read-NewPassword
$backupVerified = $false
$keystore = Join-Path $tempDir 'sangamitra-upload.p12'

try {
    New-Item -ItemType Directory -Path $tempDir | Out-Null

    # ------------------------------------------------- create the keystore
    Write-Step 'Creating the keystore'
    Set-Item -Path "Env:$PasswordEnvVar" -Value $password
    & keytool -genkeypair -keystore $keystore -alias $KeyAlias -keyalg RSA -keysize 2048 `
        -validity $ValidityDays -storetype PKCS12 -dname $DistinguishedName `
        "-storepass:env" $PasswordEnvVar "-keypass:env" $PasswordEnvVar
    Assert-NativeOk 'keytool -genkeypair'

    # ------------------------------------------------------ back it up now
    Write-Step 'Backing up the keystore'
    Copy-Item -LiteralPath $keystore -Destination $backupFile
    $sourceHash = (Get-FileHash -LiteralPath $keystore -Algorithm SHA256).Hash
    $copyHash = (Get-FileHash -LiteralPath $backupFile -Algorithm SHA256).Hash
    if ($sourceHash -ne $copyHash) { throw 'Backup copy does not match the original. Temp copy kept.' }
    $backupVerified = $true
    Write-Host "  backup verified: $backupFile"

    # ------------------------------------------------------ fingerprints
    Write-Step 'Reading fingerprints (only these two values are printed)'
    $listing = & keytool -list -v -keystore $keystore -alias $KeyAlias "-storepass:env" $PasswordEnvVar
    Assert-NativeOk 'keytool -list'
    $sha1 = Get-Fingerprint $listing 'SHA1'
    $sha256 = Get-Fingerprint $listing 'SHA256'
    Write-Host "  SHA-1:   $sha1"
    Write-Host "  SHA-256: $sha256"

    # ------------------------------------------------------ GitHub
    Write-Step "Setting GitHub secrets in environment '$Environment'"
    $base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($keystore))
    Set-GhSecret 'ANDROID_KEYSTORE_BASE64' $base64 $ghPath
    $base64 = $null
    Set-GhSecret 'ANDROID_KEYSTORE_PASSWORD' $password $ghPath
    Set-GhSecret 'ANDROID_KEY_PASSWORD' $password $ghPath
    Set-GhSecret 'ANDROID_KEY_ALIAS' $KeyAlias $ghPath

    Write-Step 'Setting repository variable UPLOAD_KEY_SHA1'
    & gh variable set UPLOAD_KEY_SHA1 --repo $Repo --body $sha1
    Assert-NativeOk 'gh variable set'

    # ------------------------------------------------------ Firebase
    Write-Step "Registering fingerprints in Firebase project $FirebaseProject"
    $listed = (& firebase apps:android:sha:list $FirebaseAppId --project $FirebaseProject | Out-String).ToUpperInvariant()
    Assert-NativeOk 'firebase apps:android:sha:list'
    foreach ($sha in $sha1, $sha256) {
        if ($listed.Contains($sha.ToUpperInvariant())) {
            Write-Host "  already registered: $sha"
            continue
        }
        & firebase apps:android:sha:create $FirebaseAppId $sha --project $FirebaseProject
        Assert-NativeOk 'firebase apps:android:sha:create'
    }

    Write-Host ''
    Write-Host 'Done.' -ForegroundColor Green
    Write-Host "Keep the backup ($backupFile) AND the password in a password manager."
    Write-Host 'If either is lost you must ask Google to reset the upload key.'
    Write-Host 'Next: refresh google-services.json (see docs/PLAY_CONSOLE.md section 11), then'
    Write-Host 'run the release workflow. After the first upload, register the Play App Signing'
    Write-Host 'SHA-1 and SHA-256 in Firebase the same way.'
}
finally {
    Remove-Item -Path "Env:$PasswordEnvVar" -ErrorAction SilentlyContinue
    $password = $null
    if ($backupVerified) {
        Remove-Securely $keystore
        if (Test-Path -LiteralPath $tempDir) { Remove-Item -LiteralPath $tempDir -Recurse -Force }
        Write-Host 'Temp copy of the keystore overwritten and deleted.'
    }
    elseif (Test-Path -LiteralPath $keystore) {
        Write-Warning "The backup was not verified, so the temp keystore was KEPT at: $keystore"
    }
}
