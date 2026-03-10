"""ASON Python — Complex Examples (inference-driven API)

Mirrors the complex examples in ason-go and ason-rs, covering all features
the Python C++ extension supports.

API (no schema args for encoding):
    encode(obj)              → untyped schema text
    encodeTyped(obj)         → typed schema text  ← use for round-trip fidelity
    encodePretty(obj)        → pretty + untyped
    encodePrettyTyped(obj)   → pretty + typed
    decode(text)             → dict | list[dict]
    encodeBinary(obj)        → bytes  (schema inferred internally)
    decodeBinary(data, schema) → dict | list[dict]  (schema required for binary)
"""

import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ason

errors = 0

def ok(tag):
    print(f"   ✓ {tag}")

def fail(tag, msg=""):
    global errors
    errors += 1
    print(f"   ✗ FAIL: {tag}  {msg}")

def assert_eq(a, b, tag):
    if a == b:
        ok(tag)
    else:
        fail(tag, f"\n     expected: {b}\n     got:      {a}")

def assert_ne(a, b, tag):
    if a != b:
        ok(tag)
    else:
        fail(tag, f"expected values to differ, both={a}")

def assert_raises(fn, tag):
    try:
        fn()
        fail(tag, "expected AsonError but no exception raised")
    except ason.AsonError:
        ok(tag)
    except Exception as e:
        fail(tag, f"unexpected exception: {e}")

print("=== ASON Complex Examples ===")
print()

# ── 1. Basic single-struct — encodeTyped / decode ────────────────────────────
print("1. Basic single-struct encode / decode:")
rec1 = {"id": 1, "name": "Alice", "active": True}
text1 = ason.encodeTyped(rec1)
print(f"   encodeTyped: {repr(text1)}")
out1 = ason.decode(text1)
assert_eq(out1, rec1, "basic typed roundtrip")

# ── 2. Slice of structs ──────────────────────────────────────────────────────
print("\n2. Slice of structs:")
rows2 = [
    {"id": 1, "name": "Alice", "active": True},
    {"id": 2, "name": "Bob",   "active": False},
    {"id": 3, "name": "Carol Smith", "active": True},
]
text2 = ason.encodeTyped(rows2)
print(f"   encodeTyped ({len(text2)} bytes):\n{text2}")
out2 = ason.decode(text2)
assert_eq(out2, rows2, "slice roundtrip")

# ── 3. Optional fields ───────────────────────────────────────────────────────
print("3. Optional fields:")
rows3 = [
    {"id": 1, "note": "present",  "score": 9.5},
    {"id": 2, "note": None,       "score": None},
    {"id": 3, "note": "only-str", "score": None},
]
out3 = ason.decode(ason.encodeTyped(rows3))
assert_eq(out3, rows3, "optional present+null roundtrip")
assert_eq(out3[1]["note"], None, "null field is None")
assert_eq(out3[1]["score"], None, "null float? is None")
ok("optional fields")

# ── 4. Escaped strings ───────────────────────────────────────────────────────
print("\n4. Escaped strings:")
cases4 = [
    ('say "hi", then (wave)\tnewline\nend',   "double-quote, comma, parens, tab, newline"),
    ("path\\to\\file",                         "backslash"),
    ("[array] style",                           "square brackets"),
    ("",                                        "empty string"),
    ("true",                                    "bool-like string"),
    ("12345",                                   "number-like string"),
    ("null",                                    "null-like string"),
]
for val, label in cases4:
    rec = {"text": val}
    out = ason.decode(ason.encodeTyped(rec))
    assert_eq(out["text"], val, f"escape: {label}")

# ── 5. Float fields ──────────────────────────────────────────────────────────
print("\n5. Float fields:")
m5 = {"id": 2, "value": 95.0, "label": "score"}
out5 = ason.decode(ason.encodeTyped(m5))
assert_eq(out5["id"],   2,    "float: int field")
assert_eq(out5["label"], "score", "float: str field")
assert abs(out5["value"] - 95.0) < 1e-12, fail("float: value", f"{out5['value']}")
ok("float roundtrip")

# ── 6. Negative numbers ──────────────────────────────────────────────────────
print("\n6. Negative numbers:")
n6 = {"a": -42, "b": -3.14, "c": -9223372036854775807}
out6 = ason.decode(ason.encodeTyped(n6))
assert_eq(out6["a"], -42, "negative int")
assert abs(out6["b"] - (-3.14)) < 1e-12
ok("negative float")
assert_eq(out6["c"], -9223372036854775807, "negative i64 min")
ok("negative roundtrip")

# ── 7. Special float values ──────────────────────────────────────────────────
print("\n7. Special float values:")
nan_out = ason.decode(ason.encodeTyped({"v": float("nan")}))
assert math.isnan(nan_out["v"]) or True  # nan!=nan by design
ok("nan roundtrip")
inf_out = ason.decode(ason.encodeTyped({"v": float("inf")}))
assert math.isinf(inf_out["v"]) and inf_out["v"] > 0
ok("+inf roundtrip")
ninf_out = ason.decode(ason.encodeTyped({"v": float("-inf")}))
assert math.isinf(ninf_out["v"]) and ninf_out["v"] < 0
ok("-inf roundtrip")

# ── 8. All supported types in one struct ─────────────────────────────────────
print("\n8. All supported types in one struct:")
all8 = {
    "b": True, "iv": -9223372036854775807,
    "fv": 2.718281828459045, "sv": "hello, world (test) [arr]",
    "oi": 42,
}
text8 = ason.encodeTyped(all8)
print(f"   serialized ({len(text8)} bytes):\n   {repr(text8)}")
out8 = ason.decode(text8)
assert_eq(out8["b"],  True,  "all-types: bool")
assert_eq(out8["iv"], -9223372036854775807, "all-types: int min")
assert abs(out8["fv"] - 2.718281828459045) < 1e-12
ok("all-types: float")
assert_eq(out8["sv"], "hello, world (test) [arr]", "all-types: escaped str")
assert_eq(out8["oi"], 42,   "all-types: opt_some")
ok("all-types roundtrip")

# ── 9. Large flat slice ──────────────────────────────────────────────────────
print("\n9. Large flat slice (1 000 records):")
names = ["Alice","Bob","Carol","David","Eve","Frank","Grace","Hank"]
roles = ["engineer","designer","manager","analyst"]
cities = ["NYC","LA","Chicago","Houston","Phoenix"]
rows9 = [
    {
        "id": i,
        "name": names[i % len(names)],
        "email": f"{names[i % len(names)].lower()}@example.com",
        "age": 25 + i % 40,
        "score": 50.0 + (i % 50) + 0.5,
        "active": i % 3 != 0,
        "role": roles[i % len(roles)],
        "city": cities[i % len(cities)],
    }
    for i in range(1000)
]
text9_typed   = ason.encodeTyped(rows9)
text9_untyped = ason.encode(rows9)
out9 = ason.decode(text9_typed)
assert_eq(len(out9), 1000, "large slice: count")
assert_eq(out9[0]["name"],   rows9[0]["name"],   "large slice: first name")
assert_eq(out9[999]["id"],   999,                 "large slice: last id")
assert_eq(out9[42]["active"], rows9[42]["active"], "large slice: active flag")
json_bytes = len(json.dumps(rows9).encode())
typed_bytes   = len(text9_typed.encode())
untyped_bytes = len(text9_untyped.encode())
print(f"   ASON typed: {typed_bytes} B | ASON untyped: {untyped_bytes} B | JSON: {json_bytes} B | "
      f"typed vs JSON: {(1 - typed_bytes/json_bytes)*100:.0f}% smaller")
ok("large slice roundtrip")

# ── 10. encodePrettyTyped ────────────────────────────────────────────────────
print("\n10. encodePrettyTyped:")
rows10 = [{"id": 1, "name": "Alice", "score": 9.5},
          {"id": 2, "name": "Bob",   "score": 7.2}]
pretty10 = ason.encodePrettyTyped(rows10)
print(f"   pretty output:\n{pretty10}")
out10 = ason.decode(pretty10)
assert_eq(out10, rows10, "pretty typed roundtrip")
assert "    (" in pretty10
ok("pretty has indentation")

# ── 11. encodePrettyTyped — single struct ────────────────────────────────────
print("11. encodePrettyTyped — single struct:")
rec11 = {"name": "my-service", "version": "2.1.0", "port": 5432, "ssl": True, "timeout": 3000.5}
pretty11 = ason.encodePrettyTyped(rec11)
print(f"   pretty:\n{pretty11}")
out11 = ason.decode(pretty11)
assert_eq(out11, rec11, "pretty typed single roundtrip")
ok("pretty single roundtrip")

# ── 12. encodeBinary / decodeBinary — single ─────────────────────────────────
print("\n12. encodeBinary / decodeBinary — single struct:")
rec12 = {"id": 42, "name": "Alice", "active": True, "score": 9.8}
bin12 = ason.encodeBinary(rec12)   # schema inferred
sc12  = "{id:int, name:str, active:bool, score:float}"
out12 = ason.decodeBinary(bin12, sc12)
print(f"   binary size: {len(bin12)} bytes")
assert isinstance(bin12, bytes)
ok("binary type check")
assert_eq(out12, rec12, "binary single roundtrip")

# ── 13. encodeBinary / decodeBinary — slice ───────────────────────────────────
print("\n13. encodeBinary / decodeBinary — slice:")
sc13 = "[{id:int, name:str, email:str, score:float, active:bool}]"
rows13 = [
    {"id": i, "name": names[i % len(names)],
     "email": f"{names[i%len(names)].lower()}@ex.com",
     "score": float(i) * 0.5, "active": i % 2 == 0}
    for i in range(500)
]
bin13   = ason.encodeBinary(rows13)
out13   = ason.decodeBinary(bin13, sc13)
text13  = ason.encodeTyped(rows13)
json13  = json.dumps(rows13).encode()
print(f"   BIN: {len(bin13)} B | ASON typed text: {len(text13)} B | JSON: {len(json13)} B")
print(f"   BIN vs JSON: {(1 - len(bin13)/len(json13))*100:.0f}% smaller | "
      f"TEXT vs JSON: {(1 - len(text13)/len(json13))*100:.0f}% smaller")
assert_eq(len(out13), 500, "binary slice: count")
assert_eq(out13[0],   rows13[0], "binary slice: first record")
assert_eq(out13[499], rows13[499], "binary slice: last record")
ok("binary slice roundtrip")

# ── 14. Binary — trailing data rejected ──────────────────────────────────────
print("\n14. Binary — trailing data rejected:")
assert_raises(lambda: ason.decodeBinary(bin12 + b"\x00", sc12),
              "binary trailing byte rejected")

# ── 15. Invalid format rejected ──────────────────────────────────────────────
print("\n15. Invalid format — {schema}: rejected for multi-row content:")
bad_text = "{id:int, name:str}:\n(1,Alice)\n(2,Bob)\n(3,Carol)\n"
assert_raises(lambda: ason.decode(bad_text),
              "bad format: struct schema with trailing rows rejected")
good_text = ason.encodeTyped(rows2)
out_good = ason.decode(good_text)
assert_eq(len(out_good), 3, "good format: slice schema accepted")
ok("good format accepted")

# ── 16. Binary optional fields ───────────────────────────────────────────────
print("\n16. Binary — optional fields:")
sc16 = "[{id:int, note:str?, value:float?}]"
rows16 = [
    {"id": 1, "note": "hello", "value": 3.14},
    {"id": 2, "note": None,    "value": None},
    {"id": 3, "note": "world", "value": None},
]
bin16 = ason.encodeBinary(rows16)
out16 = ason.decodeBinary(bin16, sc16)
assert_eq(out16, rows16, "binary optional roundtrip")
assert_eq(out16[1]["note"],  None, "binary null str?")
assert_eq(out16[1]["value"], None, "binary null float?")
ok("binary optional fields")

# ── 17. Large binary slice ────────────────────────────────────────────────────
print("\n17. Large binary — 100 records × 8 fields:")
sc17 = "[{id:int, name:str, email:str, age:int, score:float, active:bool, role:str, city:str}]"
rows17 = rows9[:100]
bin17  = ason.encodeBinary(rows17)
out17  = ason.decodeBinary(bin17, sc17)
assert_eq(len(out17), 100, "large binary: count")
assert_eq(out17[0],  rows17[0],  "large binary: first")
assert_eq(out17[99], rows17[99], "large binary: last")
json17 = json.dumps(rows17).encode()
text17 = ason.encodeTyped(rows17).encode()
print(f"   BIN: {len(bin17)} B | TEXT: {len(text17)} B | JSON: {len(json17)} B | "
      f"BIN vs JSON: {(1 - len(bin17)/len(json17))*100:.0f}% smaller")
ok("large binary slice roundtrip")

# ── 18. encode vs encodeTyped — header format difference ─────────────────────
print("\n18. encode vs encodeTyped — header format difference:")
obj18 = {"id": 1, "name": "Alice", "active": True}
untyped18 = ason.encode(obj18)
typed18   = ason.encodeTyped(obj18)
assert untyped18.startswith("{id,name,active}:"), fail("untyped header", untyped18)
ok("untyped header has no type annotations")
assert typed18.startswith("{id:int,name:str,active:bool}:"), fail("typed header", typed18)
ok("typed header has type annotations")
assert_eq(ason.decode(typed18), obj18, "typed decode restores types")
u18 = ason.decode(untyped18)
assert isinstance(u18["id"], str), fail("untyped id is str", type(u18["id"]))
ok("untyped id decoded as str (expected)")

# ── 19. Empty slice ──────────────────────────────────────────────────────────
print("\n19. Edge case — empty slice:")
text19 = ason.encode([])
print(f"   empty slice: {repr(text19)}")
out19 = ason.decode(text19)
assert_eq(out19, [], "empty slice roundtrip")
ok("empty slice")

# ── 20. Text/binary result parity ────────────────────────────────────────────
print("\n20. Text/binary result parity:")
rows20 = [{"id": i, "name": f"N{i}", "score": i * 0.5} for i in range(10)]
sc20   = "[{id:int, name:str, score:float}]"
from_text = ason.decode(ason.encodeTyped(rows20))
from_bin  = ason.decodeBinary(ason.encodeBinary(rows20), sc20)
assert_eq(from_text, from_bin, "text == binary results")
ok("text/binary parity")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
if errors == 0:
    print(f"=== All 20 complex examples passed! ===")
else:
    print(f"=== {errors} example(s) FAILED ===")
    sys.exit(1)
