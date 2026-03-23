$ErrorActionPreference = "Stop"

$ContainerName = "pm-mvp"

$existing = docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if ($existing) {
  docker rm -f $ContainerName | Out-Null
  Write-Host "Stopped and removed $ContainerName"
} else {
  Write-Host "Container $ContainerName is not running"
}
