# Mem0 Status Checker (PowerShell)
# Run from project root

Write-Host "=== mem0 Status Check ===" -ForegroundColor Cyan
Write-Host ""

# Identity
Write-Host "Identity:" -ForegroundColor Yellow
Write-Host "  User ID:     $env:MEM0_USER_ID"
Write-Host "  App ID:      $env:MEM0_APP_ID"
Write-Host "  Session ID:  $env:MEM0_SESSION_ID"
Write-Host "  Branch:      $env:MEM0_BRANCH"
Write-Host "  Global:      $env:MEM0_GLOBAL_SEARCH"
Write-Host ""

# Settings
$settingsPath = "$env:USERPROFILE\.mem0\settings.json"
if (Test-Path $settingsPath) {
    $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
    Write-Host "Settings ($settingsPath):" -ForegroundColor Yellow
    $settings | ConvertTo-Json | Write-Host
}

# Dream state
$dreamPath = "$env:USERPROFILE\.mem0\mem0-dream-state.json"
if (Test-Path $dreamPath) {
    $dream = Get-Content $dreamPath -Raw | ConvertFrom-Json
    Write-Host "Dream State:" -ForegroundColor Yellow
    $dream | ConvertTo-Json | Write-Host
}

# Categories
$catPath = "$env:USERPROFILE\.mem0\categories_setup.json"
if (Test-Path $catPath) {
    Write-Host "Categories setup: PRESENT" -ForegroundColor Green
} else {
    Write-Host "Categories setup: MISSING" -ForegroundColor Red
}

Write-Host ""
Write-Host "Config files:" -ForegroundColor Yellow
if (Test-Path ".mem0.md") { Write-Host "  .mem0.md:     PRESENT" -ForegroundColor Green }
else { Write-Host "  .mem0.md:     MISSING" -ForegroundColor Red }

if (Test-Path "$env:USERPROFILE\.config\opencode\mem0.jsonc") { Write-Host "  mem0.jsonc:   PRESENT (global config)" -ForegroundColor Green }
else { Write-Host "  mem0.jsonc:   MISSING" -ForegroundColor Red }

Write-Host ""
Write-Host "Plugin version:" -ForegroundColor Yellow
$pluginPkg = "$env:USERPROFILE\.config\opencode\node_modules\@mem0\opencode-plugin\package.json"
if (Test-Path $pluginPkg) {
    $pkg = Get-Content $pluginPkg -Raw | ConvertFrom-Json
    Write-Host "  @mem0/opencode-plugin v$($pkg.version)" -ForegroundColor Green
}
