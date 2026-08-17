param(
    [switch]$IUnderstandThisRewritesHistory
)

$ErrorActionPreference = "Stop"

if (-not $IUnderstandThisRewritesHistory) {
    throw "This rewrites Git history. Re-run with -IUnderstandThisRewritesHistory after taking an external backup."
}

$repoRoot = (git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
    throw "Not inside a Git repository."
}

$resolvedRoot = (Resolve-Path -LiteralPath $repoRoot).Path
$expectedMarker = Join-Path $resolvedRoot "pyproject.toml"
if (-not (Test-Path -LiteralPath $expectedMarker)) {
    throw "Refusing to run outside the NovaTech repository root."
}

$backupDir = Join-Path $resolvedRoot ".history-backups"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bundlePath = Join-Path $backupDir "novatech-before-filter-$stamp.bundle"
git bundle create $bundlePath --all

git filter-repo `
  --path users.json `
  --path admins.json `
  --path carts.json `
  --path TEST_ACCOUNTS.txt `
  --path __pycache__ `
  --invert-paths `
  --force

Write-Host "History rewritten locally."
Write-Host "Backup bundle: $bundlePath"
Write-Host "Run: gitleaks detect --source ."
Write-Host "After verification, push with: git push --force-with-lease origin main"
