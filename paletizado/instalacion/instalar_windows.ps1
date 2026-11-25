# Instalador del Registro de tarimas para Windows 10/11.
#
# Que hace:
#   1. Instala Python 3.12 y PostgreSQL 16 (con winget) si no estan.
#   2. Crea la base de datos "tarimas" y su usuario.
#   3. Copia la app a C:\Tarimas\app e instala sus librerias.
#   4. Crea las tablas (init_db.py).
#   5. Abre el puerto en el firewall para las tabletas.
#   6. Programa la app para que arranque sola al prender la PC.
#   7. Programa un respaldo diario de la base de datos.
#   8. Evita que la PC se suspenda.
#
# Se puede correr varias veces: la segunda vez actualiza la app y no borra datos.
# Correr como Administrador:  doble clic en instalar.cmd

#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

$Base       = "C:\Tarimas"
$App        = Join-Path $Base "app"
$Venv       = Join-Path $Base "venv"
$Respaldos  = Join-Path $Base "respaldos"
$Logs       = Join-Path $Base "logs"
$Origen     = Split-Path -Parent $PSScriptRoot      # carpeta "paletizado"
$PgVersion  = "16"
$PgBin      = "C:\Program Files\PostgreSQL\$PgVersion\bin"
$Puerto     = 5000

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
function Ok($texto)   { Write-Host "    $texto" -ForegroundColor Green }
function NuevaClave {
    $letras = (48..57) + (65..90) + (97..122)
    return -join (1..20 | ForEach-Object { [char]($letras | Get-Random) })
}

# --------------------------------------------------------------------------
Paso "Revisando requisitos"
if (-not (Test-Path (Join-Path $Origen "app.py"))) {
    throw "No encontre app.py en $Origen. Corre este script desde la carpeta paletizado\instalacion."
}
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "No se encontro winget. Instala 'App Installer' (Instalador de aplicacion) desde Microsoft Store y vuelve a correr."
}
New-Item -ItemType Directory -Force -Path $Base, $Respaldos, $Logs | Out-Null

# Solo Administradores y SYSTEM pueden leer C:\Tarimas (ahi quedan contrasenas).
# Se usan los SID para que funcione en Windows en espanol o en ingles.
icacls $Base /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" | Out-Null
Ok "Carpeta $Base lista (solo administradores)"

# --------------------------------------------------------------------------
Paso "Contrasenas"
$ArchivoClaves = Join-Path $Base "CONTRASENAS.txt"
if (Test-Path $ArchivoClaves) {
    $Claves = Get-Content $ArchivoClaves | Where-Object { $_ -match "=" } | ConvertFrom-StringData
    Ok "Se reutilizan las contrasenas de $ArchivoClaves"
} else {
    $Claves = @{
        CLAVE_POSTGRES   = NuevaClave
        CLAVE_BASE_DATOS = NuevaClave
        CLAVE_ADMIN      = NuevaClave
    }
    @(
        "# Contrasenas del Registro de tarimas. Guardalas en un lugar seguro.",
        "# Usuario de la pagina /admin: admin",
        "CLAVE_POSTGRES=$($Claves.CLAVE_POSTGRES)",
        "CLAVE_BASE_DATOS=$($Claves.CLAVE_BASE_DATOS)",
        "CLAVE_ADMIN=$($Claves.CLAVE_ADMIN)"
    ) | Set-Content -Encoding ASCII $ArchivoClaves
    Ok "Contrasenas nuevas guardadas en $ArchivoClaves"
}

# --------------------------------------------------------------------------
Paso "Python 3.12"
$Python = "C:\Program Files\Python312\python.exe"
if (-not (Test-Path $Python)) {
    winget install --id Python.Python.3.12 -e --scope machine --silent `
        --accept-package-agreements --accept-source-agreements
    if (-not (Test-Path $Python)) { throw "No se pudo instalar Python. Instalalo desde python.org (para todos los usuarios) y vuelve a correr." }
}
Ok "Python: $Python"

# --------------------------------------------------------------------------
Paso "PostgreSQL $PgVersion"
$Psql = Join-Path $PgBin "psql.exe"
if (-not (Test-Path $Psql)) {
    # La contrasena solo lleva letras y numeros, por eso no necesita comillas.
    $opciones = "--mode unattended --unattendedmodeui none --superpassword $($Claves.CLAVE_POSTGRES) --serverport 5432"
    winget install --id "PostgreSQL.PostgreSQL.$PgVersion" -e --silent `
        --accept-package-agreements --accept-source-agreements --override $opciones
    if (-not (Test-Path $Psql)) {
        throw ("No se pudo instalar PostgreSQL. Descargalo de postgresql.org (version $PgVersion), " +
               "usa como contrasena de 'postgres' la CLAVE_POSTGRES de $ArchivoClaves y vuelve a correr.")
    }
}
Ok "PostgreSQL: $PgBin"

# --------------------------------------------------------------------------
Paso "Base de datos"
$env:PGPASSWORD = $Claves.CLAVE_POSTGRES
function Psql($sql) {
    $salida = & $Psql -U postgres -h localhost -p 5432 -d postgres -tAc $sql
    if ($LASTEXITCODE -ne 0) {
        throw ("PostgreSQL rechazo la conexion como 'postgres'. Si PostgreSQL ya estaba instalado, " +
               "pon su contrasena en CLAVE_POSTGRES dentro de $ArchivoClaves y vuelve a correr.")
    }
    return $salida
}
$ClaveBD = $Claves.CLAVE_BASE_DATOS
if ((Psql "SELECT 1 FROM pg_roles WHERE rolname = 'tarimas'") -ne "1") {
    Psql "CREATE ROLE tarimas LOGIN PASSWORD '$ClaveBD'" | Out-Null
    Ok "Usuario 'tarimas' creado"
} else {
    Psql "ALTER ROLE tarimas WITH PASSWORD '$ClaveBD'" | Out-Null
    Ok "Usuario 'tarimas' ya existia"
}
if ((Psql "SELECT 1 FROM pg_database WHERE datname = 'tarimas'") -ne "1") {
    Psql "CREATE DATABASE tarimas OWNER tarimas ENCODING 'UTF8'" | Out-Null
    Ok "Base 'tarimas' creada"
} else {
    Ok "Base 'tarimas' ya existia (no se borra nada)"
}
Remove-Item Env:\PGPASSWORD

# --------------------------------------------------------------------------
Paso "Copiando la app a $App"
robocopy $Origen $App /MIR /XD instalacion __pycache__ datos .git /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Fallo la copia de archivos (robocopy $LASTEXITCODE)" }
$global:LASTEXITCODE = 0
Ok "App copiada"

Paso "Librerias de Python"
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) { & $Python -m venv $Venv }
$PyVenv = Join-Path $Venv "Scripts\python.exe"
& $PyVenv -m pip install --upgrade pip --quiet
& $PyVenv -m pip install -r (Join-Path $App "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de librerias (pip)" }
Ok "Librerias instaladas"

# --------------------------------------------------------------------------
Paso "Configuracion y tablas"
$DatabaseUrl = "postgresql://tarimas:$ClaveBD@localhost:5432/tarimas"
$Iniciar = Join-Path $Base "iniciar.cmd"
@(
    "@echo off",
    "rem Arranca el Registro de tarimas. Lo usa la tarea programada 'Tarimas - Servidor'.",
    "set DATABASE_URL=$DatabaseUrl",
    "set ADMIN_USUARIO=admin",
    "set ADMIN_CONTRASENA=$($Claves.CLAVE_ADMIN)",
    "set PUERTO=$Puerto",
    "cd /d `"$App`"",
    "`"$PyVenv`" servidor.py >> `"$Logs\servidor.log`" 2>&1"
) | Set-Content -Encoding ASCII $Iniciar

$env:DATABASE_URL = $DatabaseUrl
Push-Location $App
& $PyVenv init_db.py
$resultado = $LASTEXITCODE
Pop-Location
if ($resultado -ne 0) { throw "Fallo init_db.py" }
Ok "Tablas listas"

# --------------------------------------------------------------------------
Paso "Firewall (puerto $Puerto para las tabletas)"
if (-not (Get-NetFirewallRule -DisplayName "Registro de tarimas" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Registro de tarimas" -Direction Inbound -Protocol TCP `
        -LocalPort $Puerto -Action Allow -Profile Any | Out-Null
}
Ok "Puerto $Puerto abierto"

# --------------------------------------------------------------------------
Paso "Arranque automatico"
$Principal = New-ScheduledTaskPrincipal -UserId "S-1-5-18" -LogonType ServiceAccount -RunLevel Highest
$Ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -MultipleInstances IgnoreNew
Stop-ScheduledTask -TaskName "Tarimas - Servidor" -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "Tarimas - Servidor" -Force -Principal $Principal -Settings $Ajustes `
    -Action (New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Iniciar`"") `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) | Out-Null
Start-ScheduledTask -TaskName "Tarimas - Servidor"
Ok "La app arranca sola al prender la PC (tarea 'Tarimas - Servidor')"

# --------------------------------------------------------------------------
Paso "Respaldo diario"
$Respaldo = Join-Path $Base "respaldo.ps1"
@(
    "# Respaldo diario de la base de datos. Lo usa la tarea programada 'Tarimas - Respaldo'.",
    "`$env:PGPASSWORD = '$ClaveBD'",
    "`$archivo = Join-Path '$Respaldos' (""tarimas_"" + (Get-Date -Format 'yyyy-MM-dd') + "".dump"")",
    "& '$PgBin\pg_dump.exe' -U tarimas -h localhost -p 5432 -F c -f `$archivo tarimas",
    "# Se guardan los ultimos 30 dias",
    "Get-ChildItem '$Respaldos' -Filter 'tarimas_*.dump' | Where-Object { `$_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item"
) | Set-Content -Encoding ASCII $Respaldo
Register-ScheduledTask -TaskName "Tarimas - Respaldo" -Force -Principal $Principal `
    -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable) `
    -Action (New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Respaldo`"") `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "13:30") | Out-Null
Start-ScheduledTask -TaskName "Tarimas - Respaldo"
Ok "Respaldo diario a la 1:30 p.m. en $Respaldos (se hizo uno ahora)"

# --------------------------------------------------------------------------
Paso "Energia"
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null
Ok "La PC ya no se suspende estando conectada a la corriente"

# --------------------------------------------------------------------------
Start-Sleep -Seconds 5
$Ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress
try {
    Invoke-WebRequest "http://localhost:$Puerto/resumen" -UseBasicParsing -TimeoutSec 20 | Out-Null
    $estado = "La app esta funcionando."
} catch {
    $estado = "La app todavia no responde. Revisa $Logs\servidor.log"
}

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host " Instalacion terminada. $estado"
Write-Host ""
foreach ($ip in $Ips) {
    Write-Host " Tablet Linea 4:  http://${ip}:$Puerto/linea/L4"
    Write-Host " Operador:        http://${ip}:$Puerto/operador/L4"
    Write-Host " Resumen/Excel:   http://${ip}:$Puerto/resumen"
    Write-Host " Administracion:  http://${ip}:$Puerto/admin   (usuario: admin)"
    Write-Host ""
}
Write-Host " Contrasenas en: $ArchivoClaves  (guardalas en un lugar seguro)"
Write-Host "=========================================================" -ForegroundColor Green
