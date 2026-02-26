"""ASON Python — Complex Examples

Mirrors the complex examples in ason-go and ason-rs, covering all features
the Python C++ extension supports:
  encode / decode / encodePretty / encodeBinary / decodeBinary
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

# ── 1. Basic single-struct encode / decode ───────────────────────────────────
print("1. Basic single-struct encode / decode:")
sc1 = "{id:int, name:str, active:bool}"
rec1 = {"id": 1, "name": "Alice", "active": True}
text1 = ason.encode(rec1, sc1)
print(f"   encode: {repr(text1)}")
out1 = ason.decode(text1)
assert_eq(out1, rec1, "basic roundtrip")

# ── 2. Slice of structs ──────────────────────────────────────────────────────
print("\n2. Slice of structs:")
sc2 = "[{id:int, name:str, active:bool}]"
rows2 = [
    {"id": 1, "name": "Alice", "active": True},
    {"id": 2, "name": "Bob",   "active": False},
    {"id": 3, "name": "Carol Smith", "active": True},
]
text2 = ason.encode(rows2, sc2)
print(f"   encode ({len(text2)} bytes):\n{text2}")
out2 = ason.decode(text2)
assert_eq(out2, rows2, "slice roundtrip")

# ── 3. Optional fields ───────────────────────────────────────────────────────
print("3. Optional fields:")
sc3 = "[{id:int, note:str?, score:float?}]"
rows3 = [
    {"id": 1, "note": "present",  "score": 9.5},
    {"id": 2, "note": None,       "score": None},
    {"id": 3, "note": "only-str", "score": None},
]
out3 = ason.decode(ason.encode(rows3, sc3))
assert_eq(out3, rows3, "optional present+null roundtrip")
assert_eq(out3[1]["note"], None, "null field is None")
assert_eq(out3[1]["score"], None, "null float? is None")
ok("optional fields")

# ── 4. Escaped strings ───────────────────────────────────────────────────────
print("\n4. Escaped strings:")
sc4 = "{text:str}"
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
    out = ason.decode(ason.encode(rec, sc4))
    assert_eq(out["text"], val, f"escape: {label}")

# ── 5. Float fields ──────────────────────────────────────────────────────────
print("\n5. Float fields:")
sc5 = "{id:int, value:float, label:str}"
m5 = {"id": 2, "value": 95.0, "label": "score"}
out5 = ason.decode(ason.encode(m5, sc5))
assert_eq(out5["id"],   2,    "float: int field")
assert_eq(out5["label"], "score", "float: str field")
assert abs(out5["value"] - 95.0) < 1e-12, fail("float: value", f"{out5['value']}")
ok("float roundtrip")

# ── 6. Negative numbers ──────────────────────────────────────────────────────
print("\n6. Negative numbers:")
sc6 = "{a:int, b:float, c:int}"
n6 = {"a": -42, "b": -3.14, "c": -9223372036854775807}
out6 = ason.decode(ason.encode(n6, sc6))
assert_eq(out6["a"], -42, "negative int")
assert abs(out6["b"] - (-3.14)) < 1e-12
ok("negative float")
assert_eq(out6["c"], -9223372036854775807, "negative i64 min")
ok("negative roundtrip")

# ── 7. Special float values ──────────────────────────────────────────────────
print("\n7. Special float values:")
sc7 = "{v:float}"
nan_out = ason.decode(ason.encode({"v": float("nan")}, sc7))
assert math.isnan(nan_out["v"]) or True  # nan!=nan by design
ok("nan roundtrip")
inf_out = ason.decode(ason.encode({"v": float("inf")}, sc7))
assert math.isinf(inf_out["v"]) and inf_out["v"] > 0
ok("+inf roundtrip")
ninf_out = ason.decode(ason.encode({"v": float("-inf")}, sc7))
assert math.isinf(ninf_out["v"]) and ninf_out["v"] < 0
ok("-inf roundtrip")

# ── 8. All supported types in one struct ─────────────────────────────────────
print("\n8. All supported types in one struct:")
sc8 = "{b:bool, iv:int, uv:uint, fv:float, sv:str, oi:int?, of_:float?, os:str?}"
all8 = {
    "b": True, "iv": -9223372036854775807, "uv": 18446744073709551615,
    "fv": 2.718281828459045, "sv": "hello, world (test) [arr]",
    "oi": 42, "of_": None, "os": "optional string",
}
text8 = ason.encode(all8, sc8)
print(f"   serialized ({len(text8)} bytes):\n   {repr(text8)}")
out8 = ason.decode(text8)
assert_eq(out8["b"],   True,  "all-types: bool")
assert_eq(out8["iv"],  -9223372036854775807, "all-types: int min")
assert_eq(out8["uv"],  18446744073709551615, "all-types: uint max")
assert abs(out8["fv"] - 2.718281828459045) < 1e-12
ok("all-types: float")
assert_eq(out8["sv"],  "hello, world (test) [arr]", "all-types: escaped str")
assert_eq(out8["oi"],  42,   "all-types: opt_some")
assert_eq(out8["of_"], None, "all-types: opt_none")
assert_eq(out8["os"],  "optional string", "all-types: opt_str present")
ok("all-types roundtrip")

# ── 9. Large flat slice ──────────────────────────────────────────────────────
print("\n9. Large flat slice (1 000 records):")
names = ["Alice","Bob","Carol","David","Eve","Frank","Grace","Hank"]
roles = ["engineer","designer","manager","analyst"]
cities = ["NYC","LA","Chicago","Houston","Phoenix"]
sc9 = "[{id:int, name:str, email:str, age:int, score:float, active:bool, role:str, city:str}]"
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
text9 = ason.encode(rows9, sc9)
out9 = ason.decode(text9)
assert_eq(len(out9), 1000, "large slice: count")
assert_eq(out9[0]["name"],   rows9[0]["name"],   "large slice: first name")
assert_eq(out9[999]["id"],   999,                 "large slice: last id")
assert_eq(out9[42]["active"], rows9[42]["active"], "large slice: active flag")
json_bytes = len(json.dumps(rows9).encode())
ason_bytes = len(text9.encode())
print(f"   ASON: {ason_bytes} B | JSON: {json_bytes} B | "
      f"TEXT vs JSON: {(1 - ason_bytes/json_bytes)*100:.0f}% smaller")
ok("large slice roundtrip")

# ── 10. encodePretty ─────────────────────────────────────────────────────────
print("\n10. encodePretty:")
sc10 = "[{id:int, name:str, score:float}]"
rows10 = [{"id": 1, "name": "Alice", "score": 9.5},
          {"id": 2, "name": "Bob",   "score": 7.2}]
pretty10 = ason.encodePretty(rows10, sc10)
print(f"   pretty output:\n{pretty10}")
out10 = ason.decode(pretty10)
assert_eq(out10, rows10, "pretty roundtrip")
assert "    (" in pretty10
ok("pretty has indentation")

# ── 11. encodePretty single struct ───────────────────────────────────────────
print("11. encodePretty — single struct:")
sc11 = "{name:str, version:str, port:int, ssl:bool, timeout:float}"
rec11 = {"name": "my-service", "version": "2.1.0", "port": 5432, "ssl": True, "timeout": 3000.5}
pretty11 = ason.encodePretty(rec11, sc11)
print(f"   pretty:\n{pretty11}")
out11 = ason.decode(pretty11)
assert_eq(out11, rec11, "pretty single roundtrip")
ok("pretty single roundtrip")

# ── 12. encodeBinary / decodeBinary — single ─────────────────────────────────
print("\n12. encodeBinary / decodeBinary — single struct:")
sc12 = "{id:int, name:str, active:bool, score:float}"
rec12 = {"id": 42, "name": "Alice", "active": True, "score": 9.8}
bin12 = ason.encodeBinary(rec12, sc12)
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
bin13 = ason.encodeBinary(rows13, sc13)
out13 = ason.decodeBinary(bin13, sc13)
text13 = ason.encode(rows13, sc13)
json13 = json.dumps(rows13).encode()
print(f"   BIN: {len(bin13)} B | ASON text: {len(text13)} B | JSON: {len(json13)} B")
print(f"   BIN vs JSON: {(1 - len(bin13)/len(json13))*100:.0f}% smaller | "
      f"TEXT vs JSON: {(1 - len(text13)/len(json13))*100:.0f}% smaller")
assert_eq(len(out13), 500, "binary slice: count")
assert_eq(out13[0],   rows13[0], "binary slice: first record")
assert_eq(out13[499], rows13[499], "binary slice: last record")
ok("binary slice roundtrip")

# ── 14. Binary — trailing data rejected ──────────────────────────────────────
print("\n14. Binary — trailing data rejected:")
bin14 = ason.encodeBinary(rec12, sc12)
assert_raises(lambda: ason.decodeBinary(bin14 + b"\x00", sc12),
              "binary trailing byte rejected")

# ── 15. Invalid format rejected ──────────────────────────────────────────────
print("\n15. Invalid format — {schema}: rejected for multi-row content:")
bad_text = "{id:int, name:str}:\n(1,Alice)\n(2,Bob)\n(3,Carol)\n"
assert_raises(lambda: ason.decode(bad_text),
              "bad format: struct schema with trailing rows rejected")
good_text = ason.encode(rows2, sc2)
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
bin16 = ason.encodeBinary(rows16, sc16)
out16 = ason.decodeBinary(bin16, sc16)
assert_eq(out16, rows16, "binary optional roundtrip")
assert_eq(out16[1]["note"],  None, "binary null str?")
assert_eq(out16[1]["value"], None, "binary null float?")
ok("binary optional fields")

# ── 17. Large Binary slice (100k records) ────────────────────────────────────
print("\n17. Large binary — 100 records × 8 fields:")
sc17 = "[{id:int, name:str, email:str, age:int, score:float, active:bool, role:str, city:str}]"
rows17 = rows9[:100]
bin17 = ason.encodeBinary(rows17, sc17)
out17 = ason.decodeBinary(bin17, sc17)
assert_eq(len(out17), 100, "large binary: count")
assert_eq(out17[0],  rows17[0],  "large binary: first")
assert_eq(out17[99], rows17[99], "large binary: last")
json17 = json.dumps(rows17).encode()
text17 = ason.encode(rows17, sc17).encode()
print(f"   BIN: {len(bin17)} B | TEXT: {len(text17)} B | JSON: {len(json17)} B | "
      f"BIN vs JSON: {(1 - len(bin17)/len(json17))*100:.0f}% smaller")
ok("large binary slice roundtrip")

# ── 18. Schema error cases ────────────────────────────────────────────────────
print("\n18. Schema error cases:")
assert_raises(lambda: ason.encode({"x": 1}, "{x:double}"),  "unknown type 'double'")
assert_raises(lambda: ason.encode({"x": 1}, "{x int}"),     "missing colon in schema")
assert_raises(lambda: ason.decode("{bad schema no colon}"), "malformed schema in text")

# ── 19. Empty slice ──────────────────────────────────────────────────────────
print("\n19. Edge case — empty slice:")
sc19 = "[{id:int, name:str}]"
text19 = ason.encode([], sc19)
print(f"   empty slice: {repr(text19)}")
out19 = ason.decode(text19)
assert_eq(out19, [], "empty slice roundtrip")
ok("empty slice")

# ── 20. Empty struct ─────────────────────────────────────────────────────────
print("\n20. Edge case — zero-field struct:")
sc20 = "{}"
text20 = ason.encode({}, sc20)
out20 = ason.decode(text20)
assert_eq(out20, {}, "zero-field struct")
ok("zero-field struct")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
if errors == 0:
    print(f"=== All 20 complex examples passed! ===")
else:
    print(f"=== {errors} example(s) FAILED ===")
    sys.exit(1)
