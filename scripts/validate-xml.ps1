#requires -Version 5
<#
.SYNOPSIS
  Check XML well-formedness of every .xml and .modinfo in a mod folder.
.DESCRIPTION
  A malformed XML file can silently break loading or even crash the game at map gen, so
  validate before every deploy/test. This checks well-formedness only (not schema/FK
  correctness — those surface in Database.log at load time).
.EXAMPLE
  powershell scripts/validate-xml.ps1 .\mods\my-mod
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ModFolder
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ModFolder)) { throw "Folder not found: $ModFolder" }

# -Include is unreliable with -LiteralPath (filters silently ignored -> every file
# gets parsed as XML, so a UI mod's .md/.js/.css files all "fail"); filter by extension.
$files = Get-ChildItem -LiteralPath $ModFolder -Recurse -File |
    Where-Object { $_.Extension -in '.xml', '.modinfo' }
if (-not $files) { Write-Host "No .xml/.modinfo files under $ModFolder"; return }

$bad = 0
foreach ($f in $files) {
    try {
        [xml]$null = Get-Content -LiteralPath $f.FullName -Raw
        Write-Host ("  [ ok ] {0}" -f $f.FullName)
    }
    catch {
        $bad++
        Write-Host ("  [FAIL] {0}" -f $f.FullName) -ForegroundColor Red
        Write-Host ("         {0}" -f $_.Exception.Message) -ForegroundColor Red
    }
}

Write-Host ""
if ($bad -eq 0) {
    Write-Host "All $($files.Count) file(s) are well-formed." -ForegroundColor Green
} else {
    Write-Host "$bad of $($files.Count) file(s) FAILED. Fix these before deploying." -ForegroundColor Red
    exit 1
}
