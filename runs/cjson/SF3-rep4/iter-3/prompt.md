Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

# Safe printable code points (no quote, no backslash, no raw control).
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

_safe_text = st.text(alphabet=_safe_char, max_size=8)

# Raw control bytes / NUL that the parser tolerates inside strings.
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]
)

# Simple escapes.
_simple_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    _hex_digit, _hex_digit, _hex_digit, _hex_digit,
)

# Surrogate escapes (parser rejects lone ones; include for coverage).
_surrogate_escape = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    st.sampled_from("dD"), st.sampled_from("89abAB"), _hex_digit, _hex_digit,
)

_escape = st.one_of(_simple_escape, _unicode_escape, _surrogate_escape)

# A string body piece: safe text, raw control, or escape.
_body_piece = st.one_of(_safe_text, _raw_control, _escape)

_string_body = st.lists(_body_piece, max_size=6).map("".join)


def _make_string():
    return _string_body.map(lambda b: '"' + b + '"')


_string = _make_string()

# Unterminated string (malformed).
_unterminated_string = _string_body.map(lambda b: '"' + b)

# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_simple_int = st.one_of(
    st.just("0"),
    _int_digits,
    st.builds(lambda d: "-" + d, _int_digits),
)

# Leading-zero integers (accepted by parser).
_leading_zero_int = st.builds(
    lambda z, d: "0" + z + d,
    st.text(alphabet="0123456789", min_size=1, max_size=4),
    st.text(alphabet="0123456789", min_size=0, max_size=3),
)

# Hex numbers (accepted by parser).
_hex_number = st.builds(
    lambda sign, h: sign + "0x" + h,
    st.sampled_from(["", "-"]),
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8),
)

_fraction = st.builds(
    lambda d: "." + d,
    st.text(alphabet="0123456789", min_size=1, max_size=6),
)

# Trailing dot (accepted).
_trailing_dot = st.just(".")

_exponent = st.builds(
    lambda e, sign, d: e + sign + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

# Extreme exponents (overflow to inf).
_extreme_exponent = st.builds(
    lambda d, e: d + "e" + e,
    st.text(alphabet="123456789", min_size=1, max_size=3),
    st.sampled_from(["309", "310", "400", "-309", "-400"]),
)

_float_number = st.builds(
    lambda ip, fr, ex: ip + fr + ex,
    _simple_int,
    st.one_of(_fraction, _trailing_dot),
    st.one_of(st.just(""), _exponent),
)

_number = st.one_of(
    _simple_int,
    _leading_zero_int,
    _hex_number,
    _float_number,
    _extreme_exponent,
)

# Malformed numbers.
_bad_number = st.one_of(
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("-.5"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# ---------- recursive structure ----------

_json_string = st.one_of(_string, _unterminated_string)

_json_number = st.one_of(_number, _bad_number)

_key = _string

_ws = st.text(alphabet=" \t\n\r", max_size=2)

_literal = st.sampled_from(["true", "false", "null"])

# Malformed separators / punctuation.
_bad_token = st.sampled_from(
    [",", ":", "{", "}", "[", "]", ",,", "::", "}{", "][", "'", '"']
)


def _build_value(children):
    return st.one_of(
        _json_string,
        _json_number,
        _literal,
        _bad_token,
        children,
    )


def _make_obj(inner):
    # pair: key : value
    pair = st.builds(
        lambda k, ws1, ws2, v: k + ws1 + ":" + ws2 + v,
        _key,
        _ws,
        _ws,
        inner,
    )
    pairs = st.lists(pair, max_size=4).map(lambda ps: ",".join(ps))
    # empty object, normal object, trailing comma object (malformed)
    normal = st.builds(
        lambda ws1, body, ws2: "{" + ws1 + body + ws2 + "}",
        _ws, pairs, _ws,
    )
    empty = st.builds(lambda ws1, ws2: "{" + ws1 + ws2 + "}", _ws, _ws)
    trailing_comma = st.builds(
        lambda body: "{" + body + ",}",
        pairs,
    )
    missing_colon = st.builds(
        lambda k, v: "{" + k + " " + v + "}",
        _key, inner,
    )
    return st.one_of(normal, empty, trailing_comma, missing_colon)


def _make_arr(inner):
    elems = st.lists(inner, max_size=4).map(lambda xs: ",".join(xs))
    normal = st.builds(
        lambda ws1, body, ws2: "[" + ws1 + body + ws2 + "]",
        _ws, elems, _ws,
    )
    empty = st.builds(lambda ws1, ws2: "[" + ws1 + ws2 + "]", _ws, _ws)
    trailing_comma = st.builds(lambda body: "[" + body + ",]", elems)
    double_comma = st.builds(lambda body: "[" + body + ",,]", elems)
    return st.one_of(normal, empty, trailing_comma, double_comma)


# Recursive value strategy; depth bounded well below/around the 1000 limit.
_value = st.recursive(
    _json_number,
    lambda children: st.one_of(
        _make_obj(children),
        _make_arr(children),
    ),
    max_leaves=12,
)

# ---------- depth-focused generators near the 1000-level limit ----------

def _nested_array(depth):
    return "[" * depth + "]" * depth


def _nested_object(depth):
    return '{"a":' * depth + "1" + "}" * depth


_depth_near_limit = st.integers(min_value=990, max_value=1002).map(_nested_array)
_depth_obj_near_limit = st.integers(min_value=990, max_value=1002).map(_nested_object)

# ---------- combining ----------

_ws_wrapped = st.builds(
    lambda lead, v, trail: lead + v + trail,
    _ws, _value, _ws,
)

# Trailing content after a complete value (accepted by parser).
_trailing_content = st.builds(
    lambda v, junk: v + junk,
    _value,
    st.one_of(
        st.just("abc"),
        st.just(" 1 2"),
        st.just("\x00"),
        _bad_token,
        _safe_text,
    ),
)

_bom = st.builds(lambda v: "\ufeff" + v, _value)

_top_level = st.one_of(
    _value,
    _ws_wrapped,
    _trailing_content,
    _bom,
    _depth_near_limit,
    _depth_obj_near_limit,
    st.just(""),
    st.just("   "),
    _bad_token,
)

strategy = _top_level
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 75.57,
  "region_coverage_pct": 92.16,
  "least_covered_functions": [
    "cJSON_Compare (0% of branches)",
    "print_value (0% of branches)",
    "print_string_ptr (0% of branches)",
    "print_number (0% of branches)",
    "print_object (0% of branches)"
  ]
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.