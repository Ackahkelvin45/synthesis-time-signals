EDIT: generate_nesting_toward_cap

```python
from hypothesis import strategies as st


# ---------- scalar building blocks ----------

_hex = "0123456789abcdefABCDEF"
_hex4 = st.lists(st.sampled_from(_hex), min_size=4, max_size=4).map("".join)

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_escapes = st.one_of(
    _hex4.map(lambda h: "\\u" + h),
    # surrogate escapes (valid pairs and lone surrogates)
    st.sampled_from(
        [
            "\\ud800", "\\udbff", "\\udc00", "\\udfff",
            "\\ud83d\\ude00", "\\ud800\\udc00", "\\udbff\\udfff",
            "\\uD800", "\\uDC00",
        ]
    ),
)

# raw characters allowed inside strings, including control/NUL bytes
_raw_safe = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0x00, max_codepoint=0x1F),
    st.sampled_from(["\x00", "\t", "\n", "\r", " ", "é", "π", "\u2028", "\uffff"]),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
)

_string_body_chunk = st.one_of(
    _raw_safe,
    _simple_escapes,
    _unicode_escapes,
    st.just("\\u"),          # malformed / truncated escapes
    st.just("\\"),
    st.just("\\x41"),        # invalid escape
    st.just("\\'"),          # invalid escape
)

_string_body = st.lists(_string_body_chunk, max_size=8).map("".join)

_json_string = _string_body.map(lambda b: '"' + b + '"')

# unterminated string (missing closing quote)
_unterminated_string = _string_body.map(lambda b: '"' + b)


# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d, rest: d + rest, st.sampled_from("123456789"), st.text("0123456789", max_size=6)),
    _digits,                                   # includes leading zeros like 01
)

_frac_part = st.one_of(
    st.just("."),
    st.builds(lambda d: "." + d, _digits),
    st.just(".000"),
)

_exp_part = st.one_of(
    st.just("e309"),
    st.just("E+309"),
    st.just("e-400"),
    st.just("e1000"),
    st.builds(lambda e, s, d: e + s + d, st.sampled_from("eE"), st.sampled_from(["", "+", "-"]), _digits),
)

# Valid JSON numbers (strict grammar: no leading zeros, no bare trailing '.',
# no hex, no NaN/Infinity). Malformed numeric forms live in _malformed.
_valid_int_part = st.one_of(
    st.just("0"),
    st.builds(
        lambda d, rest: d + rest,
        st.sampled_from("123456789"),
        st.text("0123456789", max_size=6),
    ),
)

_valid_frac_part = st.builds(lambda d: "." + d, _digits)

_valid_exp_part = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    _digits,
)

_number = st.one_of(
    _valid_int_part,
    st.builds(lambda i, f: i + f, _valid_int_part, _valid_frac_part),
    st.builds(lambda i, e: i + e, _valid_int_part, _valid_exp_part),
    st.builds(lambda i, f, e: i + f + e, _valid_int_part, _valid_frac_part, _valid_exp_part),
    st.builds(lambda i: "-" + i, _valid_int_part),
    st.builds(lambda i, f: "-" + i + f, _valid_int_part, _valid_frac_part),
    st.builds(lambda i, e: "-" + i + e, _valid_int_part, _valid_exp_part),
    st.builds(lambda i, f, e: "-" + i + f + e, _valid_int_part, _valid_frac_part, _valid_exp_part),
    st.just("-0"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-999"),
    st.just("123456789012345678901234567890"),
)


# ---------- malformed fragments (near-valid) ----------

_malformed = st.one_of(
    st.just(""),
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("-.5"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.just("tru"),
    st.just("fals"),
    st.just("nul"),
    st.just("True"),
    st.just("NULL"),
    st.just("'single'"),
    st.just("{,}"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just('{"a":1,}'),
    st.just("[1,]"),
    st.just('{"a" 1}'),
    st.just('{a:1}'),
    st.just("{'a':1}"),
    st.just("[,1]"),
    st.just("[1 2]"),
    st.just('{"a":}'),
    st.just("{:1}"),
    st.just("[,]"),
    st.just("]"),
    st.just("}"),
    st.just(":"),
    st.just(","),
    # malformed numeric forms moved here from _number
    st.just("0x10"),
    st.just("-0x1F"),
    st.just("1."),
    st.just("01"),
    st.just("00"),
    _unterminated_string,
)


# ---------- recursive value strategy ----------

_leaf = st.one_of(
    _json_string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _malformed,
)

_ws = st.sampled_from(["", " ", "\n", "\t", "\r", "  ", "\x00", "\ufeff"])


def _pair_string(key, colon, value):
    return key + colon + value


_pair = st.tuples(
    _json_string,
    st.sampled_from([":", " :", ":", ":\x00"]),
    _leaf,
).map(lambda t: _pair_string(t[0], t[1], t[2]))


def _make_obj(children):
    if not children:
        return "{}"
    return "{" + ",".join(children) + "}"


def _make_arr(children):
    if not children:
        return "[]"
    return "[" + ",".join(children) + "]"


_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        st.lists(children, max_size=4).map(_make_arr),
        st.lists(children, max_size=4).map(_make_obj),
        st.lists(_pair, max_size=4).map(_make_obj),
        st.lists(children, max_size=2).map(lambda xs: "[" + ",".join(xs) + ",]"),
        st.lists(children, max_size=2).map(lambda xs: "{" + ",".join(xs) + ",}"),
    ),
    max_leaves=12,
)


# ---------- depth-targeted generation near the 1000-level limit ----------

def _nest_open(depth):
    return "[" * depth


def _nest_close(depth):
    return "]" * depth


def _deep_array(depth):
    return "[" * depth + "1" + "]" * depth


def _deep_object(depth):
    return '{"a":' * depth + "0" + "}" * depth


def _deep_mixed(depth):
    out = []
    for i in range(depth):
        out.append("[" if i % 2 == 0 else '{"k":')
    out.append("null")
    for i in reversed(range(depth)):
        out.append("]" if i % 2 == 0 else "}")
    return "".join(out)


# Concentrate depth mass tightly around the parser's 1000-level limit so we
# actually probe the boundary (998..1002) rather than the sparse extremes.
_depth = st.one_of(
    st.integers(min_value=998, max_value=1002),
    st.sampled_from([999, 1000, 1001, 1002]),
    st.integers(min_value=0, max_value=10),
    st.integers(min_value=1001, max_value=1010),
)

_deep = st.one_of(
    st.builds(_deep_array, _depth),
    st.builds(_deep_object, _depth),
    st.builds(_deep_mixed, _depth),
)


# ---------- top-level composition ----------

def _join(parts):
    return "".join(parts)


_top = st.one_of(
    _value,
    _deep,
    _leaf,
    _malformed,
    # value with trailing content (accepted by the parser)
    st.tuples(_value, st.sampled_from(["", "abc", " 1 2", "\x00", "xyz", "{}"])).map(_join),
    # leading BOM
    st.tuples(st.just("\ufeff"), _value).map(_join),
    # whitespace-padded value
    st.tuples(_ws, _value, _ws).map(_join),
    # empty container edge cases
    st.sampled_from(["{}", "[]", " { } ", "[ ]", "{}\x00", "[]\n1"]),
)


strategy = _top
```