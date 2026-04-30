#Requires -Version 5.1
<#
.SYNOPSIS
  不依赖 Android Studio：在模拟器上安装 Debug APK 并打开主界面（需本机已有 Android SDK + platform-tools）。

  用法（仓库根目录 PowerShell）:
    .\scripts\preview_on_emulator.ps1                    # 有 APK 则只安装；没有则先 assembleDebug
    .\scripts\preview_on_emulator.ps1 -StartEmulator      # 若无设备，后台拉起 FundShare_API34 再等就绪
    .\scripts\preview_on_emulator.ps1 -Rebuild            # 强制重新编译再安装

  若模拟器因硬件加速报错，请先完成 AEHD（silent_install.bat）或启用「Windows 虚拟机监控程序平台」（见 README_ANDROID.md）。
#>
param(
    [switch]$Rebuild,
    [switch]$StartEmulator
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Apk = Join-Path $Root "android\app\build\outputs\apk\debug\app-debug.apk"
$Package = "com.fundshare.app"
$Activity = "$Package/.MainActivity"

$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$env:ANDROID_HOME = $sdk
$env:Path = "$sdk\platform-tools;$sdk\emulator;$env:Path"

$adb = Join-Path $sdk "platform-tools\adb.exe"
if (-not (Test-Path $adb)) {
    Write-Host "未找到 adb。请用 sdkmanager 安装 platform-tools，或从 https://developer.android.com/studio#command-line-tools-only 安装命令行工具包。" -ForegroundColor Red
    exit 1
}

function Wait-BootCompleted {
    Write-Host "等待系统启动完成…" -ForegroundColor Cyan
    for ($i = 0; $i -lt 90; $i++) {
        $line = (Invoke-Adb shell getprop sys.boot_completed) | Select-Object -Last 1
        if ($line -match "1") { return }
        Start-Sleep -Seconds 2
    }
    Write-Warning "启动超时，仍尝试安装。"
}

function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $adb @Args 2>&1
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Fix-EmulatorNetworkFromHost {
    Write-Host "修正模拟器 DNS / 键盘相关系统设置 …" -ForegroundColor Cyan
    Invoke-Adb shell settings put global private_dns_mode 1 | Out-Null
    Invoke-Adb shell settings delete global private_dns_specifier 2>$null | Out-Null
    Invoke-Adb shell settings put secure show_ime_with_hard_keyboard 0 | Out-Null
}

function Ensure-Emulator {
    $list = Invoke-Adb devices
    $online = $list | Where-Object { $_ -match "`tdevice$" }
    if ($online) {
        Fix-EmulatorNetworkFromHost
        return
    }

    if (-not $StartEmulator) {
        Write-Host "当前没有已连接的模拟器/真机。" -ForegroundColor Yellow
        Write-Host "请先在本仓库运行: .\scripts\start_emulator.ps1 -Detach" -ForegroundColor Yellow
        Write-Host "或重新执行本脚本并加 -StartEmulator" -ForegroundColor Yellow
        exit 1
    }

    $emu = Join-Path $sdk "emulator\emulator.exe"
    if (-not (Test-Path $emu)) {
        Write-Error "未找到 emulator.exe: $emu"
    }
    Write-Host "后台启动 AVD FundShare_API34 …" -ForegroundColor Cyan
    $emuArgs = @(
        "-avd", "FundShare_API34",
        "-netdelay", "none",
        "-netspeed", "full",
        "-dns-server", "8.8.8.8,8.8.4.4"
    )
    Start-Process -FilePath $emu -ArgumentList $emuArgs -WorkingDirectory (Split-Path $emu)
    Invoke-Adb wait-for-device | Out-Null
    Wait-BootCompleted
    Fix-EmulatorNetworkFromHost
}

if ($Rebuild -or -not (Test-Path $Apk)) {
    Write-Host "构建 Debug APK …" -ForegroundColor Cyan
    if (-not $env:JAVA_HOME) {
        $jdk = Get-ChildItem "$env:ProgramFiles\Microsoft\jdk-*" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($jdk) { $env:JAVA_HOME = $jdk.FullName }
    }
    Push-Location (Join-Path $Root "android")
    try {
        & .\gradlew.bat :app:assembleDebug --no-daemon
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally { Pop-Location }
}
if (-not (Test-Path $Apk)) {
    Write-Error "缺少 APK: $Apk"
}

Ensure-Emulator

Write-Host "安装 APK …" -ForegroundColor Cyan
Invoke-Adb install -r $Apk | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "启动界面 …" -ForegroundColor Cyan
Invoke-Adb shell am start -n $Activity | Out-Null
Write-Host "完成。模拟器窗口即为安卓界面；无需 Android Studio。" -ForegroundColor Green
