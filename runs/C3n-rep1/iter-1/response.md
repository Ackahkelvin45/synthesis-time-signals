```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Safe code points: anything except control chars, '"' and '\'
_safe_char = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in Python str
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

# A "raw" body char that may include control bytes and NUL (encouraged)
_control_char = st.integers(min_value=0, max_value=0x1F).map(chr)

_body_char = st.one_of(_safe_char, _control_char)

# Escapes
_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex = st.integers(min_value=0, max_value=15).map(lambda n: "0123456789abcdef"[n])
_unicode_esc = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "\\u" + "".join(t))

# Surrogate escapes (lone high/low and valid pairs)
_high_sur = st.integers(min_value=0xD800, max_value=0xDBFF).map(
    lambda n: "\\u%04x" % n
)
_low_sur = st.integers(min_value=0xDC00, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)
_surrogate = st.one_of(_high_sur, _low_sur, st.tuples(_high_sur, _low_sur).map("".join))

_esc = st.one_of(_simple_esc, _unicode_esc, _surrogate)

# String body: mix of raw chars and escapes, possibly empty
_string_body = st.lists(st.one_of(_body_char, _esc), min_size=0, max_size=12).map("".join)

# Valid JSON string literal
_string = _string_body.map(lambda b: '"' + b + '"')

# ---------- numbers ----------

_digit = st.integers(min_value=0, max_value=9).map(str)
_nonzero = st.integers(min_value=1, max_value=9).map(str)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(_nonzero, st.lists(_digit, max_size=18).map("".join)).map("".join),
)

_frac = st.lists(_digit, min_size=1, max_size=18).map(lambda ds: "." + "".join(ds))

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.lists(_digit, min_size=1, max_size=5).map("".join),
).map("".join)

# Extreme magnitudes explicitly
_extreme = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "0e0", "1E+999", "1e-999",
    "123456789012345678901234567890", "1.7976931348623157e309",
    "-0", "-0.0", "0.0", "1e01", "1E01", "9" * 40,
])

_number = st.one_of(
    _extreme,
    st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.none(), _frac),
        st.one_of(st.none(), _exp),
    ).map(lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or "")),
    # lone '-' is accepted by the parser
    st.just("-"),
)

# ---------- malformed near-valid tokens ----------

_malformed_number = st.sampled_from([
    "+1", ".5", "1.", "01", "00", "0x1F", "-.5", "-01", "1e", "1e+", "1e-",
    "+.5", "1..2", "--1", "1.2.3", "0.", "1E", "Infinity", "NaN", "inf",
])

_malformed_string = st.sampled_from([
    '"', '"abc', '"abc\\', '"\\u12', '"\\uZZZZ"', '"\\x41"', '"\\uD800"',
    '"unterminated', '"a\x00b', '"\\', "'single'",
])

_malformed_punct = st.sampled_from([
    ",", ",,", "[,]", "[1,,2]", "{,}", "{:1}", '{"a" 1}', '{"a":}',
    '{"a":1,,"b":2}', "[1 2]", "{1:2}", "}", "]", "{", "[", ":]",
    "true false", "1abc", "[]xyz", "1 garbage", "//x", "/* */1", "{a:1}",
    "nul", "tru", "fals", "nulll", "[1,2,]", '{"a":1,}',
])

_malformed = st.one_of(_malformed_number, _malformed_string, _malformed_punct)

# ---------- recursive JSON values ----------

_key = _string  # object keys are strings

# leaf values
_leaf = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

# malformed leaf to sprinkle in
_leaf_or_bad = st.one_of(_leaf, _malformed)

# We build recursive structure with st.recursive.
# Base case: leaf values (with occasional malformed).
# Recursive case: objects and arrays.

def _make_pair(key, value):
    return key + ":" + value

_pair = st.tuples(_key, _leaf_or_bad).map(lambda t: _make_pair(t[0], t[1]))

# single trailing comma variant
_pair_trailing = st.tuples(_key, _leaf_or_bad).map(
    lambda t: _make_pair(t[0], t[1]) + ","
)

def _obj_from_pairs(pairs, trailing):
    body = ",".join(pairs)
    if trailing:
        body = body + ","
    return "{" + body + "}"

# Bias toward objects with members; allow empty
_obj = st.one_of(
    st.just("{}"),
    st.tuples(
        st.lists(_pair, min_size=1, max_size=6),
        st.booleans(),
    ).map(lambda t: _obj_from_pairs(t[0], t[1])),
    # duplicate keys: repeat a pair
    st.tuples(_pair, _pair).map(lambda t: "{" + t[0] + "," + t[1] + "}"),
)

_arr = st.one_of(
    st.just("[]"),
    st.tuples(
        st.lists(_leaf_or_bad, min_size=1, max_size=6),
        st.booleans(),
    ).map(lambda t: "[" + ",".join(t[0]) + ("," if t[1] else "") + "]"),
)

# Recursive structure via st.recursive.
# We keep depth moderate but allow depth to vary; the parser has no cap.
_json_value = st.recursive(
    _leaf_or_bad,
    lambda children: st.one_of(
        # object with members
        st.tuples(
            st.lists(
                st.tuples(_key, children).map(lambda t: t[0] + ":" + t[1]),
                min_size=1,
                max_size=5,
            ),
            st.booleans(),
        ).map(lambda t: "{" + ",".join(t[0]) + ("," if t[1] else "") + "}"),
        # array
        st.tuples(
            st.lists(children, min_size=1, max_size=5),
            st.booleans(),
        ).map(lambda t: "[" + ",".join(t[0]) + ("," if t[1] else "") + "]"),
    ),
    max_leaves=20,
)

# Deep nesting generator (no recursion cap in parser)
_deep = st.integers(min_value=1, max_value=200).flatmap(
    lambda n: st.just("[" * n + "1" + "]" * n)
)
_deep_obj = st.integers(min_value=1, max_value=200).flatmap(
    lambda n: st.just('{"a":' * n + "1" + "}" * n)
)

# top-level malformed whole documents
_top_malformed = st.one_of(
    _malformed,
    st.sampled_from([
        "", "   ", "\x00", "a", "1\x00", "[\x00]", '{"a":1}\x00',
        "[\x00,1]", '{"\x00":1}', '"\\u0000"', "null\x00",
        "true\x00", "\x00null", "[\x00]", "{\x00}",
    ]),
)

# whitespace injection
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\t\n"])

def _with_ws(text):
    return text

# Final strategy: valid-ish recursive JSON, deep nesting, malformed docs.
strategy = st.one_of(
    _json_value,
    _deep,
    _deep_obj,
    _top_malformed,
    # wrap some values with surrounding whitespace
    st.tuples(_ws, _json_value, _ws).map(lambda t: t[0] + t[1] + t[2]),
)
```