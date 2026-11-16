[CmdletBinding()]
param(
    [string]$ApiUrl = 'http://localhost:8000',
    [string]$WebUrl = 'http://localhost:8080'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
function Invoke-Docker {
    param([string[]]$DockerArguments)
    $result = & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw "Falha no Docker: $DockerArguments" }
    return $result
}
Invoke-Docker -DockerArguments @('compose', 'config', '--quiet')
$health = Invoke-RestMethod "$ApiUrl/api/v1/health"
if ($health.status -ne 'ok' -or $health.database -ne 'connected') {
    throw 'Banco/API indisponíveis.'
}
$before = (Invoke-RestMethod "$ApiUrl/api/v1/server-info").instance_id
$parsedId = [guid]::Empty
if (-not [guid]::TryParse([string]$before, [ref]$parsedId)) { throw 'UUID inválido.' }
Invoke-Docker -DockerArguments @('compose', 'run', '--rm', 'migrate')
Invoke-Docker -DockerArguments @('compose', 'run', '--rm', 'migrate')
Invoke-Docker -DockerArguments @('compose', 'restart', 'db', 'api')
Invoke-Docker -DockerArguments @('compose', 'up', '-d', '--wait', 'api', 'web')
$after = (Invoke-RestMethod "$ApiUrl/api/v1/server-info").instance_id
if ($before -ne $after) { throw 'UUID alterado após reinício/migração.' }
$proxied = Invoke-RestMethod "$WebUrl/api/v1/server-info"
if ($proxied.instance_id -ne $before) { throw 'Proxy aponta para outra instalação.' }
foreach ($url in @($WebUrl, "$ApiUrl/docs", "$ApiUrl/openapi.json")) {
    if ((Invoke-WebRequest -UseBasicParsing $url).StatusCode -ne 200) {
        throw "Página indisponível: $url"
    }
}
foreach ($service in @('api', 'web')) {
    $uid = Invoke-Docker -DockerArguments @('compose', 'exec', '-T', $service, 'id', '-u')
    if ([int]$uid -eq 0) { throw "Serviço $service executa como root." }
}
$databaseId = Invoke-Docker -DockerArguments @('compose', 'ps', '-q', 'db')
$databaseInfo = (Invoke-Docker -DockerArguments @('inspect', $databaseId) | ConvertFrom-Json)[0]
if ($databaseInfo.HostConfig.PortBindings.PSObject.Properties.Count -gt 0) {
    throw 'PostgreSQL possui porta publicada no host.'
}
if (-not ($databaseInfo.Mounts | Where-Object {
    $_.Type -eq 'volume' -and $_.Destination -eq '/var/lib/postgresql/data'
})) { throw 'Volume persistente PostgreSQL ausente.' }
Invoke-Docker -DockerArguments @('compose', 'ps')
Write-Host 'APROVADO: saúde, migrações repetidas, UUID persistente, proxy, páginas, usuário não root e volume PostgreSQL sem porta publicada.'
