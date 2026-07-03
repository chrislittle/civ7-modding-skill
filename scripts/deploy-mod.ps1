#requires -Version 5
<#
.SYNOPSIS
  Deploy a Civ VII mod by copying the dev folder into the game's Mods directory.
.DESCRIPTION
  Removes any existing deployed copy with the same folder name, then copies the dev
  folder fresh. Deploys a real copied folder (not a junction). Re-running is harmless.
.EXAMPLE
  powershell scripts/deploy-mod.ps1 .\mods\my-mod
.EXAMPLE
  powershell scripts/deploy-mod.ps1 .\mods\my-mod -ModsDir "D:\Civ7\Mods"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$DevFolder,

    [string]$ModsDir = "$env:LOCALAPPDATA\Firaxis Games\Sid Meier's Civilization VII\Mods"
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $DevFolder)) {
    throw "Dev folder not found: $DevFolder"
}
$DevFolder = (Resolve-Path -LiteralPath $DevFolder).Path
$name = Split-Path -Leaf $DevFolder

if (-not (Test-Path -LiteralPath $ModsDir)) {
    throw "Mods dir not found: $ModsDir`nIs Civ VII installed for this user? Pass -ModsDir to override."
}

# Sanity check: warn if there's no .modinfo at the root of the dev folder.
$modinfo = Get-ChildItem -LiteralPath $DevFolder -Filter '*.modinfo' -File -ErrorAction SilentlyContinue
if (-not $modinfo) {
    Write-Warning "No .modinfo found at the root of $DevFolder - is this the mod folder?"
}

$dest = Join-Path $ModsDir $name
if (Test-Path -LiteralPath $dest) {
    Write-Host "Removing existing deployed copy: $dest"
    Remove-Item -LiteralPath $dest -Recurse -Force
}

Write-Host "Copying $DevFolder -> $dest"
Copy-Item -LiteralPath $DevFolder -Destination $dest -Recurse -Force

Write-Host "Deployed '$name'."
Write-Host "Next: launch Civ VII -> Add-Ons -> enable the mod -> start a NEW game."
Write-Host "Then verify it applied:  powershell scripts/check-applied.ps1 $name"
