; Inno Setup script for Easy PDF.
;
; The installer is the update path: appupdate.py downloads and runs this. A
; zip is built as well, for people who would rather unpack a folder.
;
; Per-user install under LocalAppData with PrivilegesRequired=lowest. That is
; an accessibility decision, not a packaging one: installing into Program
; Files raises a UAC prompt, and a UAC prompt appearing while the app is
; closing around it is a dialog with no context for a screen reader user.
;
; The AppId GUID must never change. Change it and the next release installs
; alongside the old one instead of over it.

#define AppName "Easy PDF"
#define AppPublisher "TG Studios"
#define AppExeName "Easy PDF.exe"
#define AppURL "https://tgstudios.app"

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\Easy PDF"
#endif
#ifndef OutputDir
  #define OutputDir "installer"
#endif
#ifndef IconFile
  #define IconFile "..\assets\easypdf.ico"
#endif

[Setup]
AppId={{B194AFF3-AC8A-464F-9440-FB09CC0CDF62}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={localappdata}\Programs\{#AppPublisher}\{#AppName}
DefaultGroupName={#AppPublisher}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
OutputDir={#OutputDir}
OutputBaseFilename=EasyPDF-{#AppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExeName}
; Close the app before replacing files, and restart it after. Without this an
; update fails silently because the exe is locked.
CloseApplications=yes
RestartApplications=yes
; The .epdf file type is registered below, per user.
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent
; And the same thing for a SILENT install, which is how the app updates
; itself. The line above cannot do it: skipifsilent means what it says, so
; an app that installed its own update never reopened. Guarded on a flag
; rather than made unconditional, so somebody running the installer silently
; from a script does not get a window they did not ask for.
Filename: "{app}\{#AppExeName}"; Flags: nowait; Check: WantsRestart

[Registry]
; The document type, per user, so a double click on an .epdf opens the app
; and Explorer shows its icon and description. The ProgId is frozen
; (constants.DOC_PROGID); a changed ProgId orphans the old key on every
; machine. The zip copy registers nothing and the README says so.
Root: HKCU; Subkey: "Software\Classes\.epdf"; ValueType: string; ValueName: ""; ValueData: "TGStudios.EasyPDF.Document"; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\TGStudios.EasyPDF.Document"; ValueType: string; ValueName: ""; ValueData: "Easy PDF document"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\TGStudios.EasyPDF.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"",0"
Root: HKCU; Subkey: "Software\Classes\TGStudios.EasyPDF.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""

[UninstallDelete]
; Only the installed program. Settings, recent files and autosave snapshots
; live under {userappdata}\TG Studios\Easy PDF and are deliberately left
; behind: uninstalling to fix a problem must not destroy the snapshot of a
; document somebody was in the middle of writing.
Type: filesandordirs; Name: "{app}"

[Code]
function WantsRestart: Boolean;
begin
  { Set by the app when it installs its own update: /restartapp=1 }
  Result := ExpandConstant('{param:restartapp|0}') = '1';
end;
