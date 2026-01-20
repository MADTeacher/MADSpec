# Определение текущей ветки MADSpec и вывод в stdout
$branch = $null
if (Test-Path .madspec/config.json) {
  $config = Get-Content .madspec/config.json | ConvertFrom-Json
  $branch = $config.currentBranch
}
if (-not $branch) {
  try {
    $branch = git branch --show-current 2>$null
  } catch {}
}
if (-not $branch) {
  $branch = "main"
}
Write-Output $branch
