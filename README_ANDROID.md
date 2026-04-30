# Android 本地客户端（Chaquopy 预研分支）

本目录在分支 `feature/android-local` 上提供 **可在手机本地运行** 的预研工程：用 [Chaquopy](https://chaquo.com/chaquopy/) 嵌入 Python 3.12，将仓库根目录的 [`fundshare`](../fundshare) 在构建时同步进 `app/src/main/python/`，与 Streamlit 网页版共用业务层；**界面尚未复刻** `app.py` 全功能，首屏仅验证 `PortfolioService` + `JsonStorage` 在应用私有目录可读写（`DATA_DIR` = `HOME`）。

## 环境要求

- **Android Studio** 2024.x（含 Android SDK、JDK 17）
- 构建本机已安装 **Python 3.12**（与 Chaquopy `version = "3.12"` 一致，供 `pip` 与字节码步骤使用；Chaquo 会尝试 `py -3.12` 或 PATH 中的 `python`）

### 是否必须装 Android Studio？

- **可以完全不装**。体积大的是 **Android Studio 本体**；若你已有 **JDK 17 + Android SDK（命令行工具）+ Python 3.12**，用 **`gradlew assembleDebug`**、`adb`、`emulator.exe` 即可构建、装包、看模拟器窗口。  
- **只想立刻在电脑上看到安卓模拟界面 + 本 App**：完成 **硬件加速**（见「模拟器与硬件加速」）后，在仓库根目录执行：
  ```powershell
  .\scripts\preview_on_emulator.ps1 -StartEmulator
  ```
  会在需要时后台拉起 **FundShare_API34**、安装 Debug APK 并打开主界面；**弹出的模拟器窗口就是安卓界面**，无需打开 Android Studio。  
- **仍适合装 Studio 的情况**：经常改 Kotlin/Compose、需要 **Logcat / 断点调试** 时更省事。若不想装完整 IDE，可只下官方 **[Command line tools only](https://developer.android.com/studio#command-line-tools-only)**，用 `sdkmanager` 装 `platform-tools`、`emulator` 等。

### Windows 一键准备（PowerShell）

在仓库根目录执行（将尝试 `winget` 安装 OpenJDK 17、写入 `local.properties`，并安装 Python 依赖）：

```powershell
.\scripts\setup_android_env.ps1
```

若尚未安装 Android Studio，可加 `-InstallAndroidStudio`（安装包较大）。

若 winget 报错「文件被占用」，请先关闭其他正在运行的 winget/安装程序后重试。

## 打开工程

在 Android Studio 中选择 **Open**，指向本仓库下的 **`android/`** 目录（不是仓库根目录）。

首次 **Sync / Build** 时，Gradle 任务 `syncFundsharePython` 会把 `../fundshare` 复制到 `app/src/main/python/fundshare`（该目录已加入 `.gitignore`，不提交到 Git）。

## 构建产物（Debug APK）

在本机已配置 JDK 17、Android SDK、`android/local.properties` 且 Python 3.12 可用时，可在仓库根目录执行：

```powershell
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.18.8-hotspot"   # 按本机路径修改
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
cd android
.\gradlew.bat :app:assembleDebug
```

生成的 APK 默认位于：

- `android/app/build/outputs/apk/debug/app-debug.apk`

可复制为 **`dist/FundShare-debug.apk`**（约 45MB，含 Chaquopy/Python 运行时），传到手机安装即可（需允许「安装未知来源」）。

## 在电脑上实时看界面并点击

开发时要在 **PC 上看到与手机一致的界面**，并 **用鼠标点击操作**，常用两种方式：

### 方式 A：Android 模拟器（全在电脑里）

本机已可启动名为 **`FundShare_API34`** 的虚拟设备（Pixel 6 外形、Android 14 / API 34、Google APIs x86_64）。在 **PowerShell 里** 进入仓库根目录后执行（**不要双击** `.ps1`，否则黑窗容易一闪就关、看不到报错）：

```powershell
cd C:\Users\DELL\Desktop\test_png\FundShare   # 改成你的仓库路径
.\scripts\start_emulator.ps1
```

脚本会**在当前终端前台**启动模拟器，**启动日志会打印在终端**；若闪退，请把终端里红色/黄色报错复制出来排查。首次启动可能需 1～2 分钟。模拟器起来后，可在 **Android Studio** 中打开 **`android/`** 工程，对 **app** 点 **Run**，选 **FundShare_API34**。

更省事：也可**双击**仓库里的 `scripts\start_emulator.cmd`（会开 PowerShell 并执行同一脚本，结束前有暂停便于看错）。

若你尚未创建该 AVD，可在 Android Studio 中 **Tools → Device Manager → Create Device** 自建；或使用与本仓库一致的命令（需已安装 `emulator` 与对应 system-image）：

```powershell
$sdk = "$env:LOCALAPPDATA\Android\Sdk"
cmd /c "echo no | `"$sdk\cmdline-tools\latest\bin\avdmanager.bat`" create avd -n FundShare_API34 -k `"system-images;android-34;google_apis;x86_64`" -d pixel_6"
```

模拟器窗口支持键盘、鼠标滚轮与拖拽，与真机交互一致（部分传感器除外）。

#### 改代码后，如何让模拟器里的 App 看到最新效果？

命令行方案下**没有** Android Studio 的 Apply Changes 热替换：改了 **`android/`** 里的 Kotlin、Compose、资源，或仓库里的 **`fundshare/`**（构建时会同步进 APK），都需要 **重新打 Debug 包并覆盖安装**。

1. **保持模拟器窗口不关**（或确保 `adb devices` 里能看到 `emulator-*`）。
2. 在**仓库根目录** PowerShell 执行其一：
   ```powershell
   .\scripts\preview_on_emulator.ps1 -Rebuild
   ```
   或：
   ```powershell
   .\scripts\refresh_emulator_app.ps1
   ```
   会执行 **`assembleDebug` → `adb install -r` → 再次启动主界面**，模拟器里看到的就是最新构建。

若当前没有已连接设备，可加 `-StartEmulator`：  
`.\scripts\preview_on_emulator.ps1 -Rebuild -StartEmulator`。

### 方式 B：真机投屏（scrcpy，适合 MIUI 真机）

真机用 USB 连电脑，手机上打开 **开发者选项 → USB 调试**（MIUI 可能还需打开 **USB 调试（安全设置）** 才能用电脑鼠标点按）。

1. 安装投屏工具：`winget install Genymobile.scrcpy`  
2. 确认已安装 **Android SDK platform-tools**（与构建 APK 时同一套 `ANDROID_HOME`）。  
3. 在仓库根目录执行：

```powershell
.\scripts\scrcpy_preview.ps1
```

会弹出 **scrcpy** 窗口，显示手机当前画面；**鼠标点击、键盘输入**会传到手机。你在 Android Studio 里 **Run** 装到这台手机后，scrcpy 窗口会同步显示最新界面。

可选：Android 11+ 可在开发者选项里 **无线调试** 配对后 `adb connect IP:端口`，再运行 `scrcpy`。

### 方式 C：Android Studio Running Devices

较新版本 Android Studio 在 **View → Tool Windows → Running Devices** 中可嵌入模拟器或部分机型的镜像；与方式 A/B 二选一即可。

## 运行

- 用 USB 或模拟器运行 **app** 的 `debug` 变体；或直接安装上一步的 `FundShare-debug.apk`。
- 主界面为 **类 Streamlit 四 Tab 布局**（组合总览 / 基金管理 / 交易与净值 / 维护），数据由 Chaquopy 调用与网页版相同的 `fundshare` 逻辑；**复杂图表、导入、买卖表单**仍建议在 Streamlit 网页端操作，移动端侧重阅览组合指标与持仓列表。

数据文件为应用私有目录下的 `store.json`（与桌面版 `JsonStorage` 相同逻辑）。

## MIUI 14 提示

- 数据在 **应用私有存储**，卸载应用会删除；若需手动备份，请使用后续版本将导出的能力接到 Android（当前预研未做文件选择器）。
- 若以后在应用内访问公网基金接口，请在系统设置中授予 **网络** 权限（Manifest 已声明 `INTERNET`）；纯离线使用无需额外设置。
- MIUI **省电 / 自启动** 对「前台 Activity + 本地计算」影响较小；若以后加后台任务，再考虑关闭该应用的后台限制。

## 与 Streamlit 功能对照（分阶段）

详见 [ANDROID_PARITY.md](ANDROID_PARITY.md)。

## 故障排除

### 模拟器与硬件加速（`x86_64 emulation requires hardware acceleration` / `AEHD is not installed`）

x86_64 系统镜像**必须**有 CPU 虚拟化加速。按下面顺序处理（做完一类后**重启**再试 `.\scripts\start_emulator.ps1`）：

1. **安装 Android Emulator Hypervisor Driver（推荐先试）**  
   - **图形界面**：Android Studio → **Settings** → **Android SDK** → **SDK Tools** → 勾选 **Android Emulator Hypervisor Driver** → **Apply**。  
   - **命令行**（仓库根目录 PowerShell）：`.\scripts\install_emulator_hypervisor.ps1`，完成后按提示**以管理员身份**运行  
     `%LOCALAPPDATA%\Android\Sdk\extras\google\Android_Emulator_Hypervisor_Driver\silent_install.bat`。  
   官方说明：[在 Windows 上配置虚拟机加速](https://developer.android.com/studio/run/emulator-acceleration#vm-windows)。

2. **启用 Windows 虚拟机监控程序**  
   **设置** → **应用** → **可选功能** → **其他 Windows 功能** → 勾选 **Windows 虚拟机监控程序平台**（按需可同时勾选 **虚拟机平台**）→ 确定并**重启**。许多环境下模拟器会改用 **WHPX**，不再依赖 AEHD。

3. **BIOS**  
   开机进入 BIOS/UEFI，开启 **Intel VT-x** 或 **AMD-V / SVM**。

4. **其他**  
   - 日志里 `quickbootChoice.ini` 警告一般可忽略；若介意可删掉  
     `C:\Users\<用户名>\.android\avd\FundShare_API34.avd\quickbootChoice.ini` 后重开模拟器。  
   - 若因 **Hyper-V / WSL2** 等与 AEHD 冲突，优先尝试 **WHPX**（步骤 2）；仍不行时再对照 [模拟器加速文档](https://developer.android.com/studio/run/emulator-acceleration) 选择 AEHD 或 Hyper-V 方案。

---

- **构建报找不到 Python 3.12**：安装官方 Python 3.12，或在 `app/build.gradle.kts` 的 `chaquopy { defaultConfig { buildPython(...) } }` 中显式指定本机 `python.exe` 路径（参见 [Chaquopy 文档](https://chaquo.com/chaquopy/doc/current/android.html#buildpython)）。
- **import fundshare 失败**：先执行一次 **Build > Make Project**，确保 `syncFundsharePython` 已执行且 `app/src/main/python/fundshare` 存在。
