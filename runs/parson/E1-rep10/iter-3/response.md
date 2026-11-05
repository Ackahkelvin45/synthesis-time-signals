```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFE_ASCII = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " _-.:/@#$%^&*()+=[]{}|;'<>,?~`"
)


def _join(parts):
    return "".join(parts)


# ---------------------------------------------------------------------------
# Strings (JSON string literals, including quotes)
# ---------------------------------------------------------------------------

_escapes = st.sampled_from(
    [
        '\\"',
        "\\\\",
        "\\/",
        "\\b",
        "\\f",
        "\\n",
        "\\r",
        "\\t",
        "\\u0000",
        "\\u001f",
        "\\u0041",
        "\\u00e9",
        "\\u20ac",
        "\\uD800",
        "\\uDC00",
        "\\uD83D\\uDE00",
        "\\uFFFF",
        "\\u000a",
        "\\u007f",
    ]
)

_safe_chars = st.sampled_from(list(_SAFE_ASCII) + ["\u00e9", "\u20ac", "\U0001f600"])

_string_piece = st.one_of(_escapes, _safe_chars)


def _quoted_body(pieces):
    return '"' + "".join(pieces) + '"'


_string_literal = st.lists(_string_piece, min_size=0, max_size=8).map(_quoted_body)

# malformed / unterminated strings
_unterminated_string = st.lists(_string_piece, min_size=0, max_size=6).map(
    lambda ps: '"' + "".join(ps)
)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.just("-0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

_frac_part = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
)

_exp_part = st.one_of(
    st.just(""),
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.integers(min_value=-400, max_value=400).map(lambda n: "E+" + str(abs(n))),
    st.sampled_from(["e309", "e+309", "e-309", "e308", "e999", "e-999", "e01"]),
)


def _number(parts):
    intp, fracp, expp = parts
    return intp + fracp + expp


_number_literal = st.tuples(_int_part, _frac_part, _exp_part).map(_number)

# deliberately malformed / lenient numbers
_bad_number = st.sampled_from(
    [
        "-",
        "-.",
        "+1",
        "+0",
        ".5",
        "-.5",
        "1.",
        "01",
        "00",
        "-01",
        "1e",
        "1e+",
        "1e-",
        "1e309",
        "1E400",
        "--1",
        "1.2.3",
        "0x10",
        "Infinity",
        "NaN",
        "1_000",
    ]
)


# ---------------------------------------------------------------------------
# Recursive values
# ---------------------------------------------------------------------------

# Leaf values used at the base of recursion.
_leaf = st.one_of(
    _string_literal,
    _number_literal,
    _bad_number,
    st.sampled_from(["true", "false", "null"]),
    _unterminated_string,
)

_key = st.one_of(
    _string_literal,
    st.sampled_from(['"k"', '"a"', '"key"', '""', '"dup"', '"\\u0000"']),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \n "])


def _pair(key, value):
    return key + ":" + value


def _pairs(items):
    return ",".join(items)


def _obj_body(items):
    return "{" + ",".join(items) + "}"


def _arr_body(items):
    return "[" + ",".join(items) + "]"


# Build recursive strategy. Depth is modest here; deep nesting is added
# separately by the top-level strategy so we can target ~2048.
_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        st.tuples(_key, children).map(lambda kv: _pair(kv[0], kv[1])),
        st.lists(
            st.tuples(_key, children).map(lambda kv: _pair(kv[0], kv[1])),
            max_size=4,
        ).map(_obj_body),
        st.lists(children, max_size=4).map(_arr_body),
    ),
    max_leaves=12,
)

# Duplicate-key objects (expect rejection by the parser).
_dup_key_obj = st.tuples(_key, _value).map(
    lambda kv: "{" + _pair(kv[0], kv[1]) + "," + _pair(kv[0], kv[1]) + "}"
)


# ---------------------------------------------------------------------------
# Deep nesting near the parser limit (2048)
# ---------------------------------------------------------------------------

# Concentrate depth near 2048: mostly in [2000, 2050], plus some below/above.
_deep_depth = st.one_of(
    st.integers(min_value=2000, max_value=2050),
    st.integers(min_value=1, max_value=64),
    st.integers(min_value=2040, max_value=2060),
    st.integers(min_value=1900, max_value=2100),
)


def _deep_value(depth):
    # Alternate '[' and '{' nesting to exercise both openers.
    openers = []
    closers = []
    for i in range(depth):
        if i % 2 == 0:
            openers.append("[")
            closers.append("]")
        else:
            openers.append('{"k":')
            closers.append("}")
    inner = "0"
    return "".join(openers) + inner + "".join(reversed(closers))


_deep_nesting = _deep_depth.map(_deep_value)


# ---------------------------------------------------------------------------
# Near-valid-but-malformed top-level fragments
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        "[1,]",
        "[,1]",
        "[1,,2]",
        '{"a":1,}',
        '{"a":}',
        '{"a" 1}',
        '{"a":1 "b":2}',
        "{,}",
        "[,]",
        '{"a":1',
        "[1,2",
        '"unterminated',
        '"bad\\escape"',
        '"\\u12"',
        '"\\uZZZZ"',
        "{",
        "[",
        "}",
        "]",
        ":",
        ",",
        "",
        "   ",
        "tru",
        "fals",
        "nul",
        "truex",
        "nullx",
        "falsex",
    ]
)

# Trailing content after a complete value (parser accepts it).
_trailing = st.tuples(_value, st.sampled_from(["", "x", " garbage", "[]xyz", "1abc", "\n\n{}"])).map(
    lambda tv: tv[0] + tv[1]
)


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _value,
    _dup_key_obj,
    _deep_nesting,
    _malformed,
    _trailing,
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("0"),
    st.just("-"),
    st.just("1e309"),
    st.just('{"k":0,"k":1}'),
    st.just('"\\u0000"'),
    st.just('"\\uD800"'),
)
```