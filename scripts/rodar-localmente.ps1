#Requires -Version 5.1

$ErrorActionPreference = 'Stop'

function Invoke-CheckedCommand {
    param(
        [string] $Executable,
        [string[]] $Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao executar '$Executable $($Arguments -join ' ')' (código $LASTEXITCODE)."
    }
}

$root = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $root 'backend/compose.yaml'
$envFile = Join-Path $root 'backend/.env'
$composeArgs = @('compose', '-f', $composeFile)
if (Test-Path -LiteralPath $envFile -PathType Leaf) {
    $composeArgs += @('--env-file', $envFile)
}

$docker = (Get-Command docker -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $docker) {
    throw 'Instale o Docker com Docker Compose para rodar o Sócio Digital.'
}

$ollama = (Get-Command ollama -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $ollama -and $env:LOCALAPPDATA) {
    $localOllama = Join-Path $env:LOCALAPPDATA 'Programs/Ollama/ollama.exe'
    if (Test-Path -LiteralPath $localOllama -PathType Leaf) {
        $ollama = $localOllama
    }
}
if (-not $ollama) {
    throw 'Instale o Ollama e deixe o comando ollama disponível no PATH.'
}

Invoke-CheckedCommand $docker @('compose', 'version')
Invoke-CheckedCommand $docker @('info', '--format', 'Docker {{.ServerVersion}}')
Invoke-CheckedCommand $ollama @('list')

Write-Host 'Preparando os modelos do Ollama...'
Invoke-CheckedCommand $ollama @('pull', 'qwen3:8b')
Invoke-CheckedCommand $ollama @('pull', 'qwen3-embedding:0.6b')

Push-Location $root
try {
    Write-Host 'Iniciando banco de dados, fila, armazenamento e índice vetorial...'
    Invoke-CheckedCommand $docker ($composeArgs + @('up', '-d', '--wait', '--wait-timeout', '120', 'postgres', 'redis', 'storage', 'qdrant'))

    Write-Host 'Aplicando migrações do banco...'
    Invoke-CheckedCommand $docker ($composeArgs + @('run', '--rm', '--build', 'api', 'alembic', 'upgrade', 'head'))

    Write-Host 'Iniciando o Sócio Digital...'
    Invoke-CheckedCommand $docker ($composeArgs + @('up', '-d', '--build', '--wait', '--wait-timeout', '120', 'frontend', 'worker', 'dispatcher'))

    try {
        Invoke-RestMethod -Uri 'http://localhost:8000/ready' -TimeoutSec 20 | Out-Null
    } catch {
        throw "A API iniciou, mas a checagem /ready falhou. Confira o acesso ao Ollama e execute 'docker compose -f backend/compose.yaml logs api'. $($_.Exception.Message)"
    }
} finally {
    Pop-Location
}

Write-Host 'Sócio Digital: http://localhost:3000'
Write-Host 'Documentação da API: http://localhost:8000/docs'
