param([string]$Source = (Join-Path (Split-Path $PSScriptRoot) 'ZaloCallCompanion.exe'))
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Source)) { throw 'Chưa có EXE đã cài. Hãy chạy bộ cài trước.' }
$exePath = (Resolve-Path -LiteralPath $Source).Path
$link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Ghi Âm Zalo PC.lnk'))
$link.TargetPath = $exePath
$link.WorkingDirectory = Split-Path $exePath
$link.IconLocation = "$exePath,0"
$link.Save()
