param(
    [Parameter(Position=0)]
    [string]$PresetName,
    [switch]$List
)

$ConfigPath = if ($env:OPENCODE_CONFIG) {
    $env:OPENCODE_CONFIG
} else {
    Join-Path $env:USERPROFILE ".config\opencode\opencode.jsonc"
}

$Presets = @{
    deepseek = @{
        model       = "opencode-go/deepseek-v4-flash-free"
        small_model = "opencode-go/deepseek-v4-flash-free"
        description = "Default setup - uses deepseek-v4-flash-free for all tasks"
    }
    free = @{
        model       = "opencode/deepseek-v4-flash-free"
        small_model = "opencode/deepseek-v4-flash-free"
        description = "Minimal free tier - both models use the base deepseek-free endpoint"
    }
    hybrid = @{
        model       = "opencode-go/deepseek-v4-flash-free"
        small_model = "opencode/nemotron-3-ultra-free"
        description = "Mixed - deepseek-go for main, nemotron for light tasks"
    }
    mini = @{
        model       = "opencode/deepseek-v4-flash-free"
        small_model = "opencode/deepseek-v4-flash-free"
        description = "Ultra lightweight - both models use the base free endpoint, ideal for simple"
    }
}

if ($List -or (-not $PresetName)) {
    Write-Host "Available presets:" -ForegroundColor Cyan
    foreach ($key in $Presets.Keys | Sort-Object) {
        $p = $Presets[$key]
        Write-Host ("  " + $key).PadRight(15) -ForegroundColor Yellow -NoNewline
        Write-Host $p.description
    }
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Cyan
    Write-Host "  .\preset-manager.ps1 <name>    - Switch to the named preset" -ForegroundColor Gray
    Write-Host "  .\preset-manager.ps1 -List     - List presets (default with no args)" -ForegroundColor Gray
    exit 0
}

if (-not $Presets.ContainsKey($PresetName)) {
    Write-Host "ERROR: Unknown preset '$PresetName'." -ForegroundColor Red
    Write-Host "Valid presets: $($Presets.Keys -join ', ')" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    Write-Host "ERROR: Config file not found at $ConfigPath" -ForegroundColor Red
    exit 1
}

$Target = $Presets[$PresetName]

# Write Python helper to temp file to avoid quoting issues
$PyHelper = Join-Path $env:TEMP "preset_update_$(Get-Random).py"
@"
import json, re, sys, os

path = sys.argv[1]
preset_model = sys.argv[2]
preset_small = sys.argv[3]

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_model = None
old_small = None
m = re.search(r'"model"\s*:\s*"([^"]*)"', content)
if m:
    old_model = m.group(1)

m = re.search(r'"small_model"\s*:\s*"([^"]*)"', content)
if m:
    old_small = m.group(1)

content = re.sub(r'"model"\s*:\s*"[^"]*"', f'"model": "{preset_model}"', content)
content = re.sub(r'"small_model"\s*:\s*"[^"]*"', f'"small_model": "{preset_small}"', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

if old_model:
    print(f'OLD: model={old_model}, small_model={old_small}')
print(f'NEW: model={preset_model}, small_model={preset_small}')
"@ | Set-Content -Path $PyHelper -Encoding UTF8

$result = python $PyHelper $ConfigPath $Target.model $Target.small_model 2>&1
$exitCode = $LASTEXITCODE

Remove-Item -LiteralPath $PyHelper -Force -ErrorAction SilentlyContinue

if ($exitCode -ne 0) {
    Write-Host "ERROR: Failed to update config:" -ForegroundColor Red
    foreach ($line in $result) { Write-Host "  $line" -ForegroundColor Red }
    exit 1
}

Write-Host ""
Write-Host "Preset applied: $PresetName" -ForegroundColor Green
foreach ($line in $result) { Write-Host "  $line" -ForegroundColor Gray }
Write-Host "File: $ConfigPath" -ForegroundColor DarkGray
