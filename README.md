# µVision 5.43.1 简体中文资源补丁生成器

这是一个非官方、源码形式发布的 Windows 资源补丁工具，适用于精确版本的
**Arm Keil µVision 5.43.1.0**。它生成一个独立的中文副本，只修改界面资源，
不修改编译器、调试器、工程文件或许可证逻辑。

> 本项目与 Arm、Keil 无关联，也未获得其认可。使用者须自行确保拥有相关软件
> 的合法许可证，并遵守适用的软件许可协议。

## 仓库不包含什么

本仓库不提供或分发：

- `UV4.exe`、生成后的 `UV4_zh-CN.exe` 或任何 Keil 安装文件；
- 翻译来源文件；
- Pack、编译器、许可证、序列号、注册机或激活绕过工具。

使用时必须由用户自行提供两个文件。脚本只接受下列精确 SHA-256，任何版本不匹配
都会立即停止，不会修改文件：

- 官方 µVision 5.43.1 原版：`428BAF13D15E6760AF1618DEF9C9815C97F0321CC5E459EC7ADC4DDE41C42F89`
- 5.25.3 翻译来源：`AEF83B317826FEA7149946030808A2A9D34038446D621E5C514C31A450B3AB79`

## 当前覆盖范围

- 774 条简体中文界面字符串；
- 29 组菜单、234 个菜单项；
- µVision 5.43.1 新增且旧词库没有对应内容的项目仍显示英文；
- 原翻译来源未包含对话框控件翻译，因此多数设置窗口仍为英文。

## 环境要求

- Windows 10 或 Windows 11；
- Python 3.10 或更高版本；
- 用户自行提供且哈希完全匹配的两个输入文件。

本工具仅使用 Python 标准库，无需安装第三方依赖。

## 使用方法

在 PowerShell 中进入仓库目录并运行：

```powershell
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe" `
  --donor "C:\path\to\translation-donor.exe"
```

默认会在原版文件旁生成 `UV4_zh-CN.exe`，并在当前目录写入
`patch-report.json`。也可以显式指定路径：

```powershell
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe" `
  --donor "C:\path\to\translation-donor.exe" `
  --output "C:\Keil_v5\UV4\UV4_zh-CN.exe" `
  --report ".\patch-report.json"
```

只检查兼容性、不生成中文副本：

```powershell
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe" `
  --donor "C:\path\to\translation-donor.exe" `
  --dry-run
```

## 安全设计

- 永不覆盖原版 `UV4.exe`；
- 生成前严格校验两个输入文件的 SHA-256；
- 只更新 Win32 的 `RT_STRING`、兼容的 `RT_MENU` 和兼容的 `RT_DIALOG`
  显示资源；
- 可用 `tools\verify_pe_sections.py` 验证代码段没有变化；
- 因为资源发生变化，生成的中文副本不会再保留 Arm 的数字签名，这是预期结果；
- 不建议向他人分发生成后的可执行文件。

## 验证

```powershell
python .\tools\validate_formats.py "C:\Keil_v5\UV4\UV4_zh-CN.exe"
python .\tools\verify_pe_sections.py `
  "C:\Keil_v5\UV4\UV4.exe" `
  "C:\Keil_v5\UV4\UV4_zh-CN.exe"
```

本版本已在 µVision 5.43.1.0 上验证：菜单和对话框资源均可无损解析，生成副本的
`.text`、`.data`、`.rdata` 与原版一致；STM32 测试工程使用 ARM Compiler 5.06
update 5 构建结果为 0 个错误、0 个警告。

## 恢复

原版从未被修改，因此无需恢复。关闭中文副本并删除 `UV4_zh-CN.exe` 即可停止使用。
