#Requires -Version 5.1
<#
.SYNOPSIS
  用 sdkmanager 下载「Android Emulator Hypervisor Driver」组件，并提示以管理员身份运行官方静默安装脚本。
  若仍无法启动 x86_64 模拟器，请启用 Windows「虚拟机监控程序平台」并重启（见 README_ANDROID.md）。
#>
$ErrorActionPreference = "Stop"
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$sdkmanager = Get-ChildItem -Path "$sdk\cmdline-tools" -Recurse -Filter "sdkmanager.bat" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $sdkmanager) {
    Write-Host "未找到 sdkmanager.bat（期望路径类似 $sdk\cmdline-tools\...\bin\）。请先安装 Android SDK Command-line Tools。" -ForegroundColor Red
    exit 1
}

Write-Host "使用: $($sdkmanager.FullName)" -ForegroundColor Cyan
Write-Host "正在安装 extras;google;Android_Emulator_Hypervisor_Driver …（自动应答 y）" -ForegroundColor Cyan
# sdkmanager 可能提示接受许可证，用 cmd 管道 echo y
cmd /c "echo y| `"$($sdkmanager.FullName)`" --install `"extras;google;Android_Emulator_Hypervisor_Driver`""
if ($LASTEXITCODE -ne 0) {
    Write-Warning "sdkmanager 退出码 $LASTEXITCODE。若未接受许可证，可在 cmd 中先执行: sdkmanager --licenses"
}

$bat = Join-Path $sdk "extras\google\Android_Emulator_Hypervisor_Driver\silent_install.bat"
Write-Host ""
if (Test-Path $bat) {
    Write-Host "下载完成。请以「管理员身份」运行安装脚本（右键 → 以管理员身份运行）：" -ForegroundColor Yellow
    Write-Host "  $bat" -ForegroundColor White
    Write-Host ""
    Write-Host "安装后可在管理员 CMD 执行: sc query aehd （STATE 为 RUNNING 表示驱动就绪）" -ForegroundColor Gray
} else {
    Write-Host "未找到 silent_install.bat。也可用 Android Studio：SDK Manager → SDK Tools → Android Emulator Hypervisor Driver。" -ForegroundColor Yellow
}
