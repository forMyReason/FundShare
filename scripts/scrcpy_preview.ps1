#Requires -Version 5.1
<#
.SYNOPSIS
  在电脑上投屏真机并可用鼠标点击（需已安装 scrcpy、USB 调试已开）。
  安装：winget install Genymobile.scrcpy
#>
$ErrorActionPreference = "Stop"
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$adb = Join-Path $sdk "platform-tools\adb.exe"
if (-not (Test-Path $adb)) {
    Write-Error "未找到 adb: $adb 。请安装 Android SDK platform-tools 或设置 ANDROID_HOME"
}
$env:Path = "$(Split-Path $adb -Parent);$env:Path"
$scrcpy = Get-Command scrcpy -ErrorAction SilentlyContinue
if (-not $scrcpy) {
    Write-Error "未找到 scrcpy。请执行: winget install Genymobile.scrcpy 后重开终端"
}
Write-Host "已连接设备：" -ForegroundColor Cyan
& $adb devices
Write-Host "`n启动 scrcpy（关闭投屏窗口即退出）…" -ForegroundColor Cyan
& scrcpy @args
