# NE-Memory Status Checker (PowerShell wrapper)
# Delegates to check-status.py for the actual check

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
python "$ProjectRoot\scripts\check-status.py"
