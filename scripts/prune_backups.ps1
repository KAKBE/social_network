<#
.SYNOPSIS
  Deletes old backups, keeping the newest -Keep files of one database.
.DESCRIPTION
  Files are ordered by the timestamp in their name. Before deleting anything the newest copy
  is checked with pg_restore --list; if it is not readable, nothing is deleted.
  With -DryRun the script only lists what it would delete.
#>
param(
    [string]$Database = "posledu",
    [string]$BackupDir = (Join-Path $PSScriptRoot "..\backups"),
    [int]$Keep = 7,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if ($Keep -lt 1) { throw "-Keep must be at least 1: the newest copy is never deleted" }

$files = @(Get-ChildItem -Path $BackupDir -Filter "$($Database)_*.dump" | Sort-Object Name -Descending)
if ($files.Count -eq 0) { throw "No backups of $Database in $BackupDir" }

$newest = $files[0]
$inContainer = "/tmp/" + $newest.Name
docker compose cp $newest.FullName "db:$inContainer"
if ($LASTEXITCODE -ne 0) { throw "docker compose cp failed" }
docker compose exec -T db pg_restore --list $inContainer | Out-Null
$readable = $LASTEXITCODE -eq 0
docker compose exec -T db rm -f $inContainer | Out-Null
if (-not $readable) { throw "Newest backup $($newest.Name) is not readable; nothing deleted" }

$kept = $files | Select-Object -First $Keep
$toDelete = @($files | Select-Object -Skip $Keep)
Write-Output "Newest (checked): $($newest.Name)"
Write-Output "Keep ($($kept.Count)): $(($kept | ForEach-Object Name) -join ', ')"
Write-Output "Delete ($($toDelete.Count)): $(($toDelete | ForEach-Object Name) -join ', ')"
if ($DryRun) {
    Write-Output "Dry run: nothing deleted"
    exit 0
}
$toDelete | Remove-Item
Write-Output "Deleted $($toDelete.Count) file(s)"
