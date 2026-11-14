<#
.SYNOPSIS
  Restores a backup file into a separate, newly created database.
.DESCRIPTION
  Refuses to touch an existing database: restore always goes into an empty one, which is
  then checked and only after that may replace the working database.
#>
param(
    [Parameter(Mandatory = $true)][string]$File,
    [string]$Target = "posledu_restore"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Invoke-Checked([string]$what, [scriptblock]$command) {
    & $command
    if ($LASTEXITCODE -ne 0) { throw "$what failed with exit code $LASTEXITCODE" }
}

$resolved = (Resolve-Path $File).Path
$inContainer = "/tmp/" + (Split-Path $resolved -Leaf)

$exists = docker compose exec -T db psql -U posledu -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$Target'"
if ($exists -eq "1") { throw "Database $Target already exists; choose another -Target or drop it first" }

Invoke-Checked "docker compose cp" { docker compose cp $resolved "db:$inContainer" }
Invoke-Checked "createdb" { docker compose exec -T db createdb -U posledu $Target }
Invoke-Checked "pg_restore" { docker compose exec -T db pg_restore -U posledu -d $Target --no-owner --exit-on-error $inContainer }
docker compose exec -T db rm -f $inContainer | Out-Null
Write-Output "Restored $(Split-Path $resolved -Leaf) into $Target"
