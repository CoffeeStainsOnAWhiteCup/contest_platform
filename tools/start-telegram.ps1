# Windows PowerShell. Place in the tools directory of contest_platform.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root 'tools/set_telegram_webhook.py'))) {
    throw 'Place start-telegram.ps1 in the tools folder of the repository.'
}

function Invoke-Docker {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed ($LASTEXITCODE). See the output above."
    }
}

function Get-TunnelUrl {
    # Read the ngrok agent API from inside the shared network namespace.
    $probe = @'
import requests
try:
    result = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=2).json()
    for tunnel in result.get('tunnels', []):
        addr = tunnel.get('config', {}).get('addr', '').rstrip('/')
        url = tunnel.get('public_url', '')
        if addr in ('http://127.0.0.1:8011', 'http://localhost:8011') and url.startswith('https://'):
            print(url)
            break
except (ValueError, requests.RequestException):
    pass
'@
    $probe | docker exec -i contest-tg-receiver python -
    if ($LASTEXITCODE -ne 0) { throw 'Cannot check the tunnel from contest-tg-receiver.' }
}

Push-Location $root
try {
    Invoke-Docker -Arguments @('compose', 'up', '-d')
    $running = @(Invoke-Docker -Arguments @('ps', '--format', '{{.Names}}'))
    if ($running -notcontains 'contest-tg-receiver') {
        $known = @(Invoke-Docker -Arguments @('ps', '-a', '--format', '{{.Names}}'))
        if ($known -contains 'contest-tg-receiver') {
            Invoke-Docker -Arguments @('start', 'contest-tg-receiver')
        } else {
            $server = "from fastapi import FastAPI; from app.modules.notifications.router import webhook; import uvicorn; app=FastAPI(openapi_url=None); app.add_api_route('/api/v1/telegram/webhook', webhook, methods=['POST']); uvicorn.run(app, host='127.0.0.1', port=8011)"
            Invoke-Docker -Arguments @('compose', 'run', '-d', '--rm', '--no-deps', '--name', 'contest-tg-receiver', 'api', 'python', '-c', $server)
        }
    }
    $publicUrl = Get-TunnelUrl
    if (!$publicUrl -and $running -notcontains 'contest-tg-ngrok') {
        $previousToken = $env:NGROK_AUTHTOKEN
        try {
            if (!$previousToken) {
                $tokenDir = Join-Path $env:LOCALAPPDATA 'ContestPlatform'
                $tokenFile = Join-Path $tokenDir 'ngrok-token.xml'
                if (Test-Path $tokenFile) {
                    $secret = Import-Clixml -LiteralPath $tokenFile
                } else {
                    $secret = Read-Host 'Enter ngrok authtoken for this Windows user' -AsSecureString
                    if (!$secret.Length) { throw 'Empty ngrok token.' }
                    New-Item -ItemType Directory -Force -Path $tokenDir | Out-Null
                    $secret | Export-Clixml -LiteralPath $tokenFile
                }
                $env:NGROK_AUTHTOKEN = [System.Net.NetworkCredential]::new('', $secret).Password
            }
            Invoke-Docker -Arguments @('run', '-d', '--rm', '--name', 'contest-tg-ngrok', '--network', 'container:contest-tg-receiver', '-e', 'NGROK_AUTHTOKEN', 'ngrok/ngrok:latest', 'http', 'http://127.0.0.1:8011')
        } finally {
            $env:NGROK_AUTHTOKEN = $previousToken
        }
    }
    for ($attempt = 0; !$publicUrl -and $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        $publicUrl = Get-TunnelUrl
    }
    if (!$publicUrl) { throw 'No HTTPS tunnel to port 8011. Check docker ps -a and the ngrok agent.' }
    Invoke-Docker -Arguments @('compose', 'exec', '-T', 'api', 'python', '-m', 'tools.set_telegram_webhook', "$publicUrl/api/v1/telegram/webhook")
} finally {
    Pop-Location
}
