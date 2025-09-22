[Setup]
AppName={#AppName}
AppVersion={#Version}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer\out
OutputBaseFilename=SSH-Studio-{#Version}-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\SSH-Studio.bat"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\SSH-Studio.bat"; Tasks: desktopicon

[Run]
Filename: "{app}\SSH-Studio.bat"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
