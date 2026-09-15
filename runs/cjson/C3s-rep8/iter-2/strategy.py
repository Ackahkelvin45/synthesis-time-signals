import json

from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A JSON string literal, including quotes.  We deliberately include escapes
# that the parser accepts (raw control chars, NUL) and escapes it rejects
# (lone surrogates) so the fuzzer can explore both sides of the boundary.
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

_ESCAPED = st.sampled_from(
    [
        '\\"',
        "\\\\",
        "\\/",
        "\\b",
        "\\f",
        "\\n",
        "\\r",
        "\\t",
    ]
)

# \uXXXX escapes -- both valid and (deliberately) lone-surrogate forms.
_HEX4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_UNICODE_ESCAPE = st.one_of(
    st.builds(lambda h: "\\u" + h, _HEX4),
    # High/low surrogates, some of which are lone (rejected by parser).
    st.sampled_from(
        [
            "\\ud800",
            "\\udfff",
            "\\udc00",
            "\\ud83d\\ude00",
            "\\u0000",
            "\\u001f",
            "\\uffff",
        ]
    ),
)

_STRING_BODY_PIECE = st.one_of(
    _SAFE_CHARS,
    _ESCAPED,
    _UNICODE_ESCAPE,
    # Raw control / NUL bytes inside strings -- accepted by this parser.
    st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
)

_STRING_BODY = st.lists(_STRING_BODY_PIECE, max_size=12).map("".join)

_STRING = _STRING_BODY.map(lambda s: '"' + s + '"')


# ---------------------------------------------------------------------------
# Numbers -- cover extreme magnitudes, exponents, and near-valid malformed.
# ---------------------------------------------------------------------------

_INT_PART = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=10, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

_EXP_PART = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=999).map(str),
    ).map("".join),
)

_FRAC_PART = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
    st.just("."),  # trailing dot -- accepted by this parser
)

_VALID_NUMBER = st.tuples(_INT_PART, _FRAC_PART, _EXP_PART).map("".join)

# Extreme magnitudes, including overflow to inf.
_EXTREME_NUMBER = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e1000",
        "-1e1000",
        "1e999999999999999999",
        "0e0",
        "-0",
        "0.0",
        "1E+308",
        "1E-308",
        "123456789012345678901234567890",
    ]
)

# Near-valid-but-malformed numeric forms (rejected by this parser).
_MALFORMED_NUMBER = st.sampled_from(
    [
        "+1",
        ".5",
        "-.5",
        "1.",
        "01",
        "-",
        "1e",
        "1e+",
        "0x",
        "1.2.3",
        "--1",
        "1..2",
    ]
)

_NUMBER = st.one_of(
    _VALID_NUMBER,
    _EXTREME_NUMBER,
    _MALFORMED_NUMBER,
)


# ---------------------------------------------------------------------------
# Recursive value / object / array construction.
# ---------------------------------------------------------------------------

_WS = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\r\n"])


def _obj_entries(pair):
    """Join a list of already-rendered pairs into an object body."""
    return st.lists(pair, max_size=5).map(lambda ps: "{" + ",".join(ps) + "}")


def _arr_values(value):
    return st.lists(value, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]")


# A pair is a string key plus a value, rendered as text.
_PAIR = st.builds(
    lambda k, v: k + ":" + v,
    _STRING,
    st.deferred(lambda: _VALUE),
)

_VALUE = st.deferred(
    lambda: st.one_of(
        _STRING,
        _NUMBER,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _obj_entries(_PAIR),
        _arr_values(_VALUE),
    )
)

# Base JSON values for the recursive strategy.
_BASE = st.one_of(
    _STRING,
    _NUMBER,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_RECURSIVE = st.recursive(
    _BASE,
    lambda children: st.one_of(
        st.lists(children, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
        st.lists(
            st.builds(lambda k, v: k + ":" + v, _STRING, children),
            max_size=4,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ),
    max_leaves=40,
)


# ---------------------------------------------------------------------------
# Deep nesting near the parser's 1000-level limit.
# ---------------------------------------------------------------------------

def _nest_array(depth):
    return "[" * depth + "0" + "]" * depth


def _nest_object(depth):
    return '{"a":' * depth + "0" + "}" * depth


_DEPTH = st.one_of(
    st.integers(min_value=0, max_value=10),
    st.integers(min_value=995, max_value=1005),
    st.integers(min_value=1000, max_value=1001),
)

_DEEP_ARRAY = _DEPTH.map(_nest_array)
_DEEP_OBJECT = _DEPTH.map(_nest_object)


# ---------------------------------------------------------------------------
# Malformed / adversarial whole documents.
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from(
    [
        "",
        "{",
        "}",
        "[",
        "]",
        "{,}",
        "[,]",
        "[1,]",
        '{"a":1,}',
        '{"a"}',
        '{"a":}',
        "{:1}",
        '{"a":1 "b":2}',
        "[1 2]",
        '"unterminated',
        "'single'",
        "{'a':1}",
        "{a:1}",
        "NaN",
        "Infinity",
        "-Infinity",
        "nul",
        "tru",
        "fals",
        "\\",
        '"\\x41"',
        '"\\ud800"',
        '"\\u12"',
        "[1,2,",
        '{"a":1,',
    ]
)


# ---------------------------------------------------------------------------
# Trailing content, BOM, NUL, whitespace wrappers.
# ---------------------------------------------------------------------------

_TRAILING = st.sampled_from(
    [
        "",
        " ",
        "\n",
        "abc",
        " 123",
        "\x00",
        "\x00junk",
        "{}[]",
        "trailing garbage",
    ]
)

_BOM = st.sampled_from(["", "\ufeff"])

_LEADING_WS = _WS


def _wrap(prefix, value, trailing):
    return prefix + value + trailing


# ---------------------------------------------------------------------------
# Final strategy.
# ---------------------------------------------------------------------------

_CORE = st.one_of(
    _RECURSIVE,
    _VALUE,
    _DEEP_ARRAY,
    _DEEP_OBJECT,
    _MALFORMED,
)

strategy = st.builds(
    _wrap,
    _BOM + _LEADING_WS,
    _CORE,
    _TRAILING,
)