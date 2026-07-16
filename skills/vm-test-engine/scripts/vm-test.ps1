#!/usr/bin/env pwsh
<#
.SYNOPSIS
    VM Test Engine — Provision, snapshot, test, destroy VMs.
.DESCRIPTION
    Full lifecycle management for test VMs across Hyper-V, VirtualBox, and QEMU/KVM.
    
    .\scripts\vm-test.ps1 -Provider hyperv -OS windows11 -Name "installer-test"
    .\scripts\vm-test.ps1 -Provider vagrant -OS ubuntu -Name "linux-test"
    .\scripts\vm-test.ps1 -ListTemplates
    .\scripts\vm-test.ps1 -Name "installer-test" -Destroy
.PARAMETER Provider
    Hypervisor: hyperv, vagrant, qemu (default: hyperv)
.PARAMETER OS
    OS template: windows11, windows10, ubuntu, debian (default: windows11)
.PARAMETER Name
    VM name (default: auto-generated)
.PARAMETER Memory
    Memory in GB (default: 4)
.PARAMETER Cores
    CPU cores (default: 2)
.PARAMETER Snapshot
    Create a snapshot after provisioning (default: baseline)
.PARAMETER Restore
    Restore to named snapshot
.PARAMETER Destroy
    Delete the VM
.PARAMETER ListTemplates
    Show available OS templates
#>

param(
    [ValidateSet("hyperv", "vagrant", "qemu")]
    [string]$Provider = "hyperv",
    [ValidateSet("windows11", "windows10", "ubuntu", "debian", "ubuntu-server")]
    [string]$OS = "windows11",
    [string]$Name = "",
    [int]$Memory = 4,
    [int]$Cores = 2,
    [string]$Snapshot = "",
    [string]$Restore = "",
    [switch]$Destroy,
    [switch]$ListTemplates
)

$Templates = @{
    windows11 = @{ VagrantBox = "gusztavvargadr/windows-11-24h2-enterprise"; HyperVISO = "Win11_24H2_English_x64.iso"; Memory = 4; Cores = 2 }
    windows10 = @{ VagrantBox = "gusztavvargadr/windows-10-22h2-enterprise"; HyperVISO = "Win10_22H2_English_x64.iso"; Memory = 4; Cores = 2 }
    ubuntu = @{ VagrantBox = "ubuntu/jammy64"; Memory = 2; Cores = 2 }
    debian = @{ VagrantBox = "debian/bookworm64"; Memory = 2; Cores = 1 }
    "ubuntu-server" = @{ QEMUImage = "ubuntu-24.04-server-cloudimg-amd64.img"; Memory = 2; Cores = 2 }
}

function Show-Templates {
    Write-Host "Available VM Templates:" -ForegroundColor Cyan
    foreach ($t in $Templates.Keys) {
        $info = $Templates[$t]
        $sources = @()
        if ($info.VagrantBox) { $sources += "Vagrant: $($info.VagrantBox)" }
        if ($info.HyperVISO) { $sources += "Hyper-V ISO" }
        if ($info.QEMUImage) { $sources += "QEMU image" }
        Write-Host "  $t — $($sources -join ', ') — $($info.Memory)GB/$($info.Cores) cores"
    }
}

function New-HyperVVM {
    param($VMName, $Template)
    Write-Host "Creating Hyper-V VM: $VMName" -ForegroundColor Yellow

    # Create VM
    New-VM -Name $VMName -MemoryStartupBytes ($Memory * 1GB) -Generation 2
    Set-VM -Name $VMName -ProcessorCount $Cores
    Set-VMMemory -Name $VMName -DynamicMemoryEnabled $true -MinimumBytes 512MB -MaximumBytes ($Memory * 1GB)

    # Create virtual disk
    $vhdPath = "$env:ProgramData\Microsoft\Windows\Hyper-V\Virtual Hard Disks\$VMName.vhdx"
    New-VHD -Path $vhdPath -SizeBytes 80GB -Dynamic
    Add-VMHardDiskDrive -VMName $VMName -Path $vhdPath

    # Add network
    Add-VMNetworkAdapter -VMName $VMName -SwitchName "Default Switch"

    # Enable guest services
    Enable-VMIntegrationService -VMName $VMName -Name "Guest Service Interface"

    Write-Host "  VM created. Start with: Start-VM -Name $VMName" -ForegroundColor Green
}

function New-VagrantVM {
    param($VMName, $Template)
    Write-Host "Creating Vagrant VM: $VMName ($($Template.VagrantBox))" -ForegroundColor Yellow

    $dir = "$env:TEMP\vagrant-$VMName"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Set-Location $dir

    @"
Vagrant.configure("2") do |config|
  config.vm.box = "$($Template.VagrantBox)"
  config.vm.hostname = "$VMName"
  config.vm.provider "hyperv" do |h|
    h.memory = $($Memory * 1024)
    h.cpus = $Cores
  end
end
"@ | Out-File "Vagrantfile" -Encoding UTF8

    vagrant up
    Write-Host "  VM ready. SSH: cd $dir && vagrant ssh" -ForegroundColor Green
}

switch ($true) {
    $ListTemplates { Show-Templates; return }
    $Destroy -and $Name {
        switch ($Provider) {
            "hyperv" { Stop-VM -Name $Name -TurnOff -ErrorAction SilentlyContinue; Remove-VM -Name $Name -Force }
            "vagrant" { vagrant destroy -f }
        }
        Write-Host "Destroyed: $Name" -ForegroundColor Yellow
        return
    }
    $Restore -and $Name {
        switch ($Provider) {
            "hyperv" { Restore-VMSnapshot -VMName $Name -Name $Restore -Confirm:$false }
            "vagrant" { vagrant snapshot restore $Restore }
        }
        Write-Host "Restored snapshot '$Restore' on $Name" -ForegroundColor Green
        return
    }
    $Snapshot -and $Name {
        switch ($Provider) {
            "hyperv" { Checkpoint-VM -Name $Name -SnapshotName $Snapshot }
            "vagrant" { vagrant snapshot save $Snapshot }
        }
        Write-Host "Snapshot '$Snapshot' saved on $Name" -ForegroundColor Green
        return
    }
    default {
        if (-not $Name) { $Name = "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
        $template = $Templates[$OS]
        if (-not $template) { Write-Host "Unknown OS: $OS"; Show-Templates; return }

        switch ($Provider) {
            "hyperv" { New-HyperVVM -VMName $Name -Template $template }
            "vagrant" { New-VagrantVM -VMName $Name -Template $template }
            "qemu" { Write-Host "QEMU provisioning requires cloud-init — see SKILL.md" -ForegroundColor Yellow }
        }

        if ($Snapshot) {
            Start-Sleep 5
            switch ($Provider) {
                "hyperv" { Checkpoint-VM -VMName $Name -SnapshotName $Snapshot }
                "vagrant" { vagrant snapshot save $Snapshot }
            }
        }
    }
}
