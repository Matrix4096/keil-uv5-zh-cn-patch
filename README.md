# µVision 5.x 简体中文资源补丁生成器

这是一个非官方、源码形式发布的 Windows 资源补丁工具，适用于
**Arm Keil µVision 5.x**。它生成一个独立的中文副本，只修改界面资源，不修改
编译器、调试器、工程文件或许可证逻辑。`5.43.1.0` 是完整验证版本；其他相邻
5.x 版本使用原文指纹匹配的安全兼容模式。

> 本项目与 Arm、Keil 无关联，也未获得其认可。使用者须自行确保拥有相关软件
> 的合法许可证，并遵守适用的软件许可协议。

## 仓库不包含什么

本仓库不提供或分发：

- `UV4.exe`、生成后的 `UV4_zh-CN.exe` 或任何 Keil 安装文件；
- Pack、编译器、许可证、序列号、注册机或激活绕过工具。

仓库内置独立的简体中文词典 `translations/zh_CN.json`。词典只保存原英文的
SHA-256 指纹和中文译文，不包含原版可执行文件或完整英文资源。使用者只需自行提供
官方 `UV4.exe`。

## 版本兼容性

- **完整验证：** µVision `5.43.1.0`，官方文件 SHA-256 为
  `428BAF13D15E6760AF1618DEF9C9815C97F0321CC5E459EC7ADC4DDE41C42F89`。
- **安全兼容：** 其他 µVision 5.x 版本。脚本只修改资源 ID、菜单路径和原文
  SHA-256 指纹均匹配的条目；新增、删除或改变的项目保持英文。
- 未验证版本默认至少需要达到 70% 的词典匹配率，否则拒绝生成输出。
- 兼容模式不等于所有 5.x 版本均已实测；请先使用 `--dry-run` 查看报告中的覆盖率。

## 当前覆盖范围

- 在 5.43.1 上覆盖 774 条简体中文界面字符串；
- 在 5.43.1 上覆盖 29 组菜单、234 个菜单项；
- µVision 5.43.1 新增且旧词库没有对应内容的项目仍显示英文；
- 当前词典不包含对话框控件翻译，因此多数设置窗口仍为英文；
- 相邻版本的实际覆盖数量取决于资源匹配结果。

## 环境要求

- Windows 10 或 Windows 11；
- Python 3.10 或更高版本；
- 用户自行提供官方 µVision 5.x 的 `UV4.exe`。

本工具仅使用 Python 标准库，无需安装第三方依赖。

## 使用方法

在 PowerShell 中进入仓库目录并运行：

```powershell
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe"
```

默认会在原版文件旁生成 `UV4_zh-CN.exe`，并在当前目录写入
`patch-report.json`。也可以显式指定路径：

```powershell
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe" `
  --output "C:\Keil_v5\UV4\UV4_zh-CN.exe" `
  --report ".\patch-report.json"
```

只检查兼容性、不生成中文副本：

```powershell
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe" `
  --dry-run
```

只允许完整验证的 5.43.1 文件：

```powershell
python .\build_patch.py `
  --target "C:\Keil_v5\UV4\UV4.exe" `
  --exact-only
```

## 安全设计

- 永不覆盖原版 `UV4.exe`；
- 检查 Windows 文件版本，仅接受主版本为 5 的文件；
- 5.43.1 使用精确文件哈希识别，其他版本必须通过原文 SHA-256 指纹和覆盖率检查；
- 只更新匹配的 Win32 `RT_STRING` 与 `RT_MENU` 显示资源；
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
