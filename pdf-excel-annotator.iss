; Inno Setup script for PDF Excel Annotator
; Run with: iscc /DVersion=1.0.0 pdf-excel-annotator.iss

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppName=PDF Excel Annotator
AppVersion={#Version}
AppPublisher=Zerano
AppPublisherURL=https://github.com/sander541/pdf-excel-matcher
AppSupportURL=https://github.com/sander541/pdf-excel-matcher/issues
AppUpdatesURL=https://github.com/sander541/pdf-excel-matcher/releases
DefaultDirName={autopf}\PDF Excel Annotator
DefaultGroupName=PDF Excel Annotator
OutputDir=dist\installer
OutputBaseFilename=pdf-excel-annotator-setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
DisableProgramGroupPage=yes
DisableReadyPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\pdf-excel-annotator\pdf-excel-annotator.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\pdf-excel-annotator\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PDF Excel Annotator"; Filename: "{app}\pdf-excel-annotator.exe"
Name: "{group}\Uninstall PDF Excel Annotator"; Filename: "{uninstallexe}"
Name: "{commondesktop}\PDF Excel Annotator"; Filename: "{app}\pdf-excel-annotator.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\pdf-excel-annotator.exe"; Description: "{cm:LaunchProgram,PDF Excel Annotator}"; Flags: nowait postinstall

[UninstallDelete]
Type: dirifempty; Name: "{app}"
