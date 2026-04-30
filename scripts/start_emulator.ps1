#Requires -Version 5.1
<#
.SYNOPSIS
  启动 Android 虚拟设备 FundShare_API34。
  请在「终端」里运行（不要双击 .ps1），否则报错一闪而过看不到提示。
  用法（仓库根目录）:
    .\scripts\start_emulator.ps1           # 在当前窗口前台启动，日志打在终端（推荐）
    .\scripts\start_emulator.ps1 -Detach  # 另开进程启动（仍建议在终端里执行这一行，不要用双击）
#>
param(
    [switch]$Detach
)

$ErrorActionPreference = "Stop"
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$emu = Join-Path $sdk "emulator\emulator.exe"
if (-not (Test-Path $emu)) {
    Write-Host "未找到 emulator.exe: $emu" -ForegroundColor Red
    Write-Host "请先安装: sdkmanager `"emulator`" `"system-images;android-34;google_apis;x86_64`"" -ForegroundColor Yellow
    Read-Host "按 Enter 退出"
    exit 1
}
if (-not $env:JAVA_HOME) {
    $jbr = @(
        "$env:ProgramFiles\Android\Android Studio\jbr",
        "${env:ProgramFiles(x86)}\Android\Android Studio\jbr",
        "$env:ProgramFiles\Microsoft\jdk-17.0.18.8-hotspot"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($jbr) { $env:JAVA_HOME = $jbr }
}
$avd = "FundShare_API34"
# -dns-server：部分环境下模拟器默认 DNS 解析失败会导致东方财富等接口「无法联网」
$argList = @(
    "-avd", $avd,
    "-netdelay", "none",
    "-netspeed", "full",
    "-dns-server", "8.8.8.8,8.8.4.4"
)

if ($Detach) {
    Write-Host "已尝试在后台启动模拟器 $avd …" -ForegroundColor Cyan
    Start-Process -FilePath $emu -ArgumentList $argList -WorkingDirectory (Split-Path $emu)
    Write-Host "若未见模拟器窗口，请改用不加 -Detach 的方式查看报错。" -ForegroundColor Yellow
    exit 0
}

Write-Host "正在启动模拟器 $avd （日志如下；关闭模拟器窗口后本终端会继续）…" -ForegroundColor Cyan
Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "ANDROID_HOME=$sdk"
Write-Host ""

try {
    & $emu @argList
    $code = $LASTEXITCODE
    if ($code -ne 0 -and $null -ne $code) {
        Write-Host "模拟器进程退出码: $code" -ForegroundColor Yellow
        if ($code -eq 1) {
            Write-Host ""
            Write-Host "若日志中有 hardware acceleration / AEHD / hypervisor 字样：" -ForegroundColor Cyan
            Write-Host "  · Android Studio → Settings → Android SDK → SDK Tools → 勾选「Android Emulator Hypervisor Driver」安装；或运行 .\scripts\install_emulator_hypervisor.ps1" -ForegroundColor Gray
            Write-Host "  · 设置 → 应用 → 可选功能 → 其他 Windows 功能 → 勾选「Windows 虚拟机监控程序平台」→ 重启（可与 AEHD 二选一或配合使用，视本机而定）" -ForegroundColor Gray
            Write-Host "  · BIOS 中开启 Intel VT-x / AMD-V" -ForegroundColor Gray
            Write-Host "  · 详见 README_ANDROID.md「模拟器与硬件加速」" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
}
Read-Host "`n按 Enter 关闭本窗口"
