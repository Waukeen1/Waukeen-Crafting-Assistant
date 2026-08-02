#define AppName "Waukeen Crafting Assistant"
#define AppPublisher "Waukeen"
#define AppExeName "Waukeen Crafting Assistant.exe"

#ifndef AppVersion
  #define AppVersion "1.0.42"
#endif

#ifndef SourceDir
  #error SourceDir must point to the compiled application directory.
#endif

#ifndef OutputDir
  #error OutputDir must point to the release directory.
#endif

[Setup]
AppId={{38E86E49-21C4-4EBA-920A-7398F4C601A4}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Waukeen Crafting Assistant
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=Waukeen-Crafting-Assistant-Setup-v{#AppVersion}
SetupIconFile=..\assets\wca_icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoVersion={#AppVersion}

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "_internal\itemcraft\*,_internal\mapcraft\*,_internal\basejewelcraft\*,_internal\genericitemcraft\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\_internal\itemcraft\*"; DestDir: "{app}\_internal\itemcraft"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist
Source: "{#SourceDir}\_internal\mapcraft\*"; DestDir: "{app}\_internal\mapcraft"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist
Source: "{#SourceDir}\_internal\basejewelcraft\*"; DestDir: "{app}\_internal\basejewelcraft"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist
Source: "{#SourceDir}\_internal\genericitemcraft\*"; DestDir: "{app}\_internal\genericitemcraft"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaustune kisayol olustur"; GroupDescription: "Ek kisayollar:"; Flags: checkedonce

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{#AppName} uygulamasini baslat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
