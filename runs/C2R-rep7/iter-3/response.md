```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

_safe_chars = [chr(c) for c in range(0x20, 0x7f) if c not in (0x22, 0x5c)]
_safe_chars += [chr(c) for c in range(0x80, 0x2000) if c not in ()]
_safe_chars += ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f"]

_safe_text = st.text(alphabet=_safe_chars, min_size=0, max_size=8)

_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

def _unicode_escape():
    return st.tuples(
        st.just("\\u"),
        st.tuples(*[st.sampled_from(list(_hex)) for _ in range(4)]).map("".join),
    ).map("".join)

_unicode_escape = _unicode_escape()

_surrogate_escape = st.tuples(
    st.just("\\u"),
    st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DC00"]),
).map("".join)

_escape = st.one_of(_escapes, _unicode_escape, _surrogate_escape)

def _string_body():
    return st.lists(st.one_of(_safe_text, _escape), min_size=0, max_size=6).map("".join)

_string_body = _string_body()

_string = _string_body.map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_int_digits = st.one_of(
    st.just("0"),
    st.tuples(
        st.sampled_from("123456789"),
        st.text(alphabet="0123456789", min_size=0, max_size=6),
    ).map("".join),
)

_frac = st.tuples(
    st.just("."),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map("".join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map("".join)

_extreme_exp = st.sampled_from(
    ["e309", "e308", "e-323", "e-324", "e999", "E999", "e+999", "e-999",
     "e01", "E00", "e0", "e"]
)

_number = st.one_of(
    st.tuples(st.sampled_from(["", "-"]), _int_digits,
              st.one_of(st.just(""), _frac),
              st.one_of(st.just(""), _exp, _extreme_exp)).map("".join),
    st.just("-"),
    st.just("1e309"),
    st.just("1e-309"),
    st.just("0.0"),
    st.just("-0"),
)

# ---------- malformed / near-valid fragments ----------

_bad_number = st.sampled_from(
    ["+1", ".5", "1.", "01", "0x1F", "1..2", "1e", "1e+", "--1", "0.5.5",
     "+", ".", "1e++1", "00", "-01", "1.2e", "0b1"]
)

_bad_string = st.sampled_from(
    ['"unterminated', '"', '""extra', '"\\', '"\\u12"', '"\\x41"',
     '"\\uD800"', '"a\x00b', '"tab\there"']
)

_malformed = st.one_of(
    st.just("{"),
    st.just("}"),
    st.just("["),
    st.just("]"),
    st.just(","),
    st.just(":"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just("[1,2,]"),
    st.just('{"a":1,}'),
    st.just('{"a" 1}'),
    st.just('{"a":}'),
    st.just("{:1}"),
    st.just('{"a":1 "b":2}'),
    st.just("tru"),
    st.just("fals"),
    st.just("nul"),
    st.just("true false"),
    st.just("1abc"),
    st.just("[]xyz"),
    st.just("1 garbage"),
    st.just("\x00"),
    st.just("\x00\x00"),
    st.just('{"a":\x00}'),
    st.just("[1,\x002]"),
    _bad_number,
    _bad_string,
)

# ---------- recursive value ----------

json_values = st.deferred(lambda: _value)

_string_value = _string
_number_value = _number
_literal = st.sampled_from(["true", "false", "null"])
_scalar = st.one_of(_string_value, _number_value, _literal)

def _pair():
    return st.tuples(_string, st.just(":"), json_values).map("".join)

_pair = _pair()

def _obj_with_members():
    def build(parts):
        return "{" + ",".join(parts) + "}"
    return st.lists(_pair, min_size=1, max_size=5).map(build)

def _obj_any():
    return st.one_of(
        st.just("{}"),
        _obj_with_members(),
        st.lists(_pair, min_size=1, max_size=3).map(lambda ps: "{" + ",".join(ps) + ",}"),
        st.lists(_pair, min_size=1, max_size=3).map(
            lambda ps: "{" + ",".join(ps + [ps[0]]) + "}"
        ) if False else st.just("{}"),
    )

def _arr():
    def build(parts):
        return "[" + ",".join(parts) + "]"
    return st.lists(json_values, min_size=0, max_size=5).map(build)

def _arr_trailing_comma():
    return st.lists(json_values, min_size=1, max_size=4).map(
        lambda ps: "[" + ",".join(ps) + ",]"
    )

_value = st.one_of(
    _scalar,
    _obj_any(),
    _arr(),
    _arr_trailing_comma(),
)

# deep nesting: objects with members, arrays
def _deep_obj():
    def build(depth):
        s = '{"k":' * depth + "1" + "}" * depth
        return s
    return st.integers(min_value=1, max_value=200).map(build)

def _deep_arr():
    def build(depth):
        return "[" * depth + "1" + "]" * depth
    return st.integers(min_value=1, max_value=200).map(build)

_deep = st.one_of(_deep_obj(), _deep_arr())

# recursive strategy for general structure
_recursive = st.recursive(
    _scalar,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=4).map(
            lambda ps: "[" + ",".join(ps) + "]"
        ),
        st.lists(
            st.tuples(_string, st.just(":"), children).map("".join),
            min_size=0, max_size=4,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ),
    max_leaves=20,
)

strategy = st.one_of(
    _recursive,
    _value,
    _deep,
    _malformed,
    st.just("{}"),
    st.just("[]"),
    st.just('[1,2,]'),
    st.just('{"a":1,"a":2}'),
    st.just("1e309"),
    st.just("-"),
    st.just('{"a":"\\uD800"}'),
    st.just('{"\\u0000":1}'),
    st.just('{"a":1,}'),
    st.just("\x00"),
)
```