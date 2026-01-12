# Mistode

[![PyPI version](https://img.shields.io/pypi/v/mistode.svg?color=blue)](https://pypi.org/project/mistode/)
[![Python versions](https://img.shields.io/pypi/pyversions/mistode.svg)](https://pypi.org/project/mistode/)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://github.com/for13to1/mistode/actions/workflows/ci.yml/badge.svg)](https://github.com/for13to1/mistode/actions)
[![Coverage](https://codecov.io/gh/for13to1/mistode/branch/main/graph/badge.svg)](https://codecov.io/gh/for13to1/mistode)

Mistode (Mist Code, pronounced like "Miss Told") 是一个轻量级的代码混淆工具，支持 Python 和 C 语言。它专注于使代码难以阅读，同时保持功能完整性。

**🌐 语言：**
[![English](https://img.shields.io/badge/English-README-blue)](README.md)
[![中文](https://img.shields.io/badge/中文-README_ZH-red)](README_ZH.md)

## 特性

- **加密 token 生成器**: 高度可定制的加密 token 生成，支持多种配置：
  - **随机种子**：支持设置随机种子，确保生成结果的可重现性
  - **长度控制**：自定义 token 长度，范围 [8,32] 字符
  - **风格配置**：支持两种混淆风格
    - **近似字符风格**：使用易混淆字符组增强混淆效果（如：`Oo0`、`iIlL1`、`b6B8`、`Zz2`、`Ss5`）
    - **随机字符风格**：使用随机字母数字组合
  - **智能去重机制**：自动维护已生成 token 集合，避免重复
- **Python 支持**:
  - **AST 解析**: 基于抽象语法树的精确混淆，确保代码格式完全保留
  - **智能标识符分类**: 自动识别并保留导入的模块、函数和内置方法
  - **文档字符串混淆**: 将文档字符串替换为哈希值
  - **完全可逆**: 支持使用生成的密钥文件或嵌入的元数据完全恢复
  - **无损还原**: 通过分布式注释注入原始源代码，实现与原文件一致的无损还原
- **C 支持**:
  - **快速分词**: 使用健壮的正则表达式分词器
  - **布局引擎**: 使用 `// @mistode:chunk:` 元数据保留代码结构
  - **编译安全**: 保留关键字、预处理指令和外部符号
  - **无损还原**: 通过分布式布局块实现与原文件一致的无损还原

## 安装

```shell
pip install mistode
```

## 使用方法

### 简单使用（使用默认设置）

```shell
# 混淆（生成 input.obf.py 和 input.map.json）
mistode o input.py

# 恢复（如果命名匹配，自动检测 input.map.json）
# 生成 input.res.py
mistode r input.obf.py
```

### 完整使用

```shell
# 使用显式选项进行混淆
mistode obfuscate input.py --out output.py --key mapping.json

# 使用显式选项进行恢复
mistode restore output.py --out restored.py --key mapping.json
```

### 配置文件

您可以在 `pyproject.toml` 中设置默认选项，避免重复输入相同的参数：

```toml
[tool.mistode]
style = "similar"    # 默认混淆风格（"similar" 或 "random"）
length = 16          # 默认 token 长度（8-32）
stats = true         # 总是显示统计信息
# seed = 42          # 可选：设置默认随机种子以获得可重现结果
```

**工作原理**：

- Mistode 自动在当前目录和父目录中搜索 `pyproject.toml`
- 如果找到，`[tool.mistode]` 中的设置将作为默认值使用
- 命令行参数始终会覆盖配置文件设置

**示例**：

```bash
# 使用上述配置，以下两个命令等效：
mistode o input.py
mistode o input.py --style similar --length 16 --stats

# 使用命令行参数覆盖配置：
mistode o input.py --style random --length 20
```

完整指南请参阅 [`examples/CONFIG_GUIDE.md`](examples/CONFIG_GUIDE.md)。

## 高级特性

### Python 混淆的智能标识符识别

Mistode 能够智能识别以下类型的标识符并避免混淆：

- **内置模块**: `re`, `os`, `sys`, `json`, `math` 等
- **内置函数**: `print`, `len`, `range`, `str`, `int` 等
- **导入的函数**: 从 `import` 和 `from ... import` 语句中导入的函数
- **内置方法**: `re.sub`, `str.strip`, `list.append` 等

### 示例

**原始代码**:

```python
import re
from openpyxl.utils import get_column_letter, column_index_from_string

def shift_column_letter(base_column, offset):
    """根据给定的列字母和偏移量，计算偏移后的列字母"""
    base_idx = column_index_from_string(base_column)
    target_idx = base_idx + offset
    return get_column_letter(target_idx)
```

**混淆代码**:

```python
import re
from openpyxl.utils import get_column_letter, column_index_from_string

#@mistode:chunk:eJzjSklNU8hIzcnJ11BQyEvMTVVQ0LTiU...
def Oo0iIlL1b6B8Zz2Ss5(Oo0iIlL1b6B8Zz2Ss6, Oo0iIlL1b6B8Zz2Ss7):
    """混淆文档字符串: e2d30883ac53"""
#@mistode:chunk:aVaCikKXmAdOkoVEO01SopaCoogFWAiQo...
    Oo0iIlL1b6B8Zz2Ss8 = column_index_from_string(Oo0iIlL1b6B8Zz2Ss6)
    Oo0iIlL1b6B8Zz2Ss9 = Oo0iIlL1b6B8Zz2Ss8 + Oo0iIlL1b6B8Zz2Ss7
    return get_column_letter(Oo0iIlL1b6B8Zz2Ss9)
#@mistode:metadata:eJxVk1Fr3DAMx79K...
```

### 嵌入式元数据与分布式源码 (Embedded Metadata & Distributed Source)

Mistode 采用两层恢复机制：

1. **分布式源码块 (`#@mistode:chunk:` 或 `// @mistode:chunk:`)**: 将原始源代码压缩、编码并分块注入到混淆代码的每一行之前。恢复时优先使用这些块重组原始代码，实现**无损还原**（包括所有注释、空行和格式）。
2. **嵌入式元数据 (`#@mistode:metadata:`)**: 包含标识符映射表，作为备用恢复手段。

这意味着即使不保留密钥文件，您也可以完美恢复原始代码。

```python
# ... 混淆后的代码 ...
#@mistode:chunk:eJzjSk... (分布式源码块)
# ...
#@mistode:metadata:eJxVk1... (base64 编码的映射)
```

如果没有提供密钥文件，恢复命令会自动检测并使用此元数据。

## 项目结构

```shell
mistode/
├── src/
│   └── mistode/
│       ├── __init__.py      # 包初始化
│       ├── cli.py           # 命令行接口
│       ├── python.py        # Python 混淆器 (mistode.python)
│       ├── c.py             # C 混淆器 (mistode.c)
│       └── core.py          # 核心功能 (mistode.core)
├── tests/                   # 测试目录
│   ├── __init__.py
│   ├── test_python.py       # Python 混淆器测试
│   ├── test_c.py           # C 混淆器测试
│   ├── test_cli.py         # 命令行接口测试 (集成测试)
│   ├── test_cli_unit.py    # 命令行接口测试 (单元测试)
│   └── test_core.py        # 核心功能测试
├── pyproject.toml          # 项目配置
└── README.md               # 项目文档
```

## 开发

### 运行测试

```shell
python -m pytest tests/
```

### 构建包

```shell
pip install build
python -m build
```
