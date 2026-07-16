; opencode-container-server — Inno Setup Installer
; Compile with Inno Setup 6+ (https://jrsoftware.org/isdl.php)
;   iscc .\opencode-container-server.iss
;
; Output: opencode-container-server-setup.exe

#define MyAppName "opencode-container-server"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Ohm Patel"
#define MyAppURL "https://github.com/ohmpatel3877/ai-memory-core"
#define MyAppExeName "opencode-container-server.lnk"

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
DisableProgramGroupPage=yes
DisableReadyPage=no
UninstallDisplayIcon={app}\opencode-container-server.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Files]
; We don't ship any files — everything is downloaded at runtime.
; This empty section is required for Inno Setup to compile.

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "cmd.exe"; Parameters: "/C ""docker exec -it opencode-server python3 /app/scripts/tools-mcp-server.py"""; WorkingDir: "{app}"; Comment: "Connect OpenCode to container MCP server"
Name: "{group}\View Logs"; Filename: "cmd.exe"; Parameters: "/C ""docker logs opencode-server"""; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "cmd.exe"; Parameters: "/C ""docker exec -it opencode-server python3 /app/scripts/tools-mcp-server.py"""; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; After install, open the docs
Filename: "{app}\README.txt"; Description: "View setup instructions"; Flags: postinstall shellexec skipifsilent

[UninstallRun]
; Stop and remove the container on uninstall
Filename: "{cmd}"; Parameters: "/C docker stop opencode-server && docker rm opencode-server"; Flags: runhidden runascurrentuser
Filename: "{cmd}"; Parameters: "/C docker rmi ohmpatel3877/opencode-container-server:latest"; Flags: runhidden runascurrentuser

[Code]

// ─── Constants ──────────────────────────────────────────────────────
const
  COMPOSE_URL = 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/opencode-compose.yml';
  DOCKERFILE_URL = 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/Dockerfile';
  DOCKER_INSTALLER_URL = 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe';

// ─── Helper: Run PowerShell and capture output ──────────────────────
function RunPowerShell(Cmd: string; var ExitCode: Integer): string;
var
  ResultCode: Integer;
  TempFile, Command: string;
begin
  TempFile := ExpandConstant('{tmp}\ps_output.txt');
  Command := Format('powershell -NoProfile -ExecutionPolicy Bypass -Command "%s" > "%s" 2>&1', [Cmd, TempFile]);
  if not Exec('cmd.exe', '/C ' + Command, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    ExitCode := -1
  else
    ExitCode := ResultCode;
  if FileExists(TempFile) then
  begin
    LoadStringFromFile(TempFile, Result);
    DeleteFile(TempFile);
  end;
end;

// ─── Helper: Download file with progress ────────────────────────────
function DownloadFile(URL, DestFile: string; var ErrorMsg: string): Boolean;
var
  PSCommand: string;
  ExitCode: Integer;
begin
  PSCommand := Format(
    '$wc = New-Object System.Net.WebClient; ' +
    '$wc.Headers.Add("User-Agent", "opencode-installer/1.0"); ' +
    'try { $wc.DownloadFile("%s", "%s"); exit 0 } catch { write-host $_.Exception.Message; exit 1 }',
    [URL, DestFile]
  );
  RunPowerShell(PSCommand, ExitCode);
  if ExitCode <> 0 then
  begin
    // Try Invoke-WebRequest as fallback
    PSCommand := Format(
      '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ' +
      'Invoke-WebRequest -Uri "%s" -OutFile "%s" -UseBasicParsing',
      [URL, DestFile]
    );
    RunPowerShell(PSCommand, ExitCode);
  end;
  Result := (ExitCode = 0) and FileExists(DestFile);
  if not Result then
    ErrorMsg := Format('Download failed (exit code %d): %s', [ExitCode, URL]);
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
  InstallerPath, PSCommand: string;
  ExitCode: Integer;
  Page: TOutputProgressWizardPage;
begin
  Result := False;

  Page := CreateOutputProgressPage('Installing Docker Desktop', 'Downloading Docker Desktop (~500MB)...');
  Page.Show;

  try
    // Download Docker installer
    Page.SetText('Downloading Docker Desktop installer...', '');
    Page.SetProgress(0, 100);

    InstallerPath := ExpandConstant('{tmp}\DockerDesktopInstaller.exe');
    if not DownloadFile(DOCKER_INSTALLER_URL, InstallerPath, ErrorMsg) then
    begin
      Page.Hide;
      Exit;
    end;

    // Run installer silently
    Page.SetText('Installing Docker Desktop (this takes a few minutes)...', '');
    Page.SetProgress(50, 100);
    
    if not Exec(InstallerPath, 'install --quiet', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    begin
      ErrorMsg := 'Failed to launch Docker installer';
      Page.Hide;
      Exit;
    end;

    // Start Docker
    Page.SetText('Starting Docker Desktop...', '');
    Page.SetProgress(80, 100);
    RunPowerShell('Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"', ExitCode);

    // Wait for Docker
    Page.SetText('Waiting for Docker to initialize (30 seconds)...', '');
    Page.SetProgress(90, 100);

    PSCommand := 
      'for ($i = 0; $i -lt 30; $i++) { ' +
      '  try { docker info | Out-Null; exit 0 } catch {} ' +
      '  Start-Sleep -Seconds 1 ' +
      '}; exit 1';
    RunPowerShell(PSCommand, ExitCode);
    
    if ExitCode = 0 then
      Result := True
    else
      ErrorMsg := 'Docker installed but not responding. Launch Docker Desktop manually.';
  finally
    Page.Hide;
  end;
end;

// ─── Build container ────────────────────────────────────────────────
function BuildContainer(var ErrorMsg: string): Boolean;
var
  WorkDir, PSCommand: string;
  ExitCode: Integer;
  Page: TOutputProgressWizardPage;
begin
  Result := False;

  WorkDir := ExpandConstant('{app}');
  CreateDir(WorkDir);

  Page := CreateOutputProgressPage('Building Container', 'Downloading and building the MCP server container...');
  Page.Show;

  try
    // Step 1: Download compose file
    Page.SetText('Downloading container configuration...', '');
    Page.SetProgress(10, 100);
    if not DownloadFile(COMPOSE_URL, AddBackslash(WorkDir) + 'docker-compose.yml', ErrorMsg) then Exit;

    // Step 2: Download Dockerfile
    Page.SetText('Downloading Dockerfile...', '');
    Page.SetProgress(20, 100);
    if not DownloadFile(DOCKERFILE_URL, AddBackslash(WorkDir) + 'Dockerfile', ErrorMsg) then Exit;

    // Step 3: Build and start
    Page.SetText('Building container (1-3 minutes)...', '');
    Page.SetProgress(40, 100);

    PSCommand := Format(
      'Set-Location "%s"; docker compose up -d --build 2>&1',
      [WorkDir]
    );
    RunPowerShell(PSCommand, ExitCode);

    if ExitCode = 0 then
    begin
      Page.SetText('Verifying container...', '');
      Page.SetProgress(90, 100);
      RunPowerShell('timeout /t 3', ExitCode);
      Result := True;
    end
    else
      ErrorMsg := 'Container build failed. Make sure Docker Desktop is running.';
  finally
    Page.Hide;
  end;
end;

// ─── Check box for Docker license ───────────────────────────────────
var
  DockerLicensePage: TInputOptionWizardPage;
  MemoPage: TOutputMemoWizardPage;

procedure InitializeWizard;
begin
  // Welcome page
  WizardForm.WelcomeLabel1.Caption := 'Welcome to opencode-container-server Setup';
  WizardForm.WelcomeLabel2.Caption := 'This will install the MCP server container on your system.'#13#10 +
    'You need:'#13#10 +
    '  - Windows 10 or later'#13#10 +
    '  - Internet connection (for downloading components)'#13#10#13#10 +
    'The installer will:'#13#10 +
    '  1. Install Docker Desktop (if missing)'#13#10 +
    '  2. Download the container build files'#13#10 +
    '  3. Build and start the MCP server'#13#10 +
    '  4. Create shortcuts to manage it';

  // Docker license agreement (appears if Docker needs to be installed)
  DockerLicensePage := CreateInputOptionPage(
    wpLicense, 'Docker Desktop License', 'Docker Desktop requires accepting their terms.',
    'Docker Desktop is free for personal use. See https://www.docker.com/legal/docker-subscription-service-agreement',
    True, False
  );
  DockerLicensePage.Add('I accept the Docker Desktop license agreement');
  DockerLicensePage.Values[0] := True;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // Skip Docker license page if Docker is already installed
  if (PageID = DockerLicensePage.ID) and IsDockerInstalled then
    Result := True
  else
    Result := False;
end;

// ─── Main install logic ─────────────────────────────────────────────
function NextButtonClick(CurPageID: Integer): Boolean;
var
  ErrorMsg: string;
begin
  Result := True;

  if CurPageID = wpReady then
  begin
    // ── Step 1: Docker check ──
    if not IsDockerInstalled then
    begin
      if not InstallDocker(ErrorMsg) then
      begin
        MsgBox('Docker installation failed:'#13#10 + ErrorMsg + #13#10#13#10 +
          'You can install Docker manually from https://desktop.docker.com and run this installer again.',
          mbError, MB_OK);
        Result := False;
        Exit;
      end;
    end;

    // ── Step 2: Build container ──
    if not BuildContainer(ErrorMsg) then
    begin
      MsgBox('Container build failed:'#13#10 + ErrorMsg + #13#10#13#10 +
        'Make sure Docker Desktop is running and try again.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;

// ─── Post-install: create README ────────────────────────────────────
procedure CurStepChanged(CurStep: TSetupStep);
var
  ReadmePath: string;
  ReadmeContent: TArrayOfString;
begin
  if CurStep = ssPostInstall then
  begin
    ReadmePath := ExpandConstant('{app}\README.txt');
    SetArrayLength(ReadmeContent, 14);
    ReadmeContent[0] := 'opencode-container-server — MCP Server';
    ReadmeContent[1] := '============================================';
    ReadmeContent[2] := '';
    ReadmeContent[3] := 'The container is running on port 3100.';
    ReadmeContent[4] := '';
    ReadmeContent[5] := 'To connect from OpenCode, add to your opencode.json:';
    ReadmeContent[6] := '{';
    ReadmeContent[7] := '  "mcpServers": {';
    ReadmeContent[8] := '    "opencode-container-server": {';
    ReadmeContent[9] := '      "command": "docker",';
    ReadmeContent[10] := '      "args": ["exec", "-i", "opencode-server", "python3", "/app/scripts/tools-mcp-server.py"]';
    ReadmeContent[11] := '    }';
    ReadmeContent[12] := '  }';
    ReadmeContent[13] := '}';
    SaveStringsToFile(ReadmePath, ReadmeContent, False);
  end;
end;

// ─── Uninstall: clean up config directory ───────────────────────────
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    DelTree(ExpandConstant('{app}'), True, True, True);
end;
