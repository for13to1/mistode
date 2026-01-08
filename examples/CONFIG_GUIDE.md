# Mistode 配置文件使用指南

## 📖 工作原理

是的，你的理解完全正确！配置文件的工作方式如下：

### 1. 自动发现

`mistode` 会自动在以下位置搜索 `pyproject.toml`：

- 当前执行目录
- 当前目录的所有父目录（向上递归）

### 2. 自动加载

如果找到 `pyproject.toml` 且包含 `[tool.mistode]` 部分，会自动读取这些配置作为默认值。

### 3. 优先级规则

**命令行参数 > 配置文件 > 内置默认值**。

---

## 🎯 实际演示

### 配置文件内容

在 `pyproject.toml` 中添加：

```toml
[tool.mistode]
style = "random"      # 使用随机字符风格
length = 20           # token 长度 20 字符
stats = true          # 总是显示统计信息
```

### 演示 1: 不使用配置文件

```bash
$ mistode o demo_simple.py
OK Obfuscated demo_simple.py -> demo_simple.obf.py
```

生成的函数名（16字符，similar风格）：

```python
def Vbz585ziiZ5O21S5(ab065bO1bOS2zOsO):  # 易混淆字符
```

### 演示 2: 使用配置文件（自动应用）

启用上面的配置后：

```bash
$ mistode o demo_simple.py
OK Obfuscated demo_simple.py -> demo_simple.obf.py

=== Obfuscation Statistics ===  # 自动显示！
  Identifiers obfuscated: 0
  Original size: 0.23 KB
  Obfuscated size: 1.08 KB
  ...
```

生成的函数名（20字符，random风格）：

```python
def Ui12Zz158sOO8Ss0(yB1sZI0BS6SZ6bSi):  # 随机字符，更长
```

### 演示 3: 命令行参数覆盖配置

即使配置文件设置了 `length = 20`，命令行参数依然优先：

```bash
$ mistode o demo_simple.py --length 12 --style similar
# 会使用 12 字符的 similar 风格，而不是配置文件的 20 字符 random
```

---

## 💡 使用场景

### 场景 1: 团队统一配置

在项目根目录的 `pyproject.toml` 中设置，整个团队使用相同的混淆设置：

```toml
[tool.mistode]
style = "similar"
length = 16
stats = true
```

### 场景 2: 不同项目不同配置

- 项目 A 需要短名称快速混淆
- 项目 B 需要长名称高安全性

每个项目配置自己的 `pyproject.toml`。

### 场景 3: 临时覆盖

日常使用配置文件的默认设置，但偶尔需要特殊处理：

```bash
# 平时：使用配置文件的设置
mistode o file.py

# 特殊情况：临时使用不同设置
mistode o file.py --length 24 --seed 123
```

---

## ⚙️ 支持的配置项

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `style` | string | `"similar"` | 混淆风格：`"similar"` 或 `"random"` |
| `length` | integer | `16` | Token 长度，范围 8-32 |
| `stats` | boolean | `false` | 是否默认显示统计信息 |
| `seed` | integer | 无 | 可选的随机种子 |

---

## 📋 完整示例

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-project"
version = "1.0.0"

# ... 其他配置 ...

# Mistode 配置
[tool.mistode]
style = "similar"     # 使用易混淆字符
length = 18           # 18 字符长度
stats = true          # 总是显示统计
seed = 42             # 固定随机种子（可重现）
```

### 使用效果

```bash
# 在项目目录下任何位置执行，都会自动应用这些配置
$ cd /path/to/my-project/src
$ mistode o module.py

# 等同于：
$ mistode o module.py --style similar --length 18 --stats --seed 42
```

---

## ❓ 常见问题

### Q1: 配置文件必须在项目根目录吗？

**A**: 不必须。`mistode` 会向上递归搜索父目录，直到找到包含 `[tool.mistode]` 的 `pyproject.toml`。

### Q2: 如何知道当前使用了哪些配置？

**A**: 暂时没有专门的命令显示。可以通过观察生成的token长度来判断，或使用 `--stats` 查看效果。

### Q3: 配置文件会影响所有子目录吗？

**A**: 是的。如果在父目录找到配置文件，所有子目录执行 `mistode` 都会使用该配置（除非子目录有自己的 `pyproject.toml`）。

### Q4: 不想使用配置文件怎么办？

**A**: 两种方法：

1. 删除或注释掉 `[tool.mistode]` 部分
2. 使用命令行参数覆盖所有配置项

### Q5: 配置文件加载失败会报错吗？

**A**: 不会。如果：

- 找不到 `pyproject.toml`
- 文件格式错误
- 缺少 `[tool.mistode]` 部分

`mistode` 会静默使用内置默认值，不会报错。

---

## ✅ 总结

配置文件的核心优势：

1. **方便**: 不用每次都输入相同的参数
2. **统一**: 团队或项目使用一致的混淆设置
3. **灵活**: 仍然可以用命令行参数临时覆盖
4. **自动**: 无需手动指定配置文件路径

**是的，只要执行目录下（或父目录）有 `pyproject.toml` 文件，并且包含 `[tool.mistode]` 配置，mistode 执行时就会自动应用这些配置！** ✨
