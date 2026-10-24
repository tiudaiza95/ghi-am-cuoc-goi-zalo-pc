#define AppVersion "2.4.0"
[Setup]
AppId={{20AA6AF9-727D-445F-BB49-852A942694B1}
AppName=Ghi Âm Zalo PC
AppVersion={#AppVersion}
AppVerName=Ghi Âm Zalo PC {#AppVersion}
DefaultDirName={localappdata}\Programs\Zalo Call Companion
DefaultGroupName=Ghi Âm Zalo PC
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile=..\assets\companion.ico
UninstallDisplayIcon={app}\ZaloCallCompanion.exe
OutputDir=..\release\Ghi-Am-Zalo-PC-2.4.0
OutputBaseFilename=Ghi-Am-Zalo-PC-2.4.0-Setup
Compression=lzma2
SolidCompression=yes
AppMutex=Local\ZaloCallCompanion.Instance
CloseApplications=no
RestartApplications=no
DisableProgramGroupPage=yes
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce
[Files]
Source: "..\release\payload\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{userprograms}\Ghi Âm Zalo PC"; Filename: "{app}\ZaloCallCompanion.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Ghi Âm Zalo PC"; Filename: "{app}\ZaloCallCompanion.exe"; WorkingDir: "{app}"; Tasks: desktopicon
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "ZaloCallCompanion"; Flags: uninsdeletevalue
[Run]
Filename: "{app}\ZaloCallCompanion.exe"; Description: "Open Ghi Âm Zalo PC"; Flags: nowait postinstall skipifsilent unchecked
[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var Existing: String;
begin
  if CurStep = ssPostInstall then
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ZaloCallCompanion', Existing) then
      RegWriteStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ZaloCallCompanion', '"' + ExpandConstant('{app}\ZaloCallCompanion.exe') + '"');
end;
