# Building the Installer

## Prerequisites
1. Download and install **Inno Setup 6+**: https://jrsoftware.org/isdl.php
2. Clone this repo

## Build
```powershell
iscc .\opencode-container-server.iss
```

Output: `opencode-container-server-setup.exe`

## What the installer does
1. Welcome screen explaining what's being installed
2. Docker Desktop license agreement (shown only if Docker isn't installed)
3. Downloads Docker Desktop (~500MB) with progress bar — **silent install, no clicks needed**
4. Downloads the compose file + Dockerfile from GitHub
5. Builds the container (`docker compose up -d --build`) with progress bar
6. Creates Start Menu shortcuts (View Logs, Uninstall, Connect)
7. Creates optional desktop shortcut
8. On uninstall: stops the container, removes the image, deletes config files
