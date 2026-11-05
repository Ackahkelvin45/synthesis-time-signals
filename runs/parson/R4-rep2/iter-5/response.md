```python
import json
from hypothesis import strategies as st

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- scalars ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map(lambda t: "".join(t))

_unicode_escape = _hex4().map(lambda h: "\\u" + h)
_simple_escape = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00',
).filter(lambda c: ord(c) >= 0x20)

_string_body_piece = st.one_of(_safe_char, _simple_escape, _unicode_escape)
_json_string = st.lists(_string_body_piece, max_size=8).map(_join).map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), _digits).map(_join),
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

_value_ref = st.deferred(lambda: _value)

def _pair():
    return st.tuples(_json_string, st.just(":"), _value_ref).map(_join)

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

# ---------- deep nesting ----------

def _deep_nesting():
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
    '{"a":1,,}', '{"a":1,}', "[1,,2]", "[1,]",
    '{"a" 1}', '{"a":}', '{"a":1 "b":2}', '{"a":1,,"b":2}',
    '[,]', '{,}', '{"a":1', '[1,2',
    '"unterminated', '"unterminated\\', '{"a":"unterminated}',
    '+1', '.5', '-.5', '01', '-01', '1.', '00', '1e', '1e+', '-', '-.',
    'tru', 'nul', 'fals',
    '{"a":1}garbage', '[]xyz', '1abc', '1 garbage', 'null extra',
    'true false', '{"a":1} {"b":2}',
    '"\\uD800"', '"\\uDFFF"', '"\\uD800\\uDC00"', '"\\u0000"',
    '"\\u00"', '"\\uZZZZ"', '"\\x"', '"\\"',
    '{"a":1,"a":2}', '{"k":0,"k":1}', '{"a":{"b":1},"a":2}',
])

# ---------- escape coverage ----------

_escape_char = st.sampled_from([
    '"', "\\", "/", "\b", "\f", "\n", "\r", "\t",
    "\x00", "\x01", "\x02", "\x03", "\x04", "\x05", "\x06", "\x07",
    "\x0b", "\x0e", "\x0f", "\x10", "\x11", "\x12", "\x13", "\x14",
    "\x15", "\x16", "\x17", "\x18", "\x19", "\x1a", "\x1b", "\x1c",
    "\x1d", "\x1e", "\x1f", "a", "Z", " ", "\u00e9", "\u4e2d",
])

def _encode_escape(c):
    mapping = {
        '"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f",
        "\n": "\\n", "\r": "\\r", "\t": "\\t", "/": "\\/",
    }
    if c in mapping:
        return mapping[c]
    o = ord(c)
    if o < 0x20:
        return "\\u%04x" % o
    return c

_valid_escape_string = st.lists(_escape_char, min_size=0, max_size=24).map(
    lambda chars: '"' + "".join(_encode_escape(c) for c in chars) + '"'
)

# ---------- valid docs to exercise serialize/copy/equals/validate ----------

# Single string document that hits every serialize branch in one shot.
_all_escapes_doc = st.just(
    '"' + "".join(_encode_escape(c) for c in [
        '"', "\\", "/", "\b", "\f", "\n", "\r", "\t",
        "\x00", "\x01", "\x02", "\x03", "\x04", "\x05", "\x06", "\x07",
        "\x0b", "\x0e", "\x0f", "\x10", "\x11", "\x12", "\x13", "\x14",
        "\x15", "\x16", "\x17", "\x18", "\x19", "\x1a", "\x1b", "\x1c",
        "\x1d", "\x1e", "\x1f", "a", "Z", " ", "\u00e9", "\u4e2d",
    ]) + '"'
)

_serialize_doc = st.recursive(
    st.one_of(
        _valid_escape_string,
        _all_escapes_doc,
        _number_strategy,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
        st.lists(
            st.tuples(_valid_escape_string, children), max_size=4
        ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
    ),
    max_leaves=10,
)

_dup_key_doc = st.lists(
    st.tuples(
        st.sampled_from(['"a"', '"b"', '"k"', '"x"']),
        st.one_of(_number_strategy, _valid_escape_string, st.just("null"),
                  st.just("true"), st.just("false")),
    ),
    min_size=1, max_size=6,
).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}")

# Equal-valued docs to exercise json_value_equals returning true.
_equal_pair_doc = st.one_of(
    st.tuples(_serialize_doc).map(lambda t: "[" + t[0] + "," + t[0] + "]"),
    st.tuples(_valid_escape_string, _serialize_doc).map(
        lambda t: '[{"k":' + t[1] + '},{"k":' + t[1] + '}]'
    ),
)

_valid_doc = st.one_of(_serialize_doc, _dup_key_doc, _equal_pair_doc)

# ---------- top-level combination ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "\n", "[]"])).map(_join)

_value_top = st.one_of(
    _value,
    _deep,
    _malformed,
    _valid_doc,
)

_final = _value_top.map(lambda s: s.replace("\x00", ""))
_final = st.one_of(_final, _with_trailing(_value))

strategy = _final
```