# ason-py

C++ pybind11 extension for **ASON** (Array-Schema Object Notation).

Provides 5 functions: `encode`, `decode`, `encodePretty`, `encodeBinary`, `decodeBinary`.

[中文文档](README_CN.md)

---

## Requirements

| Tool | Version |
|------|---------|
| g++ | ≥ 11 (C++17) |
| python3-dev | any (provides `Python.h`) |
| Python | ≥ 3.8 |

pybind11 2.13.6 headers are **vendored** in `vendor/pybind11/` — no separate installation needed.

---

## Build

```bash
# Option A — shell script (auto-installs python3-dev via sudo if missing)
bash build.sh

# Option B — Makefile
make

# Option C — CMake
cmake -B build && cmake --build build
```

---

## API

```python
import ason

# Schema strings
# Single struct : "{field:type, ...}"
# Slice of structs: "[{field:type, ...}]"
#
# Types: int, uint, float, bool, str
# Optional suffix ?  (e.g. str?, int?)
```

### `encode(obj, schema) -> str`

```python
text = ason.encode({"id": 1, "name": "Alice"}, "{id:int, name:str}")
# → '{id:int, name:str}:\n(1,Alice)\n'

rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
text = ason.encode(rows, "[{id:int, name:str}]")
```

### `decode(text) -> dict | list[dict]`

```python
rec  = ason.decode('{id:int, name:str}:\n(1,Alice)\n')
rows = ason.decode('[{id:int, name:str}]:\n(1,Alice),\n(2,Bob)\n')
```

### `encodePretty(obj, schema) -> str`

```python
pretty = ason.encodePretty(rows, "[{id:int, name:str}]")
```

### `encodeBinary(obj, schema) -> bytes`

```python
data = ason.encodeBinary(rows, "[{id:int, name:str}]")
```

### `decodeBinary(data, schema) -> dict | list[dict]`

```python
rows = ason.decodeBinary(data, "[{id:int, name:str}]")
```

---

## Binary format

Little-endian layout, identical to ason-rs and ason-go:

| Type | Bytes |
|------|-------|
| `int` | 8 (i64 LE) |
| `uint` | 8 (u64 LE) |
| `float` | 8 (f64 LE) |
| `bool` | 1 |
| `str` | 4-byte length LE + UTF-8 bytes |
| optional | 1-byte tag (0=null, 1=present) + value |
| slice | 4-byte count LE + elements |

---

## Run tests

```bash
# after building:
python3 -m pytest tests/ -v
```

---

## Example

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
