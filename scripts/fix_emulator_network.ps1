#Requires -Version 5.1
<#
.SYNOPSIS
  在已连接 adb 的模拟器/真机上，关闭「Private DNS」并调整实体键盘/IME 设置，
  缓解 fund.eastmoney.com 无法解析、小键盘不响应等问题。

  用法（模拟器已开、adb devices 可见 device）:
    .\scripts\fix_emulator_network.ps1
#>
$ErrorActionPreference = "Stop"
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$adb = Join-Path $sdk "platform-tools\adb.exe"
if (-not (Test-Path $adb)) {
    Write-Error "未找到 adb: $adb"
}
$dev = & $adb devices
if ($dev -notmatch "`tdevice$") {
    Write-Host "未检测到已连接设备。请先启动模拟器或连接真机，再重试。" -ForegroundColor Red
    exit 1
}

function Sh([string]$arg) {
    & $adb shell $arg
}

Write-Host "==> 关闭 Private DNS（避免模拟器内 DNS 全失败）" -ForegroundColor Cyan
# AOSP: PRIVATE_DNS_MODE_OFF = 1
Sh "settings put global private_dns_mode 1" | Out-Null
Sh "settings delete global private_dns_specifier" 2>$null | Out-Null

Write-Host "==> 连接实体键盘时减少软键盘抢焦点（改善小键盘/数字键）" -ForegroundColor Cyan
# 0 = 有硬键盘时不自动弹软键盘
Sh "settings put secure show_ime_with_hard_keyboard 0" | Out-Null

Write-Host "==> 自检：ping 公网 IP 与域名（Android ping 参数因版本而异，失败可忽略）" -ForegroundColor Cyan
Sh "ping -c 1 8.8.8.8" 2>&1
Sh "ping -c 1 fund.eastmoney.com" 2>&1

Write-Host ""
Write-Host "若域名仍失败，请完全关闭模拟器后，用本仓库的 start_emulator.ps1 重新启动（已带 -dns-server）。" -ForegroundColor Yellow
Write-Host "仍不行：在模拟器 设置 → 网络和互联网 → 互联网 → 网络偏好设置 / Private DNS 改为 关闭。" -ForegroundColor Yellow
