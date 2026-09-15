Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

_esc_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_esc_unicode = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "\\u" + "".join(t))

_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

# raw control / NUL bytes are accepted by the parser inside strings
_raw_control = st.sampled_from(
    [chr(c) for c in range(0x00, 0x20)] + ["\x7f"]
)

_str_body = st.one_of(
    _safe_char,
    _esc_simple,
    _esc_unicode,
    _raw_control,
)

# lone surrogate escape: rejected by parser (interesting negative)
_lone_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udbff", "\\udc00", "\\udfff", "\\uD800", "\\uDC00"]
)

_string = st.one_of(
    st.lists(_str_body, max_size=12).map(lambda cs: '"' + "".join(cs) + '"'),
    st.just('""'),
    st.just('"\\u0000"'),
    st.just('"\\ud83d\\ude00"'),  # valid surrogate pair
    _lone_surrogate_esc.map(lambda s: '"' + s + '"'),
    # unterminated string (malformed)
    st.lists(_str_body, min_size=1, max_size=8).map(lambda cs: '"' + "".join(cs)),
)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.text(alphabet="0123456789", max_size=5)).map(
        lambda t: t[0] + t[1]
    ),
    # leading zeros (accepted by parser)
    st.text(alphabet="0123456789", min_size=2, max_size=6).filter(lambda s: s[0] == "0"),
)

_frac = st.one_of(
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
    # trailing dot (accepted by parser)
    st.just("."),
)

_exp = st.one_of(
    st.tuples(
        st.sampled_from("eE"),
        st.one_of(st.just(""), st.sampled_from("+-")),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # extreme exponents
    st.sampled_from(["e309", "e308", "e-309", "e9999", "E+308", "e-9999"]),
)

_number = st.one_of(
    _int,
    st.tuples(st.one_of(st.just(""), st.just("-")), _int, st.one_of(st.just(""), _frac), st.one_of(st.just(""), _exp)).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    ),
    # hex numbers (accepted by parser)
    st.tuples(st.sampled_from(["0x", "0X", "-0x"]), st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=6)).map(
        lambda t: t[0] + t[1]
    ),
    # malformed / rejected-by-parser numerics
    st.sampled_from(["-", "+1", ".5", "-.5", "1.", "01", "-01", "1e", "1e+", "NaN", "Infinity", "-Infinity"]),
    # extreme magnitudes
    st.sampled_from(["1e309", "-1e309", "1e-309", "1e999999", "0.0", "-0.0", "1E+308"]),
)

# ---------- whitespace ----------

_ws = st.text(alphabet=" \t\n\r", max_size=3)

# ---------- recursive values ----------

def _wrap_list(xs):
    return "[" + ",".join(xs) + "]"

def _wrap_obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _pair(k, v):
    return k + ":" + v

def _pair_ws(k, v):
    return k + ":" + v

_value = st.deferred(lambda: _value_impl)

_leaf = st.one_of(
    _string,
    _number,
    st.sampled_from(["true", "false", "null"]),
    # malformed leaves
    st.sampled_from(["tru", "fals", "nul", "True", "NULL", "'x'", "undefined"]),
)

_arr = st.lists(_value, max_size=4).map(_wrap_list)

_obj = st.lists(
    st.tuples(_string, _value).map(lambda t: _pair(t[0], t[1])),
    max_size=4,
).map(_wrap_obj)

_value_impl = st.one_of(_leaf, _arr, _obj)

# ---------- depth-focused generators (near 1000 level limit) ----------

def _nested_array(depth):
    # depth 1000 accepted, 1001 rejected
    return "[" * depth + "]" * depth

def _nested_obj(depth):
    return '{"a":' * depth + "null" + "}" * depth

_depth_choice = st.one_of(
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=990, max_value=1010),
    st.integers(min_value=999, max_value=1001),
    st.sampled_from([1000, 1001, 1002, 500, 999, 1000]),
)

_deep_arr = _depth_choice.map(_nested_array)
_deep_obj = _depth_choice.map(_nested_obj)

# ---------- malformed structural inputs ----------

_malformed = st.sampled_from([
    "[,]", "[1,]", "[1,,2]", "{,}", '{"a":}', '{"a"}', '{"a":1,}',
    '{"a":1,,"b":2}', "{", "}", "[", "]", '{"a" 1}', '{"a":1 "b":2}',
    "", "   ", ":", ",", '{"a":1', "[1,2", '"abc', "\\", "\\u", "\\u12",
    "\\uZZZZ", "01", "1.", ".5", "+1", "-", "NaN", "Infinity",
    '"\\ud800"', '"\\udfff"', '"\\uD800"',
])

# trailing content after a valid value (parser accepts, stops early)
_trailing = st.tuples(
    _value, st.sampled_from(["1abc", " 1 2", "null null", "{}[]", "x", "\x00junk"])
).map(lambda t: t[0] + t[1])

# BOM prefix (accepted)
_bom = st.tuples(st.just("\ufeff"), _value).map(lambda t: t[0] + t[1])

# embedded NUL after value (accepted)
_nul_tail = st.tuples(_value, st.just("\x00")).map(lambda t: t[0] + t[1])

# duplicate keys
_dup_keys = st.lists(_string, min_size=2, max_size=4).map(
    lambda ks: "{" + ",".join(k + ":1" for k in ks) + "}"
)

# whitespace-padded values
_padded = st.tuples(_ws, _value, _ws).map(lambda t: t[0] + t[1] + t[2])

# ---------- top-level strategy ----------

strategy = st.one_of(
    _value,
    _deep_arr,
    _deep_obj,
    _malformed,
    _trailing,
    _bom,
    _nul_tail,
    _dup_keys,
    _padded,
).map(str)
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.