"""ASON Python — Comprehensive Benchmark (ason-py C++ extension vs json)

Benchmark semantics (inference-driven API):
    "ASON untyped serialize"  → ason.encode(obj)        — no schema arg; shorter output
    "ASON typed serialize"    → ason.encodeTyped(obj)   — typed header; decode restores types
    "ASON deserialize"        → ason.decode(text)        — reads embedded schema
    "BIN serialize"           → ason.encodeBinary(obj)  — schema inferred internally
    "BIN deserialize"         → ason.decodeBinary(data, schema) — schema required

Sections:
    Section 1: Flat struct (8 fields) — untyped / typed / JSON serialize
    Section 2: All-types struct (7 fields)
    Section 3: Binary vs typed text vs JSON
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

def print_row_triple(name,
                     json_ser_ms, untyped_ser_ms, typed_ser_ms,
                     json_de_ms,  untyped_de_ms,  typed_de_ms,
                     json_bytes,  untyped_bytes,   typed_bytes):
    print(f"  {name}")
    print(f"    Serialize:   JSON {json_ser_ms:8.2f}ms | untyped {untyped_ser_ms:8.2f}ms | typed {typed_ser_ms:8.2f}ms")
    print(f"    Deserialize: JSON {json_de_ms:8.2f}ms | untyped {untyped_de_ms:8.2f}ms | typed {typed_de_ms:8.2f}ms")
    saving_typed   = (1.0 - typed_bytes / json_bytes) * 100.0
    saving_untyped = (1.0 - untyped_bytes / json_bytes) * 100.0
    print(f"    Size:  JSON {json_bytes:7d} B | untyped {untyped_bytes:7d} B (saving {saving_untyped:.0f}%) | "
          f"typed {typed_bytes:7d} B (saving {saving_typed:.0f}%)")

def print_row_binary(name, bin_ser_ms, typed_ser_ms, json_ser_ms,
                           bin_de_ms,  typed_de_ms,  json_de_ms,
                           bin_b, typed_b, json_b):
    print(f"  {name}")
    print(f"    Size:  BIN {bin_b:7d} B | typed {typed_b:7d} B | JSON {json_b:7d} B")
    print(f"    Ser:   BIN {bin_ser_ms:7.2f}ms | typed {typed_ser_ms:7.2f}ms | JSON {json_ser_ms:7.2f}ms")
    print(f"    De:    BIN {bin_de_ms:7.2f}ms | typed {typed_de_ms:7.2f}ms | JSON {json_de_ms:7.2f}ms")
    js = json_ser_ms
    print(f"    vs JSON: BIN ser {js/bin_ser_ms:.1f}x | typed ser {js/typed_ser_ms:.1f}x | "
          f"BIN de {json_de_ms/bin_de_ms:.1f}x | typed de {json_de_ms/typed_de_ms:.1f}x")

# ─── data generators ────────────────────────────────────────────────────────

_NAMES  = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Hank"]
_ROLES  = ["engineer", "designer", "manager", "analyst"]
_CITIES = ["NYC", "LA", "Chicago", "Houston", "Phoenix"]

# Schema strings used ONLY for decodeBinary (binary decode requires explicit schema)
FLAT_SCHEMA_BIN = "[{id:int, name:str, email:str, age:int, score:float, active:bool, role:str, city:str}]"
ALL_SCHEMA_BIN  = "[{b:bool, iv:int, uv:uint, fv:float, sv:str, oi:int?, os:str?}]"

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
    users = make_users(count)

    json_str        = json.dumps(users)
    json_bytes_data = json_str.encode()
    untyped_str     = ason.encode(users)       # untyped, schema inferred
    typed_str       = ason.encodeTyped(users)  # typed, schema inferred

    json_ser_ns    = bench(lambda: json.dumps(users), iters)
    untyped_ser_ns = bench(lambda: ason.encode(users), iters)
    typed_ser_ns   = bench(lambda: ason.encodeTyped(users), iters)

    json_de_ns    = bench(lambda: json.loads(json_bytes_data), iters)
    untyped_de_ns = bench(lambda: ason.decode(untyped_str), iters)
    typed_de_ns   = bench(lambda: ason.decode(typed_str), iters)

    # verify typed round-trip
    out = ason.decode(typed_str)
    assert len(out) == count, f"flat {count}: decode mismatch"

    print_row_triple(
        f"Flat struct × {count} (8 fields)",
        ms(json_ser_ns), ms(untyped_ser_ns), ms(typed_ser_ns),
        ms(json_de_ns),  ms(untyped_de_ns),  ms(typed_de_ns),
        len(json_bytes_data), len(untyped_str.encode()), len(typed_str.encode()),
    )
    print()

# ─── bench all types ────────────────────────────────────────────────────────

def bench_all_types(count: int, iters: int):
    items = make_all_types(count)

    json_bytes_data = json.dumps(items).encode()
    untyped_str = ason.encode(items)
    typed_str   = ason.encodeTyped(items)

    json_ser_ns    = bench(lambda: json.dumps(items), iters)
    untyped_ser_ns = bench(lambda: ason.encode(items), iters)
    typed_ser_ns   = bench(lambda: ason.encodeTyped(items), iters)

    json_de_ns    = bench(lambda: json.loads(json_bytes_data), iters)
    untyped_de_ns = bench(lambda: ason.decode(untyped_str), iters)
    typed_de_ns   = bench(lambda: ason.decode(typed_str), iters)

    print_row_triple(
        f"All-types struct × {count} (7 fields, optional)",
        ms(json_ser_ns), ms(untyped_ser_ns), ms(typed_ser_ns),
        ms(json_de_ns),  ms(untyped_de_ns),  ms(typed_de_ns),
        len(json_bytes_data), len(untyped_str.encode()), len(typed_str.encode()),
    )
    print()

# ─── bench binary ───────────────────────────────────────────────────────────

def bench_binary(count: int, iters: int):
    users = make_users(count)

    # encodeBinary: schema inferred internally, no schema arg
    bin_data   = ason.encodeBinary(users)
    typed_str  = ason.encodeTyped(users)
    json_bytes = json.dumps(users).encode()

    bin_ser_ns   = bench(lambda: ason.encodeBinary(users), iters)
    typed_ser_ns = bench(lambda: ason.encodeTyped(users), iters)
    json_ser_ns  = bench(lambda: json.dumps(users), iters)

    # decodeBinary: schema required (binary wire has no embedded types)
    bin_de_ns   = bench(lambda: ason.decodeBinary(bin_data, FLAT_SCHEMA_BIN), iters)
    typed_de_ns = bench(lambda: ason.decode(typed_str), iters)
    json_de_ns  = bench(lambda: json.loads(json_bytes), iters)

    print_row_binary(
        f"{count} records × {iters} iters",
        ms(bin_ser_ns),  ms(typed_ser_ns),  ms(json_ser_ns),
        ms(bin_de_ns),   ms(typed_de_ns),   ms(json_de_ns),
        len(bin_data),   len(typed_str.encode()), len(json_bytes),
    )
    print()

# ─── bench single struct roundtrip ──────────────────────────────────────────

def bench_single_roundtrip(iters: int):
    user = {
        "id": 1, "name": "Alice", "email": "alice@example.com",
        "age": 30, "score": 95.5, "active": True, "role": "engineer", "city": "NYC",
    }
    # text round-trip: encodeTyped + decode (typed fidelity)
    ason_ns = bench(lambda: ason.decode(ason.encodeTyped(user)), iters)
    json_ns = bench(lambda: json.loads(json.dumps(user)), iters)
    return ms(ason_ns), ms(json_ns)

def bench_binary_single_roundtrip(iters: int):
    user = {
        "id": 1, "name": "Alice", "email": "alice@example.com",
        "age": 30, "score": 95.5, "active": True, "role": "engineer", "city": "NYC",
    }
    # single-struct schema for decodeBinary
    schema = "{id:int, name:str, email:str, age:int, score:float, active:bool, role:str, city:str}"
    bin_ns  = bench(lambda: ason.decodeBinary(ason.encodeBinary(user), schema), iters)
    ason_ns = bench(lambda: ason.decode(ason.encodeTyped(user)), iters)
    json_ns = bench(lambda: json.loads(json.dumps(user)), iters)
    return ms(bin_ns), ms(ason_ns), ms(json_ns)

# ─── main ────────────────────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        ASON Python (C++ ext) vs JSON — Benchmark            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\nSystem: {platform.system()} {platform.machine()} | Python {platform.python_version()}")
    iters = 100
    print(f"Iterations per test: {iters}")
    print()
    print("Benchmark semantics:")
    print("  untyped = encode(obj)       → schema inferred, no type annotations")
    print("  typed   = encodeTyped(obj)  → schema inferred with type annotations")
    print("  BIN ser = encodeBinary(obj) → schema inferred internally")
    print("  BIN de  = decodeBinary(data, schema) → schema required (binary has no type info)")
    print()

    # ── Section 1 ────────────────────────────────────────────────────────────
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  Section 1: Flat Struct (8 fields) — untyped / typed / JSON     │")
    print("└─────────────────────────────────────────────────────────────────┘")
    for count in [100, 500, 1000, 5000]:
        bench_flat(count, iters)

    # ── Section 2 ────────────────────────────────────────────────────────────
    print("┌──────────────────────────────────────────────────────────────────┐")
    print("│  Section 2: All-Types Struct (7 fields) — untyped / typed / JSON │")
    print("└──────────────────────────────────────────────────────────────────┘")
    for count in [100, 500]:
        bench_all_types(count, iters)

    # ── Section 3 ────────────────────────────────────────────────────────────
    print("┌──────────────────────────────────────────────────────────────────┐")
    print("│  Section 3: Binary Format (ASON-BIN) vs ASON typed text vs JSON  │")
    print("└──────────────────────────────────────────────────────────────────┘")
    for count in [100, 1000, 5000]:
        ii = 50 if count < 5000 else 10
        bench_binary(count, ii)

    # ── Section 4 ────────────────────────────────────────────────────────────
    print("┌──────────────────────────────────────────────┐")
    print("│  Section 4: Single Struct Roundtrip (10 000×) │")
    print("└──────────────────────────────────────────────┘")
    ason_ms, json_ms = bench_single_roundtrip(10_000)
    print(f"  ASON typed text: {ason_ms:6.2f}ms | JSON: {json_ms:6.2f}ms | "
          f"ratio {json_ms/ason_ms:.2f}x")
    bin_ms, ason_ms2, json_ms2 = bench_binary_single_roundtrip(10_000)
    print(f"  BIN:             {bin_ms:6.2f}ms | ASON: {ason_ms2:6.2f}ms | JSON: {json_ms2:6.2f}ms")
    print(f"  Speedup vs JSON: BIN {json_ms2/bin_ms:.1f}x | ASON typed {json_ms2/ason_ms2:.1f}x")
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
    users_1k    = make_users(1000)
    typed_str   = ason.encodeTyped(users_1k)
    untyped_str = ason.encode(users_1k)
    json_bytes  = json.dumps(users_1k).encode()
    iters6      = 100

    json_ser_ns    = bench(lambda: json.dumps(users_1k), iters6)
    typed_ser_ns   = bench(lambda: ason.encodeTyped(users_1k), iters6)
    untyped_ser_ns = bench(lambda: ason.encode(users_1k), iters6)
    json_de_ns     = bench(lambda: json.loads(json_bytes), iters6)
    typed_de_ns    = bench(lambda: ason.decode(typed_str), iters6)
    untyped_de_ns  = bench(lambda: ason.decode(untyped_str), iters6)

    total = 1000.0 * iters6
    json_ser_rps    = total / (json_ser_ns / 1e9)
    typed_ser_rps   = total / (typed_ser_ns / 1e9)
    untyped_ser_rps = total / (untyped_ser_ns / 1e9)
    json_de_rps     = total / (json_de_ns / 1e9)
    typed_de_rps    = total / (typed_de_ns / 1e9)
    untyped_de_rps  = total / (untyped_de_ns / 1e9)

    print(f"  Serialize throughput (1 000 records × {iters6} iters):")
    print(f"    JSON:          {json_ser_rps:>12,.0f} records/s")
    print(f"    ASON typed:    {typed_ser_rps:>12,.0f} records/s  ({typed_ser_rps/json_ser_rps:.2f}x vs JSON)")
    print(f"    ASON untyped:  {untyped_ser_rps:>12,.0f} records/s  ({untyped_ser_rps/json_ser_rps:.2f}x vs JSON)")
    print(f"  Deserialize throughput:")
    print(f"    JSON:          {json_de_rps:>12,.0f} records/s")
    print(f"    ASON typed:    {typed_de_rps:>12,.0f} records/s  ({typed_de_rps/json_de_rps:.2f}x vs JSON)")
    print(f"    ASON untyped:  {untyped_de_rps:>12,.0f} records/s  ({untyped_de_rps/json_de_rps:.2f}x vs JSON)")

    # ── Section 7: Binary throughput ─────────────────────────────────────────
    print()
    print("┌──────────────────────────────────────────────┐")
    print("│  Section 7: Binary Throughput Summary        │")
    print("└──────────────────────────────────────────────┘")
    bin_data   = ason.encodeBinary(users_1k)   # schema inferred internally
    bin_ser_ns = bench(lambda: ason.encodeBinary(users_1k), iters6)
    bin_de_ns  = bench(lambda: ason.decodeBinary(bin_data, FLAT_SCHEMA_BIN), iters6)

    bin_ser_rps = total / (bin_ser_ns / 1e9)
    bin_de_rps  = total / (bin_de_ns / 1e9)

    print(f"  Size comparison (1 000 records):")
    print(f"    ASON-BIN:  {fmt_bytes(len(bin_data))}")
    print(f"    ASON typed:{fmt_bytes(len(typed_str.encode()))}")
    print(f"    JSON:      {fmt_bytes(len(json_bytes))}")
    print(f"  Serialize throughput:")
    print(f"    BIN:         {bin_ser_rps:>12,.0f} records/s  ({bin_ser_rps/json_ser_rps:.2f}x vs JSON)")
    print(f"    ASON typed:  {typed_ser_rps:>12,.0f} records/s  ({typed_ser_rps/json_ser_rps:.2f}x vs JSON)")
    print(f"    JSON:        {json_ser_rps:>12,.0f} records/s")
    print(f"  Deserialize throughput:")
    print(f"    BIN:         {bin_de_rps:>12,.0f} records/s  ({bin_de_rps/json_de_rps:.2f}x vs JSON)")
    print(f"    ASON typed:  {typed_de_rps:>12,.0f} records/s  ({typed_de_rps/json_de_rps:.2f}x vs JSON)")
    print(f"    JSON:        {json_de_rps:>12,.0f} records/s")

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    Benchmark Complete                        ║")
    print("╚══════════════════════════════════════════════════════════════╝")

if __name__ == "__main__":
    main()
