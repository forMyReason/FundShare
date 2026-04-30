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
$online = $dev | Where-Object { $_ -match "\sdevice$" -and $_ -notmatch "^List of devices" }
if (-not $online) {
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

Write-Host "==> 尝试补默认路由（某些快照恢复后会丢 default route）" -ForegroundColor Cyan
& $adb root 2>$null | Out-Null
Sh "ip route add default via 10.0.2.2 dev eth0" 2>$null | Out-Null

Write-Host "==> 连接实体键盘时允许弹出软键盘（避免输入法不出现）" -ForegroundColor Cyan
# 1 = 有硬键盘时也显示软键盘
Sh "settings put secure show_ime_with_hard_keyboard 1" | Out-Null

Write-Host "==> 自检：ping 公网 IP 与域名（Android ping 参数因版本而异，失败可忽略）" -ForegroundColor Cyan
Sh "ping -c 1 8.8.8.8" 2>&1
Sh "ping -c 1 fund.eastmoney.com" 2>&1

Write-Host ""
Write-Host "若域名仍失败，请完全关闭模拟器后，用本仓库的 start_emulator.ps1 重新启动（已带 -dns-server）。" -ForegroundColor Yellow
Write-Host "仍不行：在模拟器 设置 → 网络和互联网 → 互联网 → 网络偏好设置 / Private DNS 改为 关闭。" -ForegroundColor Yellow
