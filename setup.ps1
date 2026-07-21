$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverScript = Join-Path $repoRoot 'scripts\tools-mcp-server.py'

if (-not (Test-Path $serverScript)) {
    throw "CortexStratum server script was not found at $serverScript"
}

$venvPython = Join-Path $repoRoot '.build-venv\Scripts\python.exe'
$pythonCmd = $null
if (Test-Path $venvPython) {
    $pythonCmd = [pscustomobject]@{ Source = $venvPython }
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    }
}

if (-not $pythonCmd) {
    throw 'Python 3.10+ is required to run CortexStratum.'
}

Write-Host '============================================'
Write-Host '  CortexStratum — local Zed setup'
Write-Host '============================================'
Write-Host ''
Write-Host "  Repo root: $repoRoot"
Write-Host "  Python: $($pythonCmd.Source)"
Write-Host "  MCP server: $serverScript"

$zedConfigPath = Join-Path $env:APPDATA 'Zed\settings.json'
$zedConfigDir = Split-Path $zedConfigPath -Parent
New-Item -ItemType Directory -Path $zedConfigDir -Force | Out-Null

$config = [ordered]@{
    context_server_timeout = 300
    agent_servers = @{}
    git = @{ disable_git = $false }
    context_servers = [ordered]@{}
    session = @{ trust_all_worktrees = $true }
    base_keymap = 'JetBrains'
    ui_font_size = 16
    buffer_font_size = 15
    theme = @{ mode = 'system'; light = 'One Light'; dark = 'One Dark' }
}

$config.context_servers.CortexStratum = [ordered]@{
    timeout = 300
    command = $pythonCmd.Source
    args = @($serverScript)
    enabled = $true
}

$config.context_servers['mcp-server-playwright'] = [ordered]@{
    enabled = $true
    remote = $false
    settings = @{}
}

$config.context_servers['mcp-server-github'] = [ordered]@{
    enabled = $true
    remote = $false
    settings = @{ github_personal_access_token = 'GITHUB_PERSONAL_ACCESS_TOKEN' }
}

$config | ConvertTo-Json -Depth 10 | Set-Content -Path $zedConfigPath -Encoding UTF8

Write-Host ''
Write-Host '  Updated Zed settings with the local CortexStratum MCP server.'
Write-Host '  Verifying the server entrypoint...'

$verify = & $pythonCmd.Source $serverScript --list-tools 2>$null
if ($LASTEXITCODE -eq 0) {
    $toolCount = ($verify | ConvertFrom-Json).Count
    Write-Host "  Verified tool registry: $toolCount tools exposed"
} else {
    throw 'CortexStratum failed its local startup verification.'
}

Write-Host ''
Write-Host '  Setup complete. Restart Zed or reload the context server to pick up the new config.'
