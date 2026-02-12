$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceDir = Join-Path $repoRoot 'data/exports'
$targetDir = Join-Path $repoRoot 'web/f1-report/public/data'

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

$files = @(
  'standings_progression.json',
  'points_heatmap.json',
  'q3_gaps.json',
  'pole_to_win.json',
  'ch3_pace.json',
  'ch4_pitstops.json',
  'ch5_overtakes.json'
)

foreach ($file in $files) {
  $src = Join-Path $sourceDir $file
  if (-not (Test-Path $src)) {
    throw "Missing export file: $src"
  }

  Copy-Item -Path $src -Destination (Join-Path $targetDir $file) -Force
}

Write-Host "Synced $($files.Count) files to $targetDir"
