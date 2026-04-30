#Requires -Version 5.1
<#
.SYNOPSIS
  启动本仓库配套的 Android 虚拟设备 FundShare_API34（需已通过 sdkmanager / avdmanager 创建）。
  用法（仓库根目录）: .\scripts\start_emulator.ps1
#>
$ErrorActionPreference = "Stop"
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$emu = Join-Path $sdk "emulator\emulator.exe"
if (-not (Test-Path $emu)) {
    Write-Error "未找到 emulator.exe: $emu 。请先安装 SDK 组件: sdkmanager `"emulator`" `"system-images;android-34;google_apis;x86_64`""
}
$env:JAVA_HOME = if ($env:JAVA_HOME) { $env:JAVA_HOME } else { "C:\Program Files\Microsoft\jdk-17.0.18.8-hotspot" }
$avd = "FundShare_API34"
Write-Host "启动模拟器 $avd （关闭模拟器窗口即退出）…" -ForegroundColor Cyan
Start-Process -FilePath $emu -ArgumentList @("-avd", $avd, "-netdelay", "none", "-netspeed", "full") -WorkingDirectory (Split-Path $emu)
