Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- basic leaf strategies ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.lists(st.sampled_from(_hex), min_size=4, max_size=4).map("".join)

_escapes_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_unicode_escapes = st.one_of(
    _hex4().map(lambda h: "\\u" + h),
    st.sampled_from(["\\u0000", "\\u001f", "\\u007f", "\\u0080", "\\u00ff",
                     "\\u07ff", "\\u0800", "\\uffff", "\\uD800", "\\uDBFF",
                     "\\uDC00", "\\uDFFF", "\\uD83D\\uDE00", "\\uD800\\uD800"]),
)

# safe code points: printable-ish, avoid raw NUL and control chars
# Also include raw control characters and slash so serialization branches are hit.
_safe_chars = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7e),
    st.characters(min_codepoint=0xa0, max_codepoint=0x2fff),
    st.sampled_from([" ", "\t", "\n", "\r"]),
    # raw control chars and slash to exercise json_serialize_string escape branches
    st.characters(min_codepoint=0x00, max_codepoint=0x1f),
    st.just("/"),
)

_string_body = st.one_of(
    _safe_chars,
    _escapes_simple,
    _unicode_escapes,
)

def _string():
    return st.lists(_string_body, min_size=0, max_size=12).map(lambda xs: '"' + "".join(xs) + '"')

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=10**18, max_value=10**400).map(str),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**20).map(lambda n: "." + str(n)),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(st.sampled_from(["e", "E"]),
              st.sampled_from(["", "+", "-"]),
              st.integers(min_value=0, max_value=400).map(str)).map("".join),
    st.sampled_from(["e309", "E309", "e-309", "e400", "e-400", "e9999", "e-9999",
                     "e308", "e-308", "e000", "e+000"]),
)

def _number():
    return st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        _frac,
        _exp,
    ).map("".join)

# ---------- malformed number-ish fragments ----------

_malformed_num = st.sampled_from([
    "-", "-.", "+1", "+", ".5", "-.5", "01", "00", "1.", "1.e5", "1e", "1e+",
    "--1", "1..2", "1e1e1", "0x10", "Infinity", "-Infinity", "NaN", "1_000",
])

# ---------- recursive structure ----------

_json_str = _string()
_json_num = _number()

_leaf = st.one_of(
    _json_str,
    _json_num,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t "])

def _obj(items):
    # items: list of (key_str, value_str) already rendered
    def render(pairs):
        if not pairs:
            return "{}"
        inner = ",".join(k + ":" + v for (k, v) in pairs)
        return "{" + inner + "}"
    return items.map(render)

def _arr(items):
    def render(vals):
        if not vals:
            return "[]"
        return "[" + ",".join(vals) + "]"
    return items.map(render)

# depth control: concentrate near 2048
_depth_choices = st.one_of(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=8, max_value=64),
    st.integers(min_value=64, max_value=512),
    st.integers(min_value=1800, max_value=2050),
)

def _deep_array(depth):
    # build nested arrays with a leaf at the center
    leaf = _leaf
    return leaf.map(lambda v: "[" * depth + v + "]" * depth)

def _deep_object(depth):
    leaf = _leaf
    return leaf.map(lambda v: '{"k":' * depth + v + "}" * depth)

_deep = st.one_of(
    _depth_choices.flatmap(_deep_array),
    _depth_choices.flatmap(_deep_object),
)

_base_value = st.one_of(_leaf, _deep)

def _pair():
    return st.tuples(_json_str, _base_value).map(lambda kv: kv[0] + ":" + kv[1])

def _obj_pairs():
    return st.lists(_pair(), min_size=0, max_size=6).map(
        lambda ps: "{" + ",".join(ps) + "}"
    )

def _arr_vals():
    return st.lists(_base_value, min_size=0, max_size=6).map(
        lambda vs: "[" + ",".join(vs) + "]"
    )

_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        children.map(lambda v: "{" + '"k":' + v + "}"),
        children.map(lambda v: "[" + v + "]"),
        st.lists(children, min_size=0, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(st.tuples(_json_str, children), min_size=0, max_size=6).map(
            lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}"
        ),
    ),
    max_leaves=20,
)

# ---------- edge-case / malformed whole documents ----------

_duplicate_keys = st.lists(
    st.tuples(_json_str, _base_value), min_size=2, max_size=5
).map(lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}")

# strings with raw control characters / slashes to exercise serialization paths
_serialize_stress_string = st.lists(
    st.one_of(
        st.characters(min_codepoint=0x00, max_codepoint=0x1f),
        st.just("/"),
        st.just('"'),
        st.just("\\"),
        st.characters(min_codepoint=0x20, max_codepoint=0x7e),
    ),
    min_size=0, max_size=16,
).map(lambda xs: '"' + "".join(xs) + '"')

_serialize_doc = st.lists(
    _serialize_stress_string, min_size=0, max_size=6
).map(lambda vs: "[" + ",".join(vs) + "]")

# Documents designed to exercise serialize/validate/equals/deep-copy paths.
# These are valid JSON that a parser will accept and then re-serialize.
_roundtrip_string = st.lists(
    st.one_of(
        st.characters(min_codepoint=0x00, max_codepoint=0x1f),
        st.just("/"),
        st.just('"'),
        st.just("\\"),
        st.just("\b"),
        st.just("\f"),
        st.just("\n"),
        st.just("\r"),
        st.just("\t"),
        st.characters(min_codepoint=0x20, max_codepoint=0x7e),
        st.characters(min_codepoint=0xa0, max_codepoint=0x2fff),
    ),
    min_size=0, max_size=24,
).map(lambda xs: '"' + "".join(xs) + '"')

_roundtrip_value = st.recursive(
    st.one_of(
        _roundtrip_string,
        _number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    ),
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=5).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(st.tuples(_roundtrip_string, children), min_size=0, max_size=5).map(
            lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}"
        ),
    ),
    max_leaves=12,
)

_roundtrip_doc = st.one_of(
    _roundtrip_value,
    # documents specifically rich in escape-triggering characters
    st.lists(_roundtrip_string, min_size=1, max_size=8).map(
        lambda vs: "[" + ",".join(vs) + "]"
    ),
    st.lists(_roundtrip_string, min_size=1, max_size=8).map(
        lambda vs: "{" + ",".join('"k%d":%s' % (i, v) for i, v in enumerate(vs)) + "}"
    ),
    # all control chars packed into one string
    st.just('"' + "".join(chr(c) for c in range(0x20)) + '"'),
    st.just('["' + "".join(chr(c) for c in range(0x20)) + '"]'),
    st.just('{"k":"' + "".join(chr(c) for c in range(0x20)) + '"}'),
    st.just('"/' + '"'),
    st.just('["/","\\\\","\\"","\\b","\\f","\\n","\\r","\\t"]'),
    # nested structures for deep-copy / equals
    st.just('{"a":{"b":{"c":[1,2,3,{"d":null}]}}}'),
    st.just('[{"a":1},{"a":1},{"a":2}]'),
    st.just('[[[[["x"]]]]]'),
    st.just('{"a":[true,false,null,1,-2.5e10,"s"]}'),
)

_malformed_doc = st.one_of(
    # double commas
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just('{"a":1,,"b":2}'),
    st.just("[1,2,]"),
    st.just('{"a":1,}'),
    # missing colons
    st.just('{"a" 1}'),
    st.just('{"a"}'),
    st.just('{a:1}'),
    # unterminated strings
    st.just('"abc'),
    st.just('{"a":"b'),
    st.just('["x'),
    # leading +/.5/01
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("-"),
    st.just("-."),
    st.just("1."),
    # stray brackets
    st.just("]"),
    st.just("}"),
    st.just("[}"),
    st.just("{]"),
    # trailing content after a value
    st.just("1abc"),
    st.just("[]xyz"),
    st.just('{"a":1} trailing'),
    st.just("null null"),
    st.just("truefalse"),
    # empty / whitespace
    st.just(""),
    st.just("   "),
    st.just("\t\n\r "),
    # unicode / control escapes inside strings
    st.just('"\\u0000"'),
    st.just('"\\uD800"'),
    st.just('"\\uD800\\uDC00"'),
    st.just('"a\\u0000b"'),
    st.just('"\\u001f\\u007f"'),
    # extreme numbers
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-9999"),
    st.just("1" + "0" * 400),
    st.just("0." + "0" * 400 + "1"),
    # lone sign
    st.just("-"),
    st.just("+"),
    st.just("."),
)

# ---------- compose ----------

# Dedicated serialization stress: valid JSON documents whose strings contain
# every character that json_serialize_string has a special branch for.
# This targets json_serialize_string, json_serialize_to_buffer_r,
# json_value_deep_copy, json_value_equals, and json_validate.
_all_ctrl_str = '"' + "".join(chr(c) for c in range(0x20)) + '"'
_all_ctrl_str_slash = '"' + "".join(chr(c) for c in range(0x20)) + '/"'

_serialize_roundtrip = st.one_of(
    # single string containing every control char + special chars
    st.just(_all_ctrl_str),
    st.just(_all_ctrl_str_slash),
    st.just('[' + _all_ctrl_str + ']'),
    st.just('{"k":' + _all_ctrl_str + '}'),
    # every special escape char individually
    st.just('["\\"","\\\\","\\b","\\f","\\n","\\r","\\t","/","\\u0000","\\u0001","\\u001f"]'),
    # nested structures mixing strings with all special chars
    st.just('{"a":[{"b":"\\u0000\\u0001\\u001f"},{"c":"\\\\\\"/"}],"d":"\\b\\f\\n\\r\\t"}'),
    st.just('[{"k":"' + _all_ctrl_str[1:-1] + '"},{"k":"x/y"}]'),
    # deep nesting for deep_copy / equals
    st.just('{"a":{"b":{"c":{"d":{"e":[1,2,{"f":"g"}]}}}}}'),
    st.just('[[[[[[[["deep"]]]]]]]]'),
    st.just('[{"a":1},{"a":1},{"a":1}]'),
    st.just('{"x":[1,"1",true,null,1.0]}'),
    # strings with high unicode and slash
    st.just('["\\u00ff\\u07ff\\u0800\\uffff","/","//"]'),
)

_document = st.one_of(
    _value,
    _malformed_doc,
    _malformed_num,
    _duplicate_keys,
    _obj_pairs(),
    _arr_vals(),
    _serialize_doc,
    _roundtrip_doc,
    _serialize_roundtrip,
    st.just("{}"),
    st.just("[]"),
    st.tuples(_ws, _value, _ws).map("".join),
)

strategy = _document
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 72.28,
  "region_coverage_pct": 83.36,
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