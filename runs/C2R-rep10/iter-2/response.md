```python
import json

from hypothesis import strategies as st

# ---------- low-level leaves ----------

# Safe code points: anything except '"', '\\', and C0 controls.
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F or ord(c) < 0x00)

# Raw control bytes / NUL embedded in strings (parser reads by length).
_control_char = st.sampled_from(
    ["\x00", "\x01", "\x08", "\x0b", "\x0c", "\x1f", "\x7f"]
)

# Escapes allowed by the grammar's ESC fragment.
_simple_escape = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes (lone and paired) — classic edge class.
_surrogate_escape = st.sampled_from(
    [
        "\\ud800",
        "\\udbff",
        "\\udc00",
        "\\udfff",
        "\\uD83D\\uDE00",  # paired surrogate
        "\\uD800\\uD800",  # double high surrogate
        "\\udc00\\ud800",  # low then high
    ]
)

_string_body_piece = st.one_of(
    _safe_char.map(str),
    _control_char,
    _simple_escape,
    _unicode_escape,
    _surrogate_escape,
)

# A well-formed JSON string literal.
json_string = st.lists(_string_body_piece, max_size=8).map(lambda ps: '"' + "".join(ps) + '"')


# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map(lambda t: t[0] + t[1]),
    _digits,
)

_frac = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits,
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_sign = st.sampled_from(["", "-"])

_regular_number = st.tuples(_sign, _int_part, _frac, _exp).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)

# Extreme magnitudes / exponents, including overflow (1e309) and underflow.
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1E+308",
        "1e999999999",
        "-0",
        "0e0",
        "1e01",
        "1.7976931348623157e309",
        "5e-324",
        "1" + "0" * 30,
        "-" + "9" * 40,
    ]
)

# Parser leniency: lone '-' accepted as a number.
_lone_minus = st.just("-")

number = st.one_of(_regular_number, _extreme_number, _lone_minus)


# ---------- malformed / near-valid fragments ----------

_malformed_string = st.sampled_from(
    [
        '"unterminated',
        '"trailing backslash\\',
        '"bad escape \\x"',
        '"short unicode \\u12"',
        '"nonhex unicode \\uZZZZ"',
        '"raw newline\ninside"',
        '"\x00null\x00inside"',
    ]
)

_malformed_number = st.sampled_from(
    [
        "+1",
        ".5",
        "1.",
        "01",
        "00",
        "-01",
        "0x1F",
        "1e",
        "1e+",
        "--1",
        "1..2",
        "1e1e1",
    ]
)

_malformed_punct = st.sampled_from(
    [
        ",",
        ":",
        "}",
        "]",
        "{",
        "[",
        "{},",
        "[,]",
        "[1,,2]",
        "{,}",
        '{"a" 1}',
        '{"a":}',
        "{:1}",
        '{"a":1,,"b":2}',
        "[1 2]",
        '{"a":1 "b":2}',
    ]
)

malformed = st.one_of(
    _malformed_string,
    _malformed_number,
    _malformed_punct,
)


# ---------- recursive structure ----------

def _wrap_value(v):
    """Identity helper documenting that v is already a JSON text fragment."""
    return v


# Placeholder used to build the recursive strategy.
value = st.deferred(lambda: _value_strategy)


_true_false_null = st.sampled_from(["true", "false", "null"])

# A pair: STRING ':' value. Duplicate keys are permitted and encouraged.
pair = st.tuples(json_string, st.just(":"), value).map(lambda t: t[0] + t[1] + t[2])

# Object with members (stressed first-pass path) — biased heavily.
obj_with_members = st.lists(pair, min_size=1, max_size=5).map(
    lambda ps: "{" + ",".join(ps) + "}"
)

# Empty object.
empty_obj = st.just("{}")

# Object with a single trailing comma (parser leniency).
obj_trailing_comma = st.lists(pair, min_size=1, max_size=4).map(
    lambda ps: "{" + ",".join(ps) + ",}"
)

obj = st.one_of(
    obj_with_members,
    obj_with_members,
    obj_with_members,
    empty_obj,
    obj_trailing_comma,
)

arr_with_members = st.lists(value, min_size=1, max_size=5).map(
    lambda vs: "[" + ",".join(vs) + "]"
)

empty_arr = st.just("[]")

arr_trailing_comma = st.lists(value, min_size=1, max_size=4).map(
    lambda vs: "[" + ",".join(vs) + ",]"
)

arr = st.one_of(
    arr_with_members,
    arr_with_members,
    empty_arr,
    arr_trailing_comma,
)

# Deep nesting: many brackets/braces around a scalar.
def _deep_nesting(draw):
    depth = draw(st.integers(min_value=1, max_value=200))
    kind = draw(st.sampled_from(["arr", "obj"]))
    inner = draw(st.sampled_from(["1", "null", "true", '"x"']))
    if kind == "arr":
        return "[" * depth + inner + "]" * depth
    # nested objects with a single key each
    return '{"a":' * depth + inner + "}" * depth


deep_value = st.composite(_deep_nesting)

_value_strategy = st.one_of(
    json_string,
    number,
    obj,
    arr,
    _true_false_null,
    deep_value,
    malformed,
)

value = _value_strategy


# ---------- top-level strategy ----------

# Top-level: a complete JSON document, sometimes wrapped in whitespace,
# sometimes with trailing garbage (should be rejected — still valuable).
_ws = st.text(alphabet=" \t\n\r", max_size=3)

_trailing_garbage = st.sampled_from(["", "x", "garbage", " false", "]" , "}"])

_top = st.tuples(_ws, value, _ws, _trailing_garbage).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)

strategy = st.one_of(
    _top,
    value,
    malformed,
)
```