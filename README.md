# ason-py

C++ pybind11 extension for **ASON** (Array-Schema Object Notation).

Provides 7 functions without requiring manual schema strings for encoding:
`encode`, `encodeTyped`, `encodePretty`, `encodePrettyTyped`, `decode`, `encodeBinary`, `decodeBinary`.

The wheel also ships `ason.pyi` and `py.typed`, so editors and static type checkers can understand the extension module without a separate stub package.

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

### Type inference rules

| Python value | Inferred ASON type |
|-------------|--------------------|
| `bool` | `bool` |
| `int` | `int` |
| `float` | `float` |
| `str` | `str` |
| `None` | optional (e.g. `str?`, `int?`) |

**Cross-row type merging for lists:** When encoding a list, all rows are scanned to compute the final type:
- A field that is non-`None` in row 0 but `None` in some later row is promoted to optional (e.g. `str` → `str?`, `int` → `int?`).
- Type conflicts between non-`None` values (e.g. `int` in row 0, `str` in row 1) fall back to `str`.

This means `encodeTyped` is safe to use even when only some rows have `None` for a given field.

### `encode(obj) -> str` — untyped schema, inferred

```python
ason.encode({"id": 1, "name": "Alice"})
# → '{id,name}:\n(1,Alice)\n'

ason.encode([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
# → '[{id,name}]:\n(1,Alice),\n(2,Bob)\n'
```

> **Untyped decode semantics:** When decoded with `decode()`, all field values are returned as **strings** because the untyped schema carries no type information. Use `encodeTyped` when you need a type-preserving round-trip.

### `encodeTyped(obj) -> str` — typed schema, inferred

Type is inferred from all rows (not just the first). A field that is `None` in any row is made optional:

```python
ason.encodeTyped({"id": 1, "name": "Alice", "active": True})
# → '{id@int,name@str,active@bool}:\n(1,Alice,true)\n'

# Optional field inferred from cross-row merging:
ason.encodeTyped([{"id": 1, "tag": "hello"}, {"id": 2, "tag": None}])
# → '[{id@int,tag@str?}]:\n(1,hello),\n(2,)\n'
```

### `encodePretty(obj) -> str` — pretty + untyped, inferred

```python
pretty = ason.encodePretty(rows)
```

### `encodePrettyTyped(obj) -> str` — pretty + typed, inferred

```python
pretty = ason.encodePrettyTyped(rows)
```

### `decode(text) -> dict | list[dict]`

Decodes both typed and untyped schemas embedded in the text:

```python
# typed schema → values restored as Python types
rec  = ason.decode('{id@int, name@str}:\n(1,Alice)\n')    # {'id': 1, 'name': 'Alice'}
rows = ason.decode('[{id@int, name@str}]:\n(1,Alice),\n(2,Bob)\n')

# untyped schema → all values returned as strings
rec2 = ason.decode('{id,name}:\n(1,Alice)\n')             # {'id': '1', 'name': 'Alice'}
```

Block comments are supported anywhere whitespace is allowed:

```python
rec = ason.decode('/* top */ {id@int,name@str}: /* row */ (1, /* name */ Alice)')
```

### `encodeBinary(obj) -> bytes` — schema inferred internally

```python
data = ason.encodeBinary(rows)
```

### `decodeBinary(data, schema) -> dict | list[dict]`

Schema is required because the binary wire format carries no embedded type information:

```python
rows = ason.decodeBinary(data, "[{id@int, name@str}]")
```

## Typing

`ason-py` includes inline typing support for the compiled extension:

```python
from ason import decode

rows = decode("[{id@int, name@str}]:(1,Alice),(2,Bob)")
```

Type checkers will infer `dict[str, Any] | list[dict[str, Any]]` for decode results and validate function signatures from the bundled `ason.pyi`.

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

# Schema is inferred automatically—no schema string needed
text        = ason.encode(users)           # untyped schema
textTyped   = ason.encodeTyped(users)      # typed schema (use for round-trip)
pretty      = ason.encodePrettyTyped(users)# pretty + typed
blob        = ason.encodeBinary(users)     # binary (schema inferred internally)

assert ason.decode(textTyped)  == users    # typed round-trip
assert ason.decode(pretty)     == users
assert ason.decodeBinary(blob, "[{id@int, name@str, score@float}]") == users
```

## Latest Benchmarks

Measured on this machine with:

```bash
bash build.sh
PYTHONPATH=. python3 examples/bench.py
```

Headline numbers:

- Flat 1,000-record dataset: ASON text serialize `118.98ms` vs JSON `403.32ms`, deserialize `221.21ms` vs JSON `441.89ms`
- Flat 10,000-record dataset: ASON text serialize `81.70ms` vs JSON `293.38ms`, deserialize `158.39ms` vs JSON `317.44ms`
- Size summary for 1,000 flat records: JSON `137,674 B`, ASON text `57,761 B` (`58%` smaller), ASON binary `74,454 B` (`46%` smaller vs JSON)
- Throughput summary on 1,000 records: ASON text was `3.58x` faster than JSON for serialize and `2.01x` faster for deserialize
- Binary mode was even faster: `7.18x` faster than JSON on serialization and `4.16x` faster on deserialization in the benchmark summary

## Contributors

- [Athan](https://github.com/athxx)
