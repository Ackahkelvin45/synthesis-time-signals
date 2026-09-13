```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _hex_digits(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)

# safe code points: exclude quote, backslash, control chars, and NUL
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

_esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_esc_unicode = st.builds(
    lambda h: "\\u" + h,
    _hex_digits(4),
)

# surrogate escapes (lone and paired) - these are text, fine for the parser
_surrogate_esc = st.builds(
    lambda h: "\\u" + h,
    st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DC00", "d83d", "de00"]),
)

_esc = st.one_of(_esc_simple, _esc_unicode, _surrogate_esc)

# string body pieces
_str_piece = st.one_of(
    _safe_char.map(lambda c: c),
    _esc,
    st.just("\\u0000"),  # embedded NUL escape - text, not raw NUL
    st.just("\\u001f"),
)

# a STRING token: quoted, possibly empty
_string_token = st.lists(_str_piece, min_size=0, max_size=8).map(lambda ps: '"' + "".join(ps) + '"')

# ---------- numbers ----------

_int_small = st.integers(min_value=-1000, max_value=1000)
_int_big = st.integers(min_value=-(2**70), max_value=2**70)

_exp = st.one_of(
    st.nothing(),
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(e)),
    st.just("e309"),
    st.just("e-309"),
    st.just("e999"),
    st.just("E+999"),
    st.just("e01"),
    st.just("e0"),
)

_frac = st.one_of(
    st.nothing(),
    st.integers(min_value=0, max_value=10**6).map(lambda f: "." + str(f)),
    st.just(".0"),
    st.just(".000000"),
)

def _make_number(i, f, e):
    return ("" if i >= 0 else "-") + str(abs(i)) + f + e

_number = st.one_of(
    st.builds(_make_number, _int_small, _frac, _exp),
    st.builds(_make_number, _int_big, _frac, _exp),
    # extremes
    st.just("0"),
    st.just("-0"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e308"),
    st.just("1e-308"),
    st.just("1.7976931348623157e308"),
    st.just("1.8e308"),
    st.just("123456789012345678901234567890"),
    st.just("-123456789012345678901234567890"),
)

# ---------- malformed / near-valid fragments ----------

_malformed_fragments = st.sampled_from([
    ",",
    ",,",
    "{,}",
    "[,]",
    "[1,]",
    "[,1]",
    '{"a":}',
    '{"a" 1}',
    '{"a"::1}',
    '{"a":1,}',
    '{"a":1,,"b":2}',
    '{"a"}',
    '{:1}',
    '"unterminated',
    "'single'",
    "tru",
    "fals",
    "nul",
    "True",
    "FALSE",
    "NULL",
    "01",
    "007",
    "+1",
    ".5",
    "-.5",
    "1.",
    "1.e5",
    "-",
    "-.",
    "0x10",
    "1e",
    "1e+",
    "1e-",
    "--1",
    "1..2",
    "NaN",
    "Infinity",
    "-Infinity",
    "undefined",
    "\\u",
    "\\x41",
    "\x01",
    "\x1f",
    "\x7f",
])

# ---------- recursive JSON values ----------

json_value = st.deferred(lambda: _json_value)

_key = _string_token

_pair = st.builds(
    lambda k, v: k + ":" + v,
    _key,
    json_value,
)

_obj = st.one_of(
    st.just("{}"),
    st.lists(_pair, min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}"),
    # duplicate keys
    st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        _key,
        json_value,
        json_value,
    ),
    # trailing comma etc
    st.builds(lambda p: "{" + p + ",}", _pair),
)

_arr = st.one_of(
    st.just("[]"),
    st.lists(json_value, min_size=1, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]"),
    st.builds(lambda v: "[" + v + ",]", json_value),
)

_json_value = st.one_of(
    _string_token,
    _number,
    _obj,
    _arr,
    st.sampled_from(["true", "false", "null"]),
    _malformed_fragments,
)

# ---------- depth control near 2048 ----------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

# concentrate near the limit: 2000..2060
_depth_near = st.integers(min_value=2000, max_value=2060)

_deep_arr = st.builds(
    lambda d: "[" * d + "0" + "]" * d,
    _depth_near,
)

_deep_obj = st.builds(
    lambda d: '{"k":' * d + "0" + "}" * d,
    _depth_near,
)

# moderate nesting via recursive
_deep_structured = st.recursive(
    json_value,
    lambda children: st.one_of(
        st.builds(lambda c: "[" + c + "]", children),
        st.builds(lambda c: '{"k":' + c + "}", children),
    ),
    max_leaves=40,
)

# ---------- top-level ----------

_trailing = st.one_of(
    st.nothing(),
    st.sampled_from(["", " ", "\n", "abc", " garbage", "xyz", "\t\n", "//c", "/*c*/"]),
)

_top = st.one_of(
    json_value,
    _deep_arr,
    _deep_obj,
    _deep_structured,
    # empty containers
    st.sampled_from(["{}", "[]", " \t\n{} \r\n", "[] ", "{}"]),
    # lone sign leniency
    st.sampled_from(["-", "-.", "-e5", "-.e5"]),
    # trailing content after complete value (accepted by parser)
    st.builds(lambda v, t: v + t, json_value, _trailing),
    # malformed
    _malformed_fragments,
)

strategy = _top
```