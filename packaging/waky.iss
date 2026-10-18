; Inno Setup script for Waky. Build with: iscc packaging\waky.iss /DAppVersion=1.0.0
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\dist\Waky"
#endif

[Setup]
AppId={{6F1C2B0E-7A54-4C0B-9B7E-5A1D8E2C9A41}
AppName=Waky
AppVersion={#AppVersion}
AppPublisher=Waky
DefaultDirName={autopf}\Waky
DefaultGroupName=Waky
DisableProgramGroupPage=yes
; Per-user install: no admin prompt, and the app can update its own folder.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=Waky-Setup-{#AppVersion}
SetupIconFile=..\assets\waky.ico
UninstallDisplayIcon={app}\Waky.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0.17763
AppMutex=Waky.Dictation.Mutex
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Waky"; Filename: "{app}\Waky.exe"
Name: "{autodesktop}\Waky"; Filename: "{app}\Waky.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Waky.exe"; Description: "Start Waky and run setup"; Flags: nowait postinstall skipifsilent

[Code]
procedure StopWaky();
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM Waky.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopWaky();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    StopWaky();
    // Remove the autostart entry the app created. User data in %APPDATA%\Waky is kept.
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Waky');
  end;
end;

