Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_SAFE = st.characters(
    blacklist_categories=("Cc", "Cs"),
    blacklist_characters='"\\',
)

_ESC = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.builds(
        lambda h: "\\u" + h,
        st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
    ),
    # surrogate escapes
    st.sampled_from([
        "\\ud800", "\\udfff", "\\udc00", "\\ud83d\\ude00",
        "\\uD800\\uDC00", "\\u0000", "\\u001f", "\\u007f",
    ]),
)

_str_char = st.one_of(_SAFE, _ESC)


def _str_body():
    return st.lists(_str_char, min_size=0, max_size=8).map("".join)


def _quoted():
    return _str_body().map(lambda s: '"' + s + '"')


# ---------- numbers ----------

_EXTREME_NUMBERS = st.sampled_from([
    "0", "-0", "1", "-1", "1e309", "-1e309", "1e-309", "1e308",
    "1.7976931348623157e308", "1e400", "-1e400", "1e-400",
    "0.0", "-0.0", "123456789012345678901234567890",
    "9" * 40, "1" + "0" * 300, "1e" + "9" * 5,
    "1E+10", "1e-10", "0e0", "0e999", "1e01", "123.456e-789",
    "1.0e+308", "5e-324", "2.2250738585072014e-308",
])

_normal_number = st.builds(
    lambda sign, ip, frac, exp: sign + ip + frac + exp,
    st.sampled_from(["", "-"]),
    st.one_of(
        st.just("0"),
        st.from_regex(r"[1-9][0-9]{0,6}", fullmatch=True),
    ),
    st.one_of(
        st.just(""),
        st.from_regex(r"\.[0-9]{1,6}", fullmatch=True),
    ),
    st.one_of(
        st.just(""),
        st.builds(
            lambda e, s, d: e + s + d,
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.from_regex(r"[0-9]{1,4}", fullmatch=True),
        ),
    ),
)

_number = st.one_of(_EXTREME_NUMBERS, _normal_number)

# ---------- malformed fragments ----------

_MALFORMED = st.sampled_from([
    "", ",", ",,", ":", "::", "{,}", "[,]", "{,}", '{"a" 1}',
    '{"a":}', '{"a":1,}', "[1,]", "[1,,2]", '"unterminated',
    "+1", ".5", "01", "-", "-.", "1.", "truex", "nul", "tru",
    "fals", '{"a":1 "b":2}', "[1 2]", "{", "}", "[", "]",
    '{"a"::1}', '[,1]', '{"a":1,,"b":2}', '"\x00"',
    "1e", "1e+", "0x10", "Infinity", "NaN", "-Infinity",
    '{"a":1}garbage', "[]xyz", "1abc", "1 garbage",
])

# ---------- recursive JSON ----------

def _make_value(draw, children):
    leaf = st.one_of(
        _quoted(),
        _number,
        st.sampled_from(["true", "false", "null"]),
    )
    if children is None:
        return draw(leaf)
    return draw(st.one_of(leaf, children))


def _make_arr(draw, value):
    n = draw(st.integers(min_value=0, max_value=4))
    items = [draw(value) for _ in range(n)]
    return "[" + ",".join(items) + "]"


def _make_obj(draw, value):
    n = draw(st.integers(min_value=0, max_value=4))
    keys = draw(st.lists(_quoted(), min_size=n, max_size=n, unique=True))
    pairs = [k + ":" + draw(value) for k in keys]
    return "{" + ",".join(pairs) + "}"


def _build_value():
    return st.recursive(
        st.one_of(
            _quoted(),
            _number,
            st.sampled_from(["true", "false", "null"]),
        ),
        lambda children: st.one_of(
            children.flatmap(lambda v: st.just(_make_arr_from(v))),
            children.flatmap(lambda v: st.just(_make_obj_from(v))),
        ),
        max_leaves=20,
    )


def _make_arr_from(v):
    return "[" + v + "]"


def _make_obj_from(v):
    return '{"a":' + v + "}"


_value = _build_value()

# ---------- deep nesting near 2048 ----------

def _deep():
    return st.integers(min_value=1, max_value=2100).flatmap(
        lambda d: st.sampled_from([
            "[" * d + "]" * d,
            "[" * d + "0" + "]" * d,
            '{"a":' * d + "0" + "}" * d,
            "[" * d,  # unterminated deep
            "[" * (d - 1) + "]" * (d - 1) if d > 0 else "[]",
        ])
    )


_deep_strategy = st.one_of(
    _deep(),
    st.integers(min_value=2040, max_value=2060).flatmap(
        lambda d: st.just("[" * d + "]" * d)
    ),
)

# ---------- duplicate keys ----------

def _dup_keys():
    return st.builds(
        lambda k, a, b: '{"' + k + '":' + a + ',"' + k + '":' + b + "}",
        st.text(alphabet="abc", min_size=1, max_size=3),
        _number,
        _number,
    )


# ---------- top-level assembly ----------

_json_value = st.one_of(
    _value,
    _deep_strategy,
    _dup_keys(),
    _MALFORMED,
)

# trailing content (accepted by parser)
def _trailing():
    return st.builds(
        lambda v, t: v + t,
        _value,
        st.sampled_from(["", " ", "x", "garbage", "1abc", "[]xyz", "\n\t"]),
    )


_final = st.one_of(
    _json_value,
    _trailing(),
    _deep_strategy,
    _dup_keys(),
    _MALFORMED,
)

# whitespace variants around a value
def _ws_around():
    return st.builds(
        lambda a, v, b: a + v + b,
        st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
        _value,
        st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
    )


strategy = st.one_of(_final, _ws_around()).filter(lambda s: "\x00" not in s)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 72.28,
  "region_coverage_pct": 83.21,
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