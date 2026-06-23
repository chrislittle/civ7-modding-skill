#requires -Version 5
<#
.SYNOPSIS
  Inspect the locked Mods.sqlite registry by querying a copy.
.DESCRIPTION
  Mods.sqlite is locked while the game runs, so this copies it to %TEMP% and queries
  the copy. Shows each mod's Disabled flag (NULL/0 = enabled, 1 = disabled) and the
  Version the engine actually parsed (ModProperties) — useful to catch a non-integer
  version that parsed to 0/empty. Optionally filter to one mod id.
.EXAMPLE
  powershell scripts/inspect-registry.ps1
.EXAMPLE
  powershell scripts/inspect-registry.ps1 my-cool-mod
#>
param(
    [string]$ModId,
    [string]$BaseDir = "$env:LOCALAPPDATA\Firaxis Games\Sid Meier's Civilization VII",
    [string]$Sqlite  = "$env:TEMP\sqlitetools\sqlite3.exe"
)

$ErrorActionPreference = 'Stop'

$src = Join-Path $BaseDir 'Mods.sqlite'
if (-not (Test-Path -LiteralPath $src)) { throw "Mods.sqlite not found at $src" }

if (-not (Test-Path -LiteralPath $Sqlite)) {
    Write-Warning "sqlite3.exe not found at $Sqlite."
    Write-Warning "Install/locate sqlite3 and pass -Sqlite <path>, or open the copied DB in any SQLite browser."
}

$copy = Join-Path $env:TEMP 'Mods_copy.sqlite'
Copy-Item -LiteralPath $src -Destination $copy -Force
Write-Host "Copied locked registry -> $copy`n"

if (-not (Test-Path -LiteralPath $Sqlite)) {
    Write-Host "Copy made. Open it manually to inspect tables Mods (ModId, Disabled) and ModProperties (Name='Version')."
    return
}

$filter = if ($ModId) { "WHERE ModId LIKE '%$ModId%'" } else { '' }

Write-Host "=== Mods (Disabled: NULL/0 = enabled, 1 = disabled) ==="
& $Sqlite -header -column $copy "SELECT ModRowId, ModId, Disabled FROM Mods $filter ORDER BY ModId;"

Write-Host "`n=== ModProperties: Version (the value the engine PARSED — should be an integer) ==="
$verFilter = if ($ModId) {
    "WHERE Name='Version' AND ModRowId IN (SELECT ModRowId FROM Mods WHERE ModId LIKE '%$ModId%')"
} else { "WHERE Name='Version'" }
& $Sqlite -header -column $copy "SELECT ModRowId, Name, Value FROM ModProperties $verFilter ORDER BY ModRowId;"

Write-Host "`nIf a mod shows enabled here but never reaches 'Applied' in Modding.log, suspect the Version (must be an integer)."
