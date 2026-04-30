#Requires -Version 5.1
<#
.SYNOPSIS
  安装 Windows 上构建 android/ 工程所需依赖：OpenJDK 17、Python 包；可选安装 Android Studio。
  需已安装 winget（Windows 10/11 应用安装程序）。

  用法（仓库根目录 PowerShell）：
    .\scripts\setup_android_env.ps1
    .\scripts\setup_android_env.ps1 -InstallAndroidStudio
#>
param(
    [switch]$InstallAndroidStudio
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$Root\android\gradlew.bat")) {
    Write-Error "请在仓库根目录运行（缺少 android\gradlew.bat）。Root=$Root"
}

Write-Host "==> Python 依赖 (requirements.txt)"
Set-Location $Root
python -m pip install -r requirements.txt -q

function Find-Jdk17Home {
    $candidates = @(
        "${env:ProgramFiles}\Microsoft\jdk-*\bin\java.exe",
        "${env:ProgramFiles}\Eclipse Adoptium\jdk-17*\bin\java.exe",
        "${env:ProgramFiles}\Android\Android Studio\jbr\bin\java.exe",
        "${env:LocalAppData}\Programs\Android\Android Studio\jbr\bin\java.exe"
    )
    foreach ($pat in $candidates) {
        $j = Get-Item $pat -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($j -and $j.FullName -match "jdk-17|jdk17|jbr") {
            return (Split-Path (Split-Path $j.FullName -Parent) -Parent)
        }
    }
    foreach ($pat in $candidates) {
        $j = Get-Item $pat -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($j) {
            return (Split-Path (Split-Path $j.FullName -Parent) -Parent)
        }
    }
    return $null
}

$jdkHome = Find-Jdk17Home
if (-not $jdkHome) {
    Write-Host "==> 未检测到 JDK，尝试 winget 安装 Microsoft OpenJDK 17 …"
    winget install -e --id Microsoft.OpenJDK.17 --accept-package-agreements --accept-source-agreements --disable-interactivity
    Start-Sleep -Seconds 2
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    $jdkHome = Find-Jdk17Home
}

if ($jdkHome) {
    $env:JAVA_HOME = $jdkHome
    Write-Host "JAVA_HOME=$env:JAVA_HOME"
} else {
    Write-Warning "仍未找到 JDK。请手动安装 JDK 17 并设置 JAVA_HOME，或安装 Android Studio（自带 JBR）。"
}

if ($InstallAndroidStudio) {
    Write-Host "==> winget 安装 Android Studio（体积较大）…"
    winget install -e --id Google.AndroidStudio --accept-package-agreements --accept-source-agreements --disable-interactivity
}

$sdk = "${env:LOCALAPPDATA}\Android\Sdk"
if (-not (Test-Path $sdk)) {
    Write-Warning "未找到默认 Android SDK($sdk)。安装 Android Studio 后打开一次并完成 SDK 下载，然后可在 android\local.properties 中配置 sdk.dir。"
} else {
    $localProps = Join-Path $Root "android\local.properties"
    $sdkDir = $sdk -replace '\\', '\\'
    "sdk.dir=$sdkDir" | Set-Content -Path $localProps -Encoding UTF8
    Write-Host "已写入 android\local.properties -> sdk.dir=$sdk"
}

Write-Host "==> Gradle Wrapper 自检（需 JAVA_HOME）"
Set-Location "$Root\android"
if ($env:JAVA_HOME) {
    .\gradlew.bat --version
} else {
    .\gradlew.bat --version 2>&1
}

Write-Host ""
Write-Host "下一步：用 Android Studio 打开仓库下的 android 文件夹，同步 Gradle 后 Run app。"
Write-Host "命令行打包（需已配置 SDK）： cd android; .\gradlew.bat :app:assembleDebug"
