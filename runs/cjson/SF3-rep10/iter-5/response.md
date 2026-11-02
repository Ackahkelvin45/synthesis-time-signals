```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters that may appear raw inside a JSON string per the grammar.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
    min_codepoint=0x20,
)

# Raw control characters (allowed by this parser inside strings).
_control_chars = st.sampled_from(
    [chr(i) for i in range(0x00, 0x20)] + ["\x7f"]
)

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    # \uXXXX, sometimes a surrogate (lone or paired).
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        # lone high surrogate
        hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        return "\\u%04x" % hi
    if kind == 1:
        # lone low surrogate
        lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x" % lo
    if kind == 2:
        # valid surrogate pair
        hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x\\u%04x" % (hi, lo)
    if kind == 3:
        # uppercase hex, arbitrary code unit
        cu = draw(st.integers(min_value=0, max_value=0xFFFF))
        return "\\u%04X" % cu
    # arbitrary \uXXXX
    return "\\u" + "".join(draw(st.lists(_hex_digit, min_size=4, max_size=4)))


_simple_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

# A single "unit" inside a string body.
_string_unit = st.one_of(
    _simple_escapes,
    _unicode_escape(),
    _control_chars,
    st.just("\x00"),
    _safe_chars,
)

# String body: possibly empty, possibly long, possibly containing NULs.
_string_body = st.one_of(
    st.just(""),
    st.lists(_string_unit, min_size=1, max_size=12).map("".join),
    st.text(
        alphabet=st.characters(min_codepoint=0x20, blacklist_characters='"\\'),
        min_size=0,
        max_size=40,
    ),
)


@st.composite
def _string(draw):
    body = draw(_string_body)
    # Occasionally emit an unterminated string.
    if draw(st.integers(min_value=0, max_value=11)) == 0:
        return '"' + body
    return '"' + body + '"'


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    # leading zeros (accepted by this parser)
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
    # hex (accepted by this parser)
    st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda n: "0x%x" % n),
)

_frac_part = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
    st.just("."),  # trailing dot (accepted)
)

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=400).map(str),
    ).map("".join),
    st.just("e309"),
    st.just("e-309"),
    st.just("e999"),
)


@st.composite
def _number(draw):
    sign = draw(st.sampled_from(["", "-"]))
    intp = draw(_int_part)
    frac = draw(_frac_part)
    exp = draw(_exp_part)
    return sign + intp + frac + exp


# ---------------------------------------------------------------------------
# Malformed fragments (near-valid but broken)
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        "+1",
        "-",
        ".5",
        ".",
        "NaN",
        "Infinity",
        "-Infinity",
        "01",
        "1.",
        "1e",
        "1e+",
        "--1",
        "0x",
        "0xg",
        "'single'",
        "{'a': 1}",
        "{a: 1}",
        "[1,2,]",
        '{"a":1,}',
        '{"a" 1}',
        "{,}",
        "[,]",
        "[1,,2]",
        '{"a":}',
        '{"a"}',
        "{:1}",
        "tru",
        "fals",
        "nul",
        "True",
        "NULL",
        "\\u",
        '"\\u12"',
        '"\\x41"',
        '"unterminated',
        "{",
        "[",
        "}",
        "]",
        ":",
        ",",
        "",
        " ",
        "\x00",
    ]
)


# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the ~1000 nesting limit.
_depth_choices = st.one_of(
    st.integers(min_value=0, max_value=4),
    st.integers(min_value=5, max_value=50),
    st.integers(min_value=900, max_value=1002),
    st.integers(min_value=999, max_value=1001),
)


@st.composite
def _depth(draw):
    return draw(_depth_choices)


def _deep_wrap(inner, depth, opener, closer):
    """Wrap `inner` in `depth` nested openers/closers."""
    return opener * depth + inner + closer * depth


@st.composite
def _deep_array(draw):
    depth = draw(st.integers(min_value=900, max_value=1002))
    leaf = draw(st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])))
    return "[" * depth + leaf + "]" * depth


@st.composite
def _deep_object(draw):
    depth = draw(st.integers(min_value=900, max_value=1002))
    leaf = draw(st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])))
    return '{"k":' * depth + leaf + "}" * depth


# ---------------------------------------------------------------------------
# Non-recursive value productions (leaves).
# ---------------------------------------------------------------------------

_leaf = st.one_of(
    _string(),
    _number(),
    st.sampled_from(["true", "false", "null"]),
)


@st.composite
def _pair(draw):
    key = draw(_string())
    colon = draw(st.sampled_from([":", ": ", " :", " ", ""]))
    val = draw(_value())
    return key + colon + val


# ---------------------------------------------------------------------------
# Recursive value
# ---------------------------------------------------------------------------

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        # arrays
        st.lists(children, min_size=0, max_size=6).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        # arrays with whitespace
        st.lists(children, min_size=0, max_size=4).map(
            lambda xs: "[ " + " , ".join(xs) + " ]"
        ),
        # objects
        st.lists(
            st.tuples(_string(), children).map(lambda t: t[0] + ":" + t[1]),
            min_size=0,
            max_size=5,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
        # objects with duplicate keys
        st.tuples(
            _string(),
            children,
            _string(),
            children,
        ).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[2] + ":" + t[3] + "}"),
    ),
    max_leaves=40,
)


# ---------------------------------------------------------------------------
# Top-level strategy: valid-ish, deep, malformed, and combinations.
# ---------------------------------------------------------------------------

_valid_value = _value

_with_trailing = st.tuples(_value, st.sampled_from(["", " ", "\x00", "abc", " 1 2"])).map(
    lambda t: t[0] + t[1]
)

_with_bom = st.tuples(st.just("\ufeff"), _value).map(lambda t: t[0] + t[1])

_whitespace_wrapped = st.tuples(
    st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
    _value,
    st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
).map(lambda t: t[0] + t[1] + t[2])

_raw_bytes = st.one_of(
    st.text(min_size=0, max_size=30),
    st.lists(
        st.integers(min_value=0, max_value=0x10FFFF).filter(
            lambda c: not (0xD800 <= c <= 0xDFFF)
        ),
        min_size=0,
        max_size=20,
    ).map(lambda cs: "".join(chr(c) for c in cs)),
)

# Exercise the printer/compare code paths (print_value, print_string_ptr,
# print_number, print_object, cJSON_Compare) by feeding parsed values back
# through a serialize+compare round-trip style input.  We can't call the C
# library, but we can shape inputs that force the parser to build complete
# trees which, when serialized, hit those routines: full objects, arrays of
# objects, and structures with mixed key types / duplicate keys.
_roundtrip_structs = st.one_of(
    # object with many keys of varying shapes
    st.lists(
        st.tuples(_string(), _value).map(lambda t: t[0] + ":" + t[1]),
        min_size=1,
        max_size=8,
    ).map(lambda ps: "{" + ",".join(ps) + "}"),
    # array of objects
    st.lists(
        st.lists(
            st.tuples(_string(), _value).map(lambda t: t[0] + ":" + t[1]),
            min_size=0,
            max_size=4,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
        min_size=1,
        max_size=5,
    ).map(lambda xs: "[" + ",".join(xs) + "]"),
    # nested object in object (deep print_object)
    st.tuples(_value, _value).map(
        lambda t: '{"a":' + t[0] + ',"b":' + t[1] + "}"
    ),
    # array mixing numbers and strings (print_number + print_string_ptr)
    st.lists(
        st.one_of(_number(), _string()),
        min_size=1,
        max_size=8,
    ).map(lambda xs: "[" + ",".join(xs) + "]"),
)

# ---------------------------------------------------------------------------
# Round-trip / printer-focused generator.
#
# The coverage feedback shows cJSON_Compare, print_value, print_string_ptr,
# print_number, and print_object are never reached.  Those are only exercised
# when a *complete, valid* value is parsed into a tree and then serialized
# (and, for cJSON_Compare, compared).  So we add a generator that emits
# strictly-valid JSON values covering every node type, with emphasis on:
#   * strings needing escaping on output (quotes, backslashes, controls,
#     unicode) -> print_string_ptr
#   * numbers in all shapes/signs/exponents -> print_number
#   * non-empty objects (incl. nested) -> print_object
#   * nested arrays/objects of varied depth -> print_value recursion
#   * duplicate keys and structural twins -> cJSON_Compare
# ---------------------------------------------------------------------------

# A strictly-valid string (always terminated, escapes are all legal).
_printer_string_body = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.characters(
            min_codepoint=0x20,
            blacklist_characters='"\\',
            blacklist_categories=("Cs",),
        ),
        min_size=0,
        max_size=24,
    ),
    st.lists(
        st.one_of(
            st.sampled_from(
                ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
            ),
            st.tuples(
                st.sampled_from(["\\u", "\\U"]).map(lambda s: "\\u"),
                st.integers(min_value=0, max_value=0xFFFF).map(
                    lambda n: "%04x" % n
                ),
            ).map("".join),
            st.text(
                alphabet=st.characters(
                    min_codepoint=0x20,
                    blacklist_characters='"\\',
                    blacklist_categories=("Cs",),
                ),
                min_size=1,
                max_size=6,
            ),
        ),
        min_size=1,
        max_size=10,
    ).map("".join),
)


@st.composite
def _printer_string(draw):
    return '"' + draw(_printer_string_body) + '"'


# Strictly-valid number: -?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?
_printer_number = st.one_of(
    st.just("0"),
    st.just("-0"),
    st.integers(min_value=-(10**18), max_value=10**18).map(str),
    st.tuples(
        st.integers(min_value=-(10**9), max_value=10**9).map(str),
        st.integers(min_value=0, max_value=10**9).map(lambda n: ".%d" % n),
    ).map(lambda t: t[0] + t[1]),
    st.tuples(
        st.integers(min_value=-(10**9), max_value=10**9).map(str),
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=308).map(str),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    st.sampled_from(["1e308", "-1e308", "1e-308", "0.0", "-0.0", "1.5e10"]),
)


@st.composite
def _printer_value(draw):
    # Recursion with explicit depth control so we always produce valid JSON
    # and can hit deep nesting for print_value without blowing up.
    depth = draw(st.integers(min_value=0, max_value=6))
    return _printer_value_at(draw, depth)


def _printer_value_at(draw, depth):
    if depth <= 0:
        kind = draw(st.integers(min_value=0, max_value=4))
        if kind == 0:
            return draw(_printer_string())
        if kind == 1:
            return draw(_printer_number)
        return draw(st.sampled_from(["true", "false", "null"]))
    kind = draw(st.integers(min_value=0, max_value=4))
    if kind <= 1:
        # leaf
        return _printer_value_at(draw, 0)
    if kind == 2:
        n = draw(st.integers(min_value=0, max_value=4))
        items = [_printer_value_at(draw, depth - 1) for _ in range(n)]
        return "[" + ",".join(items) + "]"
    # object, possibly with duplicate keys
    n = draw(st.integers(min_value=0, max_value=4))
    keys = [draw(_printer_string()) for _ in range(n)]
    if n >= 2 and draw(st.integers(min_value=0, max_value=3)) == 0:
        keys[-1] = keys[0]  # duplicate key for cJSON_Compare / object paths
    pairs = [keys[i] + ":" + _printer_value_at(draw, depth - 1) for i in range(n)]
    return "{" + ",".join(pairs) + "}"


# Structural twins: two independently-generated printer values concatenated
# with a separator so a harness can compare them; also emit a bare value.
_printer_twin = st.tuples(
    _printer_value(), st.sampled_from(["", " ", "\n"]), _printer_value()
).map(lambda t: t[0] + t[1] + t[2])


# ---------------------------------------------------------------------------
# Printer/compare round-trip pairs.
#
# The coverage feedback shows cJSON_Compare and the print_* routines are
# entirely unreached.  Those only fire when a *complete, valid* value is
# parsed into a tree and then serialized/compared.  We therefore bias the
# strategy heavily toward strictly-valid values that force full trees:
#   * two structurally identical values (compare -> equal path)
#   * two values differing only in key order / whitespace (compare -> equal)
#   * two values differing in a leaf (compare -> unequal path)
#   * a value followed by its expected minified serialization
# Each is emitted as a single string so the harness can split/compare.
# ---------------------------------------------------------------------------

@st.composite
def _identical_pair(draw):
    v = draw(_printer_value())
    return v + "\n" + v


@st.composite
def _reordered_object_pair(draw):
    # Same keys/values, different key order: cJSON_Compare equal path.
    n = draw(st.integers(min_value=1, max_value=5))
    keys = [draw(_printer_string()) for _ in range(n)]
    vals = [_printer_value_at(draw, draw(st.integers(min_value=0, max_value=2)))
            for _ in range(n)]
    pairs = list(zip(keys, vals))
    a = "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
    rev = list(reversed(pairs))
    b = "{" + ",".join(k + ":" + v for k, v in rev) + "}"
    return a + "\n" + b


@st.composite
def _differing_leaf_pair(draw):
    # Two objects identical except one leaf value: cJSON_Compare unequal path.
    key = draw(_printer_string())
    v1 = _printer_value_at(draw, 0)
    v2 = _printer_value_at(draw, 0)
    if v1 == v2:
        v2 = '"different"'
    return "{" + key + ":" + v1 + "}\n{" + key + ":" + v2 + "}"


@st.composite
def _serialize_roundtrip(draw):
    # A valid value followed by a plausible minified serialization; the
    # harness parses the first, prints it, and compares to the second.
    v = draw(_printer_value())
    return v + "\n" + v


# ---------------------------------------------------------------------------
# NEW: printable / compare-heavy composite structures.
#
# The previous run showed the print_* routines and cJSON_Compare still at 0%
# branch coverage.  The most reliable way to hit them is to feed the parser
# a *single, complete, strictly-valid* document that is rich in every node
# type, rather than a pair split by a separator (a harness that only parses
# the whole string would fail on the separator and never build a tree).
# We therefore add a generator that always emits one fully-valid document
# dense with: escaped strings, all number shapes, nested non-empty objects,
# nested arrays, booleans/nulls, and duplicate keys.
# ---------------------------------------------------------------------------

@st.composite
def _rich_document(draw):
    # Build a guaranteed-valid, non-empty document with broad node coverage.
    n_keys = draw(st.integers(min_value=1, max_value=6))
    keys = [draw(_printer_string()) for _ in range(n_keys)]
    # Force at least one duplicate key to exercise object lookup on compare.
    if n_keys >= 2 and draw(st.integers(min_value=0, max_value=1)) == 0:
        keys[-1] = keys[0]

    members = []
    for k in keys:
        kind = draw(st.integers(min_value=0, max_value=6))
        if kind == 0:
            # escaped / control-heavy string (print_string_ptr)
            body = draw(st.one_of(
                st.sampled_from([
                    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
                    "\\u0000", "\\u001f", "\\u007f", "\\u00e9", "\\uD83D\\uDE00",
                ]),
                st.text(
                    alphabet=st.characters(
                        min_codepoint=0x20,
                        blacklist_characters='"\\',
                        blacklist_categories=("Cs",),
                    ),
                    min_size=0,
                    max_size=8,
                ),
            ))
            members.append(k + ':"' + body + '"')
        elif kind == 1:
            # number (print_number)
            members.append(k + ":" + draw(_printer_number))
        elif kind == 2:
            # nested array of scalars (print_value recursion)
            m = draw(st.integers(min_value=0, max_value=4))
            items = [_printer_value_at(draw, 0) for _ in range(m)]
            members.append(k + ":[" + ",".join(items) + "]")
        elif kind == 3:
            # nested object (print_object recursion)
            m = draw(st.integers(min_value=0, max_value=3))
            sub = []
            for _ in range(m):
                sk = draw(_printer_string())
                sv = _printer_value_at(draw, 0)
                sub.append(sk + ":" + sv)
            members.append(k + ":{" + ",".join(sub) + "}")
        elif kind == 4:
            members.append(k + ":" + draw(st.sampled_from(["true", "false", "null"])))
        elif kind == 5:
            # deep-ish nested array to push print_value recursion
            depth = draw(st.integers(min_value=1, max_value=8))
            leaf = draw(st.sampled_from(["0", "1", "-1", '"x"', "true"]))
            members.append(k + ":" + "[" * depth + leaf + "]" * depth)
        else:
            # array of objects (print_object inside print_value)
            m = draw(st.integers(min_value=1, max_value=3))
            objs = []
            for _ in range(m):
                ok = draw(_printer_string())
                ov = _printer_value_at(draw, 0)
                objs.append("{" + ok + ":" + ov + "}")
            members.append(k + ":[" + ",".join(objs) + "]")

    doc = "{" + ",".join(members) + "}"
    # Occasionally wrap the whole document in an array to vary the root.
    if draw(st.integers(min_value=0, max_value=3)) == 0:
        doc = "[" + doc + "]"
    return doc


# A top-level array of many scalars/objects: forces print_value over a list
# and print_object/print_string_ptr/print_number for each element.
@st.composite
def _rich_array(draw):
    n = draw(st.integers(min_value=1, max_value=8))
    items = []
    for _ in range(n):
        kind = draw(st.integers(min_value=0, max_value=3))
        if kind == 0:
            items.append(draw(_printer_string()))
        elif kind == 1:
            items.append(draw(_printer_number))
        elif kind == 2:
            items.append(draw(st.sampled_from(["true", "false", "null"])))
        else:
            k = draw(_printer_string())
            v = _printer_value_at(draw, draw(st.integers(min_value=0, max_value=2)))
            items.append("{" + k + ":" + v + "}")
    return "[" + ",".join(items) + "]"


strategy = st.one_of(
    _valid_value,
    _with_trailing,
    _with_bom,
    _whitespace_wrapped,
    _deep_array(),
    _deep_object(),
    _malformed,
    _raw_bytes,
    _roundtrip_structs,
    _printer_value(),
    _printer_twin,
    _identical_pair(),
    _reordered_object_pair(),
    _differing_leaf_pair(),
    _serialize_roundtrip(),
    _rich_document(),
    _rich_array(),
)
```