# ason-py

基于 C++ pybind11 的高性能 **ASON**（Array-Schema Object Notation）Python 扩展。

提供 5 个函数：`encode`、`decode`、`encodePretty`、`encodeBinary`、`decodeBinary`。

[English Documentation](README.md)

---

## 环境要求

| 工具 | 版本 |
|------|---------|
| g++ | ≥ 11（C++17） |
| python3-dev | 任意（提供 `Python.h`） |
| Python | ≥ 3.8 |

pybind11 2.13.6 头文件已**内置**于 `vendor/pybind11/` — 无需单独安装。

---

## 构建

```bash
# 方式 A — Shell 脚本（若缺少 python3-dev 会自动 sudo 安装）
bash build.sh

# 方式 B — Makefile
make

# 方式 C — CMake
cmake -B build && cmake --build build
```

---

## API

```python
import ason

# Schema（模式）字符串格式：
# 单个结构体："{field:type, ...}"
# 结构体切片："[{field:type, ...}]"
#
# 支持类型：int, uint, float, bool, str
# 可选后缀 ?（如 str?、int?）
```

### `encode(obj, schema) -> str`

将 `dict` 或 `list[dict]` 序列化为 ASON 文本：

```python
text = ason.encode({"id": 1, "name": "Alice"}, "{id:int, name:str}")
# → '{id:int, name:str}:\n(1,Alice)\n'

rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
text = ason.encode(rows, "[{id:int, name:str}]")
```

### `decode(text) -> dict | list[dict]`

将 ASON 文本反序列化为 `dict` 或 `list[dict]`：

```python
rec  = ason.decode('{id:int, name:str}:\n(1,Alice)\n')
rows = ason.decode('[{id:int, name:str}]:\n(1,Alice),\n(2,Bob)\n')
```

### `encodePretty(obj, schema) -> str`

序列化为带缩进的多行 ASON 文本，便于阅读：

```python
pretty = ason.encodePretty(rows, "[{id:int, name:str}]")
```

### `encodeBinary(obj, schema) -> bytes`

序列化为二进制格式（与 ason-rs、ason-go 字节级兼容）：

```python
data = ason.encodeBinary(rows, "[{id:int, name:str}]")
```

### `decodeBinary(data, schema) -> dict | list[dict]`

从二进制格式反序列化：

```python
rows = ason.decodeBinary(data, "[{id:int, name:str}]")
```

---

## 二进制格式

小端字节序，与 ason-rs 和 ason-go 完全一致：

| 类型 | 字节数 |
|------|--------|
| `int` | 8（i64 LE） |
| `uint` | 8（u64 LE） |
| `float` | 8（f64 LE） |
| `bool` | 1 |
| `str` | 4 字节长度（LE）+ UTF-8 字节 |
| 可选值 | 1 字节标记（0=null，1=有值）+ 值 |
| 切片 | 4 字节元素数量（LE）+ 各元素 |

---

## 运行测试

```bash
# 构建完成后执行：
python3 -m pytest tests/ -v
```

---

## 示例

```python
import ason

users = [
    {"id": 1, "name": "Alice", "score": 9.5},
    {"id": 2, "name": "Bob",   "score": 7.2},
]
schema = "[{id:int, name:str, score:float}]"

text   = ason.encode(users, schema)
pretty = ason.encodePretty(users, schema)
blob   = ason.encodeBinary(users, schema)

assert ason.decode(text)               == users
assert ason.decode(pretty)             == users
assert ason.decodeBinary(blob, schema) == users
```

---

## 运行示例

```bash
# 基本用法
python3 examples/basic.py

# 综合示例（20 个场景）
python3 examples/complex.py

# 性能基准测试（与 json 模块对比）
python3 examples/bench.py
```

---

## 什么是 ASON？

ASON 将**模式**与**数据**分离，消除 JSON 中重复的键名。模式只声明一次，数据行只携带值：

```text
JSON（100 tokens）：
{"users":[{"id":1,"name":"Alice","active":true},{"id":2,"name":"Bob","active":false}]}

ASON（约 35 tokens，节省 65%）：
[{id:int, name:str, active:bool}]:(1,Alice,true),(2,Bob,false)
```

| 方面 | JSON | ASON |
|------|------|------|
| Token 效率 | 100% | 30–70% ✓ |
| 键名重复 | 每个对象 | 只声明一次 ✓ |
| 可读性 | 是 | 是 ✓ |
| 类型注解 | 无 | 有 ✓ |
| 数据体积 | 100% | **40–50%** ✓ |

---

## 许可证

MIT
