; opencode-container-server — Inno Setup Installer
; Compile with Inno Setup 6+ (https://jrsoftware.org/isdl.php)
;   iscc .\opencode-container-server.iss
;
; Output: opencode-container-server-setup.exe
;
; Features:
; - Core MCP server (required)
; - Virtualization (VM test engine)
; - Samba/NAS debugging
; - Framework builder (Rust/FFI)
; - Study tools
; - Speed optimizer

#define MyAppName "opencode-container-server"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "Ohm Patel"
#define MyAppURL "https://github.com/ohmpatel3877/CortexStratum"

[Setup]
AppId={{F8A7B3C2-5D4E-4F6A-8B1C-9D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=opencode-container-server-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=no
DisableProgramGroupPage=no
DisableReadyPage=no
UninstallDisplayIcon={app}\opencode-container-server.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ─── Components (selectable pathway modules) ──────────────────────
[Components]
Name: "core"; Description: "Core MCP Server (115 tools, SQLite+FTS5 memory, OpenCode)"; Types: full custom; Flags: fixed checkablealone; ExtraDiskSpaceRequired: 1
Name: "virtualization"; Description: "VM Test Engine (Hyper-V, Vagrant, QEMU provisioning)"; Types: full custom; ExtraDiskSpaceRequired: 1
Name: "samba"; Description: "Samba/NAS Debugging (mergerfs, Podman, Jellyfin, Nextcloud)"; Types: full custom; ExtraDiskSpaceRequired: 1
Name: "framework"; Description: "Framework Builder (Rust workspaces, FFI, Tauri, MCP servers)"; Types: full custom; ExtraDiskSpaceRequired: 1
Name: "studytools"; Description: "Study Tutor (active recall, spaced repetition, learning techniques)"; Types: full custom; ExtraDiskSpaceRequired: 1
Name: "speedopt"; Description: "Speed Optimizer (token profiling, bottleneck detection, performance strategies)"; Types: full custom; ExtraDiskSpaceRequired: 1

[Types]
Name: "full"; Description: "Complete installation (all modules)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkablealone

; ─── Icons per component ──────────────────────────────────────────
[Icons]
; Core
Name: "{group}\MCP Server (connect OpenCode)"; Filename: "cmd.exe"; Parameters: "/C docker exec -it opencode-server python3 /app/scripts/tools-mcp-server.py"; WorkingDir: "{app}"; Components: core
Name: "{group}\View MCP Server Logs"; Filename: "cmd.exe"; Parameters: "/C docker logs opencode-server"; WorkingDir: "{app}"; Components: core
Name: "{autodesktop}\opencode-container-server"; Filename: "cmd.exe"; Parameters: "/C docker exec -it opencode-server python3 /app/scripts/tools-mcp-server.py"; WorkingDir: "{app}"; Tasks: desktopicon; Components: core
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

; Virtualization
Name: "{group}\VM Test Engine\Create Test VM (Hyper-V)"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\skills\vm-test-engine\scripts\vm-test.ps1"" -Provider hyperv -OS windows11 -Name ""installer-test"""; WorkingDir: "{app}"; Components: virtualization
Name: "{group}\VM Test Engine\Create Test VM (Vagrant)"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\skills\vm-test-engine\scripts\vm-test.ps1"" -Provider vagrant -OS ubuntu -Name ""vagrant-test"""; WorkingDir: "{app}"; Components: virtualization
Name: "{group}\VM Test Engine\List VM Templates"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\skills\vm-test-engine\scripts\vm-test.ps1"" -ListTemplates"; WorkingDir: "{app}"; Components: virtualization

; Samba/NAS
Name: "{group}\NAS Debugging\Run NAS Health Check"; Filename: "{app}\skills\debug-samba\scripts\nas-health-check.sh"; WorkingDir: "{app}"; Components: samba
Name: "{group}\NAS Debugging\Run Permission Trace"; Filename: "{app}\skills\debug-samba\scripts\perm-trace.sh"; WorkingDir: "{app}"; Components: samba

; Framework Builder
Name: "{group}\Framework Builder\Build All (Rust + FFI + WASM)"; Filename: "cmd.exe"; Parameters: "/C cd /d ""{app}"" && cargo build --release --workspace"; WorkingDir: "{app}"; Components: framework
Name: "{group}\Framework Builder\Documentation"; Filename: "{app}\skills\framework-builder\SKILL.md"; WorkingDir: "{app}"; Components: framework

; Study Tools
Name: "{group}\Study Tools\Study Tutor Guide"; Filename: "{app}\skills\study-tutor\SKILL.md"; WorkingDir: "{app}"; Components: studytools

; Speed Optimizer
Name: "{group}\Speed Optimizer\Run Analysis"; Filename: "cmd.exe"; Parameters: "/C cd /d ""{app}"" && python scripts\speed_optimizer.py --summary"; WorkingDir: "{app}"; Components: speedopt

[Run]
Filename: "{app}\README.txt"; Description: "View setup instructions"; Flags: postinstall shellexec skipifsilent; Components: core
Filename: "cmd.exe"; Parameters: "/C start http://localhost:3100"; Description: "Launch OpenCode and connect MCP server"; Flags: postinstall nowait skipifsilent unchecked; Components: core
Filename: "cmd.exe"; Parameters: "/K echo opencode-container-server v{#MyAppVersion} installed. Run: docker exec -it opencode-server python3 /app/scripts/tools-mcp-server.py --help"; Description: "Open verification terminal (check installation)"; Flags: postinstall nowait skipifsilent unchecked shellexec; Components: core


[UninstallRun]
Filename: "{cmd}"; Parameters: "/C docker stop opencode-server && docker rm opencode-server"; Flags: runhidden runascurrentuser
Filename: "{cmd}"; Parameters: "/C docker rmi ohmpatel3877/opencode-container-server:latest"; Flags: runhidden runascurrentuser

[Code]

const
  GITHUB_RAW = 'https://raw.githubusercontent.com/ohmpatel3877/CortexStratum/main';
  DOCKER_INSTALLER_URL = 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe';

// ─── Helper: Run PowerShell and capture output ──────────────────────
function RunPowerShell(Cmd: string; var ExitCode: Integer): string;
var
  ResultCode: Integer;
  TempFile, Command: string;
  Lines: TArrayOfString;
  i: Integer;
begin
  Result := '';
  TempFile := ExpandConstant('{tmp}\ps_out.txt');
  Command := Format('powershell -NoProfile -ExecutionPolicy Bypass -Command "%s" > "%s" 2>&1', [Cmd, TempFile]);
  if not Exec('cmd.exe', '/C ' + Command, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    ExitCode := -1
  else
    ExitCode := ResultCode;
  if FileExists(TempFile) then
  begin
    if LoadStringsFromFile(TempFile, Lines) then
    begin
      for i := 0 to GetArrayLength(Lines) - 1 do
        Result := Result + Lines[i] + #13#10;
    end;
    DeleteFile(TempFile);
  end;
end;

// ─── Helper: Download file with progress ────────────────────────────
function DownloadFile(URL, DestFile: string; var ErrorMsg: string): Boolean;
var
  PSCommand: string;
  ExitCode: Integer;
begin
  PSCommand := '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ' +
    '$wc = New-Object System.Net.WebClient; ' +
    '$wc.Headers.Add("User-Agent", "opencode-installer/1.0"); ' +
    'try { $wc.DownloadFile(' + #39 + URL + #39 + ', ' + #39 + DestFile + #39 + '); exit 0 } ' +
    'catch { write-host $_.Exception.Message; exit 1 }';
  RunPowerShell(PSCommand, ExitCode);
  Result := (ExitCode = 0) and FileExists(DestFile);
  if not Result then
    ErrorMsg := 'Download failed: ' + URL;
end;

// ─── Check if Docker is installed ──────────────────────────────────
function IsDockerInstalled: Boolean;
var
  ExitCode: Integer;
begin
  RunPowerShell('docker --version', ExitCode);
  Result := (ExitCode = 0);
end;

// ─── Install Docker Desktop ─────────────────────────────────────────
function InstallDocker(var ErrorMsg: string): Boolean;
var
  InstallerPath: string;
  ExitCode: Integer;
  Page: TOutputProgressWizardPage;
begin
  Result := False;
  Page := CreateOutputProgressPage('Installing Docker Desktop', 'Downloading Docker Desktop (~500MB)...');
  Page.Show;
  try
    InstallerPath := ExpandConstant('{tmp}\DockerDesktopInstaller.exe');
    Page.SetText('Downloading Docker Desktop installer...', '');
    Page.SetProgress(10, 100);
    if not DownloadFile(DOCKER_INSTALLER_URL, InstallerPath, ErrorMsg) then begin Page.Hide; Exit; end;

    Page.SetText('Installing Docker Desktop...', '');
    Page.SetProgress(50, 100);
    if not Exec(InstallerPath, 'install --quiet', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
      ErrorMsg := 'Docker installer failed to launch'; Page.Hide; Exit;
    end;

    Page.SetText('Starting Docker Desktop...', '');
    Page.SetProgress(80, 100);
    RunPowerShell('Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"', ExitCode);

    Page.SetText('Waiting for Docker to initialize...', '');
    Page.SetProgress(90, 100);
    RunPowerShell('for ($i=0;$i -lt 30;$i++) { try { docker info | Out-Null; exit 0 } catch {} Start-Sleep 1 }; exit 1', ExitCode);
    if ExitCode = 0 then Result := True else ErrorMsg := 'Docker installed but not responding';
  finally
    Page.Hide;
  end;
end;

// ─── Download skill files for selected components ───────────────────
procedure DownloadSkills(AppDir: string; Page: TOutputProgressWizardPage; var ErrorMsg: string);
var
  SkillDir, ScriptDir: string;
begin
  // Core skills (always installed)
  SkillDir := AddBackslash(AppDir) + 'skills\task-orchestrator';
  CreateDir(SkillDir);
  DownloadFile(GITHUB_RAW + '/skills/task-orchestrator/SKILL.md', SkillDir + '\SKILL.md', ErrorMsg);

  // Component: Security hardening (always installed with core)
  SkillDir := AddBackslash(AppDir) + 'skills\security-hardening';
  CreateDir(SkillDir);
  DownloadFile(GITHUB_RAW + '/skills/security-hardening/SKILL.md', SkillDir + '\SKILL.md', ErrorMsg);

  // Component: Virtualization
  if IsComponentSelected('virtualization') then
  begin
    SkillDir := AddBackslash(AppDir) + 'skills\vm-test-engine';
    CreateDir(SkillDir);
    DownloadFile(GITHUB_RAW + '/skills/vm-test-engine/SKILL.md', SkillDir + '\SKILL.md', ErrorMsg);
    ScriptDir := SkillDir + '\scripts';
    CreateDir(ScriptDir);
    DownloadFile(GITHUB_RAW + '/skills/vm-test-engine/scripts/vm-test.ps1', ScriptDir + '\vm-test.ps1', ErrorMsg);
    DownloadFile(GITHUB_RAW + '/skills/vm-test-engine/scripts/vm-test.sh', ScriptDir + '\vm-test.sh', ErrorMsg);
    Page.SetProgress(30, 100);
  end;

  // Component: Samba/NAS
  if IsComponentSelected('samba') then
  begin
    SkillDir := AddBackslash(AppDir) + 'skills\debug-samba';
    CreateDir(SkillDir);
    DownloadFile(GITHUB_RAW + '/skills/debug-samba/SKILL.md', SkillDir + '\SKILL.md', ErrorMsg);
    ScriptDir := SkillDir + '\scripts';
    CreateDir(ScriptDir);
    DownloadFile(GITHUB_RAW + '/skills/debug-samba/scripts/nas-health-check.sh', ScriptDir + '\nas-health-check.sh', ErrorMsg);
    DownloadFile(GITHUB_RAW + '/skills/debug-samba/scripts/fuse-podman-check.sh', ScriptDir + '\fuse-podman-check.sh', ErrorMsg);
    DownloadFile(GITHUB_RAW + '/skills/debug-samba/scripts/perm-trace.sh', ScriptDir + '\perm-trace.sh', ErrorMsg);
    Page.SetProgress(50, 100);
  end;

  // Component: Framework Builder
  if IsComponentSelected('framework') then
  begin
    SkillDir := AddBackslash(AppDir) + 'skills\framework-builder';
    CreateDir(SkillDir);
    DownloadFile(GITHUB_RAW + '/skills/framework-builder/SKILL.md', SkillDir + '\SKILL.md', ErrorMsg);
    Page.SetProgress(65, 100);
  end;

  // Component: Study Tools
  if IsComponentSelected('studytools') then
  begin
    SkillDir := AddBackslash(AppDir) + 'skills\study-tutor';
    CreateDir(SkillDir);
    DownloadFile(GITHUB_RAW + '/skills/study-tutor/SKILL.md', SkillDir + '\SKILL.md', ErrorMsg);
    Page.SetProgress(80, 100);
  end;

  // Component: Speed Optimizer
  if IsComponentSelected('speedopt') then
  begin
    SkillDir := AddBackslash(AppDir) + 'skills\speed-optimizer';
    CreateDir(SkillDir);
    DownloadFile(GITHUB_RAW + '/skills/speed-optimizer/SKILL.md', SkillDir + '\SKILL.md', ErrorMsg);
    Page.SetProgress(90, 100);
  end;
end;

// ─── Build Container ────────────────────────────────────────────────
function BuildContainer(AppDir: string; var ErrorMsg: string): Boolean;
var
  PSCommand, WorkDir: string;
  ExitCode: Integer;
  Page: TOutputProgressWizardPage;
begin
  Result := False;
  WorkDir := AppDir;
  Page := CreateOutputProgressPage('Building Container', 'Building the MCP server container...');
  Page.Show;
  try
    Page.SetText('Downloading container files...', '');
    Page.SetProgress(10, 100);
    if not DownloadFile(GITHUB_RAW + '/docker/opencode-compose.yml', AddBackslash(WorkDir) + 'docker-compose.yml', ErrorMsg) then begin Page.Hide; Exit; end;
    if not DownloadFile(GITHUB_RAW + '/docker/Dockerfile', AddBackslash(WorkDir) + 'Dockerfile', ErrorMsg) then begin Page.Hide; Exit; end;

    Page.SetText('Building container (1-3 minutes)...', '');
    Page.SetProgress(40, 100);
    PSCommand := Format('Set-Location "%s"; docker compose up -d --build 2>&1', [WorkDir]);
    RunPowerShell(PSCommand, ExitCode);
    if ExitCode = 0 then begin
      Page.SetProgress(100, 100);
      Result := True;
    end else
      ErrorMsg := 'Container build failed. Is Docker Desktop running?';
  finally
    Page.Hide;
  end;
end;

// ─── Custom wizard text ────────────────────────────────────────────
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel1.Caption := 'opencode-container-server Setup';
  WizardForm.WelcomeLabel2.Caption := 'Installs the MCP server container with optional pathway modules.'#13#10 +
    ''#13#10 +
    'Requires:'#13#10 +
    '  - Windows 10 or later'#13#10 +
    '  - Internet connection'#13#10 +
    ''#13#10 +
    'The installer will:'#13#10 +
    '  1. Install Docker Desktop (if missing)'#13#10 +
    '  2. Download selected skill modules'#13#10 +
    '  3. Build and start the MCP server container'#13#10 +
    '  4. Create shortcuts';
end;

// ─── Install logic ─────────────────────────────────────────────────
function NextButtonClick(CurPageID: Integer): Boolean;
var
  ErrorMsg: string;
  AppDir: string;
  Page: TOutputProgressWizardPage;
begin
  Result := True;

  if CurPageID = wpReady then
  begin
    AppDir := ExpandConstant('{app}');

    // Step 1: Docker
    if not IsDockerInstalled then
    begin
      if not InstallDocker(ErrorMsg) then
      begin
        MsgBox('Docker installation failed:'#13#10 + ErrorMsg, mbError, MB_OK);
        Result := False;
        Exit;
      end;
    end;

    // Step 2: Download skill files for selected components
    Page := CreateOutputProgressPage('Downloading Modules', 'Downloading selected pathway modules...');
    Page.Show;
    try
      Page.SetText('Downloading skills...', '');
      Page.SetProgress(10, 100);
      DownloadSkills(AppDir, Page, ErrorMsg);
    finally
      Page.Hide;
    end;

    // Step 3: Build container
    if not BuildContainer(AppDir, ErrorMsg) then
    begin
      MsgBox('Container build failed:'#13#10 + ErrorMsg, mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;

// ─── Post-install: README ──────────────────────────────────────────
procedure CurStepChanged(CurStep: TSetupStep);
var
  ReadmePath: string;
  Lines: TArrayOfString;
  Count: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    ReadmePath := ExpandConstant('{app}\README.txt');
    SetArrayLength(Lines, 20);
    Count := 0;
    Lines[Count] := 'opencode-container-server — MCP Server'; Count := Count + 1;
    Lines[Count] := '============================================'; Count := Count + 1;
    Lines[Count] := ''; Count := Count + 1;
    Lines[Count] := 'The container is running on port 3100.'; Count := Count + 1;
    Lines[Count] := ''; Count := Count + 1;
    Lines[Count] := 'To connect from OpenCode, add to opencode.json:'; Count := Count + 1;
    Lines[Count] := '{'; Count := Count + 1;
    Lines[Count] := '  "mcpServers": {'; Count := Count + 1;
    Lines[Count] := '    "opencode-container-server": {'; Count := Count + 1;
    Lines[Count] := '      "command": "docker",'; Count := Count + 1;
    Lines[Count] := '      "args": ["exec", "-i", "opencode-server", "python3", "/app/scripts/tools-mcp-server.py"]'; Count := Count + 1;
    Lines[Count] := '    }'; Count := Count + 1;
    Lines[Count] := '  }'; Count := Count + 1;
    Lines[Count] := '}'; Count := Count + 1;
    Lines[Count] := ''; Count := Count + 1;
    Lines[Count] := 'Installed modules:'; Count := Count + 1;
    Lines[Count] := '- Core MCP Server (115 tools)'; Count := Count + 1;
    if IsComponentSelected('virtualization') then begin Lines[Count] := '- VM Test Engine'; Count := Count + 1; end;
    if IsComponentSelected('samba') then begin Lines[Count] := '- Samba/NAS Debugging'; Count := Count + 1; end;
    if IsComponentSelected('framework') then begin Lines[Count] := '- Framework Builder'; Count := Count + 1; end;
    if IsComponentSelected('studytools') then begin Lines[Count] := '- Study Tutor'; Count := Count + 1; end;
    if IsComponentSelected('speedopt') then begin Lines[Count] := '- Speed Optimizer'; Count := Count + 1; end;
    SetArrayLength(Lines, Count);
    SaveStringsToFile(ReadmePath, Lines, False);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    DelTree(ExpandConstant('{app}'), True, True, True);
end;
