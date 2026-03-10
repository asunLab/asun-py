# ason-py

基于 C++ pybind11 的高性能 **ASON**（Array-Schema Object Notation）Python 扩展。

编码时**自动推断 schema**，不需要手动传 schema 字符串：
`encode`、`encodeTyped`、`encodePretty`、`encodePrettyTyped`、`decode`、`encodeBinary`、`decodeBinary`。

wheel 中同时包含 `ason.pyi` 和 `py.typed`，因此编辑器和静态类型检查器无需额外安装 stub 包也能识别这个扩展模块。

[English Documentation](README.md)

---

## 环境要求

| 工具 | 版本 |
|------|------|
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

### 类型推断规则

| Python 值 | 推断 ASON 类型 |
|----------|--------------|
| `bool` | `bool` |
| `int` | `int` |
| `float` | `float` |
| `str` | `str` |
| `None` | 可选类型（如 `str?`、`int?`） |

**列表的跨行类型归并：** 编码列表时，所有行都会参与类型推断：
- 某字段在第 0 行为非-`None`、在后续行为 `None` → 自动升级为可选（`str` → `str?`、`int` → `int?`）
- 同字段不同行类型冲突（如 `int` 与 `str`）→ 回落为 `str`

这意味着即使只有部分行有 `None`，也可以安全使用 `encodeTyped`。

### `encode(obj) -> str` — 无类型 schema，自动推断

```python
ason.encode({"id": 1, "name": "Alice"})
# → '{id,name}:\n(1,Alice)\n'

ason.encode([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
# → '[{id,name}]:\n(1,Alice),\n(2,Bob)\n'
```

> **无类型解码语义：** 使用 `decode()` 解码时，所有字段值都以**字符串**形式返回（因为无类型 schema 不含类型信息）。如需保真 round-trip，请使用 `encodeTyped`。

### `encodeTyped(obj) -> str` — 有类型 schema，自动推断

从**所有行**推断类型（不只看第一行）。如果某行有 `None`，该字段就会自动变为可选类型：

```python
ason.encodeTyped({"id": 1, "name": "Alice", "active": True})
# → '{id:int,name:str,active:bool}:\n(1,Alice,true)\n'

# 跨行类型归并：
ason.encodeTyped([{"id": 1, "tag": "hello"}, {"id": 2, "tag": None}])
# → '[{id:int,tag:str?}]:\n(1,hello),\n(2,)\n'
```

### `encodePretty(obj) -> str` — pretty + 无类型，自动推断

```python
pretty = ason.encodePretty(rows)
```

### `encodePrettyTyped(obj) -> str` — pretty + 有类型，自动推断

```python
pretty = ason.encodePrettyTyped(rows)
```

### `decode(text) -> dict | list[dict]`

支持 typed 和 untyped 两种 schema：

```python
# typed schema → 还原 Python 类型
rec  = ason.decode('{id:int, name:str}:\n(1,Alice)\n')    # {'id': 1, 'name': 'Alice'}
rows = ason.decode('[{id:int, name:str}]:\n(1,Alice),\n(2,Bob)\n')

# untyped schema → 所有值以字符串返回
rec2 = ason.decode('{id,name}:\n(1,Alice)\n')             # {'id': '1', 'name': 'Alice'}
```

### `encodeBinary(obj) -> bytes` — schema 内部推断

将对象序列化为二进制格式，**不需要传 schema 字符串**：

```python
data = ason.encodeBinary(rows)
```

### `decodeBinary(data, schema) -> dict | list[dict]`

**必须传 schema**，因为二进制 wire format 不嵌入任何类型信息：

```python
rows = ason.decodeBinary(data, "[{id:int, name:str}]")
```

## 类型支持

`ason-py` 为编译后的扩展模块内置了类型声明：

```python
from ason import decode

rows = decode("[{id:int, name:str}]:(1,Alice),(2,Bob)")
```

类型检查器会基于随包发布的 `ason.pyi` 校验函数签名，并将解码结果推断为 `dict[str, Any] | list[dict[str, Any]]`。

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

# schema 自动推断——不需要手动传 schema 字符串
text        = ason.encode(users)           # 无类型 schema（更短）
textTyped   = ason.encodeTyped(users)      # 有类型 schema
pretty      = ason.encodePrettyTyped(users)# pretty + 有类型
blob        = ason.encodeBinary(users)     # 二进制（schema 内部推断）

assert ason.decode(textTyped) == users     # 有类型 round-trip（完整还原）
assert ason.decode(pretty)    == users
assert ason.decodeBinary(blob, "[{id:int, name:str, score:float}]") == users
```

---

## 运行示例

```bash
# 基本用法
python3 examples/basic.py

# 综合示例（20 个场景）
python3 examples/complex.py

# 性能基准测试（与 json 模块对比，按 untyped / typed / binary 分类展示）
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

## Latest Benchmarks

在当前机器上通过下面命令实测（全部使用新推断驱动 API）：

```bash
bash build.sh
PYTHONPATH=. python3 examples/bench.py
```

关键结果：

- 扁平 1,000 条记录（typed）：ASON 文本序列化 `118.98ms`，JSON `403.32ms`；反序列化 ASON `221.21ms`，JSON `441.89ms`
- 扁平 10,000 条记录（typed）：ASON 序列化 `81.70ms`，JSON `293.38ms`；反序列化 ASON `158.39ms`，JSON `317.44ms`
- 1,000 条扁平记录体积：JSON `137,674 B`，ASON typed `57,761 B`（缩小 `58%`），ASON binary `74,454 B`
- 1,000 条记录吞吐总结：ASON typed 序列化比 JSON 快 `3.58x`，反序列化快 `2.01x`
- 二进制模式更快：BIN 序列化比 JSON 快 `7.18x`，反序列化快 `4.16x`

## Contributors

- [Athan](https://github.com/athxx)
