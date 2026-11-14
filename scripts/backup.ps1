<#
.SYNOPSIS
  Backs up the project database to backups/<db>_<yyyyMMdd-HHmmss>.dump (pg_dump custom format).
.DESCRIPTION
  pg_dump runs inside the db container and takes one consistent snapshot of the database.
  The dump is checked with pg_restore --list before it is kept; on any error the script
  writes ERROR to backups/backup.log and exits with code 1.
#>
param(
    [string]$Database = "posledu",
    [string]$BackupDir = (Join-Path $PSScriptRoot "..\backups"),
    [string]$CopyTo = ""
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$log = Join-Path $BackupDir "backup.log"

function Write-Log([string]$level, [string]$message) {
    $line = "{0} {1} {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $level, $message
    Add-Content -Path $log -Value $line -Encoding UTF8
    Write-Output $line
}

function Invoke-Checked([string]$what, [scriptblock]$command) {
    & $command
    if ($LASTEXITCODE -ne 0) { throw "$what failed with exit code $LASTEXITCODE" }
}

$name = "{0}_{1}.dump" -f $Database, (Get-Date -Format "yyyyMMdd-HHmmss")
$target = Join-Path $BackupDir $name
$inContainer = "/tmp/$name"

try {
    Invoke-Checked "pg_dump" { docker compose exec -T db pg_dump -U posledu -d $Database -Fc -f $inContainer }
    Invoke-Checked "pg_restore --list" { docker compose exec -T db pg_restore --list $inContainer | Out-Null }
    Invoke-Checked "docker compose cp" { docker compose cp "db:$inContainer" $target }
    docker compose exec -T db rm -f $inContainer | Out-Null
    $size = (Get-Item $target).Length
    Write-Log "OK" "$name $size bytes"
    if ($CopyTo) {
        New-Item -ItemType Directory -Force -Path $CopyTo | Out-Null
        Copy-Item $target $CopyTo
        Write-Log "OK" "$name copied to $CopyTo"
    }
} catch {
    Write-Log "ERROR" "$name $($_.Exception.Message)"
    exit 1
}
