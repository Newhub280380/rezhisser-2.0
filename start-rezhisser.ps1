# Rezhisser 2.0 (Maestro + cloud backend): start with one command, open the browser.
# No autostart, no scheduler: runs only when this script is started.
#   start-rezhisser.cmd            start (or just open the browser if already running)
#   start-rezhisser.cmd -Stop      stop the server started from this folder
param([int]$Port = $(if ($env:SERVER_PORT) { [int]$env:SERVER_PORT } else { 7860 }), [switch]$Stop, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Python = Join-Path $Root 'app\env\Scripts\python.exe'
$Url = "http://127.0.0.1:$Port/"
$LogDir = Join-Path $env:LOCALAPPDATA 'Rezhisser'
$Log = Join-Path $LogDir "server-$Port.log"

function Test-Up {
    try { (Invoke-WebRequest "$($Url)api/v1/cloud-config" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false }
}

function Get-OwnServer {
    # Only this folder's python on our port (a venv python runs launch.py in a child of the base
    # interpreter, so check the owner and its parent). Other Python apps are never touched.
    $owners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($id in $owners) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id"
        if (-not $p) { continue }
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)"
        if ($p.ExecutablePath -ieq $Python) { $p }
        elseif ($parent -and $parent.ExecutablePath -ieq $Python) { $parent; $p }
    }
}

if ($Stop) {
    $own = @(Get-OwnServer)
    if (-not $own) { Write-Host "Rezhisser is not running on port $Port."; exit 0 }
    foreach ($p in $own) { Stop-Process -Id $p.ProcessId -Force; Write-Host "Stopped Rezhisser (PID $($p.ProcessId))." }
    exit 0
}

if (Test-Up) {
    Write-Host "Rezhisser is already running: $Url"
    if (-not $NoBrowser) { Start-Process $Url }
    exit 0
}

if (-not (Test-Path $Python)) {
    Write-Host "Python environment not found: $Python"
    Write-Host "Install Maestro first (Pinokio Install), then run this script again."
    exit 1
}

# First start on a clean copy: create .env from .env.example (cloud fal + Wan 2.2 by default).
# Keys stay empty; they are entered in Settings -> Integrations -> Cloud.
$EnvFile = Join-Path $Root '.env'
if (-not (Test-Path $EnvFile) -and (Test-Path (Join-Path $Root '.env.example'))) {
    Copy-Item (Join-Path $Root '.env.example') $EnvFile
    Write-Host 'Created .env from .env.example (keys are entered in Settings -> Integrations -> Cloud).'
}

# Rebuild the UI only when the built bundle is missing (same rule as start.js).
if (-not (Test-Path (Join-Path $Root 'ui\dist\index.html'))) {
    Write-Host 'Building the interface (first start only)...'
    Push-Location (Join-Path $Root 'ui')
    try {
        if (-not (Test-Path 'node_modules')) { npm install; if ($LASTEXITCODE) { throw 'npm install failed' } }
        npm run build; if ($LASTEXITCODE) { throw 'UI build failed' }
    } finally { Pop-Location }
}

New-Item -ItemType Directory -Force $LogDir | Out-Null
$env:SERVER_PORT = "$Port"
$env:PYTHONUNBUFFERED = '1'
Write-Host "Starting Rezhisser on $Url (log: $Log)"
$server = Start-Process -PassThru -FilePath $Python -ArgumentList 'launch.py' -WorkingDirectory (Join-Path $Root 'app') `
    -WindowStyle Hidden -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"

$deadline = (Get-Date).AddMinutes(5)
while ((Get-Date) -lt $deadline) {
    if (Test-Up) {
        Write-Host "Rezhisser is ready: $Url"
        if (-not $NoBrowser) { Start-Process $Url }
        exit 0
    }
    if ($server.HasExited) {
        Write-Host "Rezhisser stopped during start. Last log lines:"
        Get-Content "$Log.err" -Tail 20 -ErrorAction SilentlyContinue
        exit 1
    }
    Start-Sleep -Seconds 2
}
Write-Host "Rezhisser did not answer within 5 minutes. Log: $Log"
exit 1
