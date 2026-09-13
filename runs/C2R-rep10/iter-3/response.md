```python
import json
from hypothesis import strategies as st

# --- helpers ---------------------------------------------------------------

def _join(parts):
    return "".join(parts)


def _join_comma(parts):
    return ",".join(parts)


# --- scalar building blocks ------------------------------------------------

# safe string characters (no control, no quote, no backslash)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

# raw control / NUL bytes that may appear inside strings (parser is lenient)
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x09", "\x0a", "\x0b", "\x0c", "\x0d", "\x1f"]
)

_escape_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")
_unicode_escape = st.tuples(st.just("\\u"), _hex_digit, _hex_digit, _hex_digit, _hex_digit).map(
    _join
)

# lone high surrogate / low surrogate escapes
_surrogate_escape = st.tuples(
    st.just("\\u"),
    st.sampled_from("dD"),
    st.sampled_from("89abAB"),
    _hex_digit,
    _hex_digit,
).map(_join)

_string_body_piece = st.one_of(
    _safe_char.map(str),
    _escape_simple,
    _raw_control,
    _unicode_escape,
    _surrogate_escape,
)

_string_body = st.lists(_string_body_piece, max_size=12).map(_join)

# a valid quoted string
string_lit = st.tuples(st.just('"'), _string_body, st.just('"')).map(_join)

# near-valid: unterminated string
unterminated_string = st.tuples(st.just('"'), _string_body).map(_join)

# --- numbers ---------------------------------------------------------------

_small_int = st.integers(min_value=0, max_value=9).map(str)
_nonzero_lead = st.integers(min_value=1, max_value=9).map(str)
_digits = st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=8).map(
    _join
)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(_nonzero_lead, _digits).map(_join),
)

_frac_part = st.tuples(st.just("."), _digits).map(_join)

_exp_part = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    _digits,
).map(_join)

# extreme exponent magnitudes
_huge_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.sampled_from(["309", "310", "999", "1000", "100000", "999999999"]),
).map(_join)

number_lit = st.one_of(
    st.tuples(st.just("-"), _int_part).map(_join),
    _int_part,
    st.tuples(_int_part, _frac_part).map(_join),
    st.tuples(st.just("-"), _int_part, _frac_part).map(_join),
    st.tuples(_int_part, _exp_part).map(_join),
    st.tuples(st.just("-"), _int_part, _exp_part).map(_join),
    st.tuples(_int_part, _frac_part, _exp_part).map(_join),
    st.tuples(st.just("-"), _int_part, _frac_part, _exp_part).map(_join),
    # overflow magnitude
    st.tuples(_int_part, _huge_exp).map(_join),
    st.tuples(st.just("-"), _int_part, _huge_exp).map(_join),
    # lone minus (parser accepts)
    st.just("-"),
)

# malformed numbers
bad_number = st.one_of(
    st.tuples(st.just("+"), _digits).map(_join),
    st.tuples(st.just("."), _digits).map(_join),
    st.tuples(st.just("0"), _digits).map(_join),
    st.tuples(st.just("0x"), st.sampled_from("0123456789abcdefABCDEF")).map(_join),
    st.tuples(_int_part, st.just(".")).map(_join),
)

# --- recursive structure ---------------------------------------------------

# forward-declared via st.recursive
value = st.recursive(
    st.one_of(
        string_lit,
        number_lit,
        st.sampled_from(["true", "false", "null"]),
        st.just("{}"),
        st.just("[]"),
    ),
    lambda children: st.one_of(
        _obj(children),
        _arr(children),
    ),
    max_leaves=40,
)


def _obj(children):
    pair = st.tuples(string_lit, st.just(":"), children).map(_join)
    member_list = st.lists(pair, min_size=1, max_size=6)
    body = member_list.map(_join_comma)
    # bias toward objects with members; include empty and trailing comma
    return st.one_of(
        st.tuples(st.just("{"), body, st.just("}")).map(_join),
        st.tuples(st.just("{"), body, st.just(",}")).map(_join),
        st.just("{}"),
    )


def _arr(children):
    elems = st.lists(children, min_size=1, max_size=6)
    body = elems.map(_join_comma)
    return st.one_of(
        st.tuples(st.just("["), body, st.just("]")).map(_join),
        st.tuples(st.just("["), body, st.just(",]")).map(_join),
        st.just("[]"),
    )


# --- malformed / near-valid inputs ----------------------------------------

_malformed = st.one_of(
    # double commas
    st.tuples(st.just("["), value, st.just(",,"), value, st.just("]")).map(_join),
    st.tuples(st.just("[,"), value, st.just("]")).map(_join),
    st.tuples(st.just("[,]")).map(_join),
    # missing colon in object
    st.tuples(st.just("{"), string_lit, value, st.just("}")).map(_join),
    # unterminated string
    unterminated_string,
    st.tuples(st.just("["), unterminated_string, st.just("]")).map(_join),
    # bad numbers
    bad_number,
    st.tuples(st.just("["), bad_number, st.just("]")).map(_join),
    # trailing content
    st.tuples(value, st.sampled_from(["abc", "x", " garbage", " true"])).map(_join),
    # bare keys
    st.tuples(st.just("{"), st.sampled_from(["a", "key", "_x"]), st.just(":1}")).map(_join),
    # single quotes
    st.tuples(st.just("'"), _string_body, st.just("'")).map(_join),
)


# --- top-level strategy ----------------------------------------------------

strategy = st.one_of(
    value,
    _malformed,
)
```