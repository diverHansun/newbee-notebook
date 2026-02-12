param(
    [Parameter(Mandatory = $true)]
    [string]$Id
)

$uuidPattern = '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
if ($Id -notmatch $uuidPattern) {
    Write-Error "Invalid document id format. Expected UUID."
    exit 1
}

$documentsDir = Join-Path $PSScriptRoot "..\data\documents"
$documentsDir = (Resolve-Path $documentsDir).Path
$targetPath = Join-Path $documentsDir $Id

if (-not (Test-Path $targetPath)) {
    Write-Host "Directory does not exist: $targetPath"
    exit 0
}

Write-Host "Target directory: $targetPath"
Get-ChildItem $targetPath | Format-Table Name, Length, LastWriteTime -AutoSize

$sizeBytes = (Get-ChildItem $targetPath -Recurse -File | Measure-Object -Property Length -Sum).Sum
if (-not $sizeBytes) { $sizeBytes = 0 }
$sizeMB = [math]::Round($sizeBytes / 1MB, 2)
Write-Host "Total size: $sizeMB MB"

$confirm = Read-Host "Delete this directory? [y/N]"
if ($confirm -ne 'y' -and $confirm -ne 'Y') {
    Write-Host "Canceled."
    exit 0
}

Remove-Item -Path $targetPath -Recurse -Force
Write-Host "Deleted: $targetPath"

