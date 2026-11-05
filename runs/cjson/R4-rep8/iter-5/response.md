```python
from hypothesis import strategies as st
import json

# ---------- building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = _hex4().map(lambda h: "\\u" + h)

_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udbff", "\\udc00", "\\udfff", "\\uD800", "\\uDFFF"]
)

_paired_surrogate = st.tuples(
    st.sampled_from(["\\ud800", "\\ud801", "\\ud83d", "\\udbff"]),
    st.sampled_from(["\\udc00", "\\udc01", "\\ude00", "\\udfff"]),
).map(lambda t: t[0] + t[1])

_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

_safechar = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_string_piece = st.one_of(
    _safechar,
    _simple_esc,
    _unicode_esc,
    _surrogate_esc,
    _paired_surrogate,
    _raw_control,
)

def _make_string():
    return st.lists(_string_piece, max_size=12).map(lambda parts: '"' + "".join(parts) + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map(lambda t: t[0] + t[1]),
    _digits,
    st.just(""),
)

_frac_part = st.one_of(
    st.just(""),
    _digits.map(lambda d: "." + d),
    st.just("."),
)

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits,
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_sign = st.one_of(st.just(""), st.just("-"), st.just("+"))

def _make_number():
    return st.tuples(_sign, _int_part, _frac_part, _exp_part).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-400", "-1e-400",
    "1e999999999", "0." + "0" * 20 + "1",
    "9" * 40, "-" + "9" * 40,
    "123456789012345678901234567890",
    "1e308", "1.7976931348623157e308",
    "0x10", "0xDEADBEEF", "0x", "0xg",
])

_number = st.one_of(_make_number(), _extreme_number)

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null", "NaN", "Infinity", "-Infinity"])

# ---------- recursive values ----------

_key = _make_string()

def _make_pair():
    return st.tuples(_key, st.just(":"), st.deferred(lambda: _value)).map(
        lambda t: t[0] + t[1] + t[2]
    )

def _make_obj():
    return st.tuples(
        st.just("{"),
        st.lists(_make_pair(), max_size=4).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + t[2])

def _make_arr():
    return st.tuples(
        st.just("["),
        st.lists(st.deferred(lambda: _value), max_size=4).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(lambda t: t[0] + t[1] + t[2])

_value = st.deferred(lambda: _value_strategy)

_value_strategy = st.recursive(
    st.one_of(_make_string(), _number, _literal),
    lambda children: st.one_of(_make_obj(), _make_arr()),
    max_leaves=20,
)

# ---------- deep nesting near the 1000 limit ----------

_depth = st.one_of(
    st.just(0),
    st.just(1),
    st.just(2),
    st.integers(min_value=990, max_value=1001),
    st.integers(min_value=0, max_value=50),
)

def _deep_array():
    return _depth.map(lambda d: "[" * d + "]" * d)

def _deep_object():
    return _depth.map(lambda d: '{"a":' * d + "0" + "}" * d)

# ---------- malformed near-valid ----------

_malformed = st.sampled_from([
    "",
    "{",
    "[",
    "}",
    "]",
    ",",
    ":",
    "{},",
    "[,]",
    "[1,]",
    '{"a":1,}',
    '{"a" 1}',
    '{"a":}',
    '{:1}',
    '{"a":1 "b":2}',
    '"unterminated',
    '"\\',
    '"\\u12"',
    '"\\u"',
    '"\\x41"',
    "'single'",
    "{a:1}",
    "{'a':1}",
    "-",
    "+",
    "+1",
    ".5",
    "-.5",
    "1.",
    "01",
    "00",
    "-01",
    "1e",
    "1e+",
    "1e-",
    "1.2.3",
    "1 2",
    "1abc",
    "truefalse",
    "nulll",
    "tru",
    "fals",
    "NaN",
    "Infinity",
    "-Infinity",
    "\\u0000",
    "\x00",
    "\xef\xbb\xbf1",
    "\ufeff1",
    "1\x00",
    '{"a":1}\x00',
    "[1,2,3]extra",
    '{"a":1}{"b":2}',
    "1,2",
])

# ---------- combine ----------

def _join(t):
    return "".join(t)

_roundtrip_pair = st.tuples(_value_strategy, st.just(" "), _value_strategy).map(_join)
_same_value_pair = _value_strategy.map(lambda v: v + " " + v)

def _compare_pair():
    a = _value_strategy
    b = _value_strategy
    return st.tuples(a, st.just(" "), b).map(_join)

_compare_variants = st.one_of(
    st.tuples(
        st.lists(_value_strategy, min_size=0, max_size=3),
        st.lists(_value_strategy, min_size=1, max_size=3),
    ).map(lambda t: "[" + ",".join(t[0]) + "] [" + ",".join(t[1]) + "]"),
    st.tuples(_make_string(), _make_string(), _value_strategy).map(
        lambda t: '{"a":' + t[2] + '} {"' + t[0] + '":' + t[2] + "}"
    ),
    st.tuples(_number, _number).map(lambda t: t[0] + " " + t[1]),
    st.tuples(_make_string(), _make_string()).map(lambda t: t[0] + " " + t[1]),
    st.tuples(_value_strategy, _literal).map(lambda t: t[0] + " " + t[1]),
)

_print_exercisers = st.one_of(
    st.just("{}"),
    st.just("[]"),
    st.just('{"":""}'),
    st.just('{"a":{}}'),
    st.just('[[],[[]]]'),
    st.just('{"n":0}'),
    st.just('{"n":-0.0}'),
    st.just('{"n":1.5e10}'),
    st.just('{"n":1e-7}'),
    st.just('{"s":"\\u0000\\u001f\\u007f"}'),
    st.just('{"s":"\\"\\\\\\/\\b\\f\\n\\r\\t"}'),
    st.just('{"s":"\\ud83d\\ude00"}'),
    st.just('{"s":"\\u00e9"}'),
    st.just('{"s":"\\u4e2d"}'),
    st.just('{"a":[1,2,{"b":[true,false,null]}],"c":"x"}'),
    _value_strategy,
)

_print_and_compare_doc = st.one_of(
    _value_strategy.map(lambda v: v + " " + v),
    _value_strategy.map(lambda v: "[" + v + "," + v + "]"),
    _value_strategy.map(lambda v: '{"a":' + v + ',"b":' + v + "}"),
    _value_strategy.map(lambda v: '{"x":' + v + ',"y":[' + v + "]}"),
    st.just('{"a":{},"b":[],"c":0,"d":"","e":null,"f":true,"g":false}'),
    st.just('[{"a":1},{"a":1}]'),
    st.just('{"k":{"k":{"k":[]}}}'),
    st.just('{"s":"\\"\\\\\\/\\b\\f\\n\\r\\t\\u0000\\u001f\\u007f\\u00e9"}'),
    st.just('{"s":"\\ud83d\\ude00\\u4e2d"}'),
    st.just('{"n":[0,-0.0,1,-1,1.5,-1.5,1e10,1e-10,123456789012345]}'),
)

# ---------- NEW: dedicated print/compare drivers ----------
# The coverage report shows print_value, print_string_ptr, print_number,
# print_object and cJSON_Compare are completely uncovered. Those entry points
# are only reached when the harness parses a document and then re-prints /
# compares it. We build documents that *force* the harness into those paths
# by emitting a single valid JSON value (so parse succeeds) and then a
# sibling value (so a compare pass has two roots), plus documents whose
# printed form must exercise every escaping / number-formatting branch.

# A single valid value guaranteed to round-trip through print_value.
_printable_scalar = st.one_of(
    _make_string(),
    _number,
    st.sampled_from(["true", "false", "null"]),
)

# A valid container that forces print_object / print_array recursion.
_printable_container = st.one_of(
    st.lists(_printable_scalar, max_size=3).map(lambda vs: "[" + ",".join(vs) + "]"),
    st.lists(
        st.tuples(_make_string(), st.just(":"), _printable_scalar).map(_join),
        max_size=3,
    ).map(lambda ps: "{" + ",".join(ps) + "}"),
    st.just('{"a":{"b":{"c":[1,2,3]}}}'),
    st.just('[[[[[[]]]]]]'),
    st.just('{"a":[],"b":{},"c":[[],{}]}'),
)

_printable_value = st.one_of(_printable_scalar, _printable_container)

# Strings that force print_string_ptr to take each branch:
# empty, plain, quote, backslash, each control escape, and non-ASCII.
_print_string_branches = st.one_of(
    st.just('""'),
    st.just('"plain"'),
    st.just('"a\\"b"'),
    st.just('"a\\\\b"'),
    st.just('"\\b\\f\\n\\r\\t"'),
    st.just('"\\u0000"'),
    st.just('"\\u0001\\u001f"'),
    st.just('"\\u007f"'),
    st.just('"\\u00e9\\u4e2d"'),
    st.just('"\\ud83d\\ude00"'),
    st.just('"/"'),
    st.just('"\\/"'),
)

# Numbers that force print_number to take each branch:
# integer, negative, zero, negative-zero, fraction, exponent, big, small.
_print_number_branches = st.one_of(
    st.just("0"),
    st.just("-0"),
    st.just("1"),
    st.just("-1"),
    st.just("123456789"),
    st.just("1.5"),
    st.just("-1.5"),
    st.just("0.0"),
    st.just("-0.0"),
    st.just("1e10"),
    st.just("1E10"),
    st.just("1e-10"),
    st.just("1.5e10"),
    st.just("1.5e-10"),
    st.just("1.7976931348623157e308"),
    st.just("5e-324"),
    st.just("123456789012345678"),
)

# Documents that put a print-branching value into a container so the
# harness must recurse through print_value -> print_object/print_array
# before hitting print_string_ptr / print_number.
_print_forced_doc = st.one_of(
    _print_string_branches.map(lambda s: "[" + s + "]"),
    _print_string_branches.map(lambda s: '{"k":' + s + "}"),
    _print_string_branches.map(lambda s: '{"a":' + s + ',"b":' + s + "}"),
    _print_number_branches.map(lambda n: "[" + n + "]"),
    _print_number_branches.map(lambda n: '{"k":' + n + "}"),
    _print_number_branches.map(lambda n: '{"a":' + n + ',"b":' + n + "}"),
    _printable_value.map(lambda v: "[" + v + "]"),
    _printable_value.map(lambda v: '{"k":' + v + "}"),
)

# Documents that force cJSON_Compare through every branch:
#   - identical (fast path a==b via same pointer is not reachable from
#     separate parses, but structurally-identical documents hit the deep
#     equal path)
#   - differing type
#   - differing number
#   - differing string
#   - differing array length
#   - differing array element
#   - differing object key / value
#   - one array longer than the other (the a_element != b_element branch)
_compare_forced_doc = st.one_of(
    # structurally identical pairs -> deep equal recursion
    _printable_value.map(lambda v: v + " " + v),
    _printable_value.map(lambda v: "[" + v + "," + v + "] [" + v + "," + v + "]"),
    _printable_value.map(lambda v: '{"a":' + v + "} " + '{"a":' + v + "}"),
    # type mismatch (first switch default / type compare)
    st.tuples(_number, _make_string()).map(lambda t: t[0] + " " + t[1]),
    st.tuples(_make_string(), _literal).map(lambda t: t[0] + " " + t[1]),
    st.tuples(_literal, _number).map(lambda t: t[0] + " " + t[1]),
    # number compare (equal and unequal)
    st.tuples(_number, _number).map(lambda t: t[0] + " " + t[1]),
    st.just("1 1"),
    st.just("1 2"),
    st.just("-0 0"),
    st.just("1.0 1"),
    # string compare (equal and unequal)
    _make_string().map(lambda s: s + " " + s),
    st.tuples(_make_string(), _make_string()).map(lambda t: t[0] + " " + t[1]),
    st.just('"" ""'),
    st.just('"a" "b"'),
    # array length mismatch (the trailing a_element != b_element branch)
    st.just("[] [1]"),
    st.just("[1] []"),
    st.just("[1,2] [1]"),
    st.just("[1] [1,2]"),
    st.just("[[]] [[]]"),
    st.just("[[]] [[] , []]"),
    # array element mismatch
    st.just("[1,2,3] [1,2,4]"),
    st.just("[1,2,3] [1,9,3]"),
    st.just('["a"] ["b"]'),
    # object member mismatch
    st.just('{"a":1} {"a":2}'),
    st.just('{"a":1} {"b":1}'),
    st.just('{"a":1} {"a":1,"b":2}'),
    st.just('{"a":1,"b":2} {"a":1}'),
    # nested objects/arrays in compare
    _printable_value.map(lambda v: '{"x":' + v + '} {"x":' + v + "}"),
    _printable_value.map(lambda v: "[" + v + "] [" + v + "]"),
)

_top = st.one_of(
    _value_strategy,
    _deep_array(),
    _deep_object(),
    _malformed,
    _roundtrip_pair,
    _same_value_pair,
    _compare_pair(),
    _compare_variants,
    _print_exercisers,
    _print_and_compare_doc,
    _print_forced_doc,
    _compare_forced_doc,
    st.tuples(_value_strategy, st.sampled_from(["", "\x00", " ", "x", "1"])).map(_join),
    st.tuples(st.sampled_from(["", "\ufeff", "\xef\xbb\xbf", " ", "\n"]), _value_strategy).map(_join),
)

strategy = _top
```