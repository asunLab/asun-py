"""Basic usage examples for the ason C++ pybind11 extension."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ason

# ── 1. encode / decode (text) ────────────────────────────────────────────────
user = {"id": 1, "name": "Alice", "active": True}
schema = "{id:int, name:str, active:bool}"

text = ason.encode(user, schema)
print("encode:", repr(text))

decoded = ason.decode(text)
print("decode:", decoded)

# ── 2. Slice encode / decode ─────────────────────────────────────────────────
users = [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
    {"id": 3, "name": "Carol"},
]
slice_schema = "[{id:int, name:str}]"
slice_text = ason.encode(users, slice_schema)
print("\nencode slice:\n" + slice_text)

decoded_users = ason.decode(slice_text)
print("decode slice:", decoded_users)

# ── 3. encodePretty ─────────────────────────────────────────────────────────
pretty = ason.encodePretty(users, slice_schema)
print("\nencodePretty:\n" + pretty)

# ── 4. encodeBinary / decodeBinary ──────────────────────────────────────────
data = ason.encodeBinary(users, slice_schema)
print(f"encodeBinary: {len(data)} bytes")

restored = ason.decodeBinary(data, slice_schema)
print("decodeBinary:", restored)

# ── 5. Optional fields ───────────────────────────────────────────────────────
rows = [{"id": 1, "note": "present"}, {"id": 2, "note": None}]
opt_schema = "[{id:int, note:str?}]"
opt_text = ason.encode(rows, opt_schema)
print("\noptional encode:", repr(opt_text))
print("optional decode:", ason.decode(opt_text))
