[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Falha em $Program $Arguments (código $LASTEXITCODE)." }
}
foreach ($dependency in @('git', 'docker')) {
    if (-not (Get-Command $dependency -ErrorAction SilentlyContinue)) {
        throw "Instale $dependency. No Windows, use Docker Desktop com WSL 2. Consulte TESTE_LOCAL.md."
    }
}
Invoke-Checked 'git' @('--version')
Invoke-Checked 'docker' @('compose', 'version')
Invoke-Checked 'docker' @('info')
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host 'Criado .env a partir do exemplo; revise portas e modo antes de operar.'
}
$content = [IO.File]::ReadAllText((Join-Path (Get-Location) '.env'))
if ($content -match '(?m)^POSTGRES_PASSWORD=\s*$') {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $password = -join ($bytes | ForEach-Object { $_.ToString('x2') })
    $content = [regex]::Replace($content, '(?m)^POSTGRES_PASSWORD=\s*$', "POSTGRES_PASSWORD=$password")
    [IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $content, (New-Object Text.UTF8Encoding $false))
    Write-Host 'Senha aleatória local gerada em .env; não compartilhar esse arquivo.'
}
$content = [IO.File]::ReadAllText((Join-Path (Get-Location) '.env'))
if ($content -notmatch '(?m)^RUNTIME_PASSWORD=') { $content += "`nRUNTIME_PASSWORD=`n" }
if ($content -match '(?m)^RUNTIME_PASSWORD=\s*$') {
    $runtimeBytes = New-Object byte[] 32
    $runtimeRng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $runtimeRng.GetBytes($runtimeBytes) } finally { $runtimeRng.Dispose() }
    $runtimePassword = -join ($runtimeBytes | ForEach-Object { $_.ToString('x2') })
    $content = [regex]::Replace($content, '(?m)^RUNTIME_PASSWORD=\s*$', "RUNTIME_PASSWORD=$runtimePassword")
    [IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $content, (New-Object Text.UTF8Encoding $false))
    Write-Host 'Senha do usuário restrito gerada localmente; não compartilhar .env.'
}
Invoke-Checked 'docker' @('compose', 'config', '--quiet')
Invoke-Checked 'docker' @('compose', 'up', '-d', '--build', '--wait', 'db', 'api', 'web')
Invoke-Checked 'docker' @('compose', 'run', '--rm', 'migrate')
Invoke-Checked 'docker' @('compose', 'ps')
Write-Host 'Ambiente iniciado. Padrão: http://localhost:8080 e http://localhost:8000/docs. Consulte .env se alterou as portas.'
