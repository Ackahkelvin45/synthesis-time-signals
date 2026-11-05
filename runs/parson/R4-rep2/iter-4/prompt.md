Here is the current Hypothesis strategy:

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

# ---------- serialize coverage: strings rich in escapable chars ----------

# Characters that exercise every branch of json_serialize_string:
# quotes, backslashes, all control chars (incl. \x00 through \x1f), and '/'.
_serialize_special = st.sampled_from(
    ['"', "\\", "/", "\x00", "\x01", "\x02", "\x03", "\x04", "\x05",
     "\x06", "\x07", "\x08", "\x09", "\x0a", "\x0b", "\x0c", "\x0d",
     "\x0e", "\x0f", "\x10", "\x11", "\x12", "\x13", "\x14", "\x15",
     "\x16", "\x17", "\x18", "\x19", "\x1a", "\x1b", "\x1c", "\x1d",
     "\x1e", "\x1f", "a", "Z", " ", "\u00e9", "\u4e2d"]
)

# A raw string (JSON-escaped) whose decoded content hits serialize branches.
_serialize_string = st.lists(_serialize_special, min_size=0, max_size=16).map(
    lambda chars: '"' + "".join(
        {"\"": '\\"', "\\": "\\\\"}.get(c, c) for c in chars
    ) + '"'
)

# ---------- top-level combination ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "\n", "[]"])).map(_join)

_value_top = st.one_of(
    _value,
    _deep,
    _malformed,
    _serialize_string,
)

# avoid raw NUL bytes in final output
_final = _value_top.map(lambda s: s.replace("\x00", ""))
_final = st.one_of(_final, _with_trailing(_value))

strategy = _final
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 73.64,
  "region_coverage_pct": 85.04,
  "least_covered_functions": [
    "json_serialize_string (0% of branches)",
    "json_serialize_to_buffer_r (0% of branches)",
    "json_value_deep_copy (0% of branches)",
    "json_value_equals (0% of branches)",
    "json_validate (0% of branches)"
  ],
  "least_covered_function_source": "static int json_serialize_string(const char *string, size_t len, char *buf) {\n    size_t i = 0;\n    char c = '\\0';\n    int written = -1, written_total = 0;\n    APPEND_STRING(\"\\\"\");\n    for (i = 0; i < len; i++) {\n        c = string[i];\n        switch (c) {\n            case '\\\"': APPEND_STRING(\"\\\\\\\"\"); break;\n            case '\\\\': APPEND_STRING(\"\\\\\\\\\"); break;\n            case '\\b': APPEND_STRING(\"\\\\b\"); break;\n            case '\\f': APPEND_STRING(\"\\\\f\"); break;\n            case '\\n': APPEND_STRING(\"\\\\n\"); break;\n            case '\\r': APPEND_STRING(\"\\\\r\"); break;\n            case '\\t': APPEND_STRING(\"\\\\t\"); break;\n            case '\\x00': APPEND_STRING(\"\\\\u0000\"); break;\n            case '\\x01': APPEND_STRING(\"\\\\u0001\"); break;\n            case '\\x02': APPEND_STRING(\"\\\\u0002\"); break;\n            case '\\x03': APPEND_STRING(\"\\\\u0003\"); break;\n            case '\\x04': APPEND_STRING(\"\\\\u0004\"); break;\n            case '\\x05': APPEND_STRING(\"\\\\u0005\"); break;\n            case '\\x06': APPEND_STRING(\"\\\\u0006\"); break;\n            case '\\x07': APPEND_STRING(\"\\\\u0007\"); break;\n            /* '\\x08' duplicate: '\\b' */\n            /* '\\x09' duplicate: '\\t' */\n            /* '\\x0a' duplicate: '\\n' */\n            case '\\x0b': APPEND_STRING(\"\\\\u000b\"); break;\n            /* '\\x0c' duplicate: '\\f' */\n            /* '\\x0d' duplicate: '\\r' */\n            case '\\x0e': APPEND_STRING(\"\\\\u000e\"); break;\n            case '\\x0f': APPEND_STRING(\"\\\\u000f\"); break;\n            case '\\x10': APPEND_STRING(\"\\\\u0010\"); break;\n            case '\\x11': APPEND_STRING(\"\\\\u0011\"); break;\n            case '\\x12': APPEND_STRING(\"\\\\u0012\"); break;\n            case '\\x13': APPEND_STRING(\"\\\\u0013\"); break;\n            case '\\x14': APPEND_STRING(\"\\\\u0014\"); break;\n            case '\\x15': APPEND_STRING(\"\\\\u0015\"); break;\n            case '\\x16': APPEND_STRING(\"\\\\u0016\"); break;\n            case '\\x17': APPEND_STRING(\"\\\\u0017\"); break;\n            case '\\x18': APPEND_STRING(\"\\\\u0018\"); break;\n            case '\\x19': APPEND_STRING(\"\\\\u0019\"); break;\n            case '\\x1a': APPEND_STRING(\"\\\\u001a\"); break;\n            case '\\x1b': APPEND_STRING(\"\\\\u001b\"); break;\n            case '\\x1c': APPEND_STRING(\"\\\\u001c\"); break;\n            case '\\x1d': APPEND_STRING(\"\\\\u001d\"); break;\n            case '\\x1e': APPEND_STRING(\"\\\\u001e\"); break;\n            case '\\x1f': APPEND_STRING(\"\\\\u001f\"); break;\n            case '/':\n                if (parson_escape_slashes) {\n                    APPEND_STRING(\"\\\\/\");  /* to make json embeddable in xml\\/html */\n                } else {\n                    APPEND_STRING(\"/\");\n                }\n                break;\n            default:\n                if (buf != NULL) {\n                    buf[0] = c;\n                    buf += 1;\n                }\n                written_total += 1;\n                break;\n        }\n    }\n    APPEND_STRING(\"\\\"\");\n    return written_total;\n}"
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.