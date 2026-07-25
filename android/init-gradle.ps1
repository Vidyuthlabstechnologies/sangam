param([switch]$InstallGradle)

if ($InstallGradle) {
    Write-Host "Installing Gradle via winget..."
    winget install Gradle.Gradle
    if ($LASTEXITCODE -ne 0) {
        Write-Host "winget failed. Download from https://gradle.org/releases/ manually."
        exit 1
    }
}

if (-not (Get-Command gradle -ErrorAction SilentlyContinue)) {
    Write-Host "Gradle not found in PATH. Install it first:"
    Write-Host "  .\init-gradle.ps1 -InstallGradle"
    Write-Host "Or download from https://gradle.org/releases/"
    exit 1
}

Write-Host "Generating Gradle wrapper..."
gradle wrapper --gradle-version=8.11.1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Done! Build with: .\gradlew assembleDebug"
}
