```python
from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

def _unicode_escape():
    # Valid \uXXXX, plus lone-surrogate and high/low surrogate escapes.
    return st.one_of(
        _hex4().map(lambda h: "\\u" + h),
        st.sampled_from(
            [
                "\\ud800", "\\udbff", "\\udc00", "\\udfff",
                "\\uD834", "\\uDD1E", "\\u0000", "\\u001f",
                "\\uFFFF", "\\u0000",
            ]
        ),
    )

_simple_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

# Raw characters permitted (and some disallowed) inside strings.
# Include raw NUL and control bytes deliberately.
_raw_chars = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
    st.sampled_from(
        ["\x00", "\x01", "\x08", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]
    ),
)

_string_body_piece = st.one_of(
    _raw_chars,
    _simple_escapes,
    _unicode_escape(),
    # invalid escapes / odd sequences to stress the escape decoder
    st.sampled_from(
        ["\\x", "\\u", "\\u12", "\\u123", "\\U0041", "\\'", "\\0"]
    ),
)

def _string():
    return st.lists(_string_body_piece, max_size=12).map(
        lambda parts: '"' + "".join(parts) + '"'
    )

# Numbers: valid and edge-case magnitudes, plus near-valid malformed forms.
_valid_numbers = st.one_of(
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    st.sampled_from(
        [
            "0", "-0", "1", "-1", "01", "-01", "007",
            "1.", "-1.", "0.", "1.0", "-1.5", "3.141592653589793",
            "1e309", "-1e309", "1e-999", "1E+308", "1e01", "0e0",
            "1.7976931348623157e308", "5e-324",
            "1e400", "1e999999", "-1e999999",
            "0x10", "0xDEADBEEF", "-0xFF", "0X1f",
            "123456789012345678901234567890",
            "1.000000000000000000001",
        ]
    ),
)

_malformed_numbers = st.sampled_from(
    ["-", "+1", ".5", "-.5", "1..2", "1e", "1e+", "1e-", "e5",
     "NaN", "Infinity", "-Infinity", "0x", "1.2.3", "--1"]
)

_number = st.one_of(_valid_numbers, _malformed_numbers)

_literal = st.sampled_from(["true", "false", "null", "True", "NULL"])

# ---------- recursive structure ----------

_ws = st.sampled_from(["", "", "", " ", "\t", "\n", "\r\n", "  "])

def _key():
    return _string()

def _pair(value_strategy):
    return st.tuples(_key(), _ws, st.sampled_from([":", "", "::"]), _ws, value_strategy).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

def _obj(value_strategy):
    pairs = st.lists(_pair(value_strategy), max_size=4)
    return st.tuples(_ws, pairs, _ws).map(
        lambda t: "{" + t[0] + ("," + t[0]).join(t[1]) + t[2] + "}"
    )

def _arr(value_strategy):
    items = st.lists(value_strategy, max_size=5)
    return st.tuples(_ws, items, _ws).map(
        lambda t: "[" + t[0] + ("," + t[0]).join(t[1]) + t[2] + "]"
    )

# Malformed structural fragments.
_malformed_obj = st.sampled_from(
    ["{", "}", "{,}", "{,}", '{"a"}', '{"a":}', '{"a":1,}', '{"a":1,,}',
     '{"a" 1}', '{a:1}', "{'a':1}", '{"a":1,,"b":2}']
)
_malformed_arr = st.sampled_from(
    ["[", "]", "[,]", "[1,]", "[,1]", "[1,,2]", "[1 2]", "['a']", "[1,]"]
)
_unterminated = st.sampled_from(
    ['"abc', '"', '"\\', '"\\u12', '{"a": "b', '[1, 2', '{"a"']
)

def _value(depth):
    # depth is a search-strategy-independent recursion depth handled by st.recursive
    return st.recursive(
        st.one_of(
            _string(),
            _number,
            _literal,
            _malformed_obj,
            _malformed_arr,
            _unterminated,
        ),
        lambda children: st.one_of(
            _obj(children),
            _arr(children),
        ),
        max_leaves=20,
    )

# ---------- deep nesting near the 1000-level limit ----------

_deep_depth = st.integers(min_value=990, max_value=1002)

def _deep_nested():
    def build(t):
        depth, kind, inner = t
        if kind == 0:
            return "[" * depth + inner + "]" * depth
        else:
            return '{"k":' * depth + inner + "}" * depth

    return st.tuples(
        _deep_depth,
        st.sampled_from([0, 1]),
        st.one_of(_string(), _number, _literal, st.just("")),
    ).map(build)

# ---------- top-level assembly ----------

def _with_bom(s):
    return st.booleans().map(lambda b: ("\ufeff" + s) if b else s)

def _with_trailing(s):
    return st.tuples(
        s,
        st.sampled_from(["", "", "abc", " 1 2", "\x00", "\n[]", "garbage", "  "]),
    ).map(lambda t: t[0] + t[1])

_base_value = _value(0)

_full = st.one_of(
    _base_value,
    _deep_nested(),
    _with_trailing(_base_value),
    _with_bom(_base_value),
    _with_bom(_with_trailing(_base_value)),
    # empty / whitespace-only / bare tokens
    st.sampled_from(
        [
            "", " ", "\n", "\ufeff", "\x00", "{}", "[]",
            "null", "true", "false", "NaN", "Infinity",
            "-", "+1", ".5", "01", "1.", "0x10",
            '{"a":1,"a":2}', '{"a":1,"a":2,"a":3}',
            '"\\ud800"', '"\\ud834\\udd1e"', '"\x00"', '"\x01\x02"',
            '{"":""}', '[[[[[]]]]]', '{"a":{"b":{"c":[]}}}',
        ]
    ),
)

strategy = _full
```