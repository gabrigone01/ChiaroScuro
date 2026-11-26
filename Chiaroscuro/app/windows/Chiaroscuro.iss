; Installer Windows di Chiaroscuro (Inno Setup 6). Lo usa build.py: iscc /DVersion=... /DSrc=... /DIcon=... /DOutDir=...
#ifndef Version
  #define Version "1.0.0"
#endif
[Setup]
AppId={{6B0E4C1A-2D7B-4F3E-9A51-4D1E0A7C9B21}
AppName=Chiaroscuro
AppVersion={#Version}
AppPublisher=ProgettiQlc
DefaultDirName={autopf}\Chiaroscuro
DefaultGroupName=Chiaroscuro
OutputDir={#OutDir}
OutputBaseFilename=Chiaroscuro-{#Version}-Windows-Setup
SetupIconFile={#Icon}
UninstallDisplayIcon={app}\Chiaroscuro.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Icona sul desktop"; GroupDescription: "Collegamenti:"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Chiaroscuro"; Filename: "{app}\Chiaroscuro.exe"
Name: "{autodesktop}\Chiaroscuro"; Filename: "{app}\Chiaroscuro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Chiaroscuro.exe"; Description: "Avvia Chiaroscuro"; Flags: nowait postinstall skipifsilent
