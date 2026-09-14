```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- leaf / token strategies ----------

_HEX = "0123456789abcdefABCDEF"

_safe_chars = st.characters(
    blacklist_categories=["Cs"],  # no lone surrogates
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_escape = st.text(alphabet=_HEX, min_size=4, max_size=4).map(lambda h: "\\u" + h)

_surrogate_escape = st.sampled_from(
    [
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uD83D", "\\uDE00",
        "\\uD800\\uDC00", "\\uD83D\\uDE00", "\\uDBFF\\uDFFF",
    ]
)

_control_escape = st.sampled_from(
    ["\\u0000", "\\u0001", "\\u001f", "\\u007f", "\\u0080", "\\u00ff", "\\u2028", "\\u2029"]
)

_string_body = st.one_of(
    st.lists(_safe_chars, min_size=0, max_size=8).map(_join),
    _simple_escapes,
    _unicode_escape,
    _surrogate_escape,
    _control_escape,
)

_json_string = _string_body.map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_int_str = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=10, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

_frac = st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n))

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=400).map(str),
).map(_join)

_number = st.one_of(
    _int_str,
    st.tuples(_int_str, _frac).map(_join),
    st.tuples(_int_str, _exp).map(_join),
    st.tuples(_int_str, _frac, _exp).map(_join),
    # extreme magnitudes
    st.sampled_from(
        [
            "1e309", "-1e309", "1e308", "1e-309", "1e-400", "1e9999",
            "0.0", "-0.0", "0e0", "0E+0", "0e-0", "123456789012345678901234567890",
            "1.7976931348623157e308", "2.2250738585072014e-308",
            "4.9406564584124654e-324", "1e-323", "1e308", "-1e308",
            "9" * 40, "-" + "9" * 40, "1" + "0" * 300,
        ]
    ),
    # lenient / near-number forms the parser may accept
    st.sampled_from(["-", "-.", "+1", ".5", "1.", "01", "00", "-01", "+.5", "1e", "1e+", "1e-", "--1"]),
)

# ---------- recursive structure ----------

# Depth control: concentrate near 2048.
_deep_bracket = st.integers(min_value=1, max_value=40).map(lambda n: "[" * n + "]" * n)
_very_deep = st.sampled_from(
    [
        "[" * 2047 + "]" * 2047,
        "[" * 2048 + "]" * 2048,
        "[" * 2049 + "]" * 2049,
        "[" * 2050 + "]" * 2050,
        "[" * 2100 + "]" * 2100,
        "[" * 3000 + "]" * 3000,
        "{" + '"a":' * 2047 + "null" + "}" * 2047,
        "{" + '"a":' * 2048 + "null" + "}" * 2048,
        "{" + '"a":' * 2049 + "null" + "}" * 2049,
        "[" * 200000,
        "{" * 5000,
    ]
)

# Malformed near-valid fragments.
_malformed = st.sampled_from(
    [
        "{}", "[]", "{,}", "[,]", "[1,]", "{,}", '{"a":}', '{"a"}', '{"a" 1}',
        '{"a":1,}', "[1 2]", "[1,,2]", "{:1}", "{1:2}", '{"a":1 "b":2}',
        '{"a":1,,"b":2}', '[,1]', '[1,]', '{"a":1,}', '{"a":1,,"b":2}',
        '"unterminated', '"a\\', '"\\u12"', '"\\uZZZZ"', '"\\x41"',
        "tru", "fals", "nul", "truee", "falsee", "nulll",
        "1abc", "1 garbage", "[]xyz", "{}trailing", "null null",
        '{"a":1}{"b":2}', "[1][2]", "truefalse",
        "  ", "\t\n\r ", "", "   {}   ", "\n[]\n",
        '"\\uD800"', '"\x7f"', '"\x01"',
    ]
)

# ---------- composite recursive value strategy ----------

def _make_value(children):
    return st.one_of(
        _json_string,
        _number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        # obj
        st.one_of(
            st.just("{}"),
            st.lists(
                st.tuples(_json_string, children).map(lambda p: p[0] + ":" + p[1]),
                min_size=1,
                max_size=4,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
            # duplicate keys
            st.tuples(_json_string, children, children).map(
                lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
            ),
            st.just('{"k":0,"k":1}'),
            st.just('{"k":0,"k":1,"k":2}'),
        ),
        # arr
        st.one_of(
            st.just("[]"),
            st.lists(children, min_size=1, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]"),
        ),
    )

_value = st.recursive(
    st.one_of(_json_string, _number, st.sampled_from(["true", "false", "null"])),
    _make_value,
    max_leaves=20,
)

# ---------- top-level strategy ----------

_valid = _value

_with_ws = st.tuples(
    st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "]),
    _value,
    st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "]),
).map(_join)

_trailing = st.tuples(
    _value,
    st.sampled_from(["abc", " garbage", "xyz", "null", "[]", "{}", "1", "  // hi", " /* x */", "\x01"]),
).map(_join)

strategy = st.one_of(
    _valid,
    _with_ws,
    _trailing,
    _malformed,
    _deep_bracket,
    _very_deep,
    _json_string,
    _number,
)
```