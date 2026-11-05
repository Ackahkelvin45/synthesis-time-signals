Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map("".join)

# A "safe" character for inside strings: printable ASCII excluding quote and backslash,
# plus a few unicode chars. Never a raw NUL or control char (parser is NUL-terminated).
_safe_chars = st.sampled_from(
    [chr(c) for c in range(0x20, 0x7f) if c not in (0x22, 0x5c)]
    + ["\u00e9", "\u00fc", "\u4e2d", "\u6587", "\U0001F600", "\u2028", "\u007f"]
)

_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = st.tuples(st.just("\\u"), _hex4()).map("".join)

# Surrogate escapes (lone / paired) - these are interesting edge cases.
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\uD834\\uDD1E", "\\u0000"]
)

_string_char = st.one_of(_escapes, _unicode_esc, _surrogate_esc, _safe_chars)

def _string_body(max_size=12):
    return st.lists(_string_char, max_size=max_size).map("".join)

_string = st.tuples(st.just('"'), _string_body(), st.just('"')).map("".join)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.text(alphabet="0123456789", max_size=10)).map("".join),
    st.text(alphabet="0123456789", min_size=1, max_size=18),
)

_frac = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=10)).map("".join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map("".join)

_sign = st.sampled_from(["", "-"])

_number = st.one_of(
    # normal numbers
    st.tuples(_sign, _int_part, st.one_of(st.just(""), _frac), st.one_of(st.just(""), _exp)).map("".join),
    # extreme magnitudes / overflow
    st.sampled_from([
        "1e309", "-1e309", "1e400", "-1e400", "1e-400", "1e308", "1.7976931348623157e308",
        "1.8e308", "-1.8e308", "0e0", "0e999999", "1e999999999", "123456789012345678901234567890",
        "-123456789012345678901234567890", "1.0e-999999", "-0", "-0.0", "0.0000000000000000001",
    ]),
    # lone sign (parser quirk: parses as 0)
    st.just("-"),
    # leading + / .5 / 1. / 01 style near-valid
    st.sampled_from(["+1", ".5", "1.", "01", "-01", "+.5", "--1", "1..2", "1e", "1e+", "1e-"]),
)

# ---------- recursive value ----------

_literal = st.sampled_from(["true", "false", "null"])

_json_leaves = st.one_of(_string, _number, _literal)

def _build_value(children):
    return st.one_of(
        _json_leaves,
        st.tuples(st.just("{"), st.just("}")).map("".join),
        st.tuples(st.just("["), st.just("]")).map("".join),
        # object
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_string, st.just(":"), children).map("".join),
                min_size=0, max_size=4,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map("".join),
        # array
        st.tuples(
            st.just("["),
            st.lists(children, min_size=0, max_size=4).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map("".join),
    )

# Base values (depth 0) - small, non-recursive-ish
_base = st.one_of(_json_leaves)

_value = st.recursive(_base, _build_value, max_leaves=40)

# ---------- deep nesting near the 2048 cap ----------

def _deep(depth):
    # depth nested arrays around a leaf value; depth chosen near 2048
    return st.tuples(
        st.just("[" * depth),
        _json_leaves,
        st.just("]" * depth),
    ).map("".join)

def _deep_obj(depth):
    return st.tuples(
        st.just('{"k":' * depth),
        _json_leaves,
        st.just("}" * depth),
    ).map("".join)

_depth_choice = st.sampled_from([0, 1, 2, 100, 1000, 2000, 2047, 2048, 2049, 2050, 2100, 4096])

_deep_value = st.one_of(
    _depth_choice.flatmap(_deep),
    _depth_choice.flatmap(_deep_obj),
)

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    "{,}", "[,]", "[1,,2]", '{"a":1,}', "[1,]", '{"a" 1}', '{"a":}', "{:1}",
    '{"a":1 "b":2}', '"unterminated', '"esc\\', "[1 2]", "{", "}", "[", "]",
    '{"a":1', '[1,2', '"', '\\', "tru", "fals", "nul", "True", "NULL",
    '{"a":1}}', "[[[]]", '{"a":{"b":}}', "1,2", "1 2", "[] []", "{} {}",
    '{"a":1}garbage', "1abc", "[]xyz", "1 garbage", "nullx", "truefalse",
])

# ---------- top-level composition ----------

_trailing = st.tuples(_value, st.text(alphabet=" \t\n\rabc{}[]0123", max_size=8)).map("".join)

_whitespace = st.text(alphabet=" \t\n\r", max_size=6)

def _wrap_ws(v):
    return st.tuples(_whitespace, v, _whitespace).map("".join)

strategy = _wrap_ws(
    st.one_of(
        _value,
        _deep_value,
        _malformed,
        _trailing,
        st.just(""),
        st.just("{}"),
        st.just("[]"),
        st.just('{"a":0,"a":1}'),  # duplicate keys
        st.just('{"k":0,"k":1}'),
        st.just("1e309"),
        st.just("-"),
    )
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 67.93,
  "region_coverage_pct": 81.53,
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