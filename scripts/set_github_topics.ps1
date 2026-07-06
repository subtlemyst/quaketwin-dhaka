# Set GitHub repository topics (About section) via API.
# Requires a Personal Access Token with repo scope:
#   $env:GITHUB_TOKEN = "ghp_..."
#   powershell -File scripts/set_github_topics.ps1

$ErrorActionPreference = "Stop"
$owner = "subtlemyst"
$repo = "quaketwin-dhaka"
$topicsFile = Join-Path $PSScriptRoot "..\.github\repository-topics.txt"

if (-not $env:GITHUB_TOKEN) {
    Write-Host "GITHUB_TOKEN not set. Set topics manually on GitHub:"
    Write-Host "  Repo -> About (gear icon) -> Topics -> paste lines from .github/repository-topics.txt"
    exit 1
}

$topics = Get-Content $topicsFile | Where-Object { $_.Trim() -ne "" }
$body = @{ names = @($topics) } | ConvertTo-Json

$headers = @{
    Authorization = "Bearer $env:GITHUB_TOKEN"
    Accept        = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

Invoke-RestMethod `
    -Method PUT `
    -Uri "https://api.github.com/repos/$owner/$repo/topics" `
    -Headers $headers `
    -Body $body `
    -ContentType "application/json"

Write-Host "Topics set: $($topics -join ', ')"
