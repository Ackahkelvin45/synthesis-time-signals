```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# JSON-safe characters for the interior of a string.
_SAFE = st.characters(
    blacklist_categories=("Cs",),  # no lone surrogates
    blacklist_characters='"\\',
)

# Characters allowed raw inside strings by the parser (it accepts control
# bytes and NUL), but we keep them separate so we can inject them on purpose.
_CONTROL = st.sampled_from(
    [chr(i) for i in range(0x00, 0x20)] + ["\x7f", "\x00"]
)

_UNICODE_ESCAPE = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "\\u%04x" % n
)

# Deliberately include lone surrogates (rejected by parser) and paired ones.
_LONE_SURROGATE_ESCAPE = st.sampled_from(
    ["\\ud800", "\\udbff", "\\udc00", "\\udfff", "\\uD800", "\\uDFFF"]
)

_SIMPLE_ESCAPE = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_STRING_BODY_PIECE = st.one_of(
    _SAFE.map(str),
    _SIMPLE_ESCAPE,
    _UNICODE_ESCAPE,
    _CONTROL,
)

# A "normal" string body.
_STRING_BODY = st.lists(_STRING_BODY_PIECE, max_size=12).map("".join)

# Edge-case string bodies.
_STRING_BODY_EDGE = st.one_of(
    st.just(""),
    st.just("\x00"),
    st.just("\x00\x01\x02"),
    st.just("\\u0000"),
    st.just("\\ud83d\\ude00"),  # valid surrogate pair (emoji)
    _LONE_SURROGATE_ESCAPE,
    st.just("a" * 64),
    st.lists(_CONTROL, min_size=1, max_size=8).map("".join),
)

def _quote(body):
    return '"' + body + '"'

_STRING = st.one_of(_STRING_BODY, _STRING_BODY_EDGE).map(_quote)

# Unterminated string: opening quote, maybe body, no closing quote.
_UNTERMINATED_STRING = st.one_of(
    st.just('"'),
    _STRING_BODY.map(lambda b: '"' + b),
    st.just('"abc'),
    st.just('"\\'),
    st.just('"\\u12'),
)

# ---------------------------------------------------------------------------
# Numbers: normal, plus edge cases the parser accepts/rejects.
# ---------------------------------------------------------------------------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
    st.integers(min_value=-(10**6), max_value=-1).map(str),
)

_FRAC = st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n))

_EXP = st.one_of(
    st.integers(min_value=-320, max_value=320).map(lambda e: "e" + str(e)),
    st.integers(min_value=-320, max_value=320).map(lambda e: "E+" + str(e)),
    st.just("e309"),
    st.just("E-309"),
    st.just("e999999999"),
)

_NUMBER_NORMAL = st.builds(
    lambda sign, ip, fp, ex: sign + ip + fp + ex,
    sign=st.sampled_from(["", "-"]),
    ip=_INT,
    fp=st.one_of(st.just(""), _FRAC),
    ex=st.one_of(st.just(""), _EXP),
)

_NUMBER_EDGE = st.sampled_from(
    [
        "0",
        "-0",
        "1e309",       # inf, accepted
        "-1e309",
        "1e-999",
        "1E+308",
        "123456789012345678901234567890",
        "0.0",
        "1.",
        "01",
        "007",
        "0x10",
        "0XFF",
        "1e01",
        "1E01",
        # rejected forms
        "-",
        "+1",
        ".5",
        "-.5",
        "1e",
        "1e+",
        "--1",
        "1..2",
    ]
)

_NUMBER = st.one_of(_NUMBER_NORMAL, _NUMBER_EDGE)

# ---------------------------------------------------------------------------
# Recursive value / object / array construction.
# ---------------------------------------------------------------------------

# We build strings directly (not tuples!) to avoid the join pitfall.

# Leaf values.
_LEAF = st.one_of(
    _STRING,
    _NUMBER,
    st.sampled_from(["true", "false", "null"]),
    # malformed leaves that should be rejected
    st.sampled_from(
        [
            "NaN",
            "Infinity",
            "-Infinity",
            "undefined",
            "'single'",
            "True",
            "NULL",
        ]
    ),
    _UNTERMINATED_STRING,
)

# Malformed punctuation fragments to sprinkle into containers.
_MALFORMED_OBJ = st.sampled_from(
    [
        "{,}",
        "{,}",
        '{"a":1,}',
        '{"a":1,,}',
        '{"a" 1}',
        '{"a":}',
        '{"a":1 "b":2}',
        '{"a":1,}',
        '{a:1}',
        '{"a":1',
        '{"a":{"b":}}',
        '{"a":1,,"b":2}',
    ]
)

_MALFORMED_ARR = st.sampled_from(
    [
        "[,]",
        "[1,]",
        "[1,,2]",
        "[1 2]",
        "[1,2",
        "[,1]",
        "[1,]",
        "[[]",
        "[}",
    ]
)

# Duplicate keys: generate a key and reuse it.
_DUPLICATE_KEY_OBJ = st.builds(
    lambda k, v: '{"' + k + '":' + v + ',"' + k + '":' + v + "}",
    k=_STRING_BODY.map(lambda s: s.replace('"', "")),
    v=_LEAF,
)

# ---------------------------------------------------------------------------
# Depth-controlled recursive builder.
#
# We want values near the 1000-level limit, not far beyond.  We model this with
# a depth budget: each recursive step decrements it, and we cap the budget at
# ~1005 so most generated trees are near the boundary.
# ---------------------------------------------------------------------------

def _value_at_depth(depth):
    """Return a strategy for a JSON value at the given remaining depth."""
    if depth <= 0:
        return _LEAF
    inner = st.deferred(lambda: _value_at_depth(depth - 1))
    obj = st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        pairs=st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                k=_STRING,
                v=inner,
            ),
            max_size=4,
        ),
    )
    arr = st.builds(
        lambda items: "[" + ",".join(items) + "]",
        items=st.lists(inner, max_size=4),
    )
    return st.one_of(_LEAF, obj, arr)

# Depth budgets concentrated near the parser's 1000-level limit.
_DEPTH = st.one_of(
    st.integers(min_value=0, max_value=8),      # shallow, common
    st.just(1000),                              # exactly at limit (accepted)
    st.just(1001),                              # just past limit (rejected)
    st.integers(min_value=995, max_value=1005), # near the boundary
)

# Deep nesting built explicitly as a chain (cheap, no recursion overhead).
def _deep_nesting(depth, opener, closer):
    return opener * depth + closer * depth

_DEEP = st.builds(
    lambda depth, open_ch, close_ch: _deep_nesting(depth, open_ch, close_ch),
    depth=st.integers(min_value=990, max_value=1005),
    open_ch=st.sampled_from(["[", "{"]),
    close_ch=st.sampled_from(["]", "}"]),
)

# ---------------------------------------------------------------------------
# Top-level value strategy.
# ---------------------------------------------------------------------------

_VALUE = st.one_of(
    _value_at_depth(6),
    _MALFORMED_OBJ,
    _MALFORMED_ARR,
    _DUPLICATE_KEY_OBJ,
    _DEEP,
    _LEAF,
)

# ---------------------------------------------------------------------------
# Surrounding noise: whitespace, BOM, trailing content, NUL bytes.
# ---------------------------------------------------------------------------

_WS = st.sampled_from(["", " ", "\t", "\n", "\r", "  \n\t "])

_BOM = st.sampled_from(["", "\ufeff"])

# Trailing content after a complete value is ACCEPTED (parser stops early),
# so we include it for coverage but don't rely on it for rejection.
_TRAILING = st.sampled_from(
    [
        "",
        " ",
        "\n",
        "abc",
        "1 2",
        "{}",
        "[]",
        "\x00",
        "\x00trailing",
        "garbage",
        "//comment",
    ]
)

def _assemble(bom, lead_ws, value, trail_ws, trailing):
    return bom + lead_ws + value + trail_ws + trailing

_TOP = st.builds(
    _assemble,
    bom=_BOM,
    lead_ws=_WS,
    value=_VALUE,
    trail_ws=_WS,
    trailing=_TRAILING,
)

# ---------------------------------------------------------------------------
# Final strategy: mostly valid/edge JSON, sometimes deliberately broken.
# ---------------------------------------------------------------------------

_MALFORMED_TOP = st.sampled_from(
    [
        "",
        " ",
        "\x00",
        "{",
        "}",
        "[",
        "]",
        "{]",
        "[}",
        '{"a"',
        '{"a":',
        '"',
        '"abc',
        "\\",
        "nul",
        "tru",
        "fals",
        "nulll",
        "01",
        "+1",
        ".5",
        "-",
        "1e",
        "NaN",
        "Infinity",
        "'x'",
        "{\"a\":1,}",
        "[1,]",
    ]
)

strategy = st.one_of(_TOP, _MALFORMED_TOP)
```