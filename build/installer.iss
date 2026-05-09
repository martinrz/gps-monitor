; ============================================================
; installer.iss — Inno Setup 6 script for GPS Monitor (Windows)
;
; Run with:
;   ISCC build\installer.iss
; or via build_windows.bat which calls it automatically.
;
; Output: dist\GPS_Monitor_1.0_Setup.exe
; ============================================================

#ifndef AppVersion
  #define AppVersion "1.0"
#endif

#define AppName      "GPS Monitor"
#define AppPublisher "Martin Reynolds"
#define AppURL       "https://github.com/martinrz/gps-monitor"
#define AppExeName   "GPS Monitor.exe"
#define DistDir      "..\dist\GPS Monitor"
#define IconFile     "icons\icon.ico"

[Setup]
AppId                    ={{A7B3C2D1-4E5F-6789-ABCD-EF0123456789}
AppName                  ={#AppName}
AppVersion               ={#AppVersion}
AppVerName               ={#AppName} {#AppVersion}
AppPublisher             ={#AppPublisher}
AppPublisherURL          ={#AppURL}
AppSupportURL            ={#AppURL}
AppUpdatesURL            ={#AppURL}
DefaultDirName           ={autopf}\{#AppName}
DefaultGroupName         ={#AppName}
DisableProgramGroupPage  =yes
OutputDir                =..\dist
OutputBaseFilename       =GPS_Monitor_{#AppVersion}_Setup
SetupIconFile            ={#IconFile}
Compression              =lzma2/ultra64
SolidCompression         =yes
WizardStyle              =modern
MinVersion               =10.0
ArchitecturesAllowed     =x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile              =
; Uncomment and set if you have a signing certificate:
; SignTool=signtool

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main application bundle (everything PyInstaller put in dist\GPS Monitor\)
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}";    Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Desktop (optional)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#AppExeName}"

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent; Parameters: "--simulate"

[UninstallDelete]
; Clean up runtime-generated files on uninstall
Type: filesandordirs; Name: "{app}\tle_cache"
Type: files;          Name: "{app}\gps\satellites.dat"
Type: files;          Name: "{app}\gps\satellites.dat.tmp"
Type: filesandordirs; Name: "{app}\logs"

[Code]
// Warn if the Visual C++ runtime is missing (required by Qt / VisPy).
// Users without it will see a DLL-not-found error on first launch.
function VCRedistInstalled: Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(
    HKLM,
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
    'Version',
    Version
  );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not VCRedistInstalled then
      MsgBox(
        'GPS Monitor requires the Microsoft Visual C++ 2015-2022 Redistributable (x64).' + #13#10 +
        'If the application does not start, download it from:' + #13#10 +
        'https://aka.ms/vs/17/release/vc_redist.x64.exe',
        mbInformation, MB_OK
      );
  end;
end;
