---
name: inno-setup-pipeline
description: Build Inno Setup installers in GitHub Actions, sign them, and publish to GitHub Releases. Use when setting up CI/CD for a Windows .exe installer, automating release builds, or adding code signing to an Inno Setup pipeline.
---

# Inno Setup Pipeline — GitHub Actions CI/CD

Automate compiling an Inno Setup `.iss` script into a signed `.exe` installer and publishing it to GitHub Releases — all triggered by pushing a tag.

## When to Use This Skill

- Setting up GitHub Actions to auto-build a Windows installer on tag push
- Adding code signing to an existing Inno Setup project
- Automating release creation with installer artifacts
- Replacing manual `iscc` compilation with CI
- Migrating from chocolatey local builds to CI/CD

## Architecture

```
Push tag v1.0.0
       │
       ▼
 ┌─────────────────┐
 │ GitHub Actions   │
 │ (windows-latest) │
 └─────────────────┘
       │
       ▼
 ┌─────────────────┐
 │ Install Inno     │  (choco install innosetup)
 │ Setup 6          │
 └─────────────────┘
       │
       ▼
 ┌─────────────────┐
 │ Compile .iss     │  (ISCC.exe installer.iss)
 │ → .exe           │
 └─────────────────┘
       │
       ▼
 ┌─────────────────┐
 │ Sign the .exe    │  (signtool + .pfx cert)
 │                  │
 └─────────────────┘
       │
       ▼
 ┌─────────────────┐
 │ Publish Release  │  (gh release upload)
 │ (draft)          │
 └─────────────────┘
       │
       ▼
   Manual smoke-test → flip to published
```

## Setup

### 1. Install Inno Setup locally (for development)

```powershell
# Download from https://jrsoftware.org/isdl.php
# Or via winget:
winget install --id JordanRussell.InnoSetup
```

### 2. Create your `.iss` script

Example structure matching this repo:

```
project/
├── installer/
│   ├── myapp.iss          # Inno Setup script
│   └── icons/             # Installer assets
├── src/                   # Your app source
└── .github/
    └── workflows/
        └── release.yml    # CI workflow
```

### 3. Compile locally to test

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\myapp.iss
```

## GitHub Actions Workflow

### Basic workflow (unsigned)

Create `.github/workflows/release.yml`:

```yaml
name: Build Installer

on:
  push:
    tags:
      - "v*"          # Triggers on any v1.0.0, v2.1.3, etc.

permissions:
  contents: write      # Needed to upload to Release

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      # Inno Setup is NOT pre-installed on windows-2025 runners
      # (actions/runner-images#12464). Install it via choco:
      - name: Install Inno Setup
        run: choco install innosetup --no-progress
        shell: pwsh

      - name: Compile installer
        run: |
          & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" `
            installer\myapp.iss `
            /DAppVersion=${{ github.ref_name }} `
            /Qp
        shell: pwsh

      - name: Verify artifact exists
        run: |
          $artifact = Get-ChildItem -Path installer\Output -Filter "*.exe" | Select-Object -First 1
          if (-not $artifact) { throw "No .exe found in installer\Output\" }
          $size = [math]::Round($artifact.Length / 1MB, 1)
          $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.FullName).Hash
          Write-Host "Artifact: $($artifact.Name) ($size MB)"
          Write-Host "SHA-256: $sha"
        shell: pwsh

      - name: Upload to Release
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh release upload ${{ github.ref_name }} `
            installer\Output\*.exe `
            --clobber
        shell: pwsh
```

### Workflow with code signing

```yaml
# Add to the workflow above, between "Compile" and "Upload" steps:

      - name: Sign the installer
        env:
          PFX_BASE64: ${{ secrets.WINDOWS_PFX }}
          PFX_PASSWORD: ${{ secrets.WINDOWS_PFX_PASSWORD }}
        run: |
          $pfxPath = "$env:TEMP\cert.pfx"
          [IO.File]::WriteAllBytes($pfxPath, [Convert]::FromBase64String($env:PFX_BASE64))

          $artifact = Get-ChildItem -Path installer\Output -Filter "*.exe" | Select-Object -First 1

          & "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe" sign `
            /fd SHA256 `
            /a `
            /f $pfxPath `
            /p $env:PFX_PASSWORD `
            /tr http://timestamp.digicert.com `
            /td SHA256 `
            $artifact.FullName

          Remove-Item $pfxPath -Force
        shell: pwsh
```

## Code Signing Setup

### Getting a certificate

| Option | Cost | Trust Level |
|--------|------|-------------|
| **DigiCert / Sectigo** | ~$300/yr | Full SmartScreen trust |
| **Self-signed** | Free | No trust — test only |
| **Azure Key Vault** | ~$10/mo | Enterprise signing pipeline |

### Storing the certificate in GitHub Secrets

```powershell
# Convert .pfx to base64
$pfx = [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\path\to\cert.pfx"))
Write-Host $pfx  # Copy this

# Add to GitHub:
#   repo → Settings → Secrets and variables → Actions
#   New repository secret:
#     Name: WINDOWS_PFX
#     Value: <paste base64>
#     Name: WINDOWS_PFX_PASSWORD
#     Value: <certificate password>
```

## Versioning Strategy

Stamp the version into your installer using `/DAppVersion=`:

```pascal
; In your .iss file:
#define MyAppVersion GetEnv('AppVersion')
; Fallback for local builds:
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
```

The GitHub workflow passes the tag:
```yaml
/DAppVersion=${{ github.ref_name }}
```

This lets you:
1. Build locally without a version (defaults to 0.0.0)
2. CI builds stamp the tag version

## Release Workflow

```
1. Developer: git tag v1.0.0 && git push --tags
2. GitHub Actions: builds, signs, uploads as DRAFT release
3. Developer: downloads .exe, smoke-tests on clean Windows VM
4. Developer: flips draft → published in GitHub UI
5. Users: download from Releases page
```

### Draft releases

Use `draft: true` when creating the release so it's not public until you verify the installer works:

```yaml
- uses: softprops/action-gh-release@v2
  with:
    files: installer/Output/*.exe
    draft: true
    generate_release_notes: true
```

## Inno Setup + Pascal Scripting Quick Reference

| Task | Pascal Code |
|------|-------------|
| Download file | `DownloadFile(URL, Dest, ErrorMsg)` |
| Run command | `Exec('cmd.exe', '/C dir', '', SW_HIDE, ewWaitUntilTerminated, Code)` |
| Create progress bar | `CreateOutputProgressPage('Title', 'Description')` |
| Add custom wizard page | `CreateInputOptionPage(ID, 'Title', 'Desc', 'Text', True, False)` |
| Skip a page conditionally | `ShouldSkipPage(PageID): Boolean` |
| Write text file | `SaveStringsToFile(Path, Lines, False)` |
| Delete directory | `DelTree(Path, True, True, True)` |

## Common Issues

| Issue | Fix |
|-------|-----|
| `ISCC.exe not found` | Install via `choco install innosetup` (windows-2025 runners) |
| `signtool not found` | Install Windows SDK: `choco install windows-sdk-10-version-2001-windows10sdk` |
| SmartScreen blocks installer | Add code signing, or instruct users to right-click → Properties → Unblock |
| Docker not starting in time | Add retry loop in Inno Pascal code (up to 30 seconds) |
| GitHub Release already exists | Use `--clobber` flag on `gh release upload` |
| Runner out of disk space | Clean `C:\ProgramData\Docker` or use larger runner |

## References

- [Inno Setup Documentation](https://jrsoftware.org/ishelp.php)
- [Inno-Setup-Action (GitHub)](https://github.com/Minionguyjpro/Inno-Setup-Action)
- [action-gh-release](https://github.com/softprops/action-gh-release)
- [Windows SDK + signtool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
