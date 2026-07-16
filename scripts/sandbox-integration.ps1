#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Sandbox Integration Wrapper — calls sandbox-manager.py with structured output.
.DESCRIPTION
    PowerShell wrapper for the sandbox-manager.py script. Accepts code, language,
    timeout parameters and returns formatted results.
.PARAMETER Code
    Inline code string to execute in the sandbox.
.PARAMETER Language
    Language of the code: python, powershell, or shell (default: python).
.PARAMETER Timeout
    Maximum execution time in seconds (default: 30).
.PARAMETER File
    Path to a file containing code to execute.
.PARAMETER Network
    Allow network access for Python execution.
.PARAMETER Verify
    Run sandbox health check instead of executing code.
.PARAMETER CheckSafety
    Run safety check on the provided code without executing.
.PARAMETER KeepFiles
    Do not clean up sandbox directory after execution.
.PARAMETER Log
    Show the sandbox execution log.
.PARAMETER Json
    Output results as JSON instead of formatted text.
.EXAMPLE
    .\sandbox-integration.ps1 -Code "print('hello world')" -Language python
.EXAMPLE
    .\sandbox-integration.ps1 -Code "Write-Output 'hello'" -Language powershell
.EXAMPLE
    .\sandbox-integration.ps1 -Verify
.EXAMPLE
    .\sandbox-integration.ps1 -Code "import os; os.system('rm -rf /')" -CheckSafety
#>

param(
    [string]$Code = "",
    [ValidateSet("python", "powershell", "shell")]
    [string]$Language = "python",
    [int]$Timeout = 30,
    [string]$File = "",
    [switch]$Network,
    [switch]$Verify,
    [switch]$CheckSafety,
    [switch]$KeepFiles,
    [switch]$Log,
    [switch]$Json
)

$ScriptDir = Split-Path -Parent $PSCommandPath
$SandboxManager = Join-Path $ScriptDir "sandbox-manager.py"

if (-not (Test-Path $SandboxManager)) {
    Write-Error "sandbox-manager.py not found at: $SandboxManager"
    exit 1
}

$pyArgs = @()

if ($Verify) {
    $pyArgs += "--verify"
} elseif ($CheckSafety) {
    $pyArgs += "--check-safety"
    if ($Code) { $pyArgs += "--code"; $pyArgs += $Code }
    if ($File) { $pyArgs += "--file"; $pyArgs += $File }
} elseif ($Log) {
    $pyArgs += "--log"
} else {
    $pyArgs += "--run"
    $pyArgs += "--language"; $pyArgs += $Language
    $pyArgs += "--timeout"; $pyArgs += $Timeout
    if ($Code) { $pyArgs += "--code"; $pyArgs += $Code }
    if ($File) { $pyArgs += "--file"; $pyArgs += $File }
    if ($Network) { $pyArgs += "--network" }
    if ($KeepFiles) { $pyArgs += "--keep-files" }
}

if ($Json) {
    $pyArgs += "--json"
}

try {
    $output = & python $SandboxManager @pyArgs 2>&1
    $exitCode = $LASTEXITCODE
} catch {
    Write-Error "Failed to execute sandbox-manager.py: $_"
    exit 1
}

if ($Json) {
    try {
        $parsed = $output | Out-String | ConvertFrom-Json
        Write-Output ($parsed | ConvertTo-Json -Depth 10)
    } catch {
        Write-Output ($output | Out-String)
    }
} else {
    Write-Output ($output | Out-String)
}

exit $exitCode
