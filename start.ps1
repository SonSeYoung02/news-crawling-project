param(
    [switch]$Crawl
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Start-Window {
    param([string]$Title, [string]$Cmd)
    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
        "`$host.UI.RawUI.WindowTitle = '$Title'; $Cmd"
}

if ($Crawl) {
    Write-Host "[Crawler] Starting news crawl..." -ForegroundColor Cyan
    $py = "$Root\news-crawling\venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { $py = "python" }
    Start-Window "[Crawler]" "Set-Location '$Root\news-crawling'; & '$py' main.py --run"
}

Write-Host "[Backend]  Starting uvicorn..." -ForegroundColor Green
Start-Window "[Backend  :8000]" "Set-Location '$Root\news-viewer\backend'; .\.venv\Scripts\Activate.ps1; uvicorn main:app --reload"

Write-Host "[Frontend] Starting Vite..." -ForegroundColor Yellow
Start-Window "[Frontend :5173]" "Set-Location '$Root\news-viewer\frontend'; npm run dev"

Write-Host ""
Write-Host "=====================================" -ForegroundColor White
Write-Host "  Backend  -> http://localhost:8000"  -ForegroundColor Green
Write-Host "  Frontend -> http://localhost:5173"  -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor White
Write-Host "  (To also crawl: .\start.ps1 -Crawl)" -ForegroundColor Gray
