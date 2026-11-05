Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

def _hex_digits(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)

# escapes that are valid inside a JSON string
_escapes = st.one_of(
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    st.builds(lambda h: "\\u" + h, _hex_digits(4)),
    # surrogate escapes (lone and paired)
    st.builds(lambda h: "\\u" + h, st.sampled_from(
        ["D800", "DBFF", "DC00", "DFFF", "d800", "dc00", "D834", "DD1E"])),
    st.builds(lambda a, b: "\\u" + a + "\\u" + b,
              _hex_digits(4), _hex_digits(4)),
    # embedded NUL escape (six chars, safe)
    st.just("\\u0000"),
    # control-char escapes that exercise the serializer's \\u00XX cases
    st.builds(lambda h: "\\u00" + h, st.text(alphabet="0123456789abcdef", min_size=2, max_size=2)),
)

# safe code points (no raw control chars, no raw NUL, no quote/backslash)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) >= 0x20 or c in "\t\n\r")

# raw control characters as literal bytes inside a string body are invalid
# JSON, but they exercise the serializer / validator's handling of them when
# they appear in decoded values; keep them rare and only via escapes above.

_string_body = st.lists(
    st.one_of(_escapes, _safe_char), max_size=12
).map("".join)

_json_string = _string_body.map(lambda b: '"' + b + '"')

# strings specifically crafted to hit every branch of json_serialize_string:
# quotes, backslashes, slashes, all \b\f\n\r\t, NUL, and each \x01..\x1f.
_serialize_probe_chars = "".join(chr(c) for c in range(0x00, 0x20))
_serialize_probe = st.one_of(
    st.just('"' + "".join(
        "\\u%04x" % c for c in range(0x00, 0x20)
    ) + '"'),
    st.just('"' + "".join(
        "\\u%04x" % c for c in range(0x20, 0x7f)
    ) + '"'),
    st.just('"\\"\\\\\\/\\b\\f\\n\\r\\t"'),
    st.just('"a/b/c"'),
    st.just('"\\/\\/\\/"'),
    st.just('"' + "".join("\\u%04x" % c for c in range(0x00, 0x20)) + 'x/y"'),
)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d, r: d + r,
              st.sampled_from("123456789"),
              st.text(alphabet="0123456789", max_size=6)),
)

_frac = st.builds(lambda d: "." + d, _digits)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

_number = st.builds(
    lambda sign, ip, fr, ex: sign + ip + fr + ex,
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

# extreme magnitudes / exponents
_extreme_number = st.one_of(
    st.just("1e309"), st.just("-1e309"), st.just("1e-309"),
    st.just("1e999999"), st.just("-1e999999"),
    st.just("1" + "0" * 400),
    st.just("0." + "0" * 300 + "1"),
    st.just("1e308"), st.just("1.7976931348623157e308"),
    st.just("-1.7976931348623157e308"), st.just("1e-400"),
    st.builds(lambda d: "1e" + d, st.text(alphabet="0123456789", min_size=1, max_size=10)),
    st.builds(lambda d: "-1e-" + d, st.text(alphabet="0123456789", min_size=1, max_size=10)),
)

# malformed numeric-ish tokens
_bad_number = st.one_of(
    st.just("+1"), st.just(".5"), st.just("1."), st.just("01"),
    st.just("-01"), st.just("00"), st.just("-"), st.just("-."),
    st.just("1e"), st.just("1e+"), st.just("--1"), st.just("1..2"),
    st.builds(lambda d: "0" + d, _digits),
)

# ---------- malformed fragments ----------

_unterminated_string = st.builds(
    lambda b: '"' + b,
    _string_body,
)

_malformed = st.one_of(
    _unterminated_string,
    st.just("{"),
    st.just("["),
    st.just("}"),
    st.just("]"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just('{"a":1,}'),
    st.just('[1,]'),
    st.just('[,]'),
    st.just('[1,,2]'),
    st.just('{,}'),
    st.just('{"a":1 "b":2}'),
    st.just('{"a" 1}'),
    st.just('{"a":1,,"b":2}'),
    st.just('"\\u12"'),
    st.just('"\\u"'),
    st.just('"\\q"'),
    st.just('tru'),
    st.just('nul'),
    st.just('fals'),
    st.just('True'),
)

# ---------- recursive values ----------

_leaf = st.one_of(
    _json_string,
    _serialize_probe,
    _number,
    _extreme_number,
    st.sampled_from(["true", "false", "null"]),
    _bad_number,
    _malformed,
)

_key = st.one_of(
    _json_string,
    st.just('""'),
    st.just('"k"'),
    st.just('"key"'),
    st.just('"\\u0000"'),
    st.just('"\\uD800"'),
    st.just('"a/b"'),
    st.just('"\\u0001\\u001f"'),
)

def _pair(key, value):
    return key + ":" + value

def _obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _arr(items):
    return "[" + ",".join(items) + "]"

# value strategy (recursive)
_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        st.lists(st.tuples(_key, children), max_size=4)
        .map(lambda ps: _obj([_pair(k, v) for k, v in ps])),
        st.lists(children, max_size=5).map(_arr),
    ),
    max_leaves=40,
)

# ---------- deep nesting near the 2048 cap ----------

_deep_arr = st.builds(
    lambda depth, inner: "[" * depth + inner + "]" * depth,
    st.integers(min_value=0, max_value=2060),
    st.one_of(st.just(""), st.just("0"), st.just("null")),
)

_deep_obj = st.builds(
    lambda depth: '{"a":' * depth + "0" + "}" * depth,
    st.integers(min_value=0, max_value=2060),
)

_deep = st.one_of(_deep_arr, _deep_obj)

# ---------- top-level: value, with optional trailing content ----------

_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("garbage"),
    st.just("abc"),
    st.just("[]xyz"),
    st.just(" /* c */"),
    st.just("//c"),
    st.just("\t\r\n"),
    st.just("1"),
)

_top_value = st.one_of(_value, _deep, _leaf, _malformed, _serialize_probe)

strategy = st.builds(
    lambda v, t: v + t,
    _top_value,
    _trailing,
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 73.91,
  "region_coverage_pct": 83.82,
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