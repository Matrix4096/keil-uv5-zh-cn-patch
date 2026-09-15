# µVision 5.x 简体中文资源补丁生成器

这是一个非官方、源码形式发布的 Windows 资源补丁工具。它读取用户已经合法安装的
**Arm Keil µVision 5.x**，生成独立的 `UV4_zh-CN.exe` 中文界面副本。

补丁只修改匹配的 Win32 界面字符串和菜单资源，不修改编译器、调试器、工程文件或
许可证逻辑，也不会覆盖原版 `UV4.exe`。

> [!IMPORTANT]
> 本仓库不提供 Keil 安装包、`UV4.exe`、生成后的中文 EXE、Pack、编译器、许可证、
> 序列号、注册机或激活绕过工具。请仅使用自己合法安装的软件。

## 快速开始

已经安装 µVision 5.x，并且电脑上有 Python 3.10 或更高版本时，在 PowerShell 中运行：

```powershell
git clone https://github.com/player4086/keil-uv5-zh-cn-patch.git
Set-Location .\keil-uv5-zh-cn-patch

# 先检查兼容性，不生成文件
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe" `
  --dry-run

# 检查通过后生成中文副本
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe"
```

生成成功后，中文副本默认位于：

```text
C:\Keil_v5\UV4\UV4_zh-CN.exe
```

你的安装路径可能不同，请把示例路径替换为实际路径。

## 目录

- [功能与限制](#功能与限制)
- [版本兼容性](#版本兼容性)
- [前置准备](#前置准备)
- [详细使用步骤](#详细使用步骤)
- [运行和打开工程](#运行和打开工程)
- [命令参数](#命令参数)
- [验证补丁结果](#验证补丁结果)
- [常见问题与故障排查](#常见问题与故障排查)
- [恢复原版](#恢复原版)

## 功能与限制

### 当前功能

- 不覆盖原版 `UV4.exe`，始终生成单独的中文副本；
- 内置简体中文词典，不再需要旧版中文 `UV4.exe`；
- 精确识别完整验证的 µVision 5.43.1；
- 对其他 µVision 5.x 提供基于原文 SHA-256 指纹的安全兼容模式；
- 输出详细兼容性报告，包括版本、哈希、覆盖率和未匹配项目；
- 可验证 PE 代码段是否保持不变。

### 当前翻译范围

在 µVision 5.43.1.0 上：

- 774 条简体中文界面字符串；
- 29 组菜单、234 个菜单项；
- 共匹配 1008 个翻译项目。

当前词典主要覆盖菜单和常用界面字符串。多数设置对话框仍可能显示英文，这是当前版本
的已知限制，不代表补丁安装失败。其他 µVision 5.x 的实际覆盖数量取决于资源匹配率。

## 版本兼容性

### 完整验证版本

- 文件版本：µVision `5.43.1.0`
- 官方原版 SHA-256：
  `428BAF13D15E6760AF1618DEF9C9815C97F0321CC5E459EC7ADC4DDE41C42F89`
- 预期中文副本 SHA-256：
  `7FDF1F2F48763B003862740F25CB306A20ED9D40772FCB1E8D8F2B1E839114CD`
- 词典覆盖率：`1008 / 1008`，即 100%

### 其他 µVision 5.x

其他相邻版本进入安全兼容模式：

1. 先读取 Windows 文件版本，只接受主版本为 5 的文件；
2. 对每条资源同时核对资源 ID、菜单位置和原英文 SHA-256 指纹；
3. 只修改完全匹配的项目；
4. 新增、删除或内容发生变化的项目保持英文；
5. 默认匹配率低于 70% 时拒绝生成中文副本。

兼容模式不代表所有 5.x 版本均已实测。建议先执行 `--dry-run`，查看报告后再生成。
如果某个版本通过了兼容检查，仍建议先保留并使用原版进行重要工作。

## 前置准备

### 1. 合法安装 Keil µVision 5.x

本工具不是安装程序。电脑上必须已经存在官方 `UV4.exe`。常见位置包括：

```text
C:\Keil_v5\UV4\UV4.exe
C:\Keil\UV4\UV4.exe
```

如果安装在自定义目录，可以通过以下方式定位：

1. 在开始菜单或桌面找到 µVision 快捷方式；
2. 右键选择“打开文件所在的位置”；
3. 如打开的是另一个快捷方式，再次右键并选择“打开文件所在的位置”；
4. 确认目录中存在 `UV4.exe`。

也可以在 PowerShell 中查看文件版本和哈希：

```powershell
$uv4 = "C:\Keil_v5\UV4\UV4.exe"
(Get-Item -LiteralPath $uv4).VersionInfo.FileVersion
Get-FileHash -Algorithm SHA256 -LiteralPath $uv4
```

### 2. 安装 Python

需要 Python 3.10 或更高版本，仅使用标准库，不需要安装第三方包。

```powershell
python --version
```

如果系统使用 Python Launcher，也可以运行：

```powershell
py -3 --version
```

后续示例中的 `python` 可以相应替换为 `py -3`。

### 3. 获取本仓库

选择一种方式：

- 从 [最新 Release](https://github.com/player4086/keil-uv5-zh-cn-patch/releases/latest)
  下载 Source code ZIP，然后完整解压；
- 或使用 Git：

```powershell
git clone https://github.com/player4086/keil-uv5-zh-cn-patch.git
Set-Location .\keil-uv5-zh-cn-patch
```

请保留 `translations\zh_CN.json` 与脚本的相对位置，不要只单独复制
`build_patch.py`。

### 4. 关闭正在运行的中文副本

如果之前生成过 `UV4_zh-CN.exe`，重新生成前请先关闭它，否则 Windows 可能因为文件
正在使用而无法替换输出。原版 `UV4.exe` 不会被修改，但操作前关闭所有 µVision 窗口
更容易排查文件占用问题。

## 详细使用步骤

### 步骤 1：进入补丁目录

假设仓库解压在 `C:\Tools\keil-uv5-zh-cn-patch`：

```powershell
Set-Location "C:\Tools\keil-uv5-zh-cn-patch"
```

确认关键文件存在：

```powershell
Test-Path .\build_patch.py
Test-Path .\translations\zh_CN.json
```

两个命令都应返回 `True`。

### 步骤 2：确认原版路径

```powershell
$uv4 = "C:\Keil_v5\UV4\UV4.exe"
Test-Path -LiteralPath $uv4
```

应返回 `True`。路径中有空格或中文时必须保留双引号。

### 步骤 3：执行兼容性预检

预检不会生成或修改 EXE：

```powershell
python .\build_patch.py `
  --target $uv4 `
  --dry-run
```

脚本会在仓库目录写入 `patch-report.json`。重点检查以下字段：

| 字段 | 含义 | 建议结果 |
| --- | --- | --- |
| `target_version` | 检测到的 µVision 文件版本 | 以 `5.` 开头 |
| `compatibility.mode` | 匹配模式 | `exact-tested` 或 `compatible-source-match` |
| `compatibility.accepted` | 是否允许生成 | `true` |
| `coverage.ratio` | 词典匹配率 | 完整版本为 `1.0`，兼容版本默认不低于 `0.7` |
| `coverage.matched` | 实际匹配项目数 | 数值越高，中文覆盖越完整 |
| `coverage.unmatched_*` | 未匹配项目 | 这些项目将保留英文 |

如果 `accepted` 为 `false`，脚本不会生成 EXE。不要通过大幅降低阈值强行套用补丁，
应先确认文件确实来自官方 µVision 5.x。

### 步骤 4：生成中文副本

预检通过后运行：

```powershell
python .\build_patch.py --target $uv4
```

默认输出为原版同目录下的 `UV4_zh-CN.exe`。原版 `UV4.exe` 保持不变。

如需显式指定输出和报告路径：

```powershell
python .\build_patch.py `
  --target $uv4 `
  --output "C:\Keil_v5\UV4\UV4_zh-CN.exe" `
  --report ".\patch-report.json"
```

建议把中文副本放在原版 `UV4.exe` 同一目录，便于程序继续找到 Keil 的其他组件。

### 步骤 5：确认生成成功

```powershell
Test-Path "C:\Keil_v5\UV4\UV4_zh-CN.exe"
Get-Item "C:\Keil_v5\UV4\UV4_zh-CN.exe"
```

成功时 `patch-report.json` 中还会出现 `output_sha256`。

如果 Keil 安装在受保护目录并提示“拒绝访问”，请先确认路径正确，并使用对该目录
具有写入权限的账户操作。不要关闭或绕过安全软件来完成生成。

## 运行和打开工程

启动中文副本：

```powershell
& "C:\Keil_v5\UV4\UV4_zh-CN.exe"
```

直接打开工程：

```powershell
& "C:\Keil_v5\UV4\UV4_zh-CN.exe" `
  "D:\Projects\Example\Project.uvprojx"
```

因为资源被修改，中文副本不会保留 Arm 对原版文件的数字签名，这是预期结果。只运行
自己从官方原版现场生成的副本，不要从陌生网站下载别人打包好的中文 EXE。若 Windows
或安全软件给出警告而你无法确认文件来源，请停止运行并继续使用原版。

## 命令参数

```text
--target PATH          必填，官方 µVision 5.x 的 UV4.exe
--catalog PATH         可选，翻译词典；默认使用 translations/zh_CN.json
--output PATH          可选，中文副本路径；默认放在原版旁边
--report PATH          可选，JSON 报告路径；默认写入仓库目录
--dry-run              只检查兼容性，不生成 EXE
--exact-only           只接受完整验证的 5.43.1 文件哈希
--min-coverage NUMBER  未验证版本的最低匹配率，默认 0.70
```

查看程序自己的参数说明：

```powershell
python .\build_patch.py --help
```

### 严格限定为 5.43.1

```powershell
python .\build_patch.py `
  --target $uv4 `
  --exact-only
```

### 提高兼容模式的安全阈值

例如要求至少 85% 的词典项目匹配：

```powershell
python .\build_patch.py `
  --target $uv4 `
  --min-coverage 0.85
```

不建议把阈值降低到默认值以下。`--catalog` 也只应指向你信任且经过审查的词典。

## 验证补丁结果

### 1. 验证菜单与对话框资源可无损解析

```powershell
python .\tools\validate_formats.py `
  "C:\Keil_v5\UV4\UV4_zh-CN.exe"
```

结果中的 `errors` 和 `mismatch` 应为空。

### 2. 验证程序代码段未变化

```powershell
python .\tools\verify_pe_sections.py `
  "C:\Keil_v5\UV4\UV4.exe" `
  "C:\Keil_v5\UV4\UV4_zh-CN.exe"
```

预期：

- `code_sections_identical` 为 `true`；
- `.text`、`.data`、`.rdata` 保持一致；
- `resource_section_changed` 为 `true`。

本项目在 µVision 5.43.1.0 上的验证结果为：40/40 个菜单资源与 246/246 个对话框
资源可无损解析，代码段保持一致。STM32 测试工程使用 ARM Compiler 5.06 update 5
构建结果为 0 个错误、0 个警告。

## 项目文件说明

| 路径 | 用途 |
| --- | --- |
| `build_patch.py` | 补丁生成入口与兼容性检查 |
| `translations/zh_CN.json` | 原文指纹与简体中文词典 |
| `tools/pe_resources.py` | 读取和更新 Windows PE 资源 |
| `tools/resource_formats.py` | 菜单与对话框资源解析器 |
| `tools/validate_formats.py` | 资源往返解析验证 |
| `tools/verify_pe_sections.py` | 比较原版和中文副本的 PE 段 |
| `patch-report.example.json` | 5.43.1 报告示例 |
| `CHANGELOG.md` | 版本更新记录 |

## 常见问题与故障排查

### 提示找不到 `python`

先尝试：

```powershell
py -3 --version
py -3 .\build_patch.py --help
```

如果仍不可用，请安装 Python 3.10 或更高版本，并重新打开 PowerShell。

### 提示 `Target file does not exist`

目标路径错误。确认最后一级文件确实是 `UV4.exe`，并为包含空格或中文的路径加双引号。

### 提示 `Unsupported file version`

脚本只接受 Windows 文件版本主版本为 5 的程序。请确认选择的是 µVision 5.x 的
`UV4.exe`，而不是安装器、快捷方式、其他工具或 µVision 4。

### 提示兼容性检查失败或退出码为 2

该文件未达到默认 70% 匹配率，或者使用 `--exact-only` 时文件哈希不是完整验证版本。
脚本此时不会生成 EXE。请不要直接降低阈值强行继续。

可以在提交 Issue 时提供：

- `target_version`；
- `target_sha256`；
- `coverage` 部分；
- 报错文字。

请先删除报告中的本机用户名和绝对路径，不要上传 `UV4.exe`、许可证信息或工程机密。

### 提示拒绝访问或无法替换输出

- 关闭正在运行的 `UV4_zh-CN.exe`；
- 确认输出目录具有写入权限；
- 检查输出文件是否被安全软件隔离或被其他进程占用；
- 不要通过关闭安全软件来强行继续。

### 中文副本仍有部分英文

这是当前覆盖范围的限制。未匹配的新版本资源、设置对话框和部分扩展功能会保留英文。
请查看 `patch-report.json` 的覆盖率与未匹配项目。

### 中文出现乱码或方框

确认 Windows 已安装简体中文字体和语言支持，并优先在现代 Windows 10/11 上使用。
如果原版同样显示异常，问题通常与系统语言或字体环境有关，而不是补丁资源。

### 编译器、芯片 Pack 或下载器不能使用

本项目只修改 µVision 界面资源，不安装 ARMCC、Arm Compiler 6、C51、STM32 Pack、
调试器驱动或许可证。此类问题与中文补丁相互独立。

### 安全软件报告中文副本未签名

资源修改会使原数字签名失效。不要关闭安全软件，也不要运行网络上来源不明的预制
中文 EXE。请核对仓库源码、原版哈希和 `patch-report.json`，无法确认时继续使用原版。

## 常见问答

**没有旧版中文 `UV4.exe` 可以使用吗？**

可以。v1.1.0 起词典已经包含在仓库中，不再需要任何旧版中文 EXE。

**完全没有官方 `UV4.exe` 可以使用吗？**

不可以。本工具是资源补丁生成器，不是 Keil 安装程序；必须先合法安装 µVision 5.x。

**会修改或删除原版吗？**

不会。脚本明确禁止把输出路径设为原版路径，并生成单独的 `UV4_zh-CN.exe`。

**会影响 ARM、C51 或 STM32 工程吗？**

不会主动修改工程或编译工具链。中文副本与原版共享现有 Keil 安装环境。

**可以把生成后的 EXE 发给别人吗？**

不建议。请分享本仓库源码，让每位使用者从自己合法安装的官方文件生成副本。

## 恢复原版

原版从未被修改，因此无需执行恢复程序：

1. 关闭 `UV4_zh-CN.exe`；
2. 继续运行原版 `UV4.exe`；
3. 如不再需要，可删除 `UV4_zh-CN.exe` 和 `patch-report.json`。

删除中文副本不会删除 Keil、编译器、Pack 或工程文件。

## 反馈与贡献

发现翻译问题或希望增加新版本兼容性时，可以在
[Issues](https://github.com/player4086/keil-uv5-zh-cn-patch/issues) 中提交版本、哈希、
覆盖率和可复现步骤。请勿上传任何 Keil 二进制文件、许可证、密钥或私有工程源码。

## 免责声明

本项目与 Arm、Keil 无关联，也未获得其认可。使用者须自行确保拥有相关软件的合法
许可证，并遵守适用的软件许可协议。对未完整验证版本使用兼容模式前，请保留原版并
自行评估风险。
