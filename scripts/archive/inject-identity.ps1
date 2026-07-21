<#
.SYNOPSIS
    Injects the current identity profile as a session prompt fragment.

.DESCRIPTION
    Calls identity-manager.py --render to generate a markdown session identity
    block and outputs it to stdout. Designed to be called from AGENTS.md or
    session startup scripts.

.PARAMETER IdentityScript
    Path to identity-manager.py. Defaults to <repo-root>\scripts\identity-manager.py.

.PARAMETER Python
    Path to python executable. Defaults to python.

.EXAMPLE
    .\scripts\inject-identity.ps1
    # Outputs session identity markdown to stdout

.EXAMPLE
    .\scripts\inject-identity.ps1 -Python python3
    # Uses python3 explicitly
#>

param(
    [string]$IdentityScript = "",
    [string]$Python = "python"
)

# Resolve project root from script location
$ScriptPath = if ($IdentityScript) { $IdentityScript } else { $PSScriptRoot }
$ProjectRoot = if ($IdentityScript) {
    Split-Path -Parent (Split-Path -Parent $IdentityScript)
} else {
    Split-Path -Parent $PSScriptRoot
}

$ManagerScript = Join-Path -Path $ProjectRoot -ChildPath "scripts\identity-manager.py"

if (-not (Test-Path -LiteralPath $ManagerScript)) {
    Write-Warning "identity-manager.py not found at: $ManagerScript"
    Write-Output "## Session Identity"
    Write-Output "Persona: (script not found)"
    exit 1
}

try {
    $result = & $Python $ManagerScript --render 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Output $result
    } else {
        Write-Warning "identity-manager.py exited with code $LASTEXITCODE"
        Write-Output "## Session Identity"
        Write-Output "Persona: (error during render)"
    }
}
catch {
    Write-Warning "Failed to run identity-manager.py: $_"
    Write-Output "## Session Identity"
    Write-Output "Persona: (runtime error)"
    exit 1
}
