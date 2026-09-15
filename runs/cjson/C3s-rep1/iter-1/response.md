```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helper strategies
# ---------------------------------------------------------------------------

# A "safe" JSON string body character: anything except '"', '\\', and C0 controls.
_safe_body = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

# Raw control bytes (including NUL) that the parser accepts inside strings.
_control_bytes = st.sampled_from(
    [chr(i) for i in range(0x20)] + ["\x7f"]
)

# Escape sequences.
_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex = st.characters(whitelist_characters="0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))
_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Lone surrogate escapes (parser rejects these, but they are interesting).
_lone_surrogate = st.sampled_from(
    ["\\ud800", "\\udc00", "\\udfff", "\\udbff", "\\udabc", "\\ud800\\ud800"]
)

# Valid surrogate pairs.
_surrogate_pair = st.tuples(
    st.integers(min_value=0xD800, max_value=0xDBFF),
    st.integers(min_value=0xDC00, max_value=0xDFFF),
).map(lambda t: "\\u%04x\\u%04x" % t)

_string_piece = st.one_of(
    _safe_body,
    _control_bytes,
    _escapes,
    _unicode_escape,
    _surrogate_pair,
    _lone_surrogate,
)

# A JSON string token (with quotes).
_string_token = st.lists(_string_piece, min_size=0, max_size=8).map(
    lambda pieces: '"' + "".join(pieces) + '"'
)

# Malformed string: missing closing quote, bad escape, etc.
_malformed_string = st.one_of(
    st.lists(_string_piece, min_size=0, max_size=6).map(
        lambda pieces: '"' + "".join(pieces)
    ),
    st.just('"'),
    st.just('"abc'),
    st.just('"\\x"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just("'single quotes'"),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_number = st.one_of(
    # simple integers
    st.integers(min_value=-(10**12), max_value=10**12).map(str),
    # zero
    st.just("0"),
    # leading zeros (parser accepts)
    st.tuples(st.just("0"), _int_digits).map(lambda t: t[0] + t[1]),
    # trailing dot (parser accepts)
    st.tuples(
        st.integers(min_value=0, max_value=10**6).map(str), st.just(".")
    ).map(lambda t: t[0] + t[1]),
    # hex (parser accepts)
    st.tuples(
        st.sampled_from(["0x", "0X", "-0x"]),
        st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8),
    ).map(lambda t: t[0] + t[1]),
    # exponent forms, incl. overflow
    st.tuples(
        st.integers(min_value=0, max_value=10**9).map(str),
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    # extreme exponents
    st.sampled_from(
        [
            "1e309",
            "-1e309",
            "1e-309",
            "1e999999",
            "1e-999999",
            "1e308",
            "1.7976931348623157e308",
            "1.7976931348623157e309",
            "0e0",
            "0e999",
            "1e01",
            "1.0e+0005",
        ]
    ),
    # fractional
    st.tuples(
        st.integers(min_value=0, max_value=10**6).map(str),
        st.just("."),
        st.text(alphabet="0123456789", min_size=1, max_size=6),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # malformed numbers (parser rejects)
    st.sampled_from(["-", "+1", ".5", "-.5", "01", "00", "1..2", "1e", "1e+", "1e-"]),
)

# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------


def _obj_from_pairs(pairs):
    return "{" + ",".join(pairs) + "}"


def _arr_from_values(values):
    return "[" + ",".join(values) + "]"


def _pair_str(key, value):
    return key + ":" + value


# Use st.recursive for the recursive structure.
# Base: strings, numbers, literals.
# Recursive: objects and arrays.

_base_value = st.one_of(
    _string_token,
    _number,
    st.sampled_from(["true", "false", "null"]),
)

# For objects, we need pairs. We build them from a key string and a value.
# We use st.lists of pairs and join with commas.

_pair = st.tuples(_string_token, st.deferred(lambda: _value)).map(
    lambda t: _pair_str(t[0], t[1])
)

_obj = st.lists(_pair, min_size=0, max_size=4).map(_obj_from_pairs)

_arr = st.lists(st.deferred(lambda: _value), min_size=0, max_size=4).map(
    _arr_from_values
)

_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        st.lists(_pair, min_size=0, max_size=4).map(_obj_from_pairs),
        st.lists(children, min_size=0, max_size=4).map(_arr_from_values),
    ),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Depth-controlled values near the 1000 limit
# ---------------------------------------------------------------------------


def _nested_array(depth):
    return "[" * depth + "]" * depth


def _nested_object(depth):
    return '{"a":' * depth + "null" + "}" * depth


_depth_value = st.integers(min_value=0, max_value=1005).flatmap(
    lambda d: st.one_of(
        st.just(_nested_array(d)),
        st.just(_nested_object(d)),
    )
)

# ---------------------------------------------------------------------------
# Malformed / near-valid top-level inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        "",
        " ",
        "{},",
        "[,]",
        "{,}",
        "[1,,2]",
        '{"a":1,}',
        '{"a":1,,}',
        '{"a" 1}',
        '{"a":}',
        "{:1}",
        "[1 2]",
        "{a:1}",
        "tru",
        "tru e",
        "nul",
        "fals",
        "NaN",
        "Infinity",
        "-Infinity",
        "1abc",
        "1 2",
        "\xef\xbb\xbf{}",
        "\xef\xbb\xbf",
        "\x00",
        "1\x00",
        '"\x00"',
        '"abc\x00def"',
        '{"a":"b"\x00}',
        "[]\x00",
        "{}[]",
        "[1][2]",
        '"\\ud800"',
        '"\\udc00"',
        '"\\uD800\\uD800"',
        '"\\uD800\\uDC00"',
        '"\\u0041"',
        '"\\u00e9"',
        '"\\u0000"',
        '"unterminated',
        '"\\',
        '"\\q"',
        "0x10",
        "01",
        "1.",
        "-0x10",
        "1e309",
        "1e-309",
        "1e999999",
    ]
)

# ---------------------------------------------------------------------------
# The final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _value,
    _depth_value,
    _malformed,
    # a few hand-crafted deep-ish values with duplicate keys
    st.just('{"a":1,"a":2,"a":3}'),
    st.just('{"a":{"b":{"c":[1,2,3]}}}'),
    st.just('{"":""}'),
    st.just('{"a":1,"a":1}'),
    st.just("[" + ",".join(["null"] * 100) + "]"),
    st.just('{"' + "a" * 1000 + '":null}'),
    st.just("[" * 1000 + "]" * 1000),
    st.just("[" * 1001 + "]" * 1001),
    st.just('{"a":' * 1000 + "null" + "}" * 1000),
    st.just('{"a":' * 1001 + "null" + "}" * 1001),
)
```