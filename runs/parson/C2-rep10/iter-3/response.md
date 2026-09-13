```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A "safe" character that is legal inside a JSON string without escaping.
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\",
)


def _esc():
    """A single escape sequence (the text, without surrounding quotes)."""
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    hexd = st.sampled_from("0123456789abcdefABCDEF")

    def _uni():
        return st.lists(hexd, min_size=4, max_size=4).map(lambda cs: "\\u" + "".join(cs))

    return st.one_of(simple, _uni())


# A JSON string token, including the surrounding quotes.
_string = st.one_of(
    st.just('""'),
    st.lists(st.one_of(_esc(), _SAFE_CHARS), min_size=0, max_size=12).map(
        lambda parts: '"' + "".join(parts) + '"'
    ),
)


def _num_token():
    """NUMBER per grammar, plus extreme magnitudes/exponents."""
    ints = st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.integers(min_value=-(10**18), max_value=-1).map(str),
    )
    frac = st.one_of(st.none(), st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)))
    exp = st.one_of(
        st.none(),
        st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
        st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(e)),
        st.sampled_from(["e309", "e-309", "e999", "e-999", "e308", "e-308", "e01", "E+00"]),
    )
    return st.builds(
        lambda s, i, f, e: s + i + (f or "") + (e or ""),
        st.one_of(st.just(""), st.just("-")),
        ints,
        frac,
        exp,
    )


# ---------------------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the parser's 2048 cap.
_DEPTH = st.integers(min_value=1, max_value=2100)


def _value(depth):
    """A value at a given remaining depth budget."""
    scalars = st.one_of(
        _string,
        _num_token(),
        st.sampled_from(["true", "false", "null"]),
    )
    if depth <= 0:
        return scalars

    deeper = _value(depth - 1)
    obj = _obj(deeper)
    arr = _arr(deeper)
    return st.one_of(scalars, obj, arr)


def _pair(val):
    return st.builds(lambda k, v: k + ":" + v, _string, val)


def _obj(val):
    """Object, with a bias toward duplicate keys and extreme nesting."""
    empty = st.just("{}")
    one = _pair(val).map(lambda p: "{" + p + "}")
    many = st.lists(_pair(val), min_size=2, max_size=6).map(
        lambda ps: "{" + ",".join(ps) + "}"
    )
    # Duplicate keys: same key repeated (parser rejects, grammar allows).
    dup = st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        _string,
        val,
        val,
    )
    return st.one_of(empty, one, many, dup)


def _arr(val):
    empty = st.just("[]")
    one = val.map(lambda v: "[" + v + "]")
    many = st.lists(val, min_size=2, max_size=6).map(lambda vs: "[" + ",".join(vs) + "]")
    return st.one_of(empty, one, many)


# ---------------------------------------------------------------------------
# Deep nesting near the cap (iteratively built to avoid recursion blowups).
# ---------------------------------------------------------------------------

def _deep_nesting():
    """Build nested [ ... ] / { ... } targeting depth 1500-2048 with a scalar inside."""
    n = st.integers(min_value=1500, max_value=2048)
    open_ch = st.sampled_from(["[", "{"])
    close_ch = st.sampled_from(["]", "}"])
    inner = st.one_of(
        st.just("0"),
        st.just('"x"'),
        st.just("null"),
        st.just("true"),
    )
    return st.builds(
        lambda k, o, c, v: (o * k) + v + (c * k),
        n,
        open_ch,
        close_ch,
        inner,
    )


# ---------------------------------------------------------------------------
# Near-valid-but-malformed inputs
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from(
    [
        # double commas
        "[1,,2]",
        '{"a":1,,"b":2}',
        "[,]",
        # missing colons
        '{"a" 1}',
        '{"a"}',
        '{:1}',
        # unterminated strings
        '"abc',
        '{"a":"unterminated}',
        '["x',
        # leading + / .5 / 01
        "+1",
        ".5",
        "01",
        "-01",
        "+.5",
        "1.",
        "1.e5",
        # trailing commas
        "[1,2,]",
        '{"a":1,}',
        # stray tokens
        "}",
        "]",
        ":",
        ",",
        "{",
        "[",
        '{"a":}',
        "tru",
        "nul",
        "fals",
        # lone sign (parser accepts as 0)
        "-",
        "-.",
        # trailing content after a complete value (parser accepts)
        "1abc",
        "1 garbage",
        "[]xyz",
        "{} trailing",
        "truefalse",
        "null null",
    ]
)


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

@st.composite
def _top(draw):
    choice = draw(
        st.integers(min_value=0, max_value=9)
    )
    if choice <= 5:
        # Main recursive grammar covering.
        return draw(_value(draw(st.integers(min_value=1, max_value=6))))
    if choice == 6:
        # Bias toward the parser's nesting cap: mix pure deep nesting with
        # deep wrappers around structured content, targeting 1500-2048.
        mode = draw(st.integers(min_value=0, max_value=2))
        if mode == 0:
            return draw(_deep_nesting())
        if mode == 1:
            n = draw(st.integers(min_value=1500, max_value=2048))
            open_ch = draw(st.sampled_from(["[", "{"]))
            close_ch = draw(st.sampled_from(["]", "}"]))
            inner = draw(_value(draw(st.integers(min_value=0, max_value=3))))
            return (open_ch * n) + inner + (close_ch * n)
        # mode == 2: alternate bracket kinds to stress mixed nesting.
        n = draw(st.integers(min_value=1500, max_value=2048))
        inner = draw(st.one_of(st.just("0"), st.just('"x"'), st.just("null")))
        opens = draw(st.lists(st.sampled_from(["[", "{"]), min_size=n, max_size=n))
        closes = [("]" if o == "[" else "}") for o in opens]
        return "".join(opens) + inner + "".join(reversed(closes))
    if choice == 7:
        return draw(_MALFORMED)
    if choice == 8:
        # Whitespace-padded valid value (WS is skipped).
        val = draw(_value(draw(st.integers(min_value=0, max_value=4))))
        ws = draw(st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t"]))
        return ws + val + ws
    # Trailing content after a complete value (parser accepts).
    val = draw(_value(draw(st.integers(min_value=0, max_value=3))))
    tail = draw(
        st.sampled_from(["", "x", " 1 2", "garbage", "//", "/*", "]", "}", ","])
    )
    return val + tail


strategy = _top()
```