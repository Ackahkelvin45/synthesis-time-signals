```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf strategies
# ---------------------------------------------------------------------------

_plain_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

_control_chars = st.sampled_from(
    ["\x00", "\x01", "\x1f", "\t", "\n", "\r", "\x7f", "\x0b", "\x0c"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_escape = st.builds(lambda h: "\\u" + h, _hex4)

_lone_high = st.sampled_from([f"\\ud{hi:02x}" for hi in range(0x800, 0xc00)])
_lone_low = st.sampled_from([f"\\ud{lo:02x}" for lo in range(0xc00, 0x1000)])
_surrogate_escape = st.one_of(_lone_high, _lone_low)

_simple_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_escape = st.one_of(_simple_escape, _unicode_escape, _surrogate_escape)

_string_body_piece = st.one_of(
    _plain_chars,
    _control_chars,
    _escape,
)

_string_body = st.lists(_string_body_piece, max_size=12).map("".join)

_wellformed_string = _string_body.map(lambda s: '"' + s + '"')

_unterminated_string = _string_body.map(lambda s: '"' + s)
_bad_escape_string = _string_body.map(lambda s: '"' + s + "\\q\"")
_stray_quote_string = _string_body.map(lambda s: '"' + s + '"' + '"')

_string = st.one_of(
    _wellformed_string,
    _unterminated_string,
    _bad_escape_string,
    _stray_quote_string,
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero_int = st.builds(
    lambda d, rest: d + rest,
    st.sampled_from("123456789"),
    st.text(alphabet="0123456789", max_size=6),
)

_int_part = st.one_of(
    st.just("0"),
    _nonzero_int,
    _int_digits,
)

_frac_part = st.one_of(
    st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=6)),
    st.just("."),
)

_exp_part = st.builds(
    lambda e, sign, d: e + sign + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

_sign = st.sampled_from(["", "-"])

_extreme_exp = st.sampled_from(
    ["e309", "e400", "e9999", "e-9999", "E+309", "e308", "e-324", "e-400"]
)

_number = st.one_of(
    st.builds(lambda s, i: s + i, _sign, _int_part),
    st.builds(lambda s, i, f: s + i + f, _sign, _int_part, _frac_part),
    st.builds(lambda s, i, e: s + i + e, _sign, _int_part, _exp_part),
    st.builds(lambda s, i, f, e: s + i + f + e, _sign, _int_part, _frac_part, _exp_part),
    st.builds(lambda i, e: i + e, _int_part, _extreme_exp),
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("1."),
    st.just("0x10"),
    st.just("NaN"),
    st.just("Infinity"),
)

# ---------------------------------------------------------------------------
# Recursive obj/arr/value
# ---------------------------------------------------------------------------

_DEPTH_NEAR_LIMIT = st.integers(min_value=0, max_value=1000)

def _deep_array(depth):
    return st.builds(
        lambda d: "[" * d + "]" * d,
        st.just(depth),
    )

def _deep_object(depth):
    return st.builds(
        lambda d: "{" * d + "}" * d,
        st.just(depth),
    )

_ws = st.text(alphabet=" \t\n\r", max_size=3)

_double_comma_arr = st.builds(
    lambda a, b: "[" + a + ",," + b + "]",
    _string,
    _string,
)
_missing_colon_obj = st.builds(
    lambda k, v: "{" + k + " " + v + "}",
    _wellformed_string,
    st.just("1"),
)
_trailing_comma_arr = st.builds(
    lambda a: "[" + a + ",]",
    _string,
)
_trailing_comma_obj = st.builds(
    lambda k: "{" + k + ":1,}",
    _wellformed_string,
)
_unquoted_key = st.builds(
    lambda k: "{" + k + ":1}",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=5),
)
_single_quoted = st.builds(
    lambda s: "'" + s + "'",
    st.text(alphabet="abc", max_size=4),
)

_value_leaf = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

def _obj_strategy(children):
    pair = st.tuples(_wellformed_string, children).map(lambda t: t[0] + ":" + t[1])
    nonempty = st.lists(pair, min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}")
    empty = st.just("{}")
    dup = st.tuples(_wellformed_string, children, children).map(
        lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
    )
    return st.one_of(empty, nonempty, dup)

def _arr_strategy(children):
    nonempty = st.lists(children, min_size=1, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]")
    empty = st.just("[]")
    return st.one_of(empty, nonempty)

_value = st.recursive(
    _value_leaf,
    lambda children: st.one_of(_obj_strategy(children), _arr_strategy(children)),
    max_leaves=40,
)

# ---------------------------------------------------------------------------
# Deep nesting near the 1000-level limit
# ---------------------------------------------------------------------------

_deep = st.one_of(
    _DEPTH_NEAR_LIMIT.flatmap(_deep_array),
    _DEPTH_NEAR_LIMIT.flatmap(_deep_object),
    st.just("[" * 999 + "]" * 999),
    st.just("[" * 1000 + "]" * 1000),
    st.just("[" * 1001 + "]" * 1001),
    st.just("{" * 1000 + "}" * 1000),
    st.just("{" * 1001 + "}" * 1001),
)

# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

_bom = st.sampled_from(["", "\ufeff"])

_trailing_junk = st.one_of(
    st.just(""),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("\x00"),
    st.just("garbage"),
)

_malformed_top = st.one_of(
    st.just(""),
    st.just("   "),
    st.just("{"),
    st.just("["),
    st.just("}"),
    st.just("]"),
    st.just(","),
    st.just(":"),
    _double_comma_arr,
    _missing_colon_obj,
    _trailing_comma_arr,
    _trailing_comma_obj,
    _unquoted_key,
    _single_quoted,
)

def _with_ws(v):
    return st.tuples(_ws, v, _ws).map(lambda t: t[0] + t[1] + t[2])

# NOTE: the run feedback showed every BOM-prefixed top-level document was
# rejected (divergences like b'\xef\xbb\xbf""').  A leading BOM is therefore
# not accepted by this parser, so we no longer attach it to otherwise-valid
# documents.  BOM handling is instead exercised in the malformed bucket where
# rejection is the expected outcome.
_valid_top = st.tuples(_with_ws(_value), _trailing_junk).map(
    lambda t: t[0] + t[1]
)

_bom_top = st.tuples(_bom, _with_ws(_value)).map(lambda t: t[0] + t[1])

_bare_literal_top = st.one_of(
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.builds(lambda w, lit: w + lit, _ws, st.sampled_from(["true", "false", "null"])),
)

# ---------------------------------------------------------------------------
# Object/pair focus
# ---------------------------------------------------------------------------

_obj_key = st.one_of(
    _wellformed_string,
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789",
            min_size=1, max_size=8).map(lambda s: '"' + s + '"'),
)

_obj_value_simple = st.one_of(
    _number,
    _wellformed_string,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("[]"),
    st.just("{}"),
)

_simple_pair = st.builds(
    lambda k, v: k + ":" + v,
    _obj_key,
    _obj_value_simple,
)

_simple_obj = st.lists(_simple_pair, min_size=0, max_size=5).map(
    lambda ps: "{" + ",".join(ps) + "}"
)

_obj_with_ws = st.builds(
    lambda ws, k, ws2, v, ws3: "{" + ws + k + ws2 + ":" + ws3 + v + ws + "}",
    _ws,
    _obj_key,
    _ws,
    _obj_value_simple,
    _ws,
)

_nested_obj = st.builds(
    lambda k1, k2, v: "{" + k1 + ":{" + k2 + ":" + v + "}}",
    _obj_key,
    _obj_key,
    _obj_value_simple,
)

_obj_top = st.one_of(
    _simple_obj,
    _obj_with_ws,
    _nested_obj,
    _with_ws(_simple_obj),
    _with_ws(_nested_obj),
    # Objects embedded in arrays.
    st.builds(lambda a, b: "[" + a + "," + b + "]", _simple_obj, _simple_obj),
)

# ---------------------------------------------------------------------------
# Deeply nested but structurally valid documents (arrays/objects mixed,
# with real leaves) to probe the recursion limit with accepted inputs.
# ---------------------------------------------------------------------------

_mixed_deep = st.one_of(
    st.builds(
        lambda d, leaf: "[" * d + leaf + "]" * d,
        st.integers(min_value=1, max_value=999),
        _value_leaf,
    ),
    st.builds(
        lambda d, leaf: '{"a":' * d + leaf + "}" * d,
        st.integers(min_value=1, max_value=999),
        _value_leaf,
    ),
    st.builds(
        lambda d: "[" * d + '{"a":1}' + "]" * d,
        st.integers(min_value=1, max_value=999),
    ),
)

strategy = st.one_of(
    _valid_top,
    _deep,
    _mixed_deep,
    _malformed_top,
    _bom_top,
    _with_ws(_value_leaf),
    _bare_literal_top,
    st.builds(lambda v: v + "\x00", _with_ws(_value_leaf)),
    # Object/pair coverage boost.
    _obj_top,
)
```