```python
import json
from hypothesis import strategies as st

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

def _join_comma(parts):
    return ",".join(parts)

# ---------- scalars ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map(lambda t: "".join(t))

# \uXXXX escapes including surrogates
_unicode_escape = _hex4().map(lambda h: "\\u" + h)

# simple escapes
_simple_escape = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# safe code points (excluding quote, backslash, control chars)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00',
).filter(lambda c: ord(c) >= 0x20)

_string_body_piece = st.one_of(
    _safe_char,
    _simple_escape,
    _unicode_escape,
)

_json_string = st.lists(_string_body_piece, max_size=8).map(_join).map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), _digits.map(lambda d: d)).map(_join),
    )

def _frac_part():
    return _digits.map(lambda d: "." + d)

def _exp_part():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(_join)

def _number():
    sign = st.sampled_from(["", "-"])
    frac = st.one_of(st.just(""), _frac_part())
    exp = st.one_of(st.just(""), _exp_part())
    return st.tuples(sign, _int_part(), frac, exp).map(_join)

# extreme magnitudes
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "-1e308", "1e400", "1e-400",
    "123456789012345678901234567890",
    "-123456789012345678901234567890",
    "1.7976931348623157e308",
    "2.2250738585072014e-308",
    "0e0", "0.0", "-0", "1E+10", "1e-10",
])

_number_strategy = st.one_of(_number(), _extreme_number)

# ---------- recursive values ----------

_key = _json_string

# forward reference via deferred strategy
_value_ref = st.deferred(lambda: _value)

def _pair():
    return st.tuples(_key, st.just(":"), _value_ref).map(_join)

def _obj():
    return st.one_of(
        st.just("{}"),
        st.lists(_pair(), min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}"),
    )

def _arr():
    return st.one_of(
        st.just("[]"),
        st.lists(_value_ref, min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
    )

_leaf = st.one_of(
    _json_string,
    _number_strategy,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_obj(), _arr()),
    max_leaves=12,
)

# ---------- deep nesting near the 2048 limit ----------

def _deep_nesting():
    # depth concentrated near 2048
    depth = st.integers(min_value=1, max_value=2048)
    open_ch = st.sampled_from(["[", "{"])
    return st.tuples(depth, open_ch).map(lambda t: _build_deep(t[0], t[1]))

def _build_deep(depth, ch):
    if ch == "[":
        return "[" * depth + "]" * depth
    else:
        return ('{"k":' * depth) + "0" + ("}" * depth)

_deep = _deep_nesting()

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    '{"a":1,,}',
    '{"a":1,}',
    "[1,,2]",
    "[1,]",
    '{"a" 1}',
    '{"a":}',
    '{"a":1 "b":2}',
    '{"a":1,,"b":2}',
    '[,]',
    '{,}',
    '{"a":1',
    '[1,2',
    '"unterminated',
    '"unterminated\\',
    '{"a":"unterminated}',
    '+1',
    '.5',
    '-.5',
    '01',
    '-01',
    '1.',
    '00',
    '1e',
    '1e+',
    '-',
    '-.',
    'tru',
    'nul',
    'fals',
    '{"a":1}garbage',
    '[]xyz',
    '1abc',
    '1 garbage',
    'null extra',
    'true false',
    '{"a":1} {"b":2}',
    '"\\uD800"',
    '"\\uDFFF"',
    '"\\uD800\\uDC00"',
    '"\\u0000"',
    '"\\u00"',
    '"\\uZZZZ"',
    '"\\x"',
    '"\\"',
    '{"a":1,"a":2}',
    '{"k":0,"k":1}',
    '{"a":{"b":1},"a":2}',
])

# ---------- top-level combination ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "\n", "[]"])).map(_join)

_value_top = st.one_of(
    _value,
    _deep,
    _malformed,
)

# avoid raw NUL bytes in final output
_final = _value_top.map(lambda s: s.replace("\x00", ""))
_final = st.one_of(_final, _with_trailing(_value))

# ---------- improved: exercise serialize / deep_copy / equals / validate paths ----------

# Larger, structurally diverse valid values to reach serialize/copy/equals code.
# Use a separate, deeper recursive generator with bigger containers and richer
# strings/numbers so round-trip and comparison paths are exercised.
_rich_string = st.lists(
    st.one_of(
        _safe_char,
        _simple_escape,
        _unicode_escape,
        st.sampled_from(['"', "\\", "\t", "\n", "\r", "\b", "\f", "/"]).map(
            lambda c: {"\"": '\\"', "\\": "\\\\", "\t": "\\t", "\n": "\\n",
                       "\r": "\\r", "\b": "\\b", "\f": "\\f", "/": "\\/"}[c]
        ),
        st.just("\\u0041"),
        st.just("\\u00e9"),
        st.just("\\u20ac"),
        st.just("\\ud83d\\ude00"),
    ),
    min_size=0,
    max_size=40,
).map(_join).map(lambda s: '"' + s + '"')

_rich_number = st.one_of(
    _number(),
    _extreme_number,
    st.sampled_from([
        "0", "-0", "0.0", "-0.0", "1", "-1", "1.0", "1e0", "1E0",
        "3.141592653589793", "-2.718281828459045",
        "9007199254740992", "9007199254740993",
        "18446744073709551615", "-9223372036854775808",
    ]),
)

_rich_value_ref = st.deferred(lambda: _rich_value)

def _rich_pair():
    return st.tuples(_json_string, st.just(":"), _rich_value_ref).map(_join)

def _rich_obj():
    return st.one_of(
        st.just("{}"),
        st.lists(_rich_pair(), min_size=1, max_size=8).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
    )

def _rich_arr():
    return st.one_of(
        st.just("[]"),
        st.lists(_rich_value_ref, min_size=1, max_size=8).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
    )

_rich_leaf = st.one_of(
    _rich_string,
    _rich_number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_rich_value = st.recursive(
    _rich_leaf,
    lambda children: st.one_of(_rich_obj(), _rich_arr()),
    max_leaves=40,
)

# Explicit deep-equal pairs: same value repeated inside a container forces
# json_value_equals to compare non-trivially equal structures.
def _dup_pair():
    return st.tuples(_rich_value).map(lambda t: "[" + t[0] + "," + t[0] + "]")

_equals_probe = st.one_of(
    _dup_pair(),
    st.tuples(_rich_value, _rich_value).map(lambda t: "[" + t[0] + "," + t[1] + "]"),
)

# Wrapper that pushes values through serialize + deep_copy paths by embedding
# them in containers (mimics round-trip / copy usage).
_roundtrip_probe = st.tuples(_rich_value).map(lambda t: '{"v":' + t[0] + '}')

# Whitespace-padded valid documents exercise json_validate's whitespace handling.
_ws = st.sampled_from([" ", "\t", "\n", "\r\n", ""])

def _padded(v):
    return st.tuples(_ws, v, _ws).map(_join)

_validate_probe = st.one_of(
    _padded(_rich_value),
    _padded(_value),
    _padded(st.just("{}")),
    _padded(st.just("[]")),
    _padded(st.just("null")),
    _padded(st.just("true")),
    _padded(st.just("false")),
    _padded(_rich_number),
    _padded(_rich_string),
)

_improved = st.one_of(
    _rich_value,
    _equals_probe,
    _roundtrip_probe,
    _validate_probe,
)

strategy = st.one_of(_final, _improved)
```