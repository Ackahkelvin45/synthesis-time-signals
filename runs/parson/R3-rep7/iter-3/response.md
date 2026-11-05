```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map("".join)

# A "safe" character for inside strings: printable ASCII excluding quote and backslash,
# plus a few unicode chars. Never a raw NUL or control char (parser is NUL-terminated).
_safe_chars = st.sampled_from(
    [chr(c) for c in range(0x20, 0x7f) if c not in (0x22, 0x5c)]
    + ["\u00e9", "\u00fc", "\u4e2d", "\u6587", "\U0001F600", "\u2028", "\u007f"]
)

_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = st.tuples(st.just("\\u"), _hex4()).map("".join)

# Surrogate escapes (lone / paired) - these are interesting edge cases.
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\uD834\\uDD1E", "\\u0000"]
)

_string_char = st.one_of(_escapes, _unicode_esc, _surrogate_esc, _safe_chars)

def _string_body(max_size=12):
    return st.lists(_string_char, max_size=max_size).map("".join)

_string = st.tuples(st.just('"'), _string_body(), st.just('"')).map("".join)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.text(alphabet="0123456789", max_size=10)).map("".join),
    st.text(alphabet="0123456789", min_size=1, max_size=18),
)

_frac = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=10)).map("".join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map("".join)

_sign = st.sampled_from(["", "-"])

_number = st.one_of(
    # normal numbers
    st.tuples(_sign, _int_part, st.one_of(st.just(""), _frac), st.one_of(st.just(""), _exp)).map("".join),
    # extreme magnitudes / overflow
    st.sampled_from([
        "1e309", "-1e309", "1e400", "-1e400", "1e-400", "1e308", "1.7976931348623157e308",
        "1.8e308", "-1.8e308", "0e0", "0e999999", "1e999999999", "123456789012345678901234567890",
        "-123456789012345678901234567890", "1.0e-999999", "-0", "-0.0", "0.0000000000000000001",
    ]),
    # lone sign (parser quirk: parses as 0)
    st.just("-"),
    # leading + / .5 / 1. / 01 style near-valid
    st.sampled_from(["+1", ".5", "1.", "01", "-01", "+.5", "--1", "1..2", "1e", "1e+", "1e-"]),
)

# ---------- recursive value ----------

_literal = st.sampled_from(["true", "false", "null"])

_json_leaves = st.one_of(_string, _number, _literal)

def _build_value(children):
    return st.one_of(
        _json_leaves,
        st.tuples(st.just("{"), st.just("}")).map("".join),
        st.tuples(st.just("["), st.just("]")).map("".join),
        # object
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_string, st.just(":"), children).map("".join),
                min_size=0, max_size=4,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map("".join),
        # array
        st.tuples(
            st.just("["),
            st.lists(children, min_size=0, max_size=4).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map("".join),
    )

# Base values (depth 0) - small, non-recursive-ish
_base = st.one_of(_json_leaves)

_value = st.recursive(_base, _build_value, max_leaves=40)

# ---------- deep nesting near the 2048 cap ----------

def _deep(depth):
    # depth nested arrays around a leaf value; depth chosen near 2048
    return st.tuples(
        st.just("[" * depth),
        _json_leaves,
        st.just("]" * depth),
    ).map("".join)

def _deep_obj(depth):
    return st.tuples(
        st.just('{"k":' * depth),
        _json_leaves,
        st.just("}" * depth),
    ).map("".join)

_depth_choice = st.sampled_from([0, 1, 2, 100, 1000, 2000, 2047, 2048, 2049, 2050, 2100, 4096])

_deep_value = st.one_of(
    _depth_choice.flatmap(_deep),
    _depth_choice.flatmap(_deep_obj),
)

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    "{,}", "[,]", "[1,,2]", '{"a":1,}', "[1,]", '{"a" 1}', '{"a":}', "{:1}",
    '{"a":1 "b":2}', '"unterminated', '"esc\\', "[1 2]", "{", "}", "[", "]",
    '{"a":1', '[1,2', '"', '\\', "tru", "fals", "nul", "True", "NULL",
    '{"a":1}}', "[[[]]", '{"a":{"b":}}', "1,2", "1 2", "[] []", "{} {}",
    '{"a":1}garbage', "1abc", "[]xyz", "1 garbage", "nullx", "truefalse",
])

# ---------- top-level composition ----------

_trailing = st.tuples(_value, st.text(alphabet=" \t\n\rabc{}[]0123", max_size=8)).map("".join)

_whitespace = st.text(alphabet=" \t\n\r", max_size=6)

def _wrap_ws(v):
    return st.tuples(_whitespace, v, _whitespace).map("".join)

# ---------- round-trip / serialize / copy / equals / validate exercise ----------

# Build a valid JSON document from a Python value and serialize it, so the
# parser is fed canonical output that exercises parse -> serialize -> deep_copy
# -> equals -> validate paths.
_py_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-2**53, max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(alphabet="abcXYZ 0123\u00e9\u4e2d\U0001F600\"\\\n\t/", max_size=12),
)

_py_value = st.recursive(
    _py_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(max_size=6), children, max_size=4),
    ),
    max_leaves=30,
)

def _dumps(v):
    try:
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return "null"

_roundtrip = _py_value.map(_dumps)

# A document followed by its own serialization-independent structural twin, to
# exercise json_value_equals with equal-but-not-identical trees.
def _twin(v):
    try:
        a = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        b = json.dumps(v, ensure_ascii=True, separators=(", ", ": "))
    except (TypeError, ValueError):
        return "null"
    return a + b

_equals_pair = _py_value.map(_twin)

# ---------- NEW: exercise serialize/deep_copy/equals/validate directly ----------
# The uncovered functions are all post-parse operations. Feed them values that
# stress string escaping on serialize, structural equality, deep copy, and
# validation. These are all *valid* documents so they reach the post-parse paths.

# Serialize-string stress: strings with chars needing escaping, unicode,
# control chars, quotes, backslashes. json.dumps handles escaping correctly.
_serialize_strings = st.lists(
    st.text(
        alphabet="abcXYZ 0123\"\\/\b\f\n\r\t\u00e9\u00fc\u4e2d\u6587\U0001F600\u2028\u007f",
        max_size=20,
    ),
    max_size=6,
).map(lambda xs: "[" + ",".join(json.dumps(x, ensure_ascii=False) for x in xs) + "]")

# Nested structures with many keys / duplicate-ish to exercise equals+copy.
_structural = _py_value.map(
    lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
)

# Empty-ish and scalar valid docs to hit validate early-return branches.
_simple_valid = st.sampled_from([
    "{}", "[]", "null", "true", "false", "0", "-0", '""', '"a"',
    '{"a":null}', "[null]", '{"":""}', '[[[[]]]]', '{"a":{"b":{"c":1}}}',
])

# Large flat arrays/objects to exercise iterate + copy + equals loops.
def _big_flat(n):
    return st.tuples(
        st.just("["),
        st.lists(_json_leaves, min_size=n, max_size=n).map(lambda xs: ",".join(xs)),
        st.just("]"),
    ).map("".join)

_big_flat = st.sampled_from([8, 16, 32]).flatmap(_big_flat)

_post_parse = st.one_of(
    _serialize_strings,
    _structural,
    _simple_valid,
    _big_flat,
)

strategy = _wrap_ws(
    st.one_of(
        _value,
        _deep_value,
        _malformed,
        _trailing,
        _roundtrip,
        _equals_pair,
        _post_parse,
        st.just("{}"),
        st.just("[]"),
        st.just('{"a":0,"a":1}'),  # duplicate keys
        st.just('{"k":0,"k":1}'),
        st.just("1e309"),
        st.just("-"),
    )
)
```