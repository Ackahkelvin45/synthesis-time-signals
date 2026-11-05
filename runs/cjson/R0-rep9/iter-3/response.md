```python
from hypothesis import strategies as st
import json

# ---------- scalar pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_unicode_escape = _hex4().map(lambda h: "\\u" + h)

# Surrogate escapes (accepted alone by parser? lone surrogates rejected, but
# paired high+low are fine; we emit both lone and paired to exercise decoder).
_high_surrogate_escape = st.integers(min_value=0xD800, max_value=0xDBFF).map(
    lambda n: "\\u%04x" % n
)
_low_surrogate_escape = st.integers(min_value=0xDC00, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)
_surrogate_pair = st.tuples(_high_surrogate_escape, _low_surrogate_escape).map(
    lambda t: t[0] + t[1]
)

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# Safe code points for string bodies (avoid raw quote/backslash/control here;
# controls are added deliberately elsewhere).
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
    min_codepoint=0x20,
)

# Raw control / NUL bytes inside strings - parser accepts these.
_raw_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_string_body_piece = st.one_of(
    _safe_char,
    _simple_escapes,
    _unicode_escape,
    _surrogate_pair,
    _high_surrogate_escape,   # lone surrogate -> rejection probe
    _low_surrogate_escape,
    _raw_control,
)

def _string():
    return st.lists(_string_body_piece, max_size=8).map(lambda parts: '"' + "".join(parts) + '"')

# Unterminated string probe (malformed).
_unterminated_string = st.lists(_string_body_piece, min_size=1, max_size=6).map(
    lambda parts: '"' + "".join(parts)
)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map(lambda t: t[0] + t[1]),
    _digits,  # leading zeros probe
)
_frac = st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1])
_frac_trailing_dot = st.just(".")
_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.just("+"), st.just("-")),
    _digits,
).map(lambda t: t[0] + t[1] + t[2])
_big_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.just("+"), st.just("-")),
    st.sampled_from(["309", "400", "999", "1000", "9999"]),
).map(lambda t: t[0] + t[1] + t[2])

_sign = st.one_of(st.just(""), st.just("-"))

_number = st.one_of(
    _int_part,
    st.tuples(_sign, _int_part).map(lambda t: t[0] + t[1]),
    st.tuples(_sign, _int_part, _frac).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_sign, _int_part, _frac_trailing_dot).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_sign, _int_part, _exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_sign, _int_part, _frac, _exp).map(lambda t: "".join(t)),
    st.tuples(_sign, _int_part, _big_exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_sign, _int_part, _frac, _big_exp).map(lambda t: "".join(t)),
    # hex probe
    st.tuples(st.just("0x"), _digits).map(lambda t: t[0] + t[1]),
    # malformed numeric probes (rejections)
    st.just("-"),
    st.tuples(st.just("+"), _digits).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

_literal = st.sampled_from(["true", "false", "null"])

# ---------- recursive structures ----------

_ws = st.text(alphabet=" \t\n\r", max_size=2)

def _ws_around(s):
    return st.tuples(_ws, st.just(s), _ws).map(lambda t: t[0] + t[1] + t[2])

_comma = _ws_around(",")
_colon = _ws_around(":")

def _obj_from_value(value):
    key = _string()
    pair = st.tuples(key, _colon, value).map(lambda t: t[0] + t[1] + t[2])
    pairs = st.lists(pair, min_size=0, max_size=4)
    body = pairs.map(lambda ps: ",".join(ps))
    return st.tuples(_ws, st.just("{"), body, st.just("}"), _ws).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

def _arr_from_value(value):
    items = st.lists(value, min_size=0, max_size=4)
    body = items.map(lambda xs: ",".join(xs))
    return st.tuples(_ws, st.just("["), body, st.just("]"), _ws).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

def _deep_arr(depth):
    return st.tuples(st.just("[" * depth), st.just("]" * depth)).map(
        lambda t: t[0] + t[1]
    )

def _deep_obj(depth):
    return st.tuples(
        st.just('{"k":' * depth), st.just("0"), st.just("}" * depth)
    ).map(lambda t: t[0] + t[1] + t[2])

# Malformed structural probes
_malformed_obj = st.one_of(
    st.just('{"a":1,}'),
    st.just('{"a":1,,}'),
    st.just('{"a" 1}'),
    st.just('{"a":}'),
    st.just('{:1}'),
    st.just('{a:1}'),
    st.just('{"a":1'),
    st.tuples(_string(), _colon, st.just("")).map(lambda t: "{" + t[0] + t[1] + t[2] + "}"),
)
_malformed_arr = st.one_of(
    st.just("[1,]"),
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just("[1"),
    st.just("[]]"),
)

# ---------- assemble value recursively ----------

def _make_value():
    return st.recursive(
        st.one_of(
            _string(),
            _number,
            _literal,
            _unterminated_string,
            _malformed_obj,
            _malformed_arr,
            st.just("{}"),
            st.just("[]"),
        ),
        lambda children: st.one_of(
            _obj_from_value(children),
            _arr_from_value(children),
            st.tuples(children, _comma, children).map(lambda t: t[0] + t[1] + t[2]),
            st.tuples(_ws, children, _ws).map(lambda t: t[0] + t[1] + t[2]),
        ),
        max_leaves=12,
    )

_value = _make_value()

# Depth-focused probes near the 1000-level limit.
_depth_probe = st.one_of(
    st.integers(min_value=990, max_value=1010).flatmap(_deep_arr),
    st.integers(min_value=990, max_value=1010).flatmap(_deep_obj),
    st.integers(min_value=1, max_value=50).flatmap(_deep_arr),
    st.integers(min_value=1, max_value=50).flatmap(_deep_obj),
)

# BOM / trailing-content probes.
_bom = st.just("\ufeff")
_trailing = st.text(alphabet="abc0123 \t", max_size=4)

strategy = st.one_of(
    _value,
    _depth_probe,
    st.tuples(_bom, _value).map(lambda t: t[0] + t[1]),
    st.tuples(_value, _trailing).map(lambda t: t[0] + t[1]),
    st.tuples(_value, st.just("\x00")).map(lambda t: t[0] + t[1]),
    st.just(""),
)
```