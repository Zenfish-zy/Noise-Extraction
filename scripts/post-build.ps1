# Post-build script to rename portable executable
# Usage: powershell -ExecutionPolicy Bypass -File scripts\post-build.ps1

$ErrorActionPreference = "Stop"

$ReleaseDir = "desktop\src-tauri\target\release"
$SourceExe = "$ReleaseDir\soundhunter.exe"
$TargetExe = "$ReleaseDir\寻音殿.exe"

if (Test-Path $SourceExe) {
    Write-Host "Renaming portable executable..." -ForegroundColor Cyan
    Copy-Item $SourceExe $TargetExe -Force
    Write-Host "✓ Created: $TargetExe" -ForegroundColor Green
} else {
    Write-Host "⚠ Warning: $SourceExe not found" -ForegroundColor Yellow
    exit 1
}
