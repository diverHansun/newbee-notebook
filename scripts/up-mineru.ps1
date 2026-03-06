param(
    [switch]$Build = $true,
    [switch]$Detach = $true,
    [switch]$WithMinio = $true
)

$ErrorActionPreference = "Stop"

function Test-HostGpu {
    $cmd = Get-Command "nvidia-smi" -ErrorAction SilentlyContinue
    if (-not $cmd) { return $false }
    try {
        & $cmd.Source "-L" | Out-Null
        return $true
    } catch {
        return $false
    }
}

$composeFiles = @("-f", "docker-compose.yml")
if (Test-HostGpu) {
    Write-Host "GPU detected: using docker-compose.gpu.yml"
    $composeFiles += @("-f", "docker-compose.gpu.yml")
} else {
    Write-Host "No GPU detected: using CPU MinerU (pipeline backend)"
}

$upArgs = @("up")
if ($Detach) { $upArgs += "-d" }
if ($Build) { $upArgs += "--build" }
$upArgs += @("--profile", "mineru-local")
if ($WithMinio) {
    Write-Host "Including MinIO profile and service"
    $upArgs += @("--profile", "minio")
    $upArgs += @("mineru-api", "minio")
} else {
    $upArgs += "mineru-api"
}

docker compose @composeFiles @upArgs

