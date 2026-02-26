"""ASON Python — Comprehensive Benchmark (ason-py C++ extension vs json)

Mirrors the benchmark structure in ason-go and ason-rs:
  Section 1: Flat struct (8 fields) × 100 / 500 / 1 000 / 5 000
  Section 2: All-types struct (8 fields) × 100 / 500
  Section 3: Binary vs text vs JSON
  Section 4: Single struct roundtrip (10 000×)
  Section 5: Large payload (10k records)
  Section 6: Throughput summary

Run after building the extension:
    bash build.sh   # or: make
    python3 examples/bench.py
"""

import sys, os, json, time, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ason

# ─── helpers ────────────────────────────────────────────────────────────────

def ms(ns: float) -> float:
    return ns / 1e6

def fmt_bytes(b: int) -> str:
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} MB"
    if b >= 1_024:
        return f"{b/1_024:.1f} KB"
    return f"{b} B"

def bench(fn, iters: int) -> float:
    """Return total wall-clock nanoseconds for `iters` calls to `fn()`."""
    start = time.perf_counter_ns()
    for _ in range(iters):
        fn()
    return time.perf_counter_ns() - start

def print_row(name, json_ser_ms, ason_ser_ms, json_de_ms, ason_de_ms,
              json_bytes, ason_bytes):
    ser_ratio = json_ser_ms / ason_ser_ms if ason_ser_ms > 0 else 0.0
    de_ratio  = json_de_ms  / ason_de_ms  if ason_de_ms  > 0 else 0.0
    saving    = (1.0 - ason_bytes / json_bytes) * 100.0
    ser_mark  = "✓ ASON faster" if ser_ratio >= 1.0 else ""
    de_mark   = "✓ ASON faster" if de_ratio  >= 1.0 else ""
    print(f"  {name}")
    print(f"    Serialize:   JSON {json_ser_ms:8.2f}ms | ASON {ason_ser_ms:8.2f}ms | "
          f"ratio {ser_ratio:.2f}x {ser_mark}")
    print(f"    Deserialize: JSON {json_de_ms:8.2f}ms | ASON {ason_de_ms:8.2f}ms | "
          f"ratio {de_ratio:.2f}x {de_mark}")
    print(f"    Size:        JSON {json_bytes:8d} B | ASON {ason_bytes:8d} B | "
          f"saving {saving:.0f}%")

# ─── data generators ────────────────────────────────────────────────────────

_NAMES  = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Hank"]
_ROLES  = ["engineer", "designer", "manager", "analyst"]
_CITIES = ["NYC", "LA", "Chicago", "Houston", "Phoenix"]

FLAT_SCHEMA      = "[{id:int, name:str, email:str, age:int, score:float, active:bool, role:str, city:str}]"
FLAT_SCHEMA_JSON = [{"id":0,"name":"","email":"","age":0,"score":0.0,"active":True,"role":"","city":""}]  # for type info only

def make_users(n: int) -> list:
    return [
        {
            "id":     i,
            "name":   _NAMES[i % len(_NAMES)],
            "email":  f"{_NAMES[i%len(_NAMES)].lower()}@example.com",
            "age":    25 + i % 40,
            "score":  50.0 + (i % 50) + 0.5,
            "active": i % 3 != 0,
            "role":   _ROLES[i % len(_ROLES)],
            "city":   _CITIES[i % len(_CITIES)],
        }
        for i in range(n)
    ]

ALL_SCHEMA = "[{b:bool, iv:int, uv:uint, fv:float, sv:str, oi:int?, os:str?}]"

def make_all_types(n: int) -> list:
    return [
        {
            "b":  i % 2 == 0,
            "iv": -(i * 100_000),
            "uv": i * 1_000_000_007,
            "fv": float(i) * 0.25 + 0.5,
            "sv": f"item_{i}",
            "oi": i if i % 2 == 0 else None,
            "os": None,
        }
        for i in range(n)
    ]

# ─── bench flat ─────────────────────────────────────────────────────────────

def bench_flat(count: int, iters: int):
    users  = make_users(count)
    schema = FLAT_SCHEMA

    json_ser_ns = bench(lambda: json.dumps(users), iters)
    ason_str = ason.encode(users, schema)
    ason_ser_ns = bench(lambda: ason.encode(users, schema), iters)

    json_bytes_data = json.dumps(users).encode()
    json_de_ns  = bench(lambda: json.loads(json_bytes_data), iters)
    ason_de_ns  = bench(lambda: ason.decode(ason_str), iters)

    # verify
    out = ason.decode(ason_str)
    assert len(out) == count, f"flat {count}: decode mismatch"

    print_row(
        f"Flat struct × {count} (8 fields)",
        ms(json_ser_ns), ms(ason_ser_ns),
        ms(json_de_ns),  ms(ason_de_ns),
        len(json_bytes_data), len(ason_str.encode()),
    )
    print()

# ─── bench all types ────────────────────────────────────────────────────────

def bench_all_types(count: int, iters: int):
    items  = make_all_types(count)
    schema = ALL_SCHEMA

    json_bytes_data = json.dumps(items).encode()
    json_ser_ns = bench(lambda: json.dumps(items), iters)
    ason_str    = ason.encode(items, schema)
    ason_ser_ns = bench(lambda: ason.encode(items, schema), iters)

    json_de_ns = bench(lambda: json.loads(json_bytes_data), iters)
    ason_de_ns = bench(lambda: ason.decode(ason_str), iters)

    print_row(
        f"All-types struct × {count} (7 fields, optional)",
        ms(json_ser_ns), ms(ason_ser_ns),
        ms(json_de_ns),  ms(ason_de_ns),
        len(json_bytes_data), len(ason_str.encode()),
    )
    print()

# ─── bench binary ───────────────────────────────────────────────────────────

def bench_binary(count: int, iters: int):
    users  = make_users(count)
    schema = FLAT_SCHEMA

    ason_str        = ason.encode(users, schema)
    bin_data        = ason.encodeBinary(users, schema)
    json_bytes_data = json.dumps(users).encode()

    bin_ser_ns  = bench(lambda: ason.encodeBinary(users, schema), iters)
    ason_ser_ns = bench(lambda: ason.encode(users, schema), iters)
    json_ser_ns = bench(lambda: json.dumps(users), iters)

    bin_de_ns   = bench(lambda: ason.decodeBinary(bin_data, schema), iters)
    ason_de_ns  = bench(lambda: ason.decode(ason_str), iters)
    json_de_ns  = bench(lambda: json.loads(json_bytes_data), iters)

    bin_b  = len(bin_data)
    ason_b = len(ason_str.encode())
    json_b = len(json_bytes_data)

    bin_ser_ms  = ms(bin_ser_ns)
    ason_ser_ms = ms(ason_ser_ns)
    json_ser_ms = ms(json_ser_ns)
    bin_de_ms   = ms(bin_de_ns)
    ason_de_ms  = ms(ason_de_ns)
    json_de_ms  = ms(json_de_ns)

    print(f"  {count} records × {iters} iters:")
    print(f"    Size: BIN {bin_b:6d} B | ASON {ason_b:6d} B | JSON {json_b:6d} B")
    print(f"    Ser:  BIN {bin_ser_ms:7.1f}ms | ASON {ason_ser_ms:7.1f}ms | JSON {json_ser_ms:7.1f}ms")
    print(f"    De:   BIN {bin_de_ms:7.1f}ms | ASON {ason_de_ms:7.1f}ms | JSON {json_de_ms:7.1f}ms")
    js = json_ser_ms
    print(f"    vs JSON: BIN ser {js/bin_ser_ms:.1f}x | ASON ser {js/ason_ser_ms:.1f}x | "
          f"BIN de {json_de_ms/bin_de_ms:.1f}x | ASON de {json_de_ms/ason_de_ms:.1f}x")
    print()

# ─── bench single struct roundtrip ──────────────────────────────────────────

def bench_single_roundtrip(iters: int):
    schema = "{id:int, name:str, email:str, age:int, score:float, active:bool, role:str, city:str}"
    user   = {
        "id": 1, "name": "Alice", "email": "alice@example.com",
        "age": 30, "score": 95.5, "active": True, "role": "engineer", "city": "NYC",
    }

    ason_ns = bench(lambda: ason.decode(ason.encode(user, schema)), iters)
    json_ns = bench(lambda: json.loads(json.dumps(user)), iters)
    return ms(ason_ns), ms(json_ns)

def bench_binary_single_roundtrip(iters: int):
    schema = "{id:int, name:str, email:str, age:int, score:float, active:bool, role:str, city:str}"
    user   = {
        "id": 1, "name": "Alice", "email": "alice@example.com",
        "age": 30, "score": 95.5, "active": True, "role": "engineer", "city": "NYC",
    }
    bin_ns  = bench(lambda: ason.decodeBinary(ason.encodeBinary(user, schema), schema), iters)
    ason_ns = bench(lambda: ason.decode(ason.encode(user, schema)), iters)
    json_ns = bench(lambda: json.loads(json.dumps(user)), iters)
    return ms(bin_ns), ms(ason_ns), ms(json_ns)

# ─── main ────────────────────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        ASON Python (C++ ext) vs JSON — Benchmark            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\nSystem: {platform.system()} {platform.machine()} | Python {platform.python_version()}")
    iters = 100
    print(f"Iterations per test: {iters}\n")

    # ── Section 1 ────────────────────────────────────────────────────────────
    print("┌─────────────────────────────────────────────┐")
    print("│  Section 1: Flat Struct (8 fields)          │")
    print("└─────────────────────────────────────────────┘")
    for count in [100, 500, 1000, 5000]:
        bench_flat(count, iters)

    # ── Section 2 ────────────────────────────────────────────────────────────
    print("┌──────────────────────────────────────────────┐")
    print("│  Section 2: All-Types Struct (7 fields)      │")
    print("└──────────────────────────────────────────────┘")
    for count in [100, 500]:
        bench_all_types(count, iters)

    # ── Section 3 ────────────────────────────────────────────────────────────
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Section 3: Binary Format (ASON-BIN) vs ASON text vs JSON    │")
    print("└──────────────────────────────────────────────────────────────┘")
    for count in [100, 1000, 5000]:
        ii = 50 if count < 5000 else 10
        bench_binary(count, ii)

    # ── Section 4 ────────────────────────────────────────────────────────────
    print("┌──────────────────────────────────────────────┐")
    print("│  Section 4: Single Struct Roundtrip (10 000×) │")
    print("└──────────────────────────────────────────────┘")
    ason_ms, json_ms = bench_single_roundtrip(10_000)
    print(f"  ASON text: {ason_ms:6.2f}ms | JSON: {json_ms:6.2f}ms | "
          f"ratio {json_ms/ason_ms:.2f}x")
    bin_ms, ason_ms2, json_ms2 = bench_binary_single_roundtrip(10_000)
    print(f"  BIN:       {bin_ms:6.2f}ms | ASON: {ason_ms2:6.2f}ms | JSON: {json_ms2:6.2f}ms")
    print(f"  Speedup vs JSON: BIN {json_ms2/bin_ms:.1f}x | ASON {json_ms2/ason_ms2:.1f}x")
    print()

    # ── Section 5 ────────────────────────────────────────────────────────────
    print("┌──────────────────────────────────────────────┐")
    print("│  Section 5: Large Payload (10k records)      │")
    print("└──────────────────────────────────────────────┘")
    bench_flat(10_000, 10)

    # ── Section 6 ────────────────────────────────────────────────────────────
    print("┌──────────────────────────────────────────────┐")
    print("│  Section 6: Throughput Summary               │")
    print("└──────────────────────────────────────────────┘")
    users_1k   = make_users(1000)
    schema     = FLAT_SCHEMA
    ason_str   = ason.encode(users_1k, schema)
    json_bytes = json.dumps(users_1k).encode()
    iters6     = 100

    json_ser_ns = bench(lambda: json.dumps(users_1k), iters6)
    ason_ser_ns = bench(lambda: ason.encode(users_1k, schema), iters6)
    json_de_ns  = bench(lambda: json.loads(json_bytes), iters6)
    ason_de_ns  = bench(lambda: ason.decode(ason_str), iters6)

    total = 1000.0 * iters6
    json_ser_rps = total / (json_ser_ns / 1e9)
    ason_ser_rps = total / (ason_ser_ns / 1e9)
    json_de_rps  = total / (json_de_ns  / 1e9)
    ason_de_rps  = total / (ason_de_ns  / 1e9)

    ser_mark = "✓ ASON faster" if ason_ser_rps > json_ser_rps else ""
    de_mark  = "✓ ASON faster" if ason_de_rps  > json_de_rps  else ""

    print(f"  Serialize throughput (1 000 records × {iters6} iters):")
    print(f"    JSON: {json_ser_rps:,.0f} records/s")
    print(f"    ASON: {ason_ser_rps:,.0f} records/s")
    print(f"    Speed: {ason_ser_rps/json_ser_rps:.2f}x {ser_mark}")
    print(f"  Deserialize throughput:")
    print(f"    JSON: {json_de_rps:,.0f} records/s")
    print(f"    ASON: {ason_de_rps:,.0f} records/s")
    print(f"    Speed: {ason_de_rps/json_de_rps:.2f}x {de_mark}")

    # ── Section 7: Binary throughput ─────────────────────────────────────────
    print()
    print("┌──────────────────────────────────────────────┐")
    print("│  Section 7: Binary Throughput Summary        │")
    print("└──────────────────────────────────────────────┘")
    bin_data   = ason.encodeBinary(users_1k, schema)
    bin_ser_ns = bench(lambda: ason.encodeBinary(users_1k, schema), iters6)
    bin_de_ns  = bench(lambda: ason.decodeBinary(bin_data, schema), iters6)

    bin_ser_rps = total / (bin_ser_ns / 1e9)
    bin_de_rps  = total / (bin_de_ns  / 1e9)

    print(f"  Size comparison (1 000 records):")
    print(f"    ASON-BIN: {fmt_bytes(len(bin_data))} | "
          f"ASON text: {fmt_bytes(len(ason_str.encode()))} | "
          f"JSON: {fmt_bytes(len(json_bytes))}")
    print(f"  Serialize throughput:")
    print(f"    BIN:  {bin_ser_rps:,.0f}  records/s  ({bin_ser_rps/json_ser_rps:.2f}x vs JSON)")
    print(f"    ASON: {ason_ser_rps:,.0f} records/s  ({ason_ser_rps/json_ser_rps:.2f}x vs JSON)")
    print(f"    JSON: {json_ser_rps:,.0f}  records/s")
    print(f"  Deserialize throughput:")
    print(f"    BIN:  {bin_de_rps:,.0f}  records/s  ({bin_de_rps/json_de_rps:.2f}x vs JSON)")
    print(f"    ASON: {ason_de_rps:,.0f} records/s  ({ason_de_rps/json_de_rps:.2f}x vs JSON)")
    print(f"    JSON: {json_de_rps:,.0f}  records/s")

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    Benchmark Complete                        ║")
    print("╚══════════════════════════════════════════════════════════════╝")

if __name__ == "__main__":
    main()
