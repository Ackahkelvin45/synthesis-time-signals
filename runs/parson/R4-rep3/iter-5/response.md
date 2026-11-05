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

# A single string that contains every switch case of json_serialize_string
# in one go: quote, backslash, all named escapes, all control chars, slash.
_every_escape_char_str = (
    '"'
    + '\\"'
    + "\\\\"
    + "\\b"
    + "\\f"
    + "\\n"
    + "\\r"
    + "\\t"
    + "".join(chr(c) for c in range(0x20))
    + "/"
    + '"'
)

# A string that contains every raw byte 0x00..0x1f plus quote, backslash, slash
# as raw characters (not escapes) so json_serialize_string hits every case.
_raw_special_str = '"' + "".join(chr(c) for c in range(0x20)) + '"\\/' + '"'

_serialize_roundtrip = st.one_of(
    # single string containing every control char + special chars
    st.just(_all_ctrl_str),
    st.just(_all_ctrl_str_slash),
    st.just(_raw_special_str),
    st.just(_every_escape_char_str),
    st.just('[' + _all_ctrl_str + ']'),
    st.just('[' + _raw_special_str + ']'),
    st.just('{"k":' + _all_ctrl_str + '}'),
    st.just('{"k":' + _raw_special_str + '}'),
    # every special escape char individually (as raw chars in a string)
    st.just('["\\"","\\\\","\\b","\\f","\\n","\\r","\\t","/","\\u0000","\\u0001","\\u001f"]'),
    # raw quote, backslash, slash and each control byte in a JSON string
    st.just('["' + '"' + '","' + "\\" + '","' + "/" + '","' + "\x00" + '","' + "\x01" + '","' + "\x1f" + '"]'),
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
    # randomized strings that combine every escape-triggering char
    st.lists(
        st.one_of(
            st.characters(min_codepoint=0x00, max_codepoint=0x1f),
            st.just('"'),
            st.just("\\"),
            st.just("/"),
            st.just("\b"),
            st.just("\f"),
            st.just("\n"),
            st.just("\r"),
            st.just("\t"),
        ),
        min_size=1, max_size=32,
    ).map(lambda xs: '"' + "".join(xs) + '"'),
    # randomized arrays/objects of such strings
    st.lists(
        st.lists(
            st.one_of(
                st.characters(min_codepoint=0x00, max_codepoint=0x1f),
                st.just('"'),
                st.just("\\"),
                st.just("/"),
            ),
            min_size=0, max_size=16,
        ).map(lambda xs: '"' + "".join(xs) + '"'),
        min_size=1, max_size=4,
    ).map(lambda vs: "[" + ",".join(vs) + "]"),
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