#Requires -Version 5.1
<#
.SYNOPSIS
  为 AVD FundShare_API34 启用「使用电脑物理键盘输入」。
  改的是本机 %USERPROFILE%\.android\avd\... 下的 config.ini，改完后请完全关闭模拟器再启动。

  用法: .\scripts\enable_avd_hw_keyboard.ps1
#>
$ErrorActionPreference = "Stop"
$avdName = "FundShare_API34"
$ini = Join-Path $env:USERPROFILE ".android\avd\$avdName.avd\config.ini"
if (-not (Test-Path $ini)) {
    Write-Host "未找到: $ini" -ForegroundColor Red
    Write-Host "请先创建同名 AVD，或把脚本里的 `$avdName 改成你的 AVD 名称。"
    exit 1
}

$lines = Get-Content $ini -Encoding UTF8
$out = New-Object System.Collections.ArrayList
$hasKeyboard = $false
foreach ($line in $lines) {
    if ($line -match '^\s*hw\.keyboard\s*=') {
        [void]$out.Add("hw.keyboard=yes")
        $hasKeyboard = $true
    } else {
        [void]$out.Add($line)
    }
}
if (-not $hasKeyboard) {
    if ($out.Count -gt 0 -and $out[$out.Count - 1] -ne "") { [void]$out.Add("") }
    [void]$out.Add("hw.keyboard=yes")
}

$out | Set-Content -Path $ini -Encoding UTF8
Write-Host "已写入 hw.keyboard=yes -> $ini" -ForegroundColor Green
Write-Host "请关闭全部模拟器窗口后，再运行 .\scripts\start_emulator.ps1 或 -Detach"