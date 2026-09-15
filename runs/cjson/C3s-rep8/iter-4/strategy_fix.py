import json

from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Primitive building blocks
# ---------------------------------------------------------------------------

_HEX = "0123456789abcdefABCDEF"

# Characters that are "safe" inside a JSON string per the grammar.
_SAFE_CHARS = (
    [chr(c) for c in range(0x20, 0x7F)]
    + [chr(c) for c in range(0xA0, 0x200)]
)

# Control characters (raw, allowed by this parser inside strings).
_CONTROL_CHARS = [chr(c) for c in range(0x00, 0x20)] + ["\x7f"]

# Simple escape sequences.
_SIMPLE_ESCAPES = ["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]


def _hex4():
    return st.text(alphabet=_HEX, min_size=4, max_size=4)


@st.composite
def _unicode_escape(draw):
    """A \\uXXXX escape, sometimes a valid surrogate pair, sometimes lone."""
    kind = draw(st.sampled_from(["plain", "pair", "lone_high", "lone_low"]))
    if kind == "plain":
        # Avoid surrogates for the "plain" case so it's a valid scalar.
        while True:
            h = draw(_hex4())
            v = int(h, 16)
            if not (0xD800 <= v <= 0xDFFF):
                return "\\u" + h
    elif kind == "pair":
        hi = 0xD800 + draw(st.integers(min_value=0, max_value=0x3FF))
        lo = 0xDC00 + draw(st.integers(min_value=0, max_value=0x3FF))
        return "\\u%04x\\u%04x" % (hi, lo)
    elif kind == "lone_high":
        hi = 0xD800 + draw(st.integers(min_value=0, max_value=0x3FF))
        return "\\u%04x" % hi
    else:
        lo = 0xDC00 + draw(st.integers(min_value=0, max_value=0x3FF))
        return "\\u%04x" % lo


def _string_char():
    return st.one_of(
        st.sampled_from(_SAFE_CHARS),
        st.sampled_from(_CONTROL_CHARS),
        st.sampled_from(_SIMPLE_ESCAPES),
        _unicode_escape(),
    )


@st.composite
def _string_content(draw):
    return draw(st.text(_string_char(), max_size=12))


# ---------------------------------------------------------------------------
# Numbers: valid, edge-case, and near-valid-but-malformed
# ---------------------------------------------------------------------------

def _valid_int():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=10, max_value=10**18).map(str),
        st.integers(min_value=-(10**18), max_value=-1).map(str),
    )


def _valid_number():
    int_part = _valid_int()
    frac = st.tuples(st.just("."), st.integers(min_value=0, max_value=10**9).map(str)).map(
        lambda t: t[0] + t[1]
    )
    exp = st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=10**9).map(str),
    ).map(lambda t: t[0] + t[1] + t[2])

    def assemble(triple):
        sign, body, tail = triple
        return sign + body + tail

    return st.one_of(
        int_part.map(lambda s: s),
        st.tuples(int_part, frac, st.just("")).map(assemble),
        st.tuples(int_part, st.just(""), exp).map(assemble),
        st.tuples(int_part, frac, exp).map(assemble),
        # extreme magnitudes / exponents (overflow -> inf)
        st.sampled_from([
            "1e309", "-1e309", "1e400", "1e-400", "1E309", "-1E400",
            "1e999999999999", "0e0", "-0", "-0.0", "0.0",
            "1.7976931348623157e308", "1.7976931348623159e308",
            "5e-324", "2.2250738585072014e-308",
        ]),
    )


def _malformed_number():
    """Near-valid-but-malformed numeric fragments (rejected by parser)."""
    return st.sampled_from([
        "-",
        "+1",
        "+0",
        "+1.5",
        ".5",
        "-.5",
        "01",
        "00",
        "0123",
        "1.",
        "1.e5",
        "-1.",
        "0x10",
        "0X1f",
        "0x",
        "1e",
        "1e+",
        "1e-",
        "1E",
        "--1",
        "1..2",
        "1.2.3",
        "NaN",
        "Infinity",
        "-Infinity",
        "nan",
        "inf",
    ])


# ---------------------------------------------------------------------------
# Malformed structural fragments
# ---------------------------------------------------------------------------

def _malformed_fragment():
    return st.sampled_from([
        "[,]",
        "[1,]",
        "[,1]",
        "[1,,2]",
        "{,}",
        '{"a":1,}',
        '{"a":}',
        '{"a"}',
        '{"a":1 "b":2}',
        '{"a" 1}',
        "{a:1}",
        "{'a':1}",
        "[1 2]",
        "[}",
        "{]",
        "[",
        "]",
        "{",
        "}",
        '"',
        '"abc',
        "'abc'",
        "tru",
        "fals",
        "nul",
        "True",
        "False",
        "None",
        "undefined",
        "",
    ])


# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

def _build_value(draw):
    """One JSON value, drawing from a mix of valid and malformed pieces."""
    leaf = st.one_of(
        _valid_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _string_content().map(lambda s: '"' + s + '"'),
        _malformed_number(),
        _malformed_fragment(),
    )
    return draw(leaf)


@st.composite
def _value(draw, depth=0):
    """Recursive JSON value with bounded, near-limit nesting."""
    # Bias depth distribution so we sometimes sit near the 1000 limit.
    if depth >= 1000:
        return draw(_build_value(draw))

    roll = draw(st.integers(min_value=0, max_value=99))

    if roll < 40:
        # Leaf.
        return draw(_build_value(draw))

    # Occasionally jump straight to a deep-ish nesting level.
    if roll >= 97:
        target = draw(st.integers(min_value=max(depth, 900), max_value=1005))
        return _nested(draw, target)

    # Normal recursion.
    return draw(_container(draw, depth))


def _nested(draw, target_depth):
    """Build nesting of exactly target_depth arrays/objects wrapping a leaf."""
    inner = draw(_build_value(draw))
    for _ in range(target_depth):
        if draw(st.booleans()):
            inner = "[" + inner + "]"
        else:
            inner = '{"k":' + inner + "}"
    return inner


@st.composite
def _container(draw, depth):
    """An array or object containing recursive values."""
    if draw(st.booleans()):
        # Array.
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        elems = [draw(_value(depth=depth + 1)) for _ in range(n)]
        sep = draw(st.sampled_from([",", ", ", " , ", ",\n", ",\t"]))
        return "[" + sep.join(elems) + "]"
    else:
        # Object.
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "{}"
        pairs = []
        for _ in range(n):
            key = draw(_string_content().map(lambda s: '"' + s + '"'))
            val = draw(_value(depth=depth + 1))
            colon = draw(st.sampled_from([":", ": ", " : ", ":\n"]))
            pairs.append(key + colon + val)
        sep = draw(st.sampled_from([",", ", ", " , ", ",\n", ",\t"]))
        return "{" + sep.join(pairs) + "}"


# ---------------------------------------------------------------------------
# Top-level strategy: value + optional trailing junk / BOM / whitespace
# ---------------------------------------------------------------------------

_TRAILING_JUNK = st.one_of(
    st.just(""),
    st.sampled_from([
        "abc", " 1 2", "xyz", "\x00", " \x00", "garbage",
        "  ", "\n", "\t", "null", "true",
    ]),
    st.text(alphabet="abcxyz0129 \t\n", max_size=8),
)

_LEADING = st.one_of(
    st.just(""),
    st.just("\ufeff"),  # UTF-8 BOM as a character
    st.sampled_from([" ", "\n", "\t", "\r\n"]),
)


@st.composite
def _top_level(draw):
    lead = draw(_LEADING)
    body = draw(_value(depth=0))
    trail = draw(_TRAILING_JUNK)
    return lead + body + trail


strategy = st.one_of(
    _top_level(),
    # Explicitly cover the documented edge cases.
    st.sampled_from([
        "{}",
        "[]",
        "1e309",
        "-1e309",
        "1e400",
        "-0",
        '"\\ud800"',
        '"\\udc00"',
        '"\\ud83d\\ude00"',
        '"\\u0000"',
        "\x00",
        "\x00{}",
        '{"a":1,"a":2}',
        '{"a":1,"a":2,"a":3}',
        "1abc",
        "1 2",
        "\ufeff{}",
        "\ufeff1",
        '{"a":\x00}',
        '[\x00]',
        "01",
        "1.",
        "0x10",
        "+1",
        ".5",
        "-",
        "NaN",
        "Infinity",
        "[1,]",
        '{"a":1,}',
        "[" * 1000 + "]" * 1000,
        "[" * 1001 + "]" * 1001,
        "[" * 999 + "]" * 999,
        "[" * 1000 + "1" + "]" * 1000,
    ]),
)