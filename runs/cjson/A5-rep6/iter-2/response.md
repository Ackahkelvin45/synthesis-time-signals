```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf strategies
# ---------------------------------------------------------------------------

# Safe, boring string contents.
_plain_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

# Control bytes / NUL / raw control chars inside strings (parser accepts).
_control_chars = st.sampled_from(
    ["\x00", "\x01", "\x1f", "\t", "\n", "\r", "\x7f", "\x0b", "\x0c"]
)

# Escape sequences, including \uXXXX and surrogate escapes.
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_escape = st.builds(lambda h: "\\u" + h, _hex4)

# Lone surrogates (parser rejects) and valid pairs.
_lone_high = st.sampled_from([f"\\ud{hi:02x}" for hi in range(0x800, 0xc00)])
_lone_low = st.sampled_from([f"\\ud{lo:02x}" for lo in range(0xc00, 0x1000)])
_surrogate_escape = st.one_of(_lone_high, _lone_low)

# Valid surrogate pairs (parser accepts).
_valid_surrogate_pair = st.builds(
    lambda hi, lo: f"\\ud{hi:03x}\\ud{lo:03x}",
    st.integers(min_value=0x800, max_value=0xDBF),
    st.integers(min_value=0xDC0, max_value=0xDFF),
)

_simple_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_escape = st.one_of(
    _simple_escape,
    _unicode_escape,
    _surrogate_escape,
    _valid_surrogate_pair,
)

_string_body_piece = st.one_of(
    _plain_chars,
    _control_chars,
    _escape,
)

# A string that is (mostly) well-formed, possibly containing weird escapes
# or control bytes. Sometimes unterminated / sometimes with stray quotes.
_string_body = st.lists(_string_body_piece, max_size=12).map("".join)

_wellformed_string = _string_body.map(lambda s: '"' + s + '"')

# Malformed strings: unterminated, stray quote, bad escape.
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

# Valid-ish ints, plus edge cases the parser accepts (leading zeros).
_int_part = st.one_of(
    st.just("0"),
    _nonzero_int,
    _int_digits,  # leading zeros sometimes
)

_frac_part = st.one_of(
    st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=6)),
    st.just("."),  # trailing dot: parser accepts
)

_exp_part = st.builds(
    lambda e, sign, d: e + sign + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

_sign = st.sampled_from(["", "-"])

# Extreme exponents / magnitudes (overflow to inf is accepted).
_extreme_exp = st.sampled_from(
    ["e309", "e400", "e9999", "e-9999", "E+309", "e308", "e-324", "e-400"]
)

_number = st.one_of(
    st.builds(lambda s, i: s + i, _sign, _int_part),
    st.builds(lambda s, i, f: s + i + f, _sign, _int_part, _frac_part),
    st.builds(lambda s, i, e: s + i + e, _sign, _int_part, _exp_part),
    st.builds(lambda s, i, f, e: s + i + f + e, _sign, _int_part, _frac_part, _exp_part),
    st.builds(lambda i, e: i + e, _int_part, _extreme_exp),
    # Malformed numbers (parser rejects these).
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("1."),
    st.just("0x10"),  # hex: parser accepts
    st.just("NaN"),
    st.just("Infinity"),
    st.just("+"),
    st.just("-."),
    st.just("1e"),
    st.just("1e+"),
    st.just("1e-"),
    st.just("--1"),
    st.just("00"),
    st.just("1.2.3"),
    st.just("0e"),
    st.just("0.e1"),
    st.just("e1"),
    st.just("1E"),
)

# ---------------------------------------------------------------------------
# Recursive obj/arr/value
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the parser's 1000-level limit.
_DEPTH_NEAR_LIMIT = st.integers(min_value=0, max_value=1000)

def _deep_array(depth):
    # Build "["*depth + "]"*depth, or with a value inside.
    return st.builds(
        lambda d: "[" * d + "]" * d,
        st.just(depth),
    )

def _deep_object(depth):
    return st.builds(
        lambda d: "{" * d + "}" * d,
        st.just(depth),
    )

# Whitespace (parser skips WS).
_ws = st.text(alphabet=" \t\n\r", max_size=3)

# --- malformed fragments -----------------------------------------------------
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

# More malformed structural cases.
_leading_comma_arr = st.builds(
    lambda a: "[," + a + "]",
    _string,
)
_missing_value_obj = st.builds(
    lambda k: "{" + k + ":}",
    _wellformed_string,
)
_missing_key_obj = st.builds(
    lambda v: "{:" + v + "}",
    st.just("1"),
)
_double_colon_obj = st.builds(
    lambda k: "{" + k + "::1}",
    _wellformed_string,
)
_unclosed_obj = st.builds(
    lambda k: "{" + k + ":1",
    _wellformed_string,
)
_unclosed_arr = st.builds(
    lambda a: "[" + a,
    _string,
)
_extra_close = st.builds(
    lambda a: "[" + a + "]]",
    _string,
)
_mismatched = st.builds(
    lambda a: "[" + a + "}",
    _string,
)
_nested_mismatch = st.builds(
    lambda a: "{" + _wellformed_string.map(lambda k: k + ":[" + a + "}")),
    _string,
)

# --- recursive value ---------------------------------------------------------
# Use st.recursive for obj/arr; leaves are scalars.
_value_leaf = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    # Malformed leaves at value position (parser rejects).
    st.just("tru"),
    st.just("nul"),
    st.just("TRUE"),
    st.just("None"),
    st.just("undefined"),
)

def _obj_strategy(children):
    # pair: STRING ':' value ; obj: '{' pair (',' pair)* '}' | '{' '}'
    pair = st.tuples(_wellformed_string, children).map(lambda t: t[0] + ":" + t[1])
    nonempty = st.lists(pair, min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}")
    empty = st.just("{}")
    # duplicate keys
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
    # Just under and just over the limit.
    st.just("[" * 999 + "]" * 999),
    st.just("[" * 1000 + "]" * 1000),
    st.just("[" * 1001 + "]" * 1001),
    st.just("{" * 1000 + "}" * 1000),
    st.just("{" * 1001 + "}" * 1001),
    # Unbalanced deep nesting (parser rejects).
    st.just("[" * 1001),
    st.just("[" * 1001 + "]" * 999),
    st.just("[" * 999 + "]" * 1001),
    st.just("{" * 1001),
    st.just("{" * 1001 + "}" * 999),
    st.just("{" * 999 + "}" * 1001),
    # Mixed deep nesting.
    st.just("[{" * 500 + "}]" * 500),
    st.just("[{" * 500 + "}]" * 499),
)

# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

# A leading BOM is accepted.
_bom = st.sampled_from(["", "\ufeff"])

# Trailing content after a complete value is accepted; include some.
_trailing_junk = st.one_of(
    st.just(""),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("\x00"),
    st.just("garbage"),
    st.just("}"),
    st.just("]"),
    st.just(","),
    st.just(":"),
    st.just("\n{"),
    st.just("\n["),
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
    st.just(":"),
    st.just("::"),
    st.just("[,"),
    st.just("{,"),
    st.just("[:]"),
    st.just("{:}"),
    st.just("[,]"),
    st.just("{,}"),
    _double_comma_arr,
    _missing_colon_obj,
    _trailing_comma_arr,
    _trailing_comma_obj,
    _unquoted_key,
    _single_quoted,
    _leading_comma_arr,
    _missing_value_obj,
    _missing_key_obj,
    _double_colon_obj,
    _unclosed_obj,
    _unclosed_arr,
    _extra_close,
    _mismatched,
    _nested_mismatch,
)

def _with_ws(v):
    return st.tuples(_ws, v, _ws).map(lambda t: t[0] + t[1] + t[2])

_valid_top = st.tuples(_bom, _with_ws(_value), _trailing_junk).map(
    lambda t: t[0] + t[1] + t[2]
)

strategy = st.one_of(
    _valid_top,
    _deep,
    _malformed_top,
    # Naked scalars at top level.
    _with_ws(_value_leaf),
    # Raw NUL / control bytes after a value.
    st.builds(lambda v: v + "\x00", _with_ws(_value_leaf)),
    # Raw NUL / control bytes before a value.
    st.builds(lambda v: "\x00" + v, _with_ws(_value_leaf)),
    # BOM in weird places.
    st.builds(lambda v: "\ufeff" + v, _with_ws(_value_leaf)),
    st.builds(lambda v: v + "\ufeff", _with_ws(_value_leaf)),
)
```