"""Tests for the ason C++ pybind11 extension.

Build first:
    bash build.sh          # or: make
Then run:
    python3 -m pytest tests/ -v
"""

import sys
import os
import struct
import math
import pytest

# Allow importing from the parent directory (where the .so lives)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ason


# ---------------------------------------------------------------------------
# 1.  encode  /  decode  (text round-trip)
# ---------------------------------------------------------------------------

class TestEncodeDecodeSingle:
    def test_basic_int_str(self):
        rec = {"id": 1, "name": "Alice"}
        text = ason.encode(rec, "{id:int, name:str}")
        out = ason.decode(text)
        assert out == rec

    def test_float_field(self):
        rec = {"id": 1, "value": 3.14}
        text = ason.encode(rec, "{id:int, value:float}")
        out = ason.decode(text)
        assert out["id"] == 1
        assert abs(out["value"] - 3.14) < 1e-9

    def test_bool_field(self):
        rec = {"active": True, "name": "Bob"}
        text = ason.encode(rec, "{active:bool, name:str}")
        out = ason.decode(text)
        assert out == rec

    def test_optional_present(self):
        rec = {"id": 7, "note": "hi"}
        text = ason.encode(rec, "{id:int, note:str?}")
        out = ason.decode(text)
        assert out == rec

    def test_optional_null(self):
        rec = {"id": 7, "note": None}
        text = ason.encode(rec, "{id:int, note:str?}")
        out = ason.decode(text)
        assert out == rec

    def test_negative_int(self):
        rec = {"x": -42}
        text = ason.encode(rec, "{x:int}")
        assert ason.decode(text) == rec

    def test_trailing_rejected(self):
        text = "{id:int, name:str}:\n(1,Alice)\n(2,Bob)\n"
        with pytest.raises(ason.AsonError):
            ason.decode(text)


class TestEncodeDecodeSlice:
    SCHEMA = "[{id:int, name:str}]"

    def test_empty_slice(self):
        text = ason.encode([], self.SCHEMA)
        out = ason.decode(text)
        assert out == []

    def test_single_elem(self):
        rows = [{"id": 1, "name": "Alice"}]
        out = ason.decode(ason.encode(rows, self.SCHEMA))
        assert out == rows

    def test_multi_elem(self):
        rows = [{"id": i, "name": f"user{i}"} for i in range(50)]
        out = ason.decode(ason.encode(rows, self.SCHEMA))
        assert out == rows

    def test_bad_format_no_brackets(self):
        """Struct schema (no []) must be rejected when decoding multi-row content."""
        text = "{id:int, name:str}:\n(1,Alice),(2,Bob),(3,Carol)\n"
        with pytest.raises(ason.AsonError):
            ason.decode(text)

    def test_float_slice(self):
        rows = [{"x": 1.5, "y": -2.5}, {"x": 0.0, "y": 100.0}]
        out = ason.decode(ason.encode(rows, "[{x:float, y:float}]"))
        for a, b in zip(rows, out):
            assert abs(a["x"] - b["x"]) < 1e-9
            assert abs(a["y"] - b["y"]) < 1e-9


# ---------------------------------------------------------------------------
# 2.  encodePretty  /  decode  (pretty round-trip)
# ---------------------------------------------------------------------------

class TestEncodePretty:
    def test_single_roundtrip(self):
        rec = {"id": 1, "name": "Alice"}
        pretty = ason.encodePretty(rec, "{id:int, name:str}")
        assert "    (" in pretty          # indented tuple
        out = ason.decode(pretty)
        assert out == rec

    def test_slice_roundtrip(self):
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        pretty = ason.encodePretty(rows, "[{id:int, name:str}]")
        assert "    (" in pretty
        out = ason.decode(pretty)
        assert out == rows

    def test_pretty_typed_roundtrip(self):
        rows = [{"id": i, "score": i * 1.5, "active": (i % 2 == 0)}
                for i in range(10)]
        pretty = ason.encodePretty(rows, "[{id:int, score:float, active:bool}]")
        out = ason.decode(pretty)
        assert len(out) == 10
        for r, o in zip(rows, out):
            assert r["id"] == o["id"]
            assert abs(r["score"] - o["score"]) < 1e-9
            assert r["active"] == o["active"]

    def test_pretty_large_slice(self):
        rows = [{"id": i, "name": f"item{i}", "v": float(i)} for i in range(100)]
        pretty = ason.encodePretty(rows, "[{id:int, name:str, v:float}]")
        out = ason.decode(pretty)
        assert len(out) == 100
        assert out[99]["id"] == 99

    def test_pretty_optional_roundtrip(self):
        rows = [{"id": 1, "note": "hi"}, {"id": 2, "note": None}]
        pretty = ason.encodePretty(rows, "[{id:int, note:str?}]")
        out = ason.decode(pretty)
        assert out == rows


# ---------------------------------------------------------------------------
# 3.  encodeBinary  /  decodeBinary  (binary round-trip)
# ---------------------------------------------------------------------------

class TestBinaryRoundtrip:
    def test_single_int_str(self):
        rec = {"id": 42, "name": "Alice"}
        data = ason.encodeBinary(rec, "{id:int, name:str}")
        out = ason.decodeBinary(data, "{id:int, name:str}")
        assert out == rec

    def test_single_float_bool(self):
        rec = {"score": 99.5, "active": True}
        data = ason.encodeBinary(rec, "{score:float, active:bool}")
        out = ason.decodeBinary(data, "{score:float, active:bool}")
        assert abs(out["score"] - 99.5) < 1e-12
        assert out["active"] is True

    def test_slice_roundtrip(self):
        rows = [{"id": i, "name": f"user{i}"} for i in range(20)]
        schema = "[{id:int, name:str}]"
        data = ason.encodeBinary(rows, schema)
        out = ason.decodeBinary(data, schema)
        assert out == rows

    def test_optional_present_binary(self):
        rec = {"id": 1, "tag": "rust"}
        data = ason.encodeBinary(rec, "{id:int, tag:str?}")
        out = ason.decodeBinary(data, "{id:int, tag:str?}")
        assert out == rec

    def test_optional_null_binary(self):
        rec = {"id": 1, "tag": None}
        data = ason.encodeBinary(rec, "{id:int, tag:str?}")
        out = ason.decodeBinary(data, "{id:int, tag:str?}")
        assert out == rec

    def test_binary_is_bytes(self):
        rec = {"x": 1}
        data = ason.encodeBinary(rec, "{x:int}")
        assert isinstance(data, bytes)

    def test_binary_int_encoding(self):
        """int must be encoded as 8 bytes little-endian i64."""
        rec = {"x": 256}
        data = ason.encodeBinary(rec, "{x:int}")
        v = struct.unpack_from("<q", data, 0)[0]
        assert v == 256

    def test_binary_trailing_rejected(self):
        rec = {"id": 1, "name": "Alice"}
        data = ason.encodeBinary(rec, "{id:int, name:str}")
        with pytest.raises(ason.AsonError):
            ason.decodeBinary(data + b"\x00", "{id:int, name:str}")

    def test_large_slice_binary(self):
        rows = [{"id": i, "v": float(i)} for i in range(500)]
        schema = "[{id:int, v:float}]"
        data = ason.encodeBinary(rows, schema)
        out = ason.decodeBinary(data, schema)
        assert len(out) == 500
        assert out[499]["id"] == 499


# ---------------------------------------------------------------------------
# 4.  Schema parsing error cases
# ---------------------------------------------------------------------------

class TestSchemaErrors:
    def test_unknown_type(self):
        with pytest.raises(ason.AsonError):
            ason.encode({"x": 1}, "{x:double}")

    def test_missing_colon(self):
        with pytest.raises(ason.AsonError):
            ason.encode({"x": 1}, "{x int}")

    def test_empty_schema_body(self):
        # {} is technically valid (zero fields) — empty tuple
        text = ason.encode({}, "{}")
        out = ason.decode(text)
        assert out == {}


# ---------------------------------------------------------------------------
# 5.  String escaping
# ---------------------------------------------------------------------------

class TestStringEscaping:
    def test_comma_in_string(self):
        rec = {"s": "hello, world"}
        out = ason.decode(ason.encode(rec, "{s:str}"))
        assert out["s"] == "hello, world"

    def test_newline_in_string(self):
        rec = {"s": "line1\nline2"}
        out = ason.decode(ason.encode(rec, "{s:str}"))
        assert out["s"] == "line1\nline2"

    def test_tab_in_string(self):
        rec = {"s": "col1\tcol2"}
        out = ason.decode(ason.encode(rec, "{s:str}"))
        assert out["s"] == "col1\tcol2"

    def test_backslash_in_string(self):
        rec = {"s": "path\\to\\file"}
        out = ason.decode(ason.encode(rec, "{s:str}"))
        assert out["s"] == "path\\to\\file"

    def test_parens_in_string(self):
        rec = {"s": "(nested)"}
        out = ason.decode(ason.encode(rec, "{s:str}"))
        assert out["s"] == "(nested)"

    def test_empty_string(self):
        rec = {"s": ""}
        out = ason.decode(ason.encode(rec, "{s:str}"))
        assert out["s"] == ""


# ---------------------------------------------------------------------------
# 6.  Special float values
# ---------------------------------------------------------------------------

class TestSpecialFloats:
    def test_nan_roundtrip(self):
        rec = {"v": float("nan")}
        text = ason.encode(rec, "{v:float}")
        out = ason.decode(text)
        assert math.isnan(out["v"])

    def test_inf_roundtrip(self):
        rec = {"v": float("inf")}
        out = ason.decode(ason.encode(rec, "{v:float}"))
        assert math.isinf(out["v"]) and out["v"] > 0

    def test_neg_inf_roundtrip(self):
        rec = {"v": float("-inf")}
        out = ason.decode(ason.encode(rec, "{v:float}"))
        assert math.isinf(out["v"]) and out["v"] < 0
