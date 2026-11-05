from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4().map(lambda h: "\\u" + h),
    _hex4().map(lambda h: "\\u" + h),
    st.sampled_from(["\\ud800", "\\udfff", "\\uD834", "\\uDD1E", "\\u0000"]),
)

_safe = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x7E,
    blacklist_characters='"\\',
).map(lambda c: c)

_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

_unicode_char = st.characters(min_codepoint=0x80, max_codepoint=0x2FFF)

_str_piece = st.one_of(_safe, _escapes, _raw_control, _unicode_char)

_string_body = st.lists(_str_piece, min_size=0, max_size=8).map(lambda xs: "".join(xs))

def _quoted(body):
    return '"' + body + '"'

_valid_string = _string_body.map(_quoted)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.just("00"),
    st.just("01"),
    st.just("007"),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
    st.just("."),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=10**4).map(str),
    ).map(lambda t: "".join(t)),
    st.sampled_from(["e309", "E309", "e-309", "e999", "e308", "e+00", "e01"]),
)

_sign = st.one_of(st.just(""), st.just("-"))

_valid_number = st.tuples(_sign, _int_part, _frac, _exp).map(lambda t: "".join(t))

_bad_number = st.sampled_from([
    "-", "+1", ".5", "-.5", "+", "1.2.3", "--1", "1e", "1e+", "0x", "1..2",
])

_number = st.one_of(_valid_number, _bad_number)

# ---------- literals ----------

_literal = st.one_of(
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# ---------- whitespace ----------

_ws = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t ", "\x00"]),
).map(str)

# ---------- recursive structure ----------

_json_string = st.one_of(_valid_string, _literal, _number)

def _make_obj(pairs):
    if not pairs:
        return "{}"
    inner = ",".join(k + ":" + v for (k, v) in pairs)
    return "{" + inner + "}"

def _make_arr(items):
    if not items:
        return "[]"
    return "[" + ",".join(items) + "]"

_pair = st.tuples(_valid_string, _json_string).map(lambda t: (t[0], t[1]))

_obj = st.lists(_pair, min_size=0, max_size=6).map(_make_obj)

_arr = st.lists(_json_string, min_size=0, max_size=6).map(_make_arr)

_bad_obj = st.one_of(
    st.just("{"),
    st.just("}"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just('{"a":1,}'),
    st.just('{"a":1,,}'),
    st.just('{a:1}'),
    st.just("{'a':1}"),
    st.just('{"a":1'),
    st.just('{"a" : 1 , }'),
)

_bad_arr = st.one_of(
    st.just("["),
    st.just("]"),
    st.just("[1,]"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just("[1"),
    st.just("[1 2]"),
)

# ---------- deep nesting near the ~1000 limit ----------

def _deep(depth, kind):
    if kind == "arr":
        return "[" * depth + "]" * depth
    else:
        return '{"a":' * depth + "1" + "}" * depth

_deep_nesting = st.one_of(
    st.integers(min_value=990, max_value=1002).map(lambda d: _deep(d, "arr")),
    st.integers(min_value=990, max_value=1002).map(lambda d: _deep(d, "obj")),
    st.integers(min_value=0, max_value=1000).map(lambda d: _deep(d, "arr")),
)

# ---------- top level ----------

_json_value = st.recursive(
    _json_string,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=6).map(_make_arr),
        st.lists(
            st.tuples(_valid_string, children), min_size=0, max_size=6
        ).map(_make_obj),
    ),
    max_leaves=20,
)

_bad_toplevel = st.one_of(
    _bad_number,
    _bad_obj,
    _bad_arr,
    st.just(""),
    st.just("   "),
    st.just('"unterminated'),
    st.just("'single'"),
    st.just("tru"),
    st.just("nul"),
    st.just("fals"),
    st.just('"\\x41"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just("\x00"),
    st.just("\ufeff"),
    st.just("[]extra"),
    st.just("1abc"),
)

_bom = st.one_of(st.just(""), st.just("\ufeff"))

_trailer = st.one_of(
    st.just(""),
    st.just(" \n\t "),
    st.just(" garbage"),
    st.just("\x00"),
    st.just("1 2"),
    st.just("abc"),
)

def _wrap(v):
    return _bom + v + _trailer

_toplevel_valid = st.tuples(_bom, _json_value, _trailer).map(lambda t: t[0] + t[1] + t[2])
_toplevel_deep = st.tuples(_bom, _deep_nesting, _trailer).map(lambda t: t[0] + t[1] + t[2])
_toplevel_bad = st.tuples(_bom, _bad_toplevel, _trailer).map(lambda t: t[0] + t[1] + t[2])

_toplevel_string = st.tuples(_bom, _valid_string, _trailer).map(lambda t: "".join(t))

# ---------- comparison / printing focused inputs ----------
# Drive cJSON_Compare and the print_* functions by generating documents that
# contain structurally similar but subtly different subtrees, and documents
# that exercise every value type through the printer.

def _compare_pair():
    leaf = st.one_of(
        st.just("true"),
        st.just("false"),
        st.just("null"),
        st.just("0"),
        st.just("-0"),
        st.just("1"),
        st.just("1.0"),
        st.just("1e0"),
        st.just('""'),
        st.just('"a"'),
        st.just('"A"'),
        st.just('"ab"'),
        st.just('"a\\u0000b"'),
    )
    small = st.recursive(
        leaf,
        lambda ch: st.one_of(
            st.lists(ch, min_size=0, max_size=3).map(_make_arr),
            st.lists(
                st.tuples(_valid_string, ch), min_size=0, max_size=3
            ).map(_make_obj),
        ),
        max_leaves=6,
    )
    return st.tuples(small, small).map(lambda t: "[" + t[0] + "," + t[1] + "]")

_compare_doc = _compare_pair()

_printable_string = st.one_of(
    _valid_string,
    st.just('"\\u0000"'),
    st.just('"\\u001f"'),
    st.just('"\\\\"'),
    st.just('"\\""'),
    st.just('"\\/"'),
    st.just('"\\b\\f\\n\\r\\t"'),
    st.just('"\u00e9\u4e2d\U0001F600"'),
)

_printable_value = st.one_of(
    _printable_string,
    _literal,
    _valid_number,
    st.just("0"),
    st.just("-0"),
    st.just("1e308"),
    st.just("1e-308"),
    st.just("123456789012345678"),
)

_print_doc = st.recursive(
    _printable_value,
    lambda ch: st.one_of(
        st.lists(ch, min_size=0, max_size=5).map(_make_arr),
        st.lists(
            st.tuples(_printable_string, ch), min_size=0, max_size=5
        ).map(_make_obj),
    ),
    max_leaves=15,
)

# ---------- new: explicit Compare / Print wrapper documents ----------

def _cmp_equal_leaf():
    leaf = st.one_of(
        st.just("true"), st.just("false"), st.just("null"),
        st.just("0"), st.just("-0"), st.just("1"), st.just("1.0"),
        st.just("1e0"), st.just("1E0"), st.just('""'), st.just('"a"'),
        st.just('"A"'), st.just('"ab"'),
    )
    return st.tuples(leaf, leaf).map(lambda t: "[" + t[0] + "," + t[1] + "]")

def _cmp_shapes():
    base = st.one_of(
        st.just("true"), st.just("false"), st.just("null"),
        st.just("0"), st.just("1"), st.just("1.5"),
        st.just('"a"'), st.just('"A"'), st.just('"\\u0000"'),
    )
    arr = st.lists(base, min_size=0, max_size=3).map(_make_arr)
    obj = st.lists(
        st.tuples(_valid_string, base), min_size=0, max_size=3
    ).map(_make_obj)
    shape = st.one_of(base, arr, obj)
    return st.tuples(shape, shape).map(lambda t: "[" + t[0] + "," + t[1] + "]")

_compare_doc = st.one_of(_compare_pair(), _cmp_equal_leaf(), _cmp_shapes())

_print_toplevel = st.one_of(
    _printable_value,
    _print_doc,
    st.just('"\\u0000"'),
    st.just('"\\u001f\\u007f"'),
    st.just('"\\ud834\\udd1e"'),
    st.just("1e308"),
    st.just("-1e-308"),
    st.just("0.0"),
    st.just("-0.0"),
    st.just("1.7976931348623157e308"),
    st.just("[]"),
    st.just("{}"),
    st.just('[true,false,null,0,"x",[],{}]'),
    st.just('{"a":true,"b":false,"c":null,"d":0,"e":"x","f":[],"g":{}}'),
)

_print_doc2 = _print_toplevel

_compare_print_doc = st.tuples(_printable_value, _printable_value).map(
    lambda t: "[" + t[0] + "," + t[1] + "]"
)

# ---------- IMPROVEMENT: self-referential compare documents ----------
# The previous run showed cJSON_Compare and the print_* functions at 0%
# branch coverage. Those functions are only reachable when a harness parses
# the whole input and then compares/prints its children. To maximize the
# chance a compare/print harness reaches every branch, emit documents shaped
# as two-element arrays whose two halves are *guaranteed to be parseable as
# the same top-level value type* and whose subtrees cover equal leaves,
# differing leaves, differing lengths, and differing types. We also emit
# top-level values of every printable type so a "parse then print" harness
# hits print_value on each branch.

def _cmp_leaf_pool():
    return st.one_of(
        st.just("true"), st.just("false"), st.just("null"),
        st.just("0"), st.just("-0"), st.just("1"), st.just("1.0"),
        st.just("1e0"), st.just("1E0"), st.just("1e-0"),
        st.just('""'), st.just('"a"'), st.just('"A"'), st.just('"ab"'),
        st.just('"a\\u0000b"'), st.just('"\\u00e9"'),
    )

def _cmp_arr_pair():
    # Same-length, differing-length, and equal arrays of leaves.
    leaf = _cmp_leaf_pool()
    a = st.lists(leaf, min_size=0, max_size=4).map(_make_arr)
    b = st.lists(leaf, min_size=0, max_size=4).map(_make_arr)
    return st.tuples(a, b).map(lambda t: "[" + t[0] + "," + t[1] + "]")

def _cmp_obj_pair():
    # Objects with same keys (equal / differing values) and differing keys.
    leaf = _cmp_leaf_pool()
    key = st.sampled_from(['"a"', '"b"', '"c"', '"A"', '""'])
    def build(pairs):
        return _make_obj(pairs)
    a = st.lists(st.tuples(key, leaf), min_size=0, max_size=4).map(build)
    b = st.lists(st.tuples(key, leaf), min_size=0, max_size=4).map(build)
    return st.tuples(a, b).map(lambda t: "[" + t[0] + "," + t[1] + "]")

def _cmp_mixed_type_pair():
    # Deliberately mismatched top-level types so cJSON_Compare's type-mismatch
    # branch and the default (invalid type) path are exercised.
    leaf = _cmp_leaf_pool()
    arr = st.lists(leaf, min_size=0, max_size=3).map(_make_arr)
    obj = st.lists(
        st.tuples(st.sampled_from(['"a"', '"b"']), leaf),
        min_size=0, max_size=3,
    ).map(_make_obj)
    any_val = st.one_of(leaf, arr, obj)
    return st.tuples(any_val, any_val).map(lambda t: "[" + t[0] + "," + t[1] + "]")

def _cmp_nested_equal():
    # Deeply-equal pairs (same shape, identical leaves) to drive the recursive
    # cJSON_Compare array/object branch all the way to the leaf comparison.
    leaf = _cmp_leaf_pool()
    def grow(ch):
        return st.one_of(
            st.lists(ch, min_size=1, max_size=3).map(_make_arr),
            st.lists(
                st.tuples(st.sampled_from(['"k"', '"a"']), ch),
                min_size=1, max_size=3,
            ).map(_make_obj),
        )
    shape = st.recursive(leaf, grow, max_leaves=6)
    return shape.map(lambda s: "[" + s + "," + s + "]")

_compare_doc = st.one_of(
    _compare_pair(),
    _cmp_equal_leaf(),
    _cmp_shapes(),
    _cmp_arr_pair(),
    _cmp_obj_pair(),
    _cmp_mixed_type_pair(),
    _cmp_nested_equal(),
)

# ---------- IMPROVEMENT: explicit print-coverage documents ----------
# One document per printer branch: each value type at top level, plus
# containers holding every printable type (including raw control bytes,
# escape sequences, high unicode, and number edge cases).

_print_singles = st.sampled_from([
    "true", "false", "null",
    "0", "-0", "1", "-1", "1.0", "-1.0", "1e0", "1E0", "1e-0",
    "1e308", "-1e308", "1e-308", "0.0", "-0.0",
    "1.7976931348623157e308",
    "123456789012345678",
    '""', '"a"', '"\\u0000"', '"\\u001f"', '"\\u007f"',
    '"\\\\"', '"\\""', '"\\/"', '"\\b\\f\\n\\r\\t"',
    '"\u00e9\u4e2d\U0001F600"',
    "[]", "{}",
    '[true,false,null,0,"x",[],{}]',
    '{"a":true,"b":false,"c":null,"d":0,"e":"x","f":[],"g":{}}',
])

_print_doc2 = st.one_of(_print_toplevel, _print_singles)

_compare_print_doc = st.tuples(_printable_value, _printable_value).map(
    lambda t: "[" + t[0] + "," + t[1] + "]"
)

strategy = st.one_of(
    _toplevel_valid,
    _toplevel_deep,
    _toplevel_bad,
    _toplevel_string,
    _compare_doc,
    _print_doc,
    _print_doc2,
    _compare_print_doc,
)