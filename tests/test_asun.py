"""Tests for the asun C++ pybind11 extension (inference-driven v3).

Design note:
    encode(obj)      → untyped schema {id,name,active}:...  (all fields decode as str)
    encodeTyped(obj) → typed schema   {id@int,name@str,...}: (types preserved on decode)

    For a value-type round-trip, use encodeTyped + decode.
    encodePretty / encodePrettyTyped follow the same pattern.
    encodeBinary has schema inferred internally.
    decodeBinary still requires an explicit schema string.

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

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import asun


# ---------------------------------------------------------------------------
# 1.  encode / decode — schema header tests
# ---------------------------------------------------------------------------

class TestEncodeSchemaHeader:
    def test_encode_untyped_header(self):
        rec = {"id": 1, "name": "Alice"}
        text = asun.encode(rec)
        assert text.startswith("{id,name}:")

    def test_encode_typed_header(self):
        rec = {"id": 1, "name": "Alice"}
        text = asun.encodeTyped(rec)
        assert text.startswith("{id@int,name@str}:")

    def test_encode_slice_untyped_header(self):
        rows = [{"id": 1, "name": "Alice"}]
        text = asun.encode(rows)
        assert text.startswith("[{id,name}]:")

    def test_encode_slice_typed_header(self):
        rows = [{"id": 1, "name": "Alice"}]
        text = asun.encodeTyped(rows)
        assert text.startswith("[{id@int,name@str}]:")

    def test_empty_list_encodes(self):
        text = asun.encode([])
        out = asun.decode(text)
        assert out == []


# ---------------------------------------------------------------------------
# 2.  encodeTyped + decode — full value-type round-trips
# ---------------------------------------------------------------------------

class TestEncodeTypedRoundtrip:
    def test_basic_int_str(self):
        rec = {"id": 1, "name": "Alice"}
        assert asun.decode(asun.encodeTyped(rec)) == rec

    def test_float_field(self):
        rec = {"id": 1, "value": 3.14}
        out = asun.decode(asun.encodeTyped(rec))
        assert out["id"] == 1
        assert abs(out["value"] - 3.14) < 1e-9

    def test_bool_field(self):
        rec = {"active": True, "name": "Bob"}
        assert asun.decode(asun.encodeTyped(rec)) == rec

    def test_negative_int(self):
        rec = {"x": -42}
        assert asun.decode(asun.encodeTyped(rec)) == rec

    def test_slice_roundtrip(self):
        rows = [{"id": i, "name": f"user{i}"} for i in range(50)]
        assert asun.decode(asun.encodeTyped(rows)) == rows

    def test_float_slice(self):
        rows = [{"x": 1.5, "y": -2.5}, {"x": 0.0, "y": 100.0}]
        out = asun.decode(asun.encodeTyped(rows))
        for a, b in zip(rows, out):
            assert abs(a["x"] - b["x"]) < 1e-9
            assert abs(a["y"] - b["y"]) < 1e-9


# ---------------------------------------------------------------------------
# 3.  Type inference rules
# ---------------------------------------------------------------------------

class TestTypeInference:
    def test_int_inferred(self):
        text = asun.encodeTyped({"n": 42})
        assert "n@int" in text

    def test_float_inferred(self):
        text = asun.encodeTyped({"v": 3.14})
        assert "v@float" in text

    def test_bool_inferred(self):
        text = asun.encodeTyped({"f": False})
        assert "f@bool" in text

    def test_str_inferred(self):
        text = asun.encodeTyped({"s": "hello"})
        assert "s@str" in text

    def test_none_inferred_as_str_optional(self):
        text = asun.encodeTyped({"tag": None})
        assert "tag@str?" in text


# ---------------------------------------------------------------------------
# 4.  encodePretty / encodePrettyTyped / decode
# ---------------------------------------------------------------------------

class TestEncodePretty:
    def test_pretty_untyped_has_indent(self):
        rec = {"id": 1, "name": "Alice"}
        pretty = asun.encodePretty(rec)
        assert "    (" in pretty

    def test_pretty_typed_roundtrip_single(self):
        rec = {"id": 1, "name": "Alice"}
        pretty = asun.encodePrettyTyped(rec)
        assert asun.decode(pretty) == rec

    def test_pretty_typed_roundtrip_slice(self):
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        pretty = asun.encodePrettyTyped(rows)
        assert asun.decode(pretty) == rows

    def test_pretty_typed_full(self):
        rows = [{"id": i, "score": i * 1.5, "active": (i % 2 == 0)}
                for i in range(10)]
        out = asun.decode(asun.encodePrettyTyped(rows))
        assert len(out) == 10
        for r, o in zip(rows, out):
            assert r["id"] == o["id"]
            assert abs(r["score"] - o["score"]) < 1e-9
            assert r["active"] == o["active"]

    def test_pretty_large_slice(self):
        rows = [{"id": i, "name": f"item{i}", "v": float(i)} for i in range(100)]
        out = asun.decode(asun.encodePrettyTyped(rows))
        assert len(out) == 100
        assert out[99]["id"] == 99


# ---------------------------------------------------------------------------
# 5.  encodeBinary (schema-free) / decodeBinary (schema required)
# ---------------------------------------------------------------------------

class TestBinaryRoundtrip:
    def test_single_int_str(self):
        rec = {"id": 42, "name": "Alice"}
        data = asun.encodeBinary(rec)
        out = asun.decodeBinary(data, "{id@int, name@str}")
        assert out == rec

    def test_single_float_bool(self):
        rec = {"score": 99.5, "active": True}
        data = asun.encodeBinary(rec)
        out = asun.decodeBinary(data, "{score@float, active@bool}")
        assert abs(out["score"] - 99.5) < 1e-12
        assert out["active"] is True

    def test_slice_roundtrip(self):
        rows = [{"id": i, "name": f"user{i}"} for i in range(20)]
        data = asun.encodeBinary(rows)
        out = asun.decodeBinary(data, "[{id@int, name@str}]")
        assert out == rows

    def test_binary_is_bytes(self):
        data = asun.encodeBinary({"x": 1})
        assert isinstance(data, bytes)

    def test_binary_int_encoding(self):
        """int must be encoded as 8 bytes little-endian i64."""
        data = asun.encodeBinary({"x": 256})
        v = struct.unpack_from("<q", data, 0)[0]
        assert v == 256

    def test_binary_trailing_rejected(self):
        data = asun.encodeBinary({"id": 1, "name": "Alice"})
        with pytest.raises(asun.AsunError):
            asun.decodeBinary(data + b"\x00", "{id@int, name@str}")

    def test_large_slice_binary(self):
        rows = [{"id": i, "v": float(i)} for i in range(500)]
        data = asun.encodeBinary(rows)
        out = asun.decodeBinary(data, "[{id@int, v@float}]")
        assert len(out) == 500
        assert out[499]["id"] == 499

    def test_empty_slice_binary(self):
        data = asun.encodeBinary([])
        out = asun.decodeBinary(data, "[{id@int}]")
        assert out == []


# ---------------------------------------------------------------------------
# 6.  String escaping
# ---------------------------------------------------------------------------

class TestStringEscaping:
    def test_comma_in_string(self):
        rec = {"s": "hello, world"}
        assert asun.decode(asun.encodeTyped(rec))["s"] == "hello, world"

    def test_newline_in_string(self):
        rec = {"s": "line1\nline2"}
        assert asun.decode(asun.encodeTyped(rec))["s"] == "line1\nline2"

    def test_tab_in_string(self):
        rec = {"s": "col1\tcol2"}
        assert asun.decode(asun.encodeTyped(rec))["s"] == "col1\tcol2"

    def test_backslash_in_string(self):
        rec = {"s": "path\\to\\file"}
        assert asun.decode(asun.encodeTyped(rec))["s"] == "path\\to\\file"

    def test_parens_in_string(self):
        rec = {"s": "(nested)"}
        assert asun.decode(asun.encodeTyped(rec))["s"] == "(nested)"

    def test_empty_string(self):
        rec = {"s": ""}
        assert asun.decode(asun.encodeTyped(rec))["s"] == ""

    def test_at_string_roundtrip_all_apis(self):
        obj = {"s": "@Alice"}
        plain = asun.encode(obj)
        assert '"@Alice"' in plain
        assert asun.decode(plain) == obj
        assert asun.decode(asun.encodeTyped(obj)) == obj
        assert asun.decode(asun.encodePretty(obj)) == obj
        assert asun.decode(asun.encodePrettyTyped(obj)) == obj
        assert asun.decodeBinary(asun.encodeBinary(obj), '{s@str}') == obj

    def test_reject_invalid_schema_types(self):
        for text in [
            '{id@numx,name@str}:(1,Alice)',
            '{id@int,name@textx}:(1,Alice)',
            '{score@decimalx}:(3.5)',
            '{active@flagx}:(true)',
            '{tags@[textx]}:([Alice])',
        ]:
            with pytest.raises(Exception):
                asun.decode(text)


# ---------------------------------------------------------------------------
# 7.  Special float values
# ---------------------------------------------------------------------------

class TestSpecialFloats:
    def test_nan_roundtrip(self):
        rec = {"v": float("nan")}
        text = asun.encodeTyped(rec)
        out = asun.decode(text)
        assert math.isnan(out["v"])

    def test_inf_roundtrip(self):
        rec = {"v": float("inf")}
        out = asun.decode(asun.encodeTyped(rec))
        assert math.isinf(out["v"]) and out["v"] > 0

    def test_neg_inf_roundtrip(self):
        rec = {"v": float("-inf")}
        out = asun.decode(asun.encodeTyped(rec))
        assert math.isinf(out["v"]) and out["v"] < 0


# ---------------------------------------------------------------------------
# 8.  decode error cases
# ---------------------------------------------------------------------------

class TestDecodeErrors:
    def test_trailing_rows_rejected(self):
        text = "{id@int, name@str}:\n(1,Alice)\n(2,Bob)\n"
        with pytest.raises(asun.AsunError):
            asun.decode(text)

    def test_bad_format_multi_tuples_for_single(self):
        bad = "{id@int, name@str}:\n  (1, Alice),\n  (2, Bob),\n  (3, Carol)"
        with pytest.raises(asun.AsunError):
            asun.decode(bad)

    def test_bad_format_extra_tuples(self):
        with pytest.raises(asun.AsunError):
            asun.decode("{id@int,name@str}:(10,Dave),(11,Eve)")

    def test_legacy_map_syntax_rejected(self):
        with pytest.raises(asun.AsunError):
            asun.decode("{cfg@<str,str>}:(x)")

    def test_nested_structured_schema_rejected(self):
        with pytest.raises(asun.AsunError):
            asun.decode("{cfg@{name@str}}:(x)")

    def test_nested_structured_value_rejected(self):
        with pytest.raises(asun.AsunError):
            asun.encodeTyped({"cfg": {"name": "web"}})

    def test_unclosed_block_comment_rejected(self):
        with pytest.raises(asun.AsunError):
            asun.decode("/* broken {id@int,name@str}:(1,Alice)")


# ---------------------------------------------------------------------------
# 9.  Format validation
# ---------------------------------------------------------------------------

class TestFormatValidation:
    def test_good_array_multi(self):
        good = "[{id@int, name@str}]:\n  (1, Alice),\n  (2, Bob),\n  (3, Carol)"
        out = asun.decode(good)
        assert isinstance(out, list)
        assert len(out) == 3
        assert out[0] == {"id": 1, "name": "Alice"}

    def test_good_single_struct(self):
        out = asun.decode("{id@int,name@str}:(1,Alice)")
        assert out == {"id": 1, "name": "Alice"}

    def test_good_vec_single_item(self):
        out = asun.decode("[{id@int,name@str}]:(1,Alice)")
        assert isinstance(out, list)
        assert len(out) == 1
        assert out[0] == {"id": 1, "name": "Alice"}

    def test_encode_decode_consistency(self):
        rows = [{"id": 7, "name": "Carol"}]
        out = asun.decode(asun.encodeTyped(rows))
        assert out == rows

    def test_block_comments_before_and_between_tokens(self):
        text = '/* top */ {id@int, name@str, active@bool}: /* row */ (1, /* name */ Alice, true)'
        out = asun.decode(text)
        assert out == {"id": 1, "name": "Alice", "active": True}

    def test_block_comments_between_rows_in_slice(self):
        text = '/* users */ [{id@int,name@str}]: /* first */ (1,Alice), /* second */ (2,Bob)'
        out = asun.decode(text)
        assert out == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    def test_block_comment_after_plain_value_before_comma(self):
        text = '{id@int,name@str,active@bool}:(1,Alice /* name */,true)'
        out = asun.decode(text)
        assert out == {"id": 1, "name": "Alice", "active": True}

    def test_block_comments_inside_schema(self):
        text = '{id@int, /* label */ name@str, active@bool}:(1,Alice,true)'
        out = asun.decode(text)
        assert out == {"id": 1, "name": "Alice", "active": True}


# ---------------------------------------------------------------------------
# 10. Field names with special characters
# ---------------------------------------------------------------------------

class TestFieldNamesSpecialChars:
    def test_decode_plus_minus(self):
        out = asun.decode("{a+b@int, c-d@str}:(42,hello)")
        assert out["a+b"] == 42
        assert out["c-d"] == "hello"

    def test_decode_underscore(self):
        out = asun.decode("{user_name@str, is_active@bool}:(Alice,true)")
        assert out["user_name"] == "Alice"
        assert out["is_active"] is True

    def test_encode_decode_roundtrip_special(self):
        obj = {"user_name": "Alice", "is_active": True}
        out = asun.decode(asun.encodeTyped(obj))
        assert out == obj

    def test_quoted_schema_names_roundtrip_all_text_apis(self):
        obj = {"id uuid": 1, "65": "Alice", '{}[]@"': True}

        untyped = asun.encode(obj)
        assert untyped.startswith('{"id uuid","65","{}[]@\\""')
        assert asun.decode(untyped) == {"id uuid": 1, "65": "Alice", '{}[]@"': True}

        typed = asun.encodeTyped(obj)
        assert typed.startswith('{"id uuid"@int,"65"@str,"{}[]@\\""@bool}')
        assert asun.decode(typed) == obj

        pretty = asun.encodePretty(obj)
        assert asun.decode(pretty) == {"id uuid": 1, "65": "Alice", '{}[]@"': True}

        pretty_typed = asun.encodePrettyTyped(obj)
        assert asun.decode(pretty_typed) == obj

    def test_decode_explicit_quoted_schema_names(self):
        out = asun.decode('{"id uuid"@int,"65"@str,"{}[]@\\""@bool}:(1,Alice,true)')
        assert out == {"id uuid": 1, "65": "Alice", '{}[]@"': True}

    def test_binary_with_quoted_schema_names(self):
        obj = {"id uuid": 1, "65": "Alice", '{}[]@"': True}
        data = asun.encodeBinary(obj)
        out = asun.decodeBinary(data, '{"id uuid"@int,"65"@str,"{}[]@\\""@bool}')
        assert out == obj
