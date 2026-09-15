from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Safe code points (no quote, backslash, or control chars) plus deliberate
# edge cases: raw control bytes, NUL, and escapes.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

_control_bytes = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\t", "\n", "\r"]
)

_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

# \uXXXX escapes, including lone surrogates (parser rejects those) and
# valid surrogate pairs.
_unicode_escape = _hex4.map(lambda h: "\\u" + h)

_surrogate_pair = st.tuples(
    st.integers(min_value=0xD800, max_value=0xDBFF),
    st.integers(min_value=0xDC00, max_value=0xDFFF),
).map(lambda t: "\\u%04x\\u%04x" % t)

_string_piece = st.one_of(
    _safe_chars,
    _control_bytes,
    _escapes,
    _unicode_escape,
    _surrogate_pair,
)

# A JSON string literal.
json_string = st.lists(_string_piece, max_size=8).map(lambda xs: '"' + "".join(xs) + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.integers(min_value=1, max_value=9), _digits).map(
        lambda t: str(t[0]) + t[1]
    ),
)

_frac_part = st.one_of(
    st.just("."),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("."), _digits, _digits).map(lambda t: t[0] + t[1] + t[2]),
)

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    _digits,
).map(lambda t: t[0] + t[1] + t[2])

# Extreme magnitudes / overflow.
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e308",
        "1e-308",
        "9" * 20,
        "0." + "9" * 20,
        "1" + "0" * 20,
        "-0",
        "0e0",
        "0E+0",
        "1e01",
        "1E-01",
    ]
)

# Near-valid-but-malformed numeric forms (parser accepts several of these).
_malformed_number = st.sampled_from(
    [
        "01",
        "007",
        "1.",
        "-1.",
        "0x10",
        "0X1f",
        "+1",
        ".5",
        "-",
        "-.5",
        "1e",
        "1e+",
        "1.2.3",
        "--1",
        "1..2",
    ]
)

json_number = st.one_of(
    st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac_part),
        st.one_of(st.just(""), _exp_part),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    _extreme_number,
    _malformed_number,
)

# ---------- literals ----------

_literals = st.sampled_from(["true", "false", "null"])

# Malformed literals the parser rejects.
_malformed_literals = st.sampled_from(["NaN", "Infinity", "-Infinity", "True", "NULL", "nul"])

# ---------- recursive value ----------

# Depth budget: concentrate interesting depth near the 1000-level limit.
# Base values first, then recursive obj/arr.
_value_strategy = st.deferred(lambda: json_value)

_base_value = st.one_of(
    json_string,
    json_number,
    _literals,
    _malformed_literals,
)

def _make_obj(pair_strategy):
    return st.one_of(
        st.just("{}"),
        st.tuples(
            st.just("{"),
            st.lists(pair_strategy, min_size=1, max_size=4).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )

def _make_arr(value_strategy):
    return st.one_of(
        st.just("[]"),
        st.tuples(
            st.just("["),
            st.lists(value_strategy, min_size=1, max_size=4).map(lambda vs: ",".join(vs)),
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )

_pair = st.tuples(
    json_string,
    st.just(":"),
    _value_strategy,
).map(lambda t: t[0] + t[1] + t[2])

_obj = _make_obj(_pair)
_arr = _make_arr(_value_strategy)

# Recursive construction with a depth cap near the parser's 1000-level limit.
json_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        _make_obj(_pair),
        _make_arr(children),
    ),
    max_leaves=50,
)

# ---------- deep nesting near the limit ----------

def _nested(depth, open_ch, close_ch, inner):
    return open_ch * depth + inner + close_ch * depth

_deep_array = st.integers(min_value=990, max_value=1010).map(
    lambda d: _nested(d, "[", "]", "1")
)

_deep_object = st.integers(min_value=990, max_value=1010).map(
    lambda d: _nested(d, '{"a":', "}", "1")
)

_deep_mixed = st.integers(min_value=490, max_value=510).map(
    lambda d: _nested(d, '[{"a":', "}]", "1")
)

# ---------- malformed / near-valid inputs ----------

_malformed = st.sampled_from(
    [
        "",
        " ",
        "{",
        "}",
        "[",
        "]",
        "[,]",
        "[1,]",
        "{,}",
        '{"a":}',
        '{"a"}',
        '{"a" 1}',
        '{"a":1,}',
        "[1 2]",
        "[1,,2]",
        '"unterminated',
        '"',
        "'single'",
        "{'a':1}",
        "{a:1}",
        '{"a":1',
        "[1,2",
        "\\",
        "\x00",
        "\ufeff",
        "\ufeff1",
        "1\x00",
        '"\x00"',
        '"\t"',
        '"\u0000"',
        '"\ud800"',
        '"\udfff"',
        '"\ud800\ud800"',
        "tru",
        "fals",
        "nul",
        "truex",
        "nullx",
    ]
)

# Trailing content after a complete value is ACCEPTED, so include it too
# (for coverage), but don't rely on it for rejections.
_trailing = st.tuples(
    _base_value,
    st.sampled_from(["abc", " 1 2", "\x00", "xyz", "{}", "[]", "1e309"]),
).map(lambda t: t[0] + t[1])

# ---------- cJSON_Compare coverage ----------
# cJSON_Compare(a, b, case_sensitive) is only reached when a program parses
# two documents and compares them. To exercise its branches we emit inputs
# that contain two JSON documents (separated so the parser can read both),
# chosen to hit: equal scalars, unequal scalars, equal/unequal numbers,
# equal/unequal strings with case differences, equal/unequal arrays,
# equal/unequal objects, differing types, and nested structures.
_compare_atom = st.sampled_from(
    [
        "true", "false", "null",
        "0", "1", "-1", "1.5", "1e3", "-0", "0.0", "100", "1e309",
        '"a"', '"A"', '"abc"', '"ABC"', '""', '"\\u00e9"', '"\\u00E9"',
        "[]", "{}", "[1,2,3]", "[1,2]", '{"a":1}', '{"a":2}', '{"a":1,"b":2}',
        '{"b":2,"a":1}', '{"a":[1,2]}', '{"a":{"b":1}}', "[[1],[2]]",
    ]
)

def _compare_pair(a, b):
    # Two documents separated by a newline; a fuzzer harness that parses
    # both and calls cJSON_Compare will exercise the comparison logic.
    return a + "\n" + b

_compare_same = _compare_atom.map(lambda a: _compare_pair(a, a))

_compare_diff = st.tuples(_compare_atom, _compare_atom).map(
    lambda t: _compare_pair(t[0], t[1])
)

# Explicit case-sensitivity and cross-type comparisons.
_compare_case = st.sampled_from(
    [
        _compare_pair('"a"', '"A"'),
        _compare_pair('"A"', '"a"'),
        _compare_pair('"AbC"', '"aBc"'),
        _compare_pair('{"k":"v"}', '{"k":"V"}'),
        _compare_pair('["x"]', '["X"]'),
    ]
)

_compare_type = st.sampled_from(
    [
        _compare_pair("1", '"1"'),
        _compare_pair("true", "1"),
        _compare_pair("null", "false"),
        _compare_pair("[]", "{}"),
        _compare_pair("[1]", '{"0":1}'),
        _compare_pair('{"a":1}', "[1]"),
        _compare_pair("1", "1.0"),
        _compare_pair("0", "-0"),
    ]
)

_compare_nested = st.sampled_from(
    [
        _compare_pair('{"a":[1,2,{"b":3}]}', '{"a":[1,2,{"b":3}]}'),
        _compare_pair('{"a":[1,2,{"b":3}]}', '{"a":[1,2,{"b":4}]}'),
        _compare_pair('{"a":[1,2]}', '{"a":[1,2,3]}'),
        _compare_pair('[[[1]]]', '[[[1]]]'),
        _compare_pair('[[[1]]]', '[[[2]]]'),
        _compare_pair('{"x":{"y":{"z":1}}}', '{"x":{"y":{"z":1}}}'),
        _compare_pair('{"x":{"y":{"z":1}}}', '{"x":{"y":{"z":2}}}'),
    ]
)

_compare = st.one_of(
    _compare_same,
    _compare_diff,
    _compare_case,
    _compare_type,
    _compare_nested,
)

# ---------- top-level strategy ----------

strategy = st.one_of(
    json_value,
    _deep_array,
    _deep_object,
    _deep_mixed,
    _malformed,
    _trailing,
    _compare,
    # duplicate keys
    st.just('{"a":1,"a":2}'),
    st.just('{"a":1,"a":2,"a":3}'),
    st.just('{"":1,"":2}'),
    # BOM
    st.just("\ufeff1"),
    st.just('\ufeff{"a":1}'),
    st.just("\ufeff[1,2,3]"),
    # embedded NUL / control bytes
    st.just('"a\x00b"'),
    st.just('{"a\x00b":1}'),
    st.just('"\x01\x02\x03"'),
    st.just("1\x00"),
    # extremes
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("9" * 30),
    # hex / leading zeros / trailing dot (accepted)
    st.just("0x10"),
    st.just("01"),
    st.just("1."),
    # lone surrogate escapes (rejected)
    st.just('"\\ud800"'),
    st.just('"\\udfff"'),
    # NaN / Infinity words (rejected)
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)