# VM Test Engine — Virtual OS Deployment & Testing Framework

Automated virtual machine provisioning, OS deployment, snapshot management, and destructive testing across multiple hypervisors and cloud platforms. Designed for testing installers, networking configs, and full-system integration scenarios.

## When to Use This Skill

- Testing an installer (Inno Setup, MSI, etc.) on a clean OS
- Validating network configurations across multiple VMs
- Running destructive tests (power loss, disk full, corrupt config)
- Automating OS deployment for CI/CD pipelines
- Testing cross-platform compatibility (Windows, Linux, macOS)
- Setting up isolated test environments with snapshots
- Creating reproducible bug-report environments

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    VM Test Engine                         │
├──────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Hyper-V     │  │  VirtualBox  │  │  QEMU/KVM    │   │
│  │  (Windows)   │  │  (Cross-plat)│  │  (Linux)     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                  │           │
│  ┌──────┴─────────────────┴──────────────────┴───────┐   │
│  │              Provisioning Layer                     │   │
│  │  Vagrant  │  Packer  │  cloud-init  │  Ansible    │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                  │
│  ┌──────────────────────┴──────────────────────────────┐   │
│  │              Testing Layer                            │   │
│  │  Snapshot/Rollback  │  Destructive Tests             │   │
│  │  Network Isolation  │  Integration Tests             │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                  │
│  ┌──────────────────────┴──────────────────────────────┐   │
│  │              CI/CD Integration                       │   │
│  │  GitHub Actions  │  Self-Hosted Runners             │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

## Quick Start — Spin Up a Test VM

### Windows (Hyper-V)
```powershell
# Create a Windows 11 test VM with auto-install
.\scripts\vm-test.ps1 -Provider hyperv -OS windows11 -Name "installer-test" -Snapshot
```

### Cross-Platform (Vagrant)
```powershell
# Spin up a Linux VM for testing
vagrant init ubuntu/jammy64
vagrant up
vagrant ssh
```

### Linux (QEMU/KVM)
```bash
# Quick VM with cloud-init
./scripts/vm-test.sh --provider qemu --os ubuntu-server --name test-vm
```

## Hypervisor Comparison

| Feature | Hyper-V | VirtualBox | QEMU/KVM | VMware |
|---------|---------|------------|----------|--------|
| **Host OS** | Windows Pro/Enterprise | Win/Mac/Linux | Linux | Win/Linux |
| **Performance** | Native (Type 1) | Good (Type 2) | Near-native (Type 1) | Good |
| **Snapshot** | Yes (production checkpoints) | Yes | Yes (qemu-img) | Yes |
| **Nested VM** | Yes (Hyper-V inside) | Limited | Yes | Yes |
| **GPU Passthrough** | Yes (DDA) | No | Yes (VFIO) | Yes |
| **CLI Management** | PowerShell | VBoxManage | virsh/qemu | vmrun |
| **Best for** | Windows testing | Cross-platform dev | Linux/container testing | Enterprise | 
| **Cost** | Included w/ Windows Pro | Free | Free | Paid |

## VM Provisioning Methods

### 1. Vagrant (Easiest — Cross-Platform)

Vagrant provides declarative VM management with a single `Vagrantfile`.

```ruby
# Vagrantfile — Windows test machine
Vagrant.configure("2") do |config|
  config.vm.box = "gusztavvargadr/windows-11-24h2-enterprise"
  config.vm.hostname = "installer-test"

  config.vm.provider "hyperv" do |h|
    h.memory = 4096
    h.cpus = 2
    h.enable_enhanced_session_mode = true
  end

  # Provision: copy installer and run
  config.vm.provision "file", source: "./setup.exe", destination: "C:\\setup.exe"
  config.vm.provision "shell", inline: "C:\\setup.exe /VERYSILENT"

  # Snapshot after provisioning
  config.trigger.after :up do |trigger|
    trigger.run = { inline: "vagrant snapshot save baseline" }
  end
end
```

```bash
# Commands
vagrant up                  # Create and provision
vagrant snapshot save base  # Save clean state
vagrant snapshot restore base  # Restore to clean
vagrant destroy -f          # Destroy VM
```

### 2. Packer (Immutable Images)

Packer builds reusable VM images (boxes, AMIs, VHDXs) with pre-installed software.

```hcl
# windows-test.pkr.hcl
source "hyperv-iso" "windows-11" {
  iso_url = "https://software.download.prss.microsoft.com/dbazure/Win11_24H2_English_x64.iso"
  iso_checksum = "sha256:..."
  vm_name = "windows-11-test"
  memory = 4096
  cpu = 2
  communicator = "winrm"
  winrm_username = "vagrant"
  winrm_password = "vagrant"

  # Autounattend for unattended install
  floppy_files = ["Autounattend.xml"]
}

build {
  sources = ["source.hyperv-iso.windows-11"]

  provisioner "powershell" {
    inline = [
      "Set-ExecutionPolicy Bypass -Scope Process -Force",
      "Install-WindowsFeature -Name Hyper-V-PowerShell"
    ]
  }

  post-processor "vagrant" {
    output = "windows-11-test.box"
  }
}
```

```bash
packer build windows-test.pkr.hcl
vagrant box add windows-11-test.box --name windows-11-test
```

### 3. Cloud-Init (Linux, QEMU)

```yaml
# cloud-init.yaml
#cloud-config
hostname: test-vm
users:
  - name: tester
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-rsa AAAAB3...your-public-key
packages:
  - docker.io
  - git
runcmd:
  - systemctl start docker
  - docker run -d -p 3100:3100 ohmpatel3877/opencode-container-server
```

```bash
# Create disk image with cloud-init
cloud-localds seed.img cloud-init.yaml
qemu-img create -f qcow2 test-vm.qcow2 40G

# Boot VM
qemu-system-x86_64 \
  -machine q35,accel=kvm \
  -cpu host \
  -smp 2 \
  -m 4096 \
  -drive file=ubuntu-server.iso,media=cdrom \
  -drive file=seed.img,media=cdrom \
  -drive file=test-vm.qcow2,format=qcow2 \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device e1000,netdev=net0 \
  -nographic
```

## Testing Workflows

### Installer Testing (The Primary Use Case)

```
1. vagrant snapshot restore baseline
2. Copy installer into VM (vagrant provision or scp)
3. Run installer silently
4. Verify: service running, files exist, registry keys set
5. Run uninstaller
6. Verify: service stopped, files removed
7. vagrant snapshot restore baseline  (reset for next test)
```

#### Windows Installer Test Script

```powershell
# test-installer.ps1
param(
  [string]$VM = "installer-test",
  [string]$InstallerPath = ".\setup.exe",
  [string]$TestType = "install"  # install, uninstall, upgrade
)

# Restore to clean state
vagrant snapshot restore baseline

# Copy installer
Copy-Item $InstallerPath "\\$VM\C$\setup.exe"

switch ($TestType) {
  "install" {
    # Run installer
    Invoke-VMScript -VM $VM -Script "C:\setup.exe /VERYSILENT /LOG=C:\install.log"

    # Verify installation
    $installed = Invoke-VMScript -VM $VM -Script "Test-Path 'C:\Program Files\opencode-container-server'"
    if (-not $installed) { throw "Installation failed" }

    # Verify service
    $service = Invoke-VMScript -VM $VM -Script "Get-Service opencode-server -ErrorAction SilentlyContinue"
    if (-not $service) { throw "Service not created" }

    Write-Host "INSTALL TEST: PASSED"
  }

  "uninstall" {
    # First install
    Invoke-VMScript -VM $VM -Script "C:\setup.exe /VERYSILENT"

    # Run uninstaller
    Invoke-VMScript -VM $VM -Script "& 'C:\Program Files\opencode-container-server\unins000.exe' /VERYSILENT"

    # Verify removed
    $removed = Invoke-VMScript -VM $VM -Script "! (Test-Path 'C:\Program Files\opencode-container-server')"
    if (-not $removed) { throw "Uninstall failed" }

    Write-Host "UNINSTALL TEST: PASSED"
  }
}
```

### Destructive Testing

Test how your software handles edge cases:

| Test | Method | What to verify |
|------|--------|----------------|
| **Disk full** | Fill disk with `fsutil file createnew` | Graceful error, no data loss |
| **Power loss** | `Stop-VM -TurnOff` then `Start-VM` | Recovery on boot, no corruption |
| **Network drop** | Disconnect VM NIC | Reconnection logic, queuing |
| **Memory pressure** | Reduce VM memory to minimum | OOM handling, graceful degradation |
| **Corrupt config** | Replace config file with garbage | Validation, fallback to defaults |
| **Clock skew** | Set VM date to 2030 | Certificate validation, expiry handling |

```powershell
# destructive-test.ps1
param([string]$VM = "installer-test")

# Snapshot clean state
vagrant snapshot restore baseline

# Test: Disk full
Write-Host "=== Test: Disk Full ===" -ForegroundColor Cyan
Invoke-VMScript -VM $VM -Script "fsutil file createnew C:\fill.disk 5000000000"  # 5GB
$result = Invoke-VMScript -VM $VM -Script "& 'C:\setup.exe' /VERYSILENT 2>&1"
if ($result -match "error|fail|disk space") {
  Write-Host "  PASS: Graceful error on disk full" -ForegroundColor Green
} else {
  Write-Host "  FAIL: No disk space handling" -ForegroundColor Red
}

# Restore for next test
vagrant snapshot restore baseline

# Test: Power loss
Write-Host "=== Test: Power Loss ===" -ForegroundColor Cyan
Invoke-VMScript -VM $VM -Script "C:\setup.exe /VERYSILENT"
Stop-VM -Name $VM -TurnOff
Start-Sleep 5
Start-VM -Name $VM
Start-Sleep 30  # Wait for boot
$service = Invoke-VMScript -VM $VM -Script "Get-Service opencode-server -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Status"
if ($service -eq "Running") {
  Write-Host "  PASS: Service recovered after power loss" -ForegroundColor Green
} else {
  Write-Host "  FAIL: Service did not recover" -ForegroundColor Red
}
```

## Network Topologies for Testing

```powershell
# Isolated network (no internet — test offline behavior)
New-VMSwitch -Name "Isolated" -SwitchType Internal

# NAT network (internet access, isolated from LAN)
New-VMSwitch -Name "NATNetwork" -SwitchType NAT

# Multi-VM network (test client-server)
New-VMSwitch -Name "TestNetwork" -SwitchType Private
# Add VMs to same switch for LAN testing
```

## Scripts Reference

### `vm-test.ps1` — Full VM lifecycle management

```powershell
# Create, provision, test, destroy
.\scripts\vm-test.ps1 -Provider hyperv -OS windows11 -Name "installer-test" -Memory 4GB -Cores 2
.\scripts\vm-test.ps1 -Provider vagrant -OS ubuntu -Name "linux-test"
.\scripts\vm-test.ps1 -ListTemplates    # List available OS templates
.\scripts\vm-test.ps1 -Snapshot "baseline" -Restore  # Restore to known state
```

### `test-installer.ps1` — Automated installer testing loop

```powershell
.\scripts\test-installer.ps1 -VM "installer-test" -Installer ".\setup.exe" -TestType install
.\scripts\test-installer.ps1 -VM "installer-test" -TestType uninstall
.\scripts\test-installer.ps1 -VM "installer-test" -TestType destructive
```

## CI/CD Integration (GitHub Actions)

```yaml
name: VM Test Installer

on:
  workflow_dispatch:
  release:
    types: [published]

jobs:
  test-installer:
    runs-on: [self-hosted, windows, hyperv]
    steps:
      - uses: actions/checkout@v4

      - name: Restore baseline VM
        run: vagrant snapshot restore baseline
        working-directory: ./test-vms/windows-11

      - name: Copy installer
        run: |
          Copy-Item ".\setup.exe" "\\installer-test\C$\setup.exe"

      - name: Run installer
        run: |
          $result = Invoke-VMScript -VM "installer-test" -Script "C:\setup.exe /VERYSILENT"
          if ($LASTEXITCODE -ne 0) { throw "Install failed" }

      - name: Verify installation
        run: |
          $files = Invoke-VMScript -VM "installer-test" -Script "Get-ChildItem 'C:\Program Files\opencode-container-server'"
          Write-Host "Installed files: $files"

      - name: Test uninstall
        run: |
          Invoke-VMScript -VM "installer-test" -Script "& 'C:\Program Files\opencode-container-server\unins000.exe' /VERYSILENT"
          $exists = Invoke-VMScript -VM "installer-test" -Script "Test-Path 'C:\Program Files\opencode-container-server'"
          if ($exists) { throw "Uninstall failed" }

      - name: Publish test results
        run: |
          Write-Host "All tests passed on clean Windows 11 VM"
```

## OS Templates Reference

| Name | Provider | Box/ISO | Credentials |
|------|----------|---------|-------------|
| `windows11` | Hyper-V | Official MS ISO + Autounattend | vagrant/vagrant |
| `windows11` | Vagrant | `gusztavvargadr/windows-11-24h2-enterprise` | vagrant/vagrant |
| `windows10` | Vagrant | `gusztavvargadr/windows-10-22h2-enterprise` | vagrant/vagrant |
| `ubuntu-server` | QEMU | Ubuntu Server LTS ISO + cloud-init | tester/tester |
| `ubuntu` | Vagrant | `ubuntu/jammy64` | vagrant/vagrant |
| `debian` | Vagrant | `debian/bookworm64` | vagrant/vagrant |

## VM Test Engine Architecture Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Hyper-V     │     │  Vagrant     │     │  QEMU/KVM    │
│  (Native)    │     │  (Abstract)  │     │  (Native)    │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ windows11    │     │ windows11    │     │ ubuntu       │
│ windows10    │     │ ubuntu       │     │ debian       │
│ windows-server│    │ debian       │     │ arch         │
└──────┬───────┘     │ macos (host) │     └──────┬───────┘
       │             └──────┬───────┘            │
       └────────────────────┼────────────────────┘
                            │
                    ┌───────┴────────┐
                    │  Test Runner    │
                    ├────────────────┤
                    │  Install Test   │
                    │  Uninstall Test │
                    │  Destructive    │
                    │  Network Test   │
                    │  Upgrade Test   │
                    └────────────────┘
```

## Common Issues

| Issue | Fix |
|-------|-----|
| Hyper-V not enabled | `Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All` |
| Vagrant box too old | `vagrant box update` |
| QEMU lacks KVM | Enable virtualization in BIOS, verify with `kvm-ok` |
| VM won't boot ISO | Check secure boot settings for the VM generation |
| Snapshot disk full | Increase VHDX size or use differencing disks |
| Network isolation fails | Check VM switch type — use Internal or Private, not External |
| WinRM not connecting | `Set-Item WSMan:\localhost\Client\TrustedHosts *` on host |

## References

- [Vagrant Documentation](https://developer.hashicorp.com/vagrant/docs)
- [Packer Documentation](https://developer.hashicorp.com/packer/docs)
- [Hyper-V PowerShell Reference](https://learn.microsoft.com/en-us/powershell/module/hyper-v/)
- [cloud-init Documentation](https://cloudinit.readthedocs.io/)
- [QEMU System Emulation](https://www.qemu.org/docs/master/system/index.html)
