; Inno Setup script — wraps the PyInstaller build into a Windows installer.
;
;   iscc installer.iss        (run AFTER pyinstaller produces dist\SalesManager)
;
; Produces Output\SalesManagerSetup.exe.
;
; During installation the user is asked once for the installation passkey. It
; is checked against the embedded one-way hashes; a wrong key stops the install.
; Only hashes are stored here — never the plaintext passkey.
; (Two hashes are accepted: the passkey with and without its trailing "...".
;  To accept only one, set both lines to the same hash.)

#define MyAppName "Sales Manager"
#define MyAppShortName "SalesManager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Health Data Matrics (HDM Group)"
#define MyAppExeName "SalesManager.exe"
#define MyPasskeyHash "430924d1b4ed167717b33a2b217ec5e678858770254b652d86f274c244590912"
#define MyPasskeyHashAlt "58d54b4cbebe99306073644162ccd8b2dd83664fd820d0c2a7be6118470735ed"

[Setup]
AppId={{525ABAD8-539D-4711-B2CA-69FD3BC14702}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppShortName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=SalesManagerSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} (HDM POS)
SetupIconFile=logo.ico
; x64compatible only exists from Inno Setup 6.3, so fall back on older builds.
#if VER >= EncodeVer(6,3,0,0)
ArchitecturesInstallIn64BitMode=x64compatible
#else
ArchitecturesInstallIn64BitMode=x64
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\SalesManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Start {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Program files only. Sales data in %LOCALAPPDATA%\SalesManager is kept so a
; reinstall or upgrade never loses it.
Type: filesandordirs; Name: "{app}"

[Code]
var
  PasskeyPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  PasskeyPage := CreateInputQueryPage(wpLicense,
    'Installation passkey',
    'Sales Manager (HDM POS) is licensed software. Please enter your passkey.',
    'Enter the installation passkey supplied by Health Data Matrics, then click Next. ' +
    'Installation cannot continue without it.');
  PasskeyPage.Add('Passkey:', True);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Entered, H: String;
begin
  Result := True;
  if CurPageID = PasskeyPage.ID then
  begin
    Entered := Trim(PasskeyPage.Values[0]);
    if Entered = '' then
    begin
      MsgBox('Please enter your passkey to continue.', mbError, MB_OK);
      Result := False;
    end
    else
    begin
      H := GetSHA256OfString(AnsiString(Entered));
      if (CompareText(H, '{#MyPasskeyHash}') <> 0) and
         (CompareText(H, '{#MyPasskeyHashAlt}') <> 0) then
      begin
        MsgBox('That passkey is not correct.' + #13#10#13#10 +
               'Check it and try again, or contact Health Data Matrics.',
               mbError, MB_OK);
        Result := False;
      end;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\passkey.hash'),
                     '{#MyPasskeyHash}', False);
end;
