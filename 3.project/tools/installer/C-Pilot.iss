#ifndef PayloadDir
  #error PayloadDir is required
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppIdentifier
  #define AppIdentifier "{{6D69CE81-0553-47F0-8214-A58256398931}"
#endif
#ifndef SetupSuffix
  #define SetupSuffix ""
#endif

[Setup]
AppId={#AppIdentifier}
AppName=C-Pilot
AppVersion={#AppVersion}
AppPublisher=C-Pilot
DefaultDirName={localappdata}\Programs\C-Pilot
DefaultGroupName=C-Pilot
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir={#ReleaseDir}
OutputBaseFilename=C-Pilot-Setup-{#AppVersion}{#SetupSuffix}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\launcher\assets\cpilot.ico
UninstallDisplayIcon={app}\C-Pilot.exe
DisableProgramGroupPage=yes
CloseApplications=no
RestartApplications=no
DisableWelcomePage=no
InfoBeforeFile=customer-install.txt

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면에 C-Pilot 바로가기 만들기"; Flags: unchecked
Name: "localai"; Description: "로컬 AI 준비 (Ollama와 Qwen 모델 약 12GB 다운로드, 인터넷 필요)"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"

[Icons]
Name: "{group}\C-Pilot"; Filename: "{app}\C-Pilot.exe"; WorkingDir: "{app}"
Name: "{group}\C-Pilot 관리 (백업·복구)"; Filename: "{app}\C-Pilot.exe"; Parameters: "manage"; WorkingDir: "{app}"
Name: "{group}\C-Pilot AI 준비"; Filename: "{app}\C-Pilot.exe"; Parameters: "setup-ai"; WorkingDir: "{app}"
Name: "{group}\C-Pilot 사용 안내"; Filename: "{app}\사용안내.txt"
Name: "{autodesktop}\C-Pilot"; Filename: "{app}\C-Pilot.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\C-Pilot.exe"; Parameters: "setup-ai"; Description: "Ollama와 Qwen 모델 준비"; Tasks: localai; Flags: postinstall skipifsilent
Filename: "{app}\C-Pilot.exe"; Description: "C-Pilot 실행"; Flags: postinstall nowait skipifsilent

[Code]
function StopOwnedServer(): Boolean;
var
  Code: Integer;
  PythonPath, LauncherPath: String;
begin
  Result := True;
  PythonPath := ExpandConstant('{app}\runtime\python\python.exe');
  LauncherPath := ExpandConstant('{app}\backend\pilot_launcher.py');
  if FileExists(PythonPath) and FileExists(LauncherPath) then
  begin
    { Older GUI entrypoints may fail when invoked without console handles. }
    Result := Exec(PythonPath, '-X utf8 "' + LauncherPath + '" stop --no-browser', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
    Exit;
  end;
  if FileExists(ExpandConstant('{app}\C-Pilot.exe')) then
    Result := Exec(ExpandConstant('{app}\C-Pilot.exe'), 'stop --no-browser', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not StopOwnedServer() then
    Result := 'C-Pilot 서버를 종료하지 못했습니다. 관리 메뉴에서 종료한 뒤 설치를 다시 실행하세요.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := StopOwnedServer();
  if not Result then
    SuppressibleMsgBox('C-Pilot 서버를 관리 메뉴에서 종료한 뒤 제거를 다시 실행하세요.', mbError, MB_OK, IDOK);
end;
