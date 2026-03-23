$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$ImageName = "pm-mvp:dev"
$ContainerName = "pm-mvp"
$DataDir = Join-Path $RootDir "backend/data"

Set-Location $RootDir

if (-not (Test-Path $DataDir)) {
  New-Item -ItemType Directory -Path $DataDir | Out-Null
}

function Invoke-RetryCommand {
  param(
    [Parameter(Mandatory = $true)][int]$Attempts,
    [Parameter(Mandatory = $true)][int]$DelaySeconds,
    [Parameter(Mandatory = $true)][scriptblock]$Command
  )

  for ($i = 1; $i -le $Attempts; $i++) {
    try {
      & $Command
      return
    } catch {
      if ($i -ge $Attempts) {
        throw
      }
      Write-Warning "Command failed (attempt $i/$Attempts). Retrying in $DelaySeconds seconds..."
      Start-Sleep -Seconds $DelaySeconds
    }
  }
}

try {
  Invoke-RetryCommand -Attempts 3 -DelaySeconds 3 -Command { docker build -t $ImageName . }
} catch {
  Write-Warning "Falling back to local-only Docker build (no registry pull)."
  docker image inspect node:22-alpine *> $null
  $hasNode = $LASTEXITCODE -eq 0
  docker image inspect python:3.12-slim *> $null
  $hasPython = $LASTEXITCODE -eq 0

  if ($hasNode -and $hasPython) {
    $env:DOCKER_BUILDKIT = "0"
    docker build --pull=false -t $ImageName .
    if ($LASTEXITCODE -ne 0) {
      throw "Local-only Docker build failed"
    }
  } else {
    throw "Unable to build image: Docker Hub is unreachable and base images are not cached locally. When network is available, run: docker pull node:22-alpine && docker pull python:3.12-slim"
  }
}

$existing = docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if ($existing) {
  docker rm -f $ContainerName | Out-Null
}

docker run -d `
  --name $ContainerName `
  -p 8000:8000 `
  -v "${DataDir}:/app/backend/data" `
  --env-file (Join-Path $RootDir ".env") `
  $ImageName | Out-Null

Write-Host "PM MVP running at http://localhost:8000"
