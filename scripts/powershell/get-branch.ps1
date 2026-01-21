# Определение текущей ветки MADSpec и вывод в stdout
$branch = $null
# Сначала проверяем текущую ветку Git (как наиболее актуальный источник)
try {
  $branch = git branch --show-current 2>$null
} catch {}
# Если Git недоступен или не может определить ветку, используем config.json
if (-not $branch -and (Test-Path .madspec/config.json)) {
  $config = Get-Content .madspec/config.json | ConvertFrom-Json
  $branch = $config.currentBranch
}
# Последний fallback на main
if (-not $branch) {
  $branch = "main"
}
Write-Output $branch
