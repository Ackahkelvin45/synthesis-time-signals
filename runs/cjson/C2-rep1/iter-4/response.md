```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters that are "safe" inside a JSON string (no quote, no backslash,
# no raw control chars) -- the grammar's SAFECODEPOINT.
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08'
    "\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19"
    "\x1a\x1b\x1c\x1d\x1e\x1f",
)

# Raw control / NUL bytes that the parser accepts inside strings.
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x0b", "\x0c"]
)

# Escapes the grammar allows.
_simple_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _hex4(draw):
    return "".join(draw(st.lists(_hex_digit, min_size=4, max_size=4)))


@st.composite
def _unicode_escape(draw):
    return "\\u" + draw(_hex4())


# A lone surrogate escape -- the parser rejects these.
_lone_surrogate_escape = st.sampled_from(
    ["\\ud800", "\\udfff", "\\uD800", "\\uDC00", "\\uDFFF"]
)


@st.composite
def _string_body(draw):
    """Pieces that may appear between the quotes of a string literal."""
    piece = st.one_of(
        _safe_char.map(str),
        _raw_control,
        _simple_escapes,
        _unicode_escape(),
        _lone_surrogate_escape,
    )
    n = draw(st.integers(min_value=0, max_value=12))
    return "".join(draw(st.lists(piece, min_size=n, max_size=n)))


@st.composite
def _json_string(draw):
    return '"' + draw(_string_body()) + '"'


# A string that is deliberately unterminated (no closing quote).
@st.composite
def _unterminated_string(draw):
    return '"' + draw(_string_body())


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text("123456789", min_size=1, max_size=1).flatmap(
    lambda first: st.tuples(
        st.just(first), st.text("0123456789", min_size=0, max_size=5)
    ).map(lambda t: t[0] + t[1])
)

# INT: '0' | [1-9][0-9]*
_int_part = st.one_of(
    st.just("0"),
    _nonzero_digits,
    # leading zeros -- parser accepts, strict rejects
    st.text("0123456789", min_size=2, max_size=6).filter(
        lambda s: s[0] == "0"
    ),
)

# Exponent: [Ee][+-]?[0-9]+
_exp_part = st.one_of(
    st.tuples(st.sampled_from(["e", "E"]),
              st.sampled_from(["", "+", "-"]),
              st.text("0123456789", min_size=1, max_size=4))
    .map(lambda t: t[0] + t[1] + t[2]),
    # extreme exponents for overflow
    st.sampled_from(["e309", "e-309", "e999", "e308", "E+308", "e-999",
                     "e01", "e+01"]),
)

# Fraction: '.' [0-9]+
_frac_part = st.one_of(
    st.text("0123456789", min_size=1, max_size=6).map(lambda s: "." + s),
    # trailing dot -- parser accepts, strict rejects
    st.just("."),
)


@st.composite
def _number(draw):
    sign = draw(st.sampled_from(["", "-"]))
    int_part = draw(_int_part)
    frac = draw(st.one_of(st.none(), _frac_part))
    exp = draw(st.one_of(st.none(), _exp_part))
    body = int_part
    if frac is not None:
        body += frac
    if exp is not None:
        body += exp
    return sign + body


# Malformed-but-close numbers the parser rejects.
_malformed_number = st.sampled_from([
    "-", "+1", ".5", "-.5", "+.5", "NaN", "Infinity", "-Infinity",
    "01", "00", "1.", "1..2", "1e", "1e+", "1e-", "--1", "1-2",
    "0x", "0xG", "1.2.3", "+", "e5", ".", "-.",
])


# ---------------------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------------------

# Depth near the parser's 1000-level nesting limit.
_NEAR_LIMIT_DEPTH = st.integers(min_value=990, max_value=1005)


@st.composite
def _deep_nesting(draw):
    """A deeply nested array/object near the 1000-level limit."""
    depth = draw(_NEAR_LIMIT_DEPTH)
    inner = draw(_number())
    if draw(st.booleans()):
        # arrays
        return "[" * depth + inner + "]" * depth
    else:
        # objects
        return '{"k":' * depth + inner + "}" * depth


# Terminal (non-recursive) values.
_leaf = st.one_of(
    _json_string(),
    _number(),
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _malformed_number,
    _unterminated_string(),
)

# Malformed structural fragments.
_malformed_structural = st.sampled_from([
    "{}", "[]", "[1,]", '{"a":1,}', "[,1]", "[1,,2]", '{"a":}',
    '{"a"}', '{"a" 1}', '{"a":1 "b":2}', "[1 2]", "{", "}", "[", "]",
    '{"a":1', "[1,2", '{"a"', '{"a":', '{"a":1,"b"', "[1,2,",
    "{,}", "[:]", "{:1}", "[1:2]", "}", "{", "]", "[", '"', "'a'",
    "{'a':1}", "{a:1}", "tru", "fals", "nul", "TRUE", "True", "NULL",
    "1abc", "1 2",
])


@st.composite
def _obj(draw):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        return "{}"
    pairs = []
    for _ in range(n):
        key = draw(_json_string())
        val = draw(_value())
        pairs.append(key + ":" + val)
    return "{" + ",".join(pairs) + "}"


@st.composite
def _arr(draw):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        return "[]"
    items = [draw(_value()) for _ in range(n)]
    return "[" + ",".join(items) + "]"


_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        children,
        _arr(),
        _obj(),
    ),
    max_leaves=8,
)


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

@st.composite
def _top(draw):
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        # deep nesting near the limit
        return draw(_deep_nesting())
    if kind == 1:
        # duplicate keys
        return draw(st.sampled_from([
            '{"a":1,"a":2}',
            '{"a":1,"a":2,"a":3}',
            '{"x":{"y":1},"x":{"y":2}}',
            '{"k":1,"k":2,"k":3,"k":4}',
        ]))
    if kind == 2:
        # extreme magnitudes / exponents
        return draw(st.sampled_from([
            "1e309", "-1e309", "1e-309", "1e999", "1e-999",
            "1.7976931348623157e308", "1.7976931348623157e309",
            "2.2250738585072014e-308", "0.0", "-0.0",
            "1e01", "1E+01", "1e-01", "0e0", "0E0",
            "123456789012345678901234567890",
            "-123456789012345678901234567890",
            "1.0e309", "1e+308", "1e-308",
        ]))
    if kind == 3:
        # surrogate / unicode escapes
        return draw(st.sampled_from([
            '"\\u0041"', '"\\u00e9"', '"\\ud83d\\ude00"',
            '"\\ud800"', '"\\udfff"', '"\\uD800"', '"\\uDC00"',
            '"\\u0000"', '"\\uFFFF"', '"\\u1234"', '"\\uabcd"',
            '"\\uD83D\\uDE00"', '"a\\ud800b"',
        ]))
    if kind == 4:
        # embedded NUL / control bytes
        return draw(st.sampled_from([
            '"\x00"', '"a\x00b"', '"\x01\x02\x03"', '"\t\n\r"',
            '"a\tb"', '"a\nb"', '"\x1f"', '"\x0b\x0c"',
            '"\x00\x01\x02\x03\x04"', '[\x00]', '{\x00}',
            '1\x00', '"abc"\x00', '\x00',
        ]))
    if kind == 5:
        # near-valid-but-malformed
        return draw(_malformed_structural)
    if kind == 6:
        # BOM
        return draw(st.sampled_from([
            "\ufeff1", "\ufeff{}", "\ufeff[]", "\ufefftrue",
            '\ufeff{"a":1}',
        ]))
    if kind == 7:
        # trailing content after a complete value (accepted)
        return draw(
            st.tuples(
                st.one_of(_number(), _json_string(), st.just("true"),
                          st.just("null"), st.just("{}"), st.just("[]")),
                st.sampled_from(["abc", " 1 2", "xyz", "\x00", "junk",
                                 '"extra"', "{}", "[]"]),
            ).map(lambda t: t[0] + t[1])
        )
    if kind == 8:
        # whitespace / empty-ish
        return draw(st.sampled_from([
            "", " ", "\t", "\n", "\r\n", "   \n\t  ",
            " \t\n\r ", "\x00", "  \x00  ",
        ]))
    # kind == 9: a normal, well-formed value
    return draw(_value())


strategy = _top()
```