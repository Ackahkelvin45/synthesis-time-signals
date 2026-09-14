```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Characters that are safe inside a JSON string per the grammar
_safe_chars = (
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF)
    .filter(lambda c: c not in '"\\')
)

# Raw control bytes and NUL - allowed by the harness even though the grammar
# forbids them inside strings; good for fuzzing the parser's byte handling.
_control_chars = st.characters(min_codepoint=0x00, max_codepoint=0x1F)

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")


def _hex4():
    return st.tuples(*([_hex_digit] * 4)).map(lambda t: "".join(t))


_unicode_escape = _hex4().map(lambda h: "\\u" + h)

_simple_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_esc = st.one_of(_simple_escape, _unicode_escape)

# A string body: mixture of safe chars, escapes, controls, and raw NUL.
_string_body = st.one_of(
    _safe_chars,
    _esc,
    _control_chars,
)


def _make_string(body):
    return '"' + body + '"'


# JSON strings (well-formed)
json_string = st.lists(_string_body, max_size=12).map("".join).map(_make_string)

# Strings with embedded NUL bytes / control bytes deliberately
nul_string = st.lists(
    st.one_of(_safe_chars, st.just("\x00"), _control_chars), max_size=8
).map("".join).map(_make_string)

# Unterminated strings (malformed)
unterminated_string = st.lists(_string_body, min_size=1, max_size=8).map(
    lambda parts: '"' + "".join(parts)
)

# ---------- numbers ----------

_int_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text("0123456789", min_size=1, max_size=6)

_int_part = st.one_of(st.just("0"), _nonzero_digits)

_frac = st.tuples(st.just("."), _int_digits).map(lambda t: t[0] + t[1])

_exp_sign = st.sampled_from(["", "+", "-"])
_exp = st.tuples(
    st.sampled_from(["e", "E"]), _exp_sign, _int_digits
).map(lambda t: t[0] + t[1] + t[2])

_opt_frac = st.one_of(st.just(""), _frac)
_opt_exp = st.one_of(st.just(""), _exp)

json_number = st.tuples(
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    _opt_frac,
    _opt_exp,
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# Extreme magnitudes / overflow
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e308",
        "1e-309",
        "1E+400",
        "1e999999999999999999",
        "0e0",
        "-0",
        "-0.0",
        "1.7976931348623157e308",
        "5e-324",
        "1e-400",
        "123456789012345678901234567890",
        "0.0000000000000000000000000000001",
    ]
)

# Malformed / near-valid numbers
_bad_number = st.sampled_from(
    [
        "+1",
        ".5",
        "1.",
        "01",
        "0x1F",
        "-",
        "-.",
        "1e",
        "1e+",
        "1e-",
        "--1",
        "1..2",
        "1ee2",
    ]
)

_number = st.one_of(json_number, _extreme_number, _bad_number)

# ---------- recursive values ----------

_json_value = st.deferred(lambda: _value_strategy)


def _obj_member():
    key = st.one_of(json_string, nul_string)
    val = _json_value
    return st.tuples(key, st.just(":"), val).map(lambda t: t[0] + t[1] + t[2])


_member = _obj_member()

# Objects with members (biased), plus empty object
_obj_with_members = st.lists(_member, min_size=1, max_size=6).map(
    lambda parts: "{" + ",".join(parts) + "}"
)

# Objects with a single trailing comma (accepted by parser)
_obj_trailing_comma = st.lists(_member, min_size=1, max_size=5).map(
    lambda parts: "{" + ",".join(parts) + ",}"
)

# Duplicate keys
_duplicate_key_obj = st.tuples(
    st.one_of(json_string, nul_string),
    _json_value,
    _json_value,
).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}")

_empty_obj = st.just("{}")

_obj = st.one_of(
    _obj_with_members,
    _obj_trailing_comma,
    _duplicate_key_obj,
    _empty_obj,
)

# Arrays
_arr_with_values = st.lists(_json_value, min_size=1, max_size=6).map(
    lambda parts: "[" + ",".join(parts) + "]"
)

_arr_trailing_comma = st.lists(_json_value, min_size=1, max_size=5).map(
    lambda parts: "[" + ",".join(parts) + ",]"
)

_empty_arr = st.just("[]")

_arr = st.one_of(_arr_with_values, _arr_trailing_comma, _empty_arr)

# Malformed composite structures
_malformed = st.one_of(
    # double commas
    st.lists(_json_value, min_size=1, max_size=4).map(
        lambda parts: "[" + ",,".join(parts) + "]"
    ),
    st.just("[,]"),
    st.just("[,1]"),
    st.just("[1,,2]"),
    # missing colon
    st.tuples(json_string, _json_value).map(lambda t: "{" + t[0] + " " + t[1] + "}"),
    # unterminated array
    st.lists(_json_value, min_size=1, max_size=4).map(
        lambda parts: "[" + ",".join(parts)
    ),
    # unterminated object
    st.tuples(json_string, _json_value).map(lambda t: "{" + t[0] + ":" + t[1]),
    # lone '-' as a number
    st.just("-"),
    # trailing content after a value
    st.tuples(_json_value, st.sampled_from(["abc", "xyz", " garbage", " false"])).map(
        lambda t: t[0] + t[1]
    ),
    # bare keys
    st.tuples(
        st.text("abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=4), _json_value
    ).map(lambda t: "{" + t[0] + ":" + t[1] + "}"),
    # single quotes
    st.text("abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=4).map(
        lambda s: "'" + s + "'"
    ),
)


def _leaf():
    return st.one_of(
        json_string,
        nul_string,
        unterminated_string,
        _number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )


def _value_strategy():
    return st.one_of(
        _leaf(),
        _obj,
        _arr,
        _malformed,
    )


# Recursive strategy: leaves + containers, with varying depth (no cap).
_recursive_value = st.recursive(
    _leaf(),
    lambda children: st.one_of(
        st.lists(children, min_size=1, max_size=6).map(
            lambda parts: "[" + ",".join(parts) + "]"
        ),
        st.lists(children, min_size=1, max_size=5).map(
            lambda parts: "[" + ",".join(parts) + ",]"
        ),
        st.lists(
            _obj_member_with(children), min_size=1, max_size=6
        ).map(lambda parts: "{" + ",".join(parts) + "}"),
        st.lists(
            _obj_member_with(children), min_size=1, max_size=5
        ).map(lambda parts: "{" + ",".join(parts) + ",}"),
        st.just("{}"),
        st.just("[]"),
    ),
    max_leaves=20,
)


def _obj_member_with(value_strategy):
    key = st.one_of(json_string, nul_string)
    return st.tuples(key, st.just(":"), value_strategy).map(
        lambda t: t[0] + t[1] + t[2]
    )


# Deep nesting generators (no depth cap)
def _deep_nesting():
    depth = st.integers(min_value=1, max_value=200)
    return depth.flatmap(
        lambda d: st.just("[" * d + "]" * d)
    )


def _deep_obj_nesting():
    depth = st.integers(min_value=1, max_value=200)
    return depth.flatmap(
        lambda d: st.just(
            "{" + '"k":' + "{" * d + "}" * d + "}"
        )
    )


# Whole-document strategy
strategy = st.one_of(
    _recursive_value,
    _malformed,
    _deep_nesting(),
    _deep_obj_nesting(),
    st.just(""),
    st.just("   "),
    st.just("\x00"),
    st.just('"\\uD800"'),
    st.just('"\\uDC00"'),
    st.just('"\\uD800\\uDC00"'),
    st.just('"\\uD800\\uD800"'),
    st.just('"\\u0000"'),
    st.just('"\x00"'),
    st.just('{"a":1,"a":2}'),
    st.just("[1,2,]"),
    st.just("{\"a\":1,}"),
    st.just("-"),
    st.just("1e309"),
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("[1,,2]"),
    st.just("{\"a\" 1}"),
    st.just('"unterminated'),
)
```