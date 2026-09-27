<#
.SYNOPSIS
    Script de empaquetado para generar la distribución portable de MintPlay en Windows x64.
.DESCRIPTION
    Ejecuta PyInstaller usando MintPlay.spec, valida la presencia de binarios (FFmpeg, Node.js),
    y genera el archivo ZIP portable listo para doble clic.
#>

$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Construyendo MintPlay Distribución Portable (Windows) " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$Raiz = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $Raiz

$PythonExe = Join-Path $Raiz "venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

Write-Host "[1/6] Verificando binarios auxiliares en bin/..." -ForegroundColor Yellow
$BinariosRequeridos = @("ffmpeg.exe", "ffprobe.exe", "node.exe")
foreach ($bin in $BinariosRequeridos) {
    $rutaBin = Join-Path $Raiz "bin\$bin"
    if (-not (Test-Path $rutaBin)) {
        Write-Error "No se encontró $bin en $rutaBin. Es necesario para la distribución portable."
    }
}
Write-Host "Binarios verificados correctamente." -ForegroundColor Green

Write-Host "[2/6] Limpiando artefactos de compilación anteriores..." -ForegroundColor Yellow
$CarpetasLimpiar = @("build", "dist\MintPlay", "dist\MintPlay-windows-x64-v1.0.0.zip")
foreach ($carpeta in $CarpetasLimpiar) {
    $ruta = Join-Path $Raiz $carpeta
    if (Test-Path $ruta) {
        Remove-Item -Path $ruta -Recurse -Force
    }
}

Write-Host "[3/6] Ejecutando PyInstaller..." -ForegroundColor Yellow
& $PythonExe -m PyInstaller --clean --noconfirm packaging/MintPlay.spec

$DistApp = Join-Path $Raiz "dist\MintPlay"
if (-not (Test-Path $DistApp)) {
    Write-Error "PyInstaller no generó el directorio esperado en $DistApp"
}

Write-Host "[4/6] Garantizando estructura de binarios y licencias en dist/MintPlay..." -ForegroundColor Yellow
$DistBin = Join-Path $DistApp "bin"
if (-not (Test-Path $DistBin)) {
    New-Item -ItemType Directory -Path $DistBin | Out-Null
}

foreach ($bin in $BinariosRequeridos) {
    $origen = Join-Path $Raiz "bin\$bin"
    $destino = Join-Path $DistBin $bin
    if (-not (Test-Path $destino)) {
        Copy-Item -Path $origen -Destination $destino -Force
        Write-Host "  Copiado $bin a dist/MintPlay/bin/" -ForegroundColor Gray
    }
}

# Copiar licencias
Copy-Item -Path (Join-Path $Raiz "LICENSE") -Destination $DistApp -Force
Copy-Item -Path (Join-Path $Raiz "LICENSES") -Destination $DistApp -Recurse -Force

Write-Host "[5/6] Verificando integridad del bundle empaquetado..." -ForegroundColor Yellow
$ExeSalida = Join-Path $DistApp "MintPlay.exe"
if (-not (Test-Path $ExeSalida)) {
    Write-Error "No se generó el ejecutable principal MintPlay.exe"
}

Write-Host "[6/6] Creando archivo ZIP portable..." -ForegroundColor Yellow
$ZipSalida = Join-Path $Raiz "dist\MintPlay-windows-x64-v1.0.0.zip"
Compress-Archive -Path $DistApp -DestinationPath $ZipSalida -Force

$TamanoMb = [math]::Round((Get-Item $ZipSalida).Length / 1MB, 2)
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  ¡Distribución portable generada con éxito!" -ForegroundColor Green
Write-Host "  ZIP: $ZipSalida ($TamanoMb MB)" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
