#Requires -Version 5.1
<#
.SYNOPSIS
  开发迭代：模拟器/设备已连接时，重新编译 Debug APK、覆盖安装并打开主界面。
  等价于: .\scripts\preview_on_emulator.ps1 -Rebuild
#>
& "$PSScriptRoot\preview_on_emulator.ps1" -Rebuild
