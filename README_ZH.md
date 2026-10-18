# Mistode

[![PyPI version](https://img.shields.io/pypi/v/mistode.svg?color=blue)](https://pypi.org/project/mistode/)
[![Python versions](https://img.shields.io/pypi/pyversions/mistode.svg)](https://pypi.org/project/mistode/)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://github.com/for13to1/mistode/actions/workflows/ci.yml/badge.svg)](https://github.com/for13to1/mistode/actions)
[![Coverage](https://codecov.io/gh/for13to1/mistode/branch/main/graph/badge.svg)](https://codecov.io/gh/for13to1/mistode)

**🌐 语言：**
[![English](https://img.shields.io/badge/English-README-blue)](README.md)
[![中文](https://img.shields.io/badge/中文-README_ZH-red)](README_ZH.md)

Mistode (Mist Code，发音类似 *miss-told*) 是一个面向 **Python** 与 **C** 的代码混淆工具。它结合 AST/正则解析与分布式布局引擎，使交付代码难以阅读的同时保持可正常运行，支持凭密钥完整还原。

## 特性

- **🛡️ 高级混淆引擎**:
  - **随机 Token 生成**：Token 长度（8-32 字符）与风格均可配置，如近似字符（`Oo01Il`）或随机字母数字。
  - **去重与校验**：保证 Token 无冲突，并按语言关键字校验。
  - **种子支持**：通过 `--seed` 实现完全可复现的混淆。

- **🔐 密钥门控还原** (`--password`):
  - **认证流密码**：完全基于标准库实现——scrypt 密钥派生、SHA-256 CTR 密钥流、HMAC-SHA256 校验（encrypt-then-MAC）。
  - **无密钥流复用**：nonce 按 payload 内容派生，单处已知明文无法解开文件其余部分。
  - **确定性**：相同输入与密码产生相同输出，可复现构建不受影响。
  - **算法可配置**：`--cipher stream`（默认）或 `--cipher none`。

- **🐍 Python 支持 (v3.14+)**:
  - **基于 AST 的精确转换**：解析抽象语法树，确保重命名安全准确。
  - **选择性保留**：自动保护导入、内置函数（`print`、`len`）、标准库调用、`__all__` 导出、关键字实参名、`main`（保证 `console_scripts` 与 `python -m` 正常工作）及属性名。
  - **文档字符串隐藏**：将 docstring 替换为最小占位符，可从内嵌布局数据无损还原。

- **🇨 C 支持**:
  - **健壮分词**：基于正则表达式，可靠处理宏、指针、结构体，以及 `#include <...>` 与 `#include "..."` 两种形式。
  - **布局引擎**：以分布式 `/* @mistode:chunk:... */` 块注释标记保留复杂文件结构，多行宏的反斜杠续行后依然合法。
  - **符号安全**：自动保留关键字、预处理指令和标准头文件；有 `gcc`/`nm` 时优先使用编译器探测（并将源文件目录加入 include 路径），否则回退到保守的启发式扫描器。

- **🔄 零损还原 (Zero-Loss Restoration)**:
  - **分布式布局数据**：空白、注释、docstring 与原始换行经压缩后以 chunk 注释分块嵌入（默认 base64，`--password` 时加密）。
  - **嵌入式元数据**：标识符映射直接嵌入文件页脚，**还原无需密钥文件**。
  - **比特级完美还原**：逐字节还原原始代码，包括注释、格式、CRLF 与空行。

- **📦 自包含交付**:
  - **项目（目录）模式**：镜像整个目录树并保留原文件名，导入/包含关系不受影响。
  - **默认携带非源码文件**（`--assets copy`）：复制模板、数据与配置，混淆后的项目可直接运行；凭据类文件（`.env`、`*.pem` 等）默认包含，`--assets-skip-secrets` 可跳过。

- **⚙️ 现代工具链**:
  - **配置文件**：通过 `pyproject.toml` 设置全局默认值（style、length、seed、cipher、assets 等）。
  - **详细统计**：`--stats` 输出标识符数量、保留名数量与文件大小分析。

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

### 3. 密码保护交付

```bash
# 以交付密钥混淆
mistode o app.py --password "$DELIVERY_KEY"

# 产物运行无需密码
python app.obf.py

# 以密钥还原
mistode r app.obf.py --password "$DELIVERY_KEY"
```

### 4. 项目（目录）模式

传入目录而不是单个文件，即可混淆整个项目：

```bash
# 将 src/ 混淆到 src.obf/（镜像目录结构，保留原文件名，
# 保证 import/include 不断；跨文件引用自动保留）
mistode o src/

# 直接运行混淆后的项目（Python）
python src.obf/app.py

# 或编译（C）
gcc -Isrc.obf src.obf/main.c src.obf/util.c -o app

# 非源码文件（模板、数据、配置）默认一并复制；
# --assets list 查看，--assets skip 关闭：
mistode o src/ --assets list
mistode o src/ --assets skip

# 逐字节还原整个项目
mistode r src.obf/   # 生成 src.res/
```

项目模式自动处理跨文件引用：通过 `from mod import name` 导入的名字（Python）和跨编译单元共享的符号（C）在每个文件中都保留原名，因此混淆后的项目仍可运行/编译。

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
| `--key` | `-k` | 写出/读取映射 JSON（可选；默认使用内嵌元数据）。 |
| `--stats` | | 处理后显示详细统计信息。 |
| `--style` | | `similar`（默认）或 `random`。 |
| `--length` | `-l` | Token 长度 (8-32)。 |
| `--seed` | `-s` | 用于可复现性的随机种子。 |
| `--password` | `-p` | 解密加密 payload 的密码。 |
| `--cipher` | | payload 加密算法：`stream` 或 `none`。 |
| `--aggressive-methods` | | 同时重命名接收者仅为 `self`/类名的类方法。 |
| `--assets` | | 是否复制非源码文件：`copy`（默认）、`skip`、`list`。 |
| `--assets-skip-secrets` | | 复制时跳过 `.env`、`*.pem`、`*.key` 等凭据类文件。 |

### 配置文件 (`pyproject.toml`)

项目级默认值可在 `pyproject.toml` 中定义；Mistode 会搜索当前目录及其父目录。

```toml
[tool.mistode]
style = "similar"          # "similar" (Io01) 或 "random" (aB3d)
length = 24                # 更强的 token
stats = true               # 总是显示统计信息
seed = 12345               # 确定性构建
cipher = "stream"          # payload 加密算法（需配合 --password）
assets = "copy"            # 复制非源码文件
assets_skip_secrets = false
```

有关详细指南，请参阅 [examples/CONFIG_GUIDE.md](examples/CONFIG_GUIDE.md)。

## 混淆清单

### Python

| 组件 | 状态 | 说明 |
| :--- | :---: | :--- |
| **变量名** | ✅ | 替换为 Token |
| **函数/类名** | ✅ | 替换为 Token |
| **文档字符串** | ✅ | 替换为占位符（无损还原） |
| **`main`** | ❌ | 保留（`console_scripts` / `python -m` 的入口） |
| **`__all__` 导出** | ❌ | 保留（公共 API） |
| **关键字实参名** | ❌ | 保留（调用方按名传参） |
| **属性名** | ❌ | 保留（`obj.attr` 从不改名） |
| **导入 (Imports)** | ❌ | 保留 (`import math`) |
| **内置函数** | ❌ | 保留 (`print`, `len`) |
| **标准库方法** | ❌ | 保留 (`os.path.join`) |

### C / C++

| 组件 | 状态 | 说明 |
| :--- | :---: | :--- |
| **函数** | ✅ | 仅用户定义的函数 |
| **变量/结构体** | ✅ | 局部和全局 |
| **注释** | ✅ | 混淆产物中隐藏（无损还原） |
| **多行宏** | ✅ | 布局 chunk 使用块注释，`\` 续行不受影响 |
| **关键字** | ❌ | 保留 (`if`, `while`) |
| **预处理器** | ❌ | 保留 (`#include`、`#define`、宏名) |
| **标准库** | ❌ | 保留 (`printf`, `malloc`) |

## 还原机制

还原数据内嵌在产物中；密码是唯一需要保管的外部秘密。

1. **分布式布局数据 (首选)**: 布局数据（空白、注释、docstring、原始换行）被压缩并作为注释注入到整个文件中（Python 用 `#@mistode:chunk:`，C 用 `/* @mistode:chunk: */`）。这是**100% 比特级完美还原**的基础。

2. **嵌入式映射 (次选)**: 重命名映射被压缩并嵌入在文件页脚（`#@mistode:metadata:`）。

3. **密码（密钥）**: `--password` 使两类 payload 以 `secure_chunk` / `secure_metadata` 形式存储：scrypt 派生密钥、按内容派生 nonce 并附加 HMAC 校验；缺失或错误的密码会显式报错。

4. **密钥文件 (可选)**: `--key` 可将标识符映射写入 JSON，便于审计，或在元数据被剥离时还原；标准流程不需要它。

## 已知限制

- **动态访问不被跟踪**：通过字符串访问的名字（`globals()[...]`、`setattr`、`getattr(obj, "name")`、pickle）无法一致地重命名。
- **外部引用属于公共契约**：`__all__` 导出与跨文件导入/调用的名字会被保留，不做混淆。
- **C 启发式模式**：没有 `gcc`/`nm` 时回退到保守的启发式扫描器；有 `gcc` 时会将其 `nm -u` 结果与该扫描合并，因此更多名字被视为外部符号、改名更少。
- **混淆不是端到端保密**：字符串字面量、数值常量与控制流仍然可读。混淆提高的是理解成本，不是彻底隐藏业务逻辑。
- **`--password` 保护的是还原数据，而非代码本身**：无密码者仍可阅读混淆源码，只是无法还原。请使用长且唯一的口令；`scrypt` 显著提高离线破解成本，但无法挽救弱口令。
- **加密产物仍是普通 `.py` / `.c`**：密码保护的是还原，不是执行。
- **产物中不保留 docstring**：它们存放在还原数据里，运行期 `__doc__` 为空，`help()` / Sphinx / `doctest` 无法获取文档，直到还原后才恢复。
- **`--cipher stream` 需要 `--password`**：缺少密码时报错，而非静默降级为明文。
- **KDF 盐值固定**（`mistode-kdf-v1`）：相同口令在任意安装上派生出相同密钥。这是可复现构建的要求；代价是预计算可跨安装复用，口令强度因此更重要。
- **旧版 payload**：Mistode <= 0.1.3 加密的文件（无 nonce/tag）无法通过认证，会显式报错；请以当前版本重新混淆。
- **使用 `##` 的文件不混淆**：预处理器可在展开期合成任意标识符。
- **改名比例有限**：属性访问、星号导入、关键字实参、反射等动态特性使许多名字成为外部契约。以本项目自身源码实测，单文件模式约 45% 的候选名会被改名，项目模式约 36%；跨模块接口更多的真实项目更低。
- **`--aggressive-methods` 不适用于库**：它只重命名接收者可证明为 `self`/类名的方法。外部调用方按方法名访问，库可能因此损坏；仅用于自包含代码。
- **`--key` 在项目模式还原时不适用**：项目产物按文件携带元数据，直接用内嵌元数据还原（混淆时会写出汇总 key 供审计，但还原会拒绝 `--key` 以避免逐文件映射歧义）。

## 贡献

欢迎贡献。详情请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)（英文）。

## 许可证

本项目采用 [GPLv3 许可证](LICENSE) 授权。
