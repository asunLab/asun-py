from typing import Any

JsonObject = dict[str, Any]
AsonResult = JsonObject | list[JsonObject]

def encode(obj: JsonObject | list[JsonObject]) -> str:
    """Encode to ASON text with inferred *untyped* schema.

    The schema header contains no type annotations, e.g. ``{id,name,active}``.
    This produces the shortest output.

    When decoded with ``decode()``, all field values are returned as **strings**
    because the untyped schema carries no type information.
    Use ``encodeTyped()`` when you need a full-fidelity round-trip.

    Example::

        encode({"id": 1, "name": "Alice"})
        # → '{id,name}:\\n(1,Alice)\\n'
    """
    ...

def encodeTyped(obj: JsonObject | list[JsonObject]) -> str:
    """Encode to ASON text with inferred *typed* schema.

    The schema header includes type annotations, e.g. ``{id:int,name:str,active:bool}``.
    Type inference rules:
        - ``bool``   → ``bool``
        - ``int``    → ``int``
        - ``float``  → ``float``
        - ``str``    → ``str``
        - ``None``   → base type promoted to optional (e.g. ``str?``, ``int?``)
    When multiple rows are given, types are merged across all rows:
    a field that is non-``None`` in row 0 but ``None`` in row N is promoted to optional.

    Use this function for type-preserving round-trips.

    Example::

        encodeTyped({"id": 1, "name": "Alice", "active": True})
        # → '{id:int,name:str,active:bool}:\\n(1,Alice,true)\\n'
    """
    ...

def encodePretty(obj: JsonObject | list[JsonObject]) -> str:
    """Encode to pretty-printed ASON text with inferred *untyped* schema.

    Equivalent to ``encode()`` with indented tuple rows.
    """
    ...

def encodePrettyTyped(obj: JsonObject | list[JsonObject]) -> str:
    """Encode to pretty-printed ASON text with inferred *typed* schema.

    Equivalent to ``encodeTyped()`` with indented tuple rows.
    """
    ...

def decode(text: str) -> AsonResult:
    """Decode ASON text to ``dict`` or ``list[dict]``.

    The schema is embedded in the text itself (produced by any of the encode
    functions).  Both typed and untyped schemas are supported:

    - **Typed schema** (e.g. ``{id:int,name:str}``): field values are returned
      with their proper Python types (``int``, ``float``, ``bool``, ``str``,
      ``None``).
    - **Untyped schema** (e.g. ``{id,name}``): all field values are returned
      as ``str``.

    Example::

        decode('{id:int,name:str}:\\n(1,Alice)\\n')   # → {'id': 1, 'name': 'Alice'}
        decode('{id,name}:\\n(1,Alice)\\n')            # → {'id': '1', 'name': 'Alice'}
    """
    ...

def encodeBinary(obj: JsonObject | list[JsonObject]) -> bytes:
    """Encode to ASON binary format.

    Schema is inferred internally from the object — no schema argument needed.
    The resulting bytes are byte-identical to ason-rs and ason-go binary output.

    Example::

        data = encodeBinary({"id": 1, "name": "Alice"})
    """
    ...

def decodeBinary(data: bytes, schema: str) -> AsonResult:
    """Decode ASON binary bytes.

    ``schema`` is **required** because the binary wire format carries no embedded
    type information.

    Example::

        decodeBinary(data, '{id:int, name:str}')
        decodeBinary(data, '[{id:int, name:str, score:float}]')
    """
    ...
