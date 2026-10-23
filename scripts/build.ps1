# Construye dist\ImageStudio con PyInstaller, lo verifica y arma el instalador con Inno Setup 6.
# Uso: .\scripts\build.ps1            (ejecutable e instalador)
#      .\scripts\build.ps1 -SinInstalador
param([switch]$SinInstalador)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$python = Join-Path $raiz ".venv\Scripts\python.exe"

function Invoke-Externo([string]$Programa, [string[]]$Argumentos, [string]$Mensaje) {
    # PowerShell 5.1 convierte la salida de error de un programa externo en errores fatales cuando
    # ErrorActionPreference es Stop; PyInstaller escribe ahí sus mensajes informativos.
    $anterior = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Programa @Argumentos 2>&1 | ForEach-Object { "$_" }
    $codigo = $LASTEXITCODE
    $ErrorActionPreference = $anterior
    if ($codigo -ne 0) { throw "$Mensaje (código $codigo)" }
}

$version = & $python -X utf8 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
Invoke-Externo $python @("-m", "PyInstaller", "--noconfirm", "--log-level", "WARN", "--distpath", "dist", "--workpath", "build", "packaging\image_studio.spec") "PyInstaller falló"
Invoke-Externo "dist\ImageStudio\image-studio-cli.exe" @("diagnostico") "El diagnóstico del ejecutable falló"
if ($SinInstalador) { return }

$candidatos = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
)
$iscc = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "No se encontró Inno Setup 6 (winget install --id JRSoftware.InnoSetup -e)" }
Invoke-Externo $iscc @("/Q", "/DVersion=$version", "packaging\instalador.iss") "Inno Setup falló"
Get-Item "dist\instalador\ImageStudio-Setup-$version.exe" | Select-Object Name, @{n = "MB"; e = { [int]($_.Length / 1MB) } }
