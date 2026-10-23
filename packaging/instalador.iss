; Instalador por usuario de Image Studio (Inno Setup 6). Lo invoca scripts\build.ps1 con /DVersion=X.Y.Z.
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{80C60E47-96C4-42A4-872C-01027E0D87A6}
AppName=Image Studio
AppVersion={#Version}
AppPublisher=jhanva
DefaultDirName={localappdata}\Programs\Image Studio
DefaultGroupName=Image Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\instalador
OutputBaseFilename=ImageStudio-Setup-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ImageStudio.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "..\dist\ImageStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Al actualizar, Inno Setup no borra archivos de la versión anterior: quedarían, por ejemplo, los
; metadatos image_studio-<versión vieja>.dist-info y Python leería la versión equivocada.
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
; La caché de numba (__pycache__) la crea "preparar" después de instalar; sin esto queda la carpeta.
Type: filesandordirs; Name: "{app}\_internal\pymatting"

[Icons]
Name: "{group}\Image Studio"; Filename: "{app}\ImageStudio.exe"
Name: "{autodesktop}\Image Studio"; Filename: "{app}\ImageStudio.exe"; Tasks: escritorio

[Run]
; numba compila el motor la primera vez (unos 40 s); hacerlo aquí evita esperar al abrir la app.
Filename: "{app}\image-studio-cli.exe"; Parameters: "preparar"; StatusMsg: "Preparando el motor de recorte (puede tardar un minuto)..."; Flags: runhidden waituntilterminated
Filename: "{app}\ImageStudio.exe"; Description: "Abrir Image Studio"; Flags: nowait postinstall skipifsilent
