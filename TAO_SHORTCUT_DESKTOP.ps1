param(
    [Parameter(Mandatory=$true)][string]$Source
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
    throw "Khong tim thay tep EXE: $Source"
}
$appDir = Join-Path $env:LOCALAPPDATA 'Programs\Zalo Call Companion'
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
$target = Join-Path $appDir 'ZaloCallCompanion.exe'
Copy-Item -LiteralPath $Source -Destination $target -Force
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcut = Join-Path $desktop 'Ghi Âm Zalo PC.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $target
$link.WorkingDirectory = $appDir
$link.IconLocation = "$target,0"
$link.Description = 'Ghi Am Zalo PC - Ghi am cuoc goi va luu tren may.'
$link.Save()
Write-Host "Da cai: $target"
Write-Host "Da tao shortcut: $shortcut"
