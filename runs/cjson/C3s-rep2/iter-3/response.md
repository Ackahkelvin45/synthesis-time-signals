```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Primitive fragments
# ---------------------------------------------------------------------------

_hex = st.sampled_from("0123456789abcdefABCDEF")

_esc_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_esc_unicode = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    _hex, _hex, _hex, _hex,
)

# Surrogate escapes: lone surrogates are rejected by the parser, so they make
# interesting near-valid inputs.  Paired surrogates form valid astral chars.
_high_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF)
_low_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF)

_lone_surrogate_esc = st.builds(
    lambda n: "\\u%04x" % n,
    st.one_of(_high_surrogate, _low_surrogate),
)

_paired_surrogate_esc = st.builds(
    lambda hi, lo: "\\u%04x\\u%04x" % (hi, lo),
    _high_surrogate, _low_surrogate,
)

# Raw control bytes / NUL: allowed by the parser, forbidden by the grammar.
_raw_control = st.integers(min_value=0, max_value=0x1F).map(chr)
_raw_nul = st.just("\x00")

# Safe code points (excluding quote, backslash, and controls).
_safe_cp = st.integers(min_value=0x20, max_value=0x10FFFF).filter(
    lambda c: c != 0x22 and c != 0x5C and not (0xD800 <= c <= 0xDFFF)
).map(chr)

_string_char = st.one_of(
    _safe_cp,
    _esc_simple,
    _esc_unicode,
    _lone_surrogate_esc,
    _paired_surrogate_esc,
    _raw_control,
    _raw_nul,
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    # leading zeros: accepted by the parser, rejected by the grammar
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
)

_frac_part = st.one_of(
    st.just("."),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
    st.just(".0"),
)

_exp_part = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda n: "e%+d" % n),
    st.integers(min_value=0, max_value=400).map(lambda n: "e%d" % n),
    st.integers(min_value=-400, max_value=400).map(lambda n: "E%d" % n),
    # extreme magnitudes / overflow
    st.sampled_from(["e309", "e308", "e1000", "e-1000", "E+999", "e+308", "e-324"]),
)

_opt_sign = st.one_of(st.just(""), st.just("-"))

_number = st.builds(
    lambda s, i, f, e: s + i + f + e,
    _opt_sign,
    _int_part,
    st.one_of(st.just(""), _frac_part),
    st.one_of(st.just(""), _exp_part),
)

# Hex numbers: accepted by the parser, rejected by the grammar.
_hex_number = st.builds(
    lambda s, prefix, digits: s + "0" + prefix + digits,
    _opt_sign,
    st.sampled_from("xX"),
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8),
)

# ---------------------------------------------------------------------------
# Malformed / near-valid fragments
# ---------------------------------------------------------------------------

_malformed = st.sampled_from([
    "-", "+1", "+", ".5", ".", "e5", "1e", "1e+", "--1", "1..2",
    "NaN", "Infinity", "-Infinity", "nan", "inf",
    "tru", "fals", "nul", "True", "FALSE", "NULL",
    "01", "007", "00",
    "0x", "0xZ",
])

_unterminated_string = st.builds(
    lambda chars: '"' + chars,
    st.text(alphabet="abcXYZ0123 \\\"", max_size=8),
)

_bad_escape_string = st.builds(
    lambda pre, bad: '"' + pre + "\\" + bad + '"',
    st.text(alphabet="abc012", max_size=5),
    st.sampled_from(["x", "u12", "u", "U0000", "q", "8"]),
)

_single_quoted = st.builds(
    lambda s: "'" + s + "'",
    st.text(alphabet="abc012", max_size=6),
)

# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

_json_leaf = st.one_of(
    _number,
    _hex_number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _malformed,
    _unterminated_string,
    _bad_escape_string,
    _single_quoted,
)

_ws = st.text(alphabet=" \t\n\r", max_size=3)

_string = st.builds(
    lambda chars: '"' + "".join(chars) + '"',
    st.lists(_string_char, max_size=12),
)


def _make_value(children):
    """Build a JSON value strategy from recursive children strategies."""
    child = st.one_of(children)

    # Arrays, including empty, with optional whitespace and trailing commas.
    arr_elems = st.lists(child, max_size=4)
    arr = st.builds(
        lambda elems, ws: "[" + ",".join(elems) + ws + "]",
        arr_elems, _ws,
    )
    arr_empty = st.builds(lambda ws: "[" + ws + "]", _ws)
    arr_trailing_comma = st.builds(
        lambda elems, ws: "[" + ",".join(elems) + "," + ws + "]",
        st.lists(child, min_size=1, max_size=3), _ws,
    )

    # Objects, including empty, duplicate keys, missing colons, double commas.
    pair = st.builds(
        lambda k, ws1, ws2, v: k + ws1 + ":" + ws2 + v,
        _string, _ws, _ws, child,
    )
    obj_elems = st.lists(pair, max_size=4)
    obj = st.builds(
        lambda pairs, ws: "{" + ",".join(pairs) + ws + "}",
        obj_elems, _ws,
    )
    obj_empty = st.builds(lambda ws: "{" + ws + "}", _ws)
    obj_dup_keys = st.builds(
        lambda k, v1, v2, ws: "{" + k + ":" + v1 + "," + k + ":" + v2 + ws + "}",
        _string, child, child, _ws,
    )
    obj_missing_colon = st.builds(
        lambda k, v, ws: "{" + k + v + ws + "}",
        _string, child, _ws,
    )
    obj_double_comma = st.builds(
        lambda k, v, ws: "{" + k + ":" + v + ",," + ws + "}",
        _string, child, _ws,
    )
    obj_trailing_comma = st.builds(
        lambda k, v, ws: "{" + k + ":" + v + "," + ws + "}",
        _string, child, _ws,
    )

    return st.one_of(
        _string,
        arr, arr_empty, arr_trailing_comma,
        obj, obj_empty, obj_dup_keys,
        obj_missing_colon, obj_double_comma, obj_trailing_comma,
    )


# Base case for recursion: leaves plus shallow composites.
_base = st.one_of(
    _json_leaf,
    _string,
    st.just("{}"),
    st.just("[]"),
    st.just("[ ]"),
    st.just("{ }"),
)

_value = st.recursive(
    _base,
    _make_value,
    max_leaves=12,
)

# ---------------------------------------------------------------------------
# Wrappers: whitespace, BOM, trailing content, deep nesting
# ---------------------------------------------------------------------------

_leading_ws = st.text(alphabet=" \t\n\r", max_size=4)
_trailing_content = st.one_of(
    st.just(""),
    st.just("abc"),
    st.just(" 1 2"),
    st.just(" \x00"),
    st.just("//comment"),
    st.just(" garbage"),
)

_wrapped = st.builds(
    lambda pre, val, post: pre + val + post,
    _leading_ws, _value, _trailing_content,
)

_bom_wrapped = st.builds(
    lambda val: "\ufeff" + val,
    _value,
)

# Deep nesting near the 1000-level limit: depths 990..1010.
_deep_depth = st.integers(min_value=990, max_value=1010)


def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_object(depth):
    return '{"a":' * depth + "null" + "}" * depth


_deep = st.builds(
    lambda depth, kind: kind(depth),
    _deep_depth,
    st.sampled_from([_deep_array, _deep_object]),
)

# Very deep (far beyond the limit) to exercise clean rejection.
_very_deep = st.builds(
    lambda depth, kind: kind(depth),
    st.integers(min_value=1001, max_value=5000),
    st.sampled_from([_deep_array, _deep_object]),
)

# ---------------------------------------------------------------------------
# Malformed top-level inputs
# ---------------------------------------------------------------------------

_malformed_top = st.sampled_from([
    "", " ", "\t\n",
    "{", "}", "[", "]", "[,]", "{,}", "[1,]", '{"a":1,}',
    "{1:2}", "{a:1}", '{"a"}', '{"a":}', "{:1}",
    '{"a":1 "b":2}', "[1 2]", "[1,,2]", "1,2",
    '"unterminated', "'single'", "\\", ":", ",",
    "+", ".", "-", "e", "0x", "tru", "NaN", "Infinity",
    "0x10", "01", "1.",
    '"\ud800"', '"\\ud800"', '"\\uD800"',
    "\x00", "1\x00", '"\x00"', '{"\x00":1}',
    "\xef\xbb\xbf",  # raw BOM bytes as latin-1 chars
])

# ---------------------------------------------------------------------------
# Deeply nested composites with near-limit depth to exercise recursion branches
# ---------------------------------------------------------------------------

def _nested_arrays(depth):
    return "[" * depth + "]" * depth


def _nested_objects(depth):
    return '{"a":' * depth + "null" + "}" * depth


def _nested_mixed(depth):
    # alternate arrays and objects to hit both recursion paths
    out = ""
    for i in range(depth):
        if i % 2 == 0:
            out += "["
        else:
            out += '{"a":'
    out += "null"
    for i in reversed(range(depth)):
        if i % 2 == 0:
            out += "]"
        else:
            out += "}"
    return out


_medium_depth = st.integers(min_value=50, max_value=999)

_medium_nested = st.builds(
    lambda depth, kind: kind(depth),
    _medium_depth,
    st.sampled_from([_nested_arrays, _nested_objects, _nested_mixed]),
)

# ---------------------------------------------------------------------------
# Trailing-garbage / extra-content branches after a valid top-level value.
# The parser likely has code paths for handling trailing tokens, comments,
# whitespace-only tails, and EOF checks that the current inputs rarely reach.
# ---------------------------------------------------------------------------

_trailing_junk = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("\t\r"),
    st.just("x"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("{}"),
    st.just("[]"),
    st.just(","),
    st.just(":"),
    st.just("]"),
    st.just("}"),
    st.just("/*"),
    st.just("*/"),
    st.just("//"),
    st.just("#"),
    st.just("\x00"),
    st.just("\ufeff"),
)

_trailing_value = st.builds(
    lambda pre, val, junk: pre + val + junk,
    st.one_of(st.just(""), st.just(" "), st.just("\n")),
    _value,
    _trailing_junk,
)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _wrapped,
    _bom_wrapped,
    _deep,
    _very_deep,
    _medium_nested,
    _malformed_top,
    _trailing_value,
    _value,
)
```