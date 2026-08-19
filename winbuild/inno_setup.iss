; Inno Setup script for Vocabulary App (M20 Release Contract § 2.5, § 8.4).
; Compiled by winbuild/build.py, which passes /DAppVersion=<version> --
; do not hardcode a version string here.
;
; Frozen installer contract (§ 8.4):
;   - Windows 10/11 x64, per-user install, no admin requirement
;     (PrivilegesRequired=lowest, no override escape hatch);
;   - Start Menu entry required, Desktop shortcut optional/default-enabled;
;   - binaries under the per-user Program Files equivalent ({autopf} auto-
;     redirects there under PrivilegesRequired=lowest);
;   - user data (%LOCALAPPDATA%\vocabulary_app\) is never touched by
;     install/uninstall except the explicit, unchecked-by-default,
;     confirm-at-uninstall-time opt-in below.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#define AppName "Vocabulary App"
#define AppPublisher "Yunsong Shi (Peter Shi)"
#define AppExeName "Vocabulary App.exe"
#define UserDataDirName "vocabulary_app"

[Setup]
; Generated once for this application; never regenerate for a new
; version -- this identifies "Vocabulary App" across upgrades so Inno
; Setup/Windows treat a new version as an upgrade, not a separate app.
AppId={{6C6F9E2A-6E3A-4C9F-9E8E-6B9C6E9A6F3D}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
; Intentionally omitted: PrivilegesRequiredOverridesAllowed. Setting it
; to `commandline`/`dialog` exposes an /ALLUSERS (or UI) path into
; administrative install mode, which would contradict the frozen
; per-user-only decision (M20 Release Contract § 2.5).
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=..\dist\installer
OutputBaseFilename=VocabularyApp-Setup-{#AppVersion}
SetupIconFile=..\assets\icons\vocabulary_app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Default-enabled (no "unchecked" flag) per § 8.4 "Desktop shortcut
; optional/default-enabled".
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\Vocabulary App\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// § 8.4 "explicit, unchecked-by-default... opt-in" data-deletion path,
// via the documented CurUninstallStepChanged/usPostUninstall event --
// runs after the install directory itself is already removed, so this
// only ever touches the separate per-user data root, never {app}.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
  Response: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    UserDataDir := ExpandConstant('{localappdata}\{#UserDataDirName}');
    if DirExists(UserDataDir) then
    begin
      Response := MsgBox(
        'Also delete your local Vocabulary App data?' + #13#10 + #13#10 +
        UserDataDir + #13#10 + #13#10 +
        '(database, backups, audio cache, preferences)' + #13#10 + #13#10 +
        'This cannot be undone. Choose No to keep your data for a future reinstall.',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
      if Response = IDYES then
      begin
        DelTree(UserDataDir, True, True, True);
      end;
    end;
  end;
end;
