[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot '../..')
docker compose run --rm migrate python -m app.manage seed-demo
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar a demonstração. Confira o modo cloud e as migrações.' }
