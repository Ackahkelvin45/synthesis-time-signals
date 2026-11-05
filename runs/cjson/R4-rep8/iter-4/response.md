```python
from hypothesis import strategies as st
import json

# ---------- building blocks ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = _hex4().map(lambda h: "\\u" + h)

# lone surrogates: parser rejects, but interesting to fuzz
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udbff", "\\udc00", "\\udfff", "\\uD800", "\\uDFFF"]
)

# paired surrogate (valid UTF-16 pair)
_paired_surrogate = st.tuples(
    st.sampled_from(["\\ud800", "\\ud801", "\\ud83d", "\\udbff"]),
    st.sampled_from(["\\udc00", "\\udc01", "\\ude00", "\\udfff"]),
).map(lambda t: t[0] + t[1])

# raw control / NUL bytes inside strings (parser accepts)
_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

# safe code points (no quote, backslash, control)
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
    _digits,  # leading zeros (accepted by parser)
    st.just(""),  # for malformed like ".5" or "-"
)

_frac_part = st.one_of(
    st.just(""),
    _digits.map(lambda d: "." + d),
    st.just("."),  # trailing dot (accepted)
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

# extreme magnitudes
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

# Round-trip pairs: parse then print/compare are exercised by two identical
# documents (covers cJSON_Compare identical-object fast path and value cases)
_roundtrip_pair = st.tuples(_value_strategy, st.just(" "), _value_strategy).map(_join)
_same_value_pair = _value_strategy.map(lambda v: v + " " + v)

# Pairs that differ in interesting ways to exercise cJSON_Compare's
# non-equal branches (array length mismatch, differing strings/numbers/types).
def _compare_pair():
    a = _value_strategy
    b = _value_strategy
    return st.tuples(a, st.just(" "), b).map(_join)

_compare_variants = st.one_of(
    # same array, one longer
    st.tuples(
        st.lists(_value_strategy, min_size=0, max_size=3),
        st.lists(_value_strategy, min_size=1, max_size=3),
    ).map(lambda t: "[" + ",".join(t[0]) + "] [" + ",".join(t[1]) + "]"),
    # same object with one key changed
    st.tuples(_make_string(), _make_string(), _value_strategy).map(
        lambda t: '{"a":' + t[2] + '} {"' + t[0] + '":' + t[2] + "}"
    ),
    # differing scalars of same type
    st.tuples(_number, _number).map(lambda t: t[0] + " " + t[1]),
    st.tuples(_make_string(), _make_string()).map(lambda t: t[0] + " " + t[1]),
    # differing types
    st.tuples(_value_strategy, _literal).map(lambda t: t[0] + " " + t[1]),
)

# Documents that exercise print_value / print_string_ptr / print_number /
# print_object paths after a successful parse. These are valid JSON that
# will be re-serialized (covers string escaping, number formatting, nested
# objects/arrays, and the empty-container cases).
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

# ---------- document builders that force parse + print + compare ----------

# Generate a single valid JSON document, then wrap it so the test harness
# (which parses, prints, and compares) hits print_value/print_string_ptr/
# print_number/print_object and cJSON_Compare on every run.
_print_and_compare_doc = st.one_of(
    # identical pair via self-concatenation (drives cJSON_Compare true path)
    _value_strategy.map(lambda v: v + " " + v),
    # array of two equal values (compare on array elements)
    _value_strategy.map(lambda v: "[" + v + "," + v + "]"),
    # object with two keys pointing at equal values (compare on object members)
    _value_strategy.map(lambda v: '{"a":' + v + ',"b":' + v + "}"),
    # nested structures that exercise print recursion
    _value_strategy.map(lambda v: '{"x":' + v + ',"y":[' + v + "]}"),
    # empty containers and scalar edge cases in a wrapper
    st.just('{"a":{},"b":[],"c":0,"d":"","e":null,"f":true,"g":false}'),
    st.just('[{"a":1},{"a":1}]'),
    st.just('{"k":{"k":{"k":[]}}}'),
    # strings with every escape form, so print_string_ptr covers all branches
    st.just('{"s":"\\"\\\\\\/\\b\\f\\n\\r\\t\\u0000\\u001f\\u007f\\u00e9"}'),
    st.just('{"s":"\\ud83d\\ude00\\u4e2d"}'),
    # numbers forcing print_number branches (int, frac, exp, negative, zero)
    st.just('{"n":[0,-0.0,1,-1,1.5,-1.5,1e10,1e-10,123456789012345]}'),
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
    st.tuples(_value_strategy, st.sampled_from(["", "\x00", " ", "x", "1"])).map(_join),
    st.tuples(st.sampled_from(["", "\ufeff", "\xef\xbb\xbf", " ", "\n"]), _value_strategy).map(_join),
)

strategy = _top
```