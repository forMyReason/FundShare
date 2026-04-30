# 在仓库根目录执行：.\scripts\build_apk.ps1
# 依赖：JAVA_HOME (JDK 17+)、Android SDK、android/local.properties、py -3.12
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Jdk = "C:\Program Files\Microsoft\jdk-17.0.18.8-hotspot"
if (-not (Test-Path $Jdk)) {
    Write-Error "未找到 JDK: $Jdk 。请安装 OpenJDK 17 或设置 `$env:JAVA_HOME"
}
$env:JAVA_HOME = $Jdk
$env:ANDROID_HOME = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
if (-not (Test-Path $env:ANDROID_HOME)) {
    Write-Error "未找到 Android SDK: $($env:ANDROID_HOME) 。请先安装 SDK 或设置 ANDROID_HOME"
}
Set-Location (Join-Path $Root "android")
.\gradlew.bat :app:assembleDebug --no-daemon
$apk = Join-Path $Root "android\app\build\outputs\apk\debug\app-debug.apk"
$outDir = Join-Path $Root "dist"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$out = Join-Path $outDir "FundShare-debug.apk"
Copy-Item $apk $out -Force
Write-Host "OK: $out"
