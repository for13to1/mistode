# Mistode

[![PyPI version](https://img.shields.io/pypi/v/mistode.svg?color=blue)](https://pypi.org/project/mistode/)
[![Python versions](https://img.shields.io/pypi/pyversions/mistode.svg)](https://pypi.org/project/mistode/)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://github.com/for13to1/mistode/actions/workflows/ci.yml/badge.svg)](https://github.com/for13to1/mistode/actions)
[![Coverage](https://codecov.io/gh/for13to1/mistode/branch/main/graph/badge.svg)](https://codecov.io/gh/for13to1/mistode)

**🌐 语言：**
[![English](https://img.shields.io/badge/English-README-blue)](README.md)
[![中文](https://img.shields.io/badge/中文-README_ZH-red)](README_ZH.md)

Mistode (Mist Code, pronounced like *miss-told*) 是一个轻量级的高级代码混淆工具，保护 **Python** 和 **C** 源代码。它结合了强大的 AST/Regex 解析与分布式布局引擎，确保代码难以阅读，同时保持功能完整并能够完美还原。

## 特性

- **🛡️ 高级混淆引擎**:
  - **加密 Token 生成**: 可配置 Token 长度（8-32字符）和风格（近似字符如 `Oo01Il` 或随机字母数字）。
  - **智能去重与验证**: 确保无冲突，并针对语言关键字验证生成的 Token。
  - **种子支持**:通过 `--seed` 实现完全可复现的混淆。

- **🐍 Python 支持 (v3.14+)**:
  - **基于 AST 的精确性**: 解析抽象语法树，进行安全准确的转换。
  - **智能保留**: 自动保护导入、内置函数（`print`, `len`）和标准库调用。
  - **文档字符串哈希**: 将文档字符串替换为唯一的哈希标记。

- **🇨 C 支持**:
  - **健壮的分词**: 基于正则表达式的引擎，安全处理宏、指针和结构体。
  - **布局引擎**: 使用分布式的 `// @mistode:chunk:` 标记保留复杂的文件结构。
  - **符号安全**: 自动保留关键字、预处理指令和标准头文件。

- **🔄 零损还原 (Zero-Loss Restoration)**:
  - **分布式源码块**: 原始源代码被压缩、加密，并作为注释分块分布在整个混淆文件中。
  - **嵌入式元数据**: 标识符映射直接嵌入在文件头/尾中。**恢复文件不需要密钥文件。**
  - **比特级完美还原**: 还原原始代码的每一个字节，包括注释、格式和空行。

- **⚙️ 现代工具链**:
  - **配置文件**: 通过 `pyproject.toml` 设置全局默认值。
  - **详细统计**: `--stats` 标志提供标识符计数、压缩率和安全检查。

## 安装

> [!IMPORTANT]
> Mistode 需要 **Python 3.14** 或更高版本。

```bash
pip install mistode
```

## 快速开始

### 1. Python 示例

```bash
# 混淆 'app.py' (生成 app.obf.py)
mistode o app.py --stats

# 还原为原始文件 (生成 app.res.py)
# 不需要密钥文件 - 使用嵌入式元数据！
mistode r app.obf.py

# 验证匹配
diff app.py app.res.py
```

### 2. C 示例

```bash
# 混淆 'main.c' (生成 main.obf.c)
mistode o main.c --stats

# 编译并运行混淆后的代码
gcc main.obf.c -o main_obf
./main_obf

# 还原
mistode r main.obf.c
```

## 使用指南

### 命令行接口

```bash
# 通用语法
mistode [command] [file] [options]

# 命令
o, obf, obfuscate   混淆文件
r, res, restore     还原文件
```

### 常用选项

| 选项 | 别名 | 描述 |
| :--- | :--- | :--- |
| `--out` | `-o` | 指定输出文件名。 |
| `--key` | `-k` | 指定密钥文件路径（可选，因为元数据已嵌入）。 |
| `--stats` | | 处理后显示详细统计信息。 |
| `--style` | | `similar`（默认）或 `random`。 |
| `--length` | `-l` | Token 长度 (8-32)。 |
| `--seed` | `-s` | 用于可复现性的随机种子。 |
| `--password` | `-p` | 用于加密/解密的密码。 |

### 配置文件 (`pyproject.toml`)

您可以在 `pyproject.toml` 中定义项目范围的默认值。Mistode 会自动在当前目录和父目录中查找此文件。

```toml
[tool.mistode]
style = "similar"    # "similar" (Io01) 或 "random" (aB3d)
length = 24          # 更强的 token
stats = true         # 总是显示统计信息
seed = 12345         # 确定性构建
```

有关详细指南，请参阅 [examples/CONFIG_GUIDE.md](examples/CONFIG_GUIDE.md)。

## 混淆内容清单

### Python

| 组件 | 状态 | 说明 |
| :--- | :---: | :--- |
| **变量名** | ✅ | 替换为 Token |
| **函数/类名** | ✅ | 替换为 Token |
| **文档字符串** | ✅ | 替换为哈希占位符 |
| **导入 (Imports)** | ❌ | 保留 (`import math`) |
| **内置函数** | ❌ | 保留 (`print`, `len`) |
| **标准库方法** | ❌ | 保留 (`os.path.join`) |

### C / C++

| 组件 | 状态 | 说明 |
| :--- | :---: | :--- |
| **函数** | ✅ | 仅用户定义的函数 |
| **变量/结构体** | ✅ | 局部和全局 |
| **注释** | ✅ | 打乱或移除 |
| **关键字** | ❌ | 保留 (`if`, `while`) |
| **预处理器** | ❌ | 保留 (`#include`, `#define`) |
| **标准库** | ❌ | 保留 (`printf`, `malloc`) |

## 还原机制

Mistode 使用**双层还原系统**来保证安全性：

1. **分布式源码块 (首选)**:
    压缩后的原始源码块作为注释（例如 `#@mistode:chunk:...`）注入到整个文件中。这允许**100% 比特级完美还原**。

2. **嵌入式映射 (次选)**:
    重命名映射被压缩并嵌入在文件页脚（`#@mistode:metadata:`）。如果源码块损坏，这允许功能性还原。

3. **密钥文件 (可选)**:
    您可以使用 `--key` 显式将映射保存到 JSON 文件，但在标准工作流中不需要。

## 贡献

欢迎贡献！详情请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)（英文）。

## 许可证

本项目采用 [GPLv3 许可证](LICENSE) 授权。
