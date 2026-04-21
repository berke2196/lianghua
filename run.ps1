Set-Location $PSScriptRoot
$ErrorActionPreference = "Continue"
function Write-Banner($m,$col="Cyan"){Write-Host ("="*44) -ForegroundColor $col;Write-Host "  $m" -ForegroundColor $col;Write-Host ("="*44) -ForegroundColor $col}
Write-Banner "AsterDex HFT Trader"

function Load-Env {
    if(Test-Path "$PSScriptRoot\.env"){
        Get-Content "$PSScriptRoot\.env"|ForEach-Object{
            if($_-match"^\s*([A-Z_][A-Z0-9_]*)=(.+)$"){
                [System.Environment]::SetEnvironmentVariable($Matches[1],$Matches[2].Trim(),"Process")
            }
        }
    }
}
Load-Env
$BP = if($env:BACKEND_PORT){$env:BACKEND_PORT.Trim()}else{"8000"}
New-Item -ItemType Directory -Path "$PSScriptRoot\logs" -Force|Out-Null

#  Kill all 
Write-Host "[INFO] Killing old processes..." -ForegroundColor Yellow
Get-Process python,pythonw,node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2

# Wait port free
for($i=0;$i-lt10;$i++){
    $busy = netstat -ano 2>$null | Select-String "\s:$BP\s" | Where-Object {$_ -match "LISTEN"}
    if(-not $busy){ Write-Host "[OK] Port $BP free" -ForegroundColor Green; break }
    Start-Sleep 1
}

#  Step 1: Sync prefix (read from .env; generate only if missing)
Write-Host "[INFO] Syncing API prefix..." -ForegroundColor Yellow
Load-Env
$prefixOk = $false
if($env:REACT_APP_API_PREFIX -and $env:REACT_APP_API_PREFIX.Trim().Length -gt 0){
    Write-Host "[OK] Prefix already in .env: $env:REACT_APP_API_PREFIX" -ForegroundColor Green
    $prefixOk = $true
} else {
    Write-Host "[INFO] No prefix found, generating via python..." -ForegroundColor Yellow
    & python -c "from dotenv import load_dotenv; load_dotenv(); import asterdex_backend" *> "$PSScriptRoot\logs\init_out.txt"
    Start-Sleep 2
    Load-Env
    if($env:REACT_APP_API_PREFIX -and $env:REACT_APP_API_PREFIX.Trim().Length -gt 0){
        Write-Host "[OK] Prefix: $env:REACT_APP_API_PREFIX" -ForegroundColor Green
        $prefixOk = $true
    }
}

# 确保没有残留python进程
Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
for($i=0;$i-lt8;$i++){
    $busy = netstat -ano 2>$null | Select-String "\s:$BP\s" | Where-Object {$_ -match "LISTEN"}
    if(-not $busy){ break }; Start-Sleep 1
}

if(-not $prefixOk){
    Write-Host "[ERROR] Failed to get prefix:" -ForegroundColor Red
    Get-Content "$PSScriptRoot\logs\init_out.txt" -ErrorAction SilentlyContinue | Select-Object -Last 20
    Read-Host "Press Enter to exit"; exit 1
}

#  Step 2: Build 
Write-Host "[INFO] Building frontend..." -ForegroundColor Yellow
$env:REACT_APP_API_PREFIX = $env:REACT_APP_API_PREFIX
$out = & npm run build 2>&1
if($LASTEXITCODE -ne 0){
    Write-Host "[ERROR] Build failed:" -ForegroundColor Red
    $out | Select-Object -Last 20 | ForEach-Object { Write-Host $_ }
    Read-Host "Press Enter to exit"; exit 1
}
Write-Host "[OK] Build complete" -ForegroundColor Green

#  Step 3: Backend window (watchdog)
Write-Host "[INFO] Starting backend on port $BP..." -ForegroundColor Yellow
$beScript = "$PSScriptRoot\logs\_run_backend.ps1"
@"
`$Host.UI.RawUI.WindowTitle = 'AsterDex Backend :$BP'
Set-Location '$PSScriptRoot'
if(Test-Path '.env'){ Get-Content '.env' | ForEach-Object { if(`$_ -match '^\s*([A-Z_][A-Z0-9_]*)=(.+)$'){ [System.Environment]::SetEnvironmentVariable(`$Matches[1],`$Matches[2].Trim(),'Process') } } }
Write-Host '=== AsterDex Backend ===' -ForegroundColor Cyan
python watchdog.py
"@ | Set-Content $beScript -Encoding UTF8
Start-Process powershell.exe -ArgumentList "-NoExit","-NoProfile","-File",$beScript -WindowStyle Normal

# Wait backend ready
$ready = $false
Write-Host "[INFO] Waiting backend on :$BP..." -ForegroundColor Yellow
for($i=1;$i-le30;$i++){
    Start-Sleep 1
    try{
        $r = Invoke-RestMethod "http://127.0.0.1:$BP/cfg" -TimeoutSec 2 -ErrorAction Stop
        if($r.p){ $ready=$true; Write-Host "[OK] Backend ready after ${i}s" -ForegroundColor Green; break }
    }catch{}
    Write-Host "  Waiting... ${i}s" -ForegroundColor DarkGray
}
if(-not $ready){ Write-Host "[ERROR] Backend timeout" -ForegroundColor Red; Read-Host "Press Enter"; exit 1 }

#  Step 4: Frontend window 
Write-Host "[INFO] Starting frontend on :3000..." -ForegroundColor Yellow
$feScript = "$PSScriptRoot\logs\_run_frontend.ps1"
@"
`$Host.UI.RawUI.WindowTitle = 'AsterDex Frontend :3000'
Set-Location '$PSScriptRoot'
Write-Host '=== AsterDex Frontend ===' -ForegroundColor Cyan
npx serve -s build -l 3000 --no-clipboard
"@ | Set-Content $feScript -Encoding UTF8
Start-Process powershell.exe -ArgumentList "-NoExit","-NoProfile","-File",$feScript -WindowStyle Normal
Start-Sleep 4

Write-Host ""
Write-Banner "ALL SERVICES READY" "Green"
Write-Host "  Frontend  ->  http://localhost:3000" -ForegroundColor Green
Write-Host "  Backend   ->  http://localhost:$BP"  -ForegroundColor Green
Write-Host ""
Write-Host "  Admin: admin / (ADMIN_PASSWORD in .env)" -ForegroundColor Yellow
Write-Host ""
Start-Process "http://localhost:3000"
Read-Host "Press Enter to close launcher"