#requires -Version 5
<#
.SYNOPSIS
  Report whether a Civ VII mod is Discovered / Enabled / Applied.
.DESCRIPTION
  Reads Modding.log to tell the three states apart — the key debugging step, because a
  mod can be Enabled but never Applied (e.g. a non-integer version drops it from
  "Target Mods") with no error. "Applied" is the only state that means your rows ran.
  Pass the mod id (== the deployed folder name / <Mod id=...>).
.EXAMPLE
  powershell scripts/check-applied.ps1 my-cool-mod
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ModId,

    [string]$BaseDir = "$env:LOCALAPPDATA\Firaxis Games\Sid Meier's Civilization VII"
)

$ErrorActionPreference = 'Stop'

$log = Join-Path $BaseDir 'Logs\Modding.log'
if (-not (Test-Path -LiteralPath $log)) {
    throw "Modding.log not found at $log. Launch the game at least once (logs are overwritten each launch)."
}

# Read with shared access (the game may hold the file open).
$text = [System.IO.File]::ReadAllText($log)
$lines = $text -split "`r?`n"

function Test-State($label, $found, $hint) {
    $mark = if ($found) { '[YES]' } else { '[ no]' }
    Write-Host ("  {0} {1}" -f $mark, $label)
    if (-not $found -and $hint) { Write-Host ("        -> {0}" -f $hint) -ForegroundColor Yellow }
    return $found
}

Write-Host "Checking mod '$ModId' against $log`n"

# Discovered: a "Loading Mod" line mentioning the id.
$discovered = $lines | Where-Object { $_ -match 'Loading Mod' -and $_ -match [regex]::Escape($ModId) }
# Target Mods: the id appears in the target-mods listing.
$targeted = $lines | Where-Object { $_ -match 'Target Mods' -or ($_ -match [regex]::Escape($ModId) -and $_ -match 'Target') }
# Applied: locate the "Applied all components of enabled mods" section and look for the id after it.
$appliedIdx = $null
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match 'Applied all components of enabled mods') { $appliedIdx = $i; break }
}
$applied = $false
if ($appliedIdx -ne $null) {
    $tail = $lines[$appliedIdx..([Math]::Min($appliedIdx + 400, $lines.Count - 1))]
    $applied = [bool]($tail | Where-Object { $_ -match [regex]::Escape($ModId) })
}

Test-State 'Discovered (engine found the modinfo)' ([bool]$discovered) `
    "Not deployed where the engine looks? Re-run deploy-mod.ps1 and confirm the folder is in \Mods." | Out-Null
Test-State 'Applied (action groups actually ran — your rows loaded)' $applied `
    "Enabled but not applied is the classic non-integer-version symptom. Check <Version> is an integer; inspect ModProperties via inspect-registry.ps1." | Out-Null

Write-Host ""
if ($applied) {
    Write-Host "RESULT: '$ModId' APPLIED. Your rows ran. If a bonus still does nothing, the issue is in the modifier (attach-wrapper? requirements? arg names?) — see references/troubleshooting.md." -ForegroundColor Green
} elseif ($discovered) {
    Write-Host "RESULT: '$ModId' was discovered but did NOT apply. Check version integer + ActionGroup criteria/scope. See references/troubleshooting.md." -ForegroundColor Red
} else {
    Write-Host "RESULT: '$ModId' not found in Modding.log at all. Confirm it's deployed and that this is the right mod id. See references/deploy-and-debug.md." -ForegroundColor Red
}

Write-Host "`n(Enabled/disabled state lives in Mods.sqlite — run inspect-registry.ps1 $ModId to check the toggle and the parsed Version.)"
