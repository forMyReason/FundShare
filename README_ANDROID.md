# Android 本地客户端（Chaquopy 预研分支）

本目录在分支 `feature/android-local` 上提供 **可在手机本地运行** 的预研工程：用 [Chaquopy](https://chaquo.com/chaquopy/) 嵌入 Python 3.12，将仓库根目录的 [`fundshare`](../fundshare) 在构建时同步进 `app/src/main/python/`，与 Streamlit 网页版共用业务层；**界面尚未复刻** `app.py` 全功能，首屏仅验证 `PortfolioService` + `JsonStorage` 在应用私有目录可读写（`DATA_DIR` = `HOME`）。

## 环境要求

- **Android Studio** 2024.x（含 Android SDK、JDK 17）
- 构建本机已安装 **Python 3.12**（与 Chaquopy `version = "3.12"` 一致，供 `pip` 与字节码步骤使用；Chaquo 会尝试 `py -3.12` 或 PATH 中的 `python`）

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

## 运行

- 用 USB 或模拟器运行 **app** 的 `debug` 变体；或直接安装上一步的 `FundShare-debug.apk`。
- 首屏应显示 `DATA_DIR=...`、基金数量、组合总成本等；数据文件为应用私有目录下的 `store.json`（与桌面版 `JsonStorage` 相同逻辑）。

## MIUI 14 提示

- 数据在 **应用私有存储**，卸载应用会删除；若需手动备份，请使用后续版本将导出的能力接到 Android（当前预研未做文件选择器）。
- 若以后在应用内访问公网基金接口，请在系统设置中授予 **网络** 权限（Manifest 已声明 `INTERNET`）；纯离线使用无需额外设置。
- MIUI **省电 / 自启动** 对「前台 Activity + 本地计算」影响较小；若以后加后台任务，再考虑关闭该应用的后台限制。

## 与 Streamlit 功能对照（分阶段）

详见 [ANDROID_PARITY.md](ANDROID_PARITY.md)。

## 故障排除

- **构建报找不到 Python 3.12**：安装官方 Python 3.12，或在 `app/build.gradle.kts` 的 `chaquopy { defaultConfig { buildPython(...) } }` 中显式指定本机 `python.exe` 路径（参见 [Chaquopy 文档](https://chaquo.com/chaquopy/doc/current/android.html#buildpython)）。
- **import fundshare 失败**：先执行一次 **Build > Make Project**，确保 `syncFundsharePython` 已执行且 `app/src/main/python/fundshare` 存在。
