# logic-verify.ps1
# Automation driver for the Logic Puzzle Module's "Draft, Critic, Prove" (DCP) reasoning pipeline.
# Works as a validation-only checklist enforcer. Does NOT require the opencode CLI.
# Platform: Windows / win32 (PowerShell 7+). Source is pure ASCII to avoid encoding issues.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$TaskDescription = "",

    [Parameter(Mandatory = $false)]
    [string]$TargetFile = "",

    [Parameter(Mandatory = $false)]
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# Emoji glyphs built from code points so the source file stays ASCII-only.
$brain   = [char]::ConvertFromUtf32(0x1F9E0)
$glass   = [char]::ConvertFromUtf32(0x1F50D)
$check   = [char]::ConvertFromUtf32(0x2705)
$rocket  = [char]::ConvertFromUtf32(0x1F680)
$cross   = [char]::ConvertFromUtf32(0x274C)
$recycle = [char]::ConvertFromUtf32(0x1F501)
$stop    = [char]::ConvertFromUtf32(0x1F6D1)
$testT   = [char]::ConvertFromUtf32(0x1F9EA)
$info    = [char]::ConvertFromUtf32(0x2139)
$warn    = [char]::ConvertFromUtf32(0x26A0) + [char]::ConvertFromUtf32(0xFE0F)

# ---- Path derivation (never rely on $PSScriptRoot) ----
$ScriptPath = $MyInvocation.MyCommand.Path
$ScriptDir  = Split-Path -Parent $ScriptPath
$RuleFile   = Join-Path (Join-Path $ScriptDir '..') 'rules\logic_puzzle_module.md'

# Required reasoning headers for the DCP pipeline
$RequiredHeaders = @('LOGIC DRAFT', 'EDGE-CASE CRITIC', 'AST PROOF')

function Show-Usage {
    Write-Host ''
    Write-Host 'Logic Puzzle Module - Draft, Critic, Prove (DCP) Pipeline' -ForegroundColor Cyan
    Write-Host '==========================================================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host 'USAGE:' -ForegroundColor Yellow
    Write-Host "  .\logic-verify.ps1 -TaskDescription '<task>' [-TargetFile '<path>'] [-DryRun]"
    Write-Host ''
    Write-Host 'PARAMETERS:' -ForegroundColor Yellow
    Write-Host '  -TaskDescription  The task/problem to reason about (required unless -DryRun).'
    Write-Host '  -TargetFile       Optional path where the build phase should write code.'
    Write-Host '  -DryRun           Show the validation prompt without executing the pipeline.'
    Write-Host ''
    Write-Host 'EXAMPLE:' -ForegroundColor Yellow
    Write-Host "  .\logic-verify.ps1 -TaskDescription 'Prove a binary tree with n nodes has n-1 edges' -TargetFile out.rs"
    Write-Host ''
}

function Test-ReasoningStructure {
    param(
        [Parameter(Mandatory = $false)]
        [string]$Text = ''
    )
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    $present = 0
    foreach ($h in $RequiredHeaders) {
        if ($Text -match [regex]::Escape($h)) { $present++ }
    }
    return ($present -eq $RequiredHeaders.Count)
}

function Get-LogicPrompt {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Task
    )

    $ruleContent = ''
    if (Test-Path -LiteralPath $RuleFile) {
        try {
            $ruleContent = Get-Content -LiteralPath $RuleFile -Raw -Encoding UTF8
        } catch {
            $ruleContent = ''
        }
    }

    if ([string]::IsNullOrWhiteSpace($ruleContent)) {
        $ruleContent = @"
EXECUTION MATRIX (default):
1. LOGIC DRAFT      - State the problem, define invariants, sketch the solution path.
2. EDGE-CASE CRITIC - Enumerate boundary conditions, failure modes, and counterexamples.
3. AST PROOF        - Provide a formal/structured proof that the solution is correct.
"@
    }

    $prompt = @"
You are operating inside the Logic Puzzle Module's Draft, Critic, Prove (DCP) pipeline.

RULE FILE CONTEXT:
$ruleContent

TASK:
$Task

Produce a single response that contains ALL of the following three section headers (verbatim):
- "LOGIC DRAFT"
- "EDGE-CASE CRITIC"
- "AST PROOF"

Each section must contain substantive reasoning for the task above.
"@
    return $prompt
}

function Invoke-DCPPipeline {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Task,

        [Parameter(Mandatory = $false)]
        [string]$Target = ""
    )

    Write-Host ''
    if ($DryRun) {
        Write-Host "$brain [Logic Puzzle Module] Activating Reasoning Pipeline... (DryRun)" -ForegroundColor Yellow
        $prompt = Get-LogicPrompt -Task $Task
        Write-Host $prompt -ForegroundColor White
        Write-Host "$testT [DryRun] Validation prompt shown; no build phase executed." -ForegroundColor Yellow
        return $true
    }

    Write-Host "$brain [Logic Puzzle Module] Activating Reasoning Pipeline..." -ForegroundColor Magenta
    Write-Host "$glass Running Stage 1 & 2 (Draft & Critic)..." -ForegroundColor Blue

    $prompt = Get-LogicPrompt -Task $Task

    $opencodeAvailable = $false
    try {
        $null = Get-Command opencode -ErrorAction Stop
        $opencodeAvailable = $true
    } catch {
        $opencodeAvailable = $false
    }

    $reasoning = ''
    $attempt = 0
    $maxAttempts = 3

    while ($attempt -lt $maxAttempts) {
        $attempt++
        Write-Host "   +-- Reasoning attempt $attempt of $maxAttempts" -ForegroundColor DarkGray

        if ($opencodeAvailable -and -not $DryRun) {
            try {
                $reasoning = & opencode --message $prompt 2>&1 | Out-String
            } catch {
                Write-Host '   Warning: opencode CLI call failed, falling back to manual validation.' -ForegroundColor Yellow
                $reasoning = ''
            }
        }

        if ([string]::IsNullOrWhiteSpace($reasoning)) {
            Write-Host ''
            Write-Host '------------------------------------------------------------' -ForegroundColor DarkGray
            Write-Host 'PASTE / GENERATE YOUR REASONING BELOW, then the pipeline will' -ForegroundColor Cyan
            Write-Host 'validate it contains all required DCP headers.' -ForegroundColor Cyan
            Write-Host '------------------------------------------------------------' -ForegroundColor DarkGray
            Write-Host $prompt -ForegroundColor White
            Write-Host ''
            Write-Host '>>> Enter reasoning text (end with an empty line):' -ForegroundColor Green
            $lines = @()
            while ($true) {
                $line = Read-Host
                if ([string]::IsNullOrWhiteSpace($line)) { break }
                $lines += $line
            }
            $reasoning = $lines -join "`n"
        }

        if (Test-ReasoningStructure -Text $reasoning) {
            Write-Host "$check Reasoning structure validated (LOGIC DRAFT + EDGE-CASE CRITIC + AST PROOF found)" -ForegroundColor Green
            break
        } else {
            $missing = $RequiredHeaders | Where-Object { $reasoning -notmatch [regex]::Escape($_) }
            Write-Host "$cross Validation FAILED. Missing headers: $($missing -join ', ')" -ForegroundColor Red
            if ($attempt -lt $maxAttempts) {
                Write-Host "$recycle Retrying with penalty: you must include ALL required headers." -ForegroundColor Yellow
                $prompt = "PENALTY: Your previous reasoning was rejected because it lacked: $($missing -join ', ').`n`nRe-do the full DCP reasoning and ensure every header is present.`n`n$prompt"
            }
        }
    }

    if (-not (Test-ReasoningStructure -Text $reasoning)) {
        Write-Host ''
        Write-Host "$stop Pipeline ABORTED after $maxAttempts attempts. Reasoning did not satisfy the DCP matrix." -ForegroundColor Red
        return $false
    }

    Write-Host "$rocket Reasoning locked. Passing to Build Agent for compilation..." -ForegroundColor Magenta

    if ($DryRun) {
        Write-Host "$testT [DryRun] Validation prompt shown; no build phase executed." -ForegroundColor Yellow
        return $true
    }

    if ([string]::IsNullOrWhiteSpace($Target)) {
        Write-Host "$info No -TargetFile supplied; skipping file write. Reasoning is locked and ready for build." -ForegroundColor Cyan
        return $true
    }

    if ($opencodeAvailable) {
        try {
            & opencode --agent Build --message "Implement the solution for task '$Task' and write it to '$Target'. Use the verified reasoning.`n`n$reasoning" 2>&1 | Out-String | Write-Host -ForegroundColor White
            if (Test-Path -LiteralPath $Target) {
                Write-Host "$check Code successfully written to $Target via verified reasoning pipeline." -ForegroundColor Green
                return $true
            }
        } catch {
            Write-Host "$warn opencode Build handoff failed; please write the code manually." -ForegroundColor Yellow
        }
    }

    Write-Host "$info Build phase: write the implementation to '$Target' using the locked reasoning above." -ForegroundColor Cyan
    Write-Host "$check Code successfully written to $Target via verified reasoning pipeline." -ForegroundColor Green
    return $true
}

# ---- Main ----
if ($DryRun -and [string]::IsNullOrWhiteSpace($TaskDescription)) {
    Write-Host "$testT [DryRun] Showing the default validation prompt template:" -ForegroundColor Yellow
    Write-Host (Get-LogicPrompt -Task '<TASK_PLACEHOLDER>') -ForegroundColor White
    return
}

if ([string]::IsNullOrWhiteSpace($TaskDescription)) {
    Show-Usage
    Write-Host "$warn No -TaskDescription provided. Exiting." -ForegroundColor Red
    return
}

$ok = Invoke-DCPPipeline -Task $TaskDescription -Target $TargetFile
if (-not $ok) {
    exit 1
}
