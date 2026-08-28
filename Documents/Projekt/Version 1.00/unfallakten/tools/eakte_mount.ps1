<#
    Stellt den E-Akte-Mount nach einem PC- oder Docker-Neustart wieder her.

    Der Mount liegt in der Docker-Desktop-VM (NICHT in der Standard-WSL-Distro)
    und geht bei jedem Neustart verloren. Ohne ihn sieht das Backend die
    E-Akte-Dokumente auf //192.168.10.100/ServerSQL/ra nicht.

    Aufruf (PowerShell, im Projektordner):
        .\tools\eakte_mount.ps1

    Idempotent: fehlt der Mount, wird er gesetzt; sieht der laufende Container
    ihn nicht (Mount-Propagation greift nur beim Containerstart), wird das
    Backend neu gestartet. Steht schon alles, passiert nichts.

    Zugangsdaten kommen aus .env (EAKTE_SMB_USER / EAKTE_SMB_PASSWORD).
    Sie werden als Argument an wsl uebergeben und sind dadurch kurzzeitig in
    der Prozessliste sichtbar -- wie beim manuellen Handgriff auch. WSLENV
    waere sauberer, wird von der Docker-Desktop-Distro aber ignoriert
    (Variablen kommen leer an -> STATUS_LOGON_FAILURE).
#>

$ErrorActionPreference = "Stop"

$projekt = Split-Path -Parent $PSScriptRoot
$envPfad = Join-Path $projekt ".env"
$freigabe = "//192.168.10.100/ServerSQL/ra"
$ziel = "/mnt/eakte"
$container = "unfallakten-backend-dev"

if (-not (Test-Path $envPfad)) { throw ".env nicht gefunden: $envPfad" }

function Get-EnvWert($schluessel) {
    $zeile = Select-String -Path $envPfad -Pattern "^$schluessel=" | Select-Object -First 1
    if (-not $zeile) { throw "$schluessel fehlt in .env" }
    return $zeile.Line.Substring($schluessel.Length + 1).Trim()
}

function Test-ContainerSieht {
    docker exec $container sh -c "ls $ziel 2>/dev/null | head -1" 2>$null | Out-Null
    $inhalt = docker exec $container sh -c "ls $ziel 2>/dev/null | wc -l" 2>$null
    return ($LASTEXITCODE -eq 0 -and [int]$inhalt -gt 0)
}

# ── 1. Mount in der Docker-Desktop-VM ────────────────────────────────────────
Write-Host "Pruefe Mount in der Docker-Desktop-VM ..."
wsl -d docker-desktop -- sh -c "mount | grep -q ' $ziel '" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Mount vorhanden."
} else {
    Write-Host "  Fehlt - mounte $freigabe ..."
    $opt = "username=$(Get-EnvWert 'EAKTE_SMB_USER'),password=$(Get-EnvWert 'EAKTE_SMB_PASSWORD'),ro"
    wsl -d docker-desktop -- sh -c "mkdir -p $ziel" 2>$null
    wsl -d docker-desktop -- mount -t cifs $freigabe $ziel -o $opt
    if ($LASTEXITCODE -ne 0) {
        throw ("Mount fehlgeschlagen (Exit $LASTEXITCODE). Ursache mit " +
               "'wsl -d docker-desktop -- dmesg | tail -5' nachsehen: " +
               "STATUS_LOGON_FAILURE = Zugangsdaten, sonst Netzwerk/VPN zu 192.168.10.100.")
    }
    Write-Host "  Gemountet."
}

# ── 2. Sieht der laufende Container den Mount? ───────────────────────────────
Write-Host "Pruefe, ob $container den Mount sieht ..."
if (Test-ContainerSieht) {
    Write-Host "  Ja."
} else {
    Write-Host "  Nein - starte $container neu (Mount-Propagation greift nur beim Start) ..."
    docker restart $container | Out-Null
    Start-Sleep -Seconds 5
    if (-not (Test-ContainerSieht)) {
        Write-Host "Container sieht $ziel weiterhin NICHT." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
docker exec $container sh -c "ls $ziel | head -3" | ForEach-Object { Write-Host "  $_" }
Write-Host "E-Akte-Mount steht." -ForegroundColor Green
