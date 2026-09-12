```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf-level strategies
# ---------------------------------------------------------------------------

# Safe string characters (per grammar SAFECODEPOINT): anything except " \ and
# control chars 0x00-0x1F. We *also* deliberately emit raw control bytes and
# NUL inside strings since the parser is length-aware and tests them.
_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

# Raw control / NUL bytes allowed inside string bodies (parser tests these).
_CTRL = st.sampled_from(
    [
        "\x00",
        "\x01",
        "\x1f",
        "\x0b",
        "\x7f",
        "\u0000",
        "\u001f",
    ]
)

# Escape sequences from the grammar's ESC fragment.
_ESCAPES = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

# \uXXXX escapes, including surrogate halves and random hex.
_HEX = st.characters(whitelist_characters="0123456789abcdefABCDEF")
_UNICODE_ESC = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet=_HEX, min_size=4, max_size=4),
)
# Explicit surrogate escapes (lone and paired) — classic parser stress.
_SURROGATE_ESC = st.sampled_from(
    [
        "\\uD800",
        "\\uDBFF",
        "\\uDC00",
        "\\uDFFF",
        "\\uD800\\uDC00",  # valid pair
        "\\uD800\\uD800",  # invalid pair
        "\\uDC00\\uD800",  # reversed pair
        "\\u0000",
        "\\uFFFF",
    ]
)

# A single string-body token.
_STRING_BODY_ATOM = st.one_of(
    _SAFE.map(str),
    _CTRL,
    _ESCAPES,
    _UNICODE_ESC,
    _SURROGATE_ESC,
)

# A well-formed JSON string literal (quoted).
_STRING = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_STRING_BODY_ATOM, min_size=0, max_size=8),
)

# Malformed / unterminated strings (near-valid-but-bad).
_BAD_STRING = st.one_of(
    # unterminated
    st.builds(
        lambda parts: '"' + "".join(parts),
        st.lists(_STRING_BODY_ATOM, min_size=0, max_size=6),
    ),
    # bare quote only
    st.just('"'),
    # trailing backslash (unterminated escape)
    st.builds(
        lambda parts: '"' + "".join(parts) + "\\",
        st.lists(_STRING_BODY_ATOM, min_size=0, max_size=6),
    ),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

# Valid per grammar: -? INT ('.' [0-9]+)? EXP?
_INT = st.one_of(
    st.just("0"),
    st.from_regex(r"[1-9][0-9]*", fullmatch=True),
)
_FRAC = st.from_regex(r"\.[0-9]+", fullmatch=True)
_EXP = st.from_regex(r"[Ee][+-]?[0-9]+", fullmatch=True)

_GOOD_NUMBER = st.builds(
    lambda s, i, f, e: ("-" if s else "") + i + f + e,
    st.booleans(),
    _INT,
    st.one_of(st.just(""), _FRAC),
    st.one_of(st.just(""), _EXP),
)

# Extreme magnitudes / overflow (accepted by parser as inf).
_EXTREME_NUMBER = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e308",
        "1e-308",
        "1e999999999",
        "1e-999999999",
        "0e0",
        "0e999",
        "-0",
        "-0.0",
        "123456789012345678901234567890",
        "1.7976931348623157e308",
        "2.2250738585072014e-308",
        "5e-324",
        "1.8e308",
        "9" * 40,
        "0." + "0" * 50 + "1",
        "1e+309",
        "1E309",
        "1e01",
        "1e-01",
    ]
)

# Malformed numbers (parser rejects, but useful fuzzing).
_BAD_NUMBER = st.sampled_from(
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
        "1.2.3",
        "--1",
        "1..2",
        "1e1e1",
        "0b101",
        "0o17",
        "Infinity",
        "NaN",
        "-",
        "+",
        ".",
        "e5",
    ]
)

_NUMBER = st.one_of(_GOOD_NUMBER, _EXTREME_NUMBER, _BAD_NUMBER)

# ---------------------------------------------------------------------------
# Malformed punctuation fragments (near-valid-but-bad)
# ---------------------------------------------------------------------------

_MALFORMED_FRAGMENTS = st.sampled_from(
    [
        ",,",
        "{,}",
        "[,]",
        "[,1]",
        "[1,,2]",
        '{"a" 1}',
        '{"a":}',
        '{"a":,}',
        "{:1}",
        "{a:1}",
        "{'a':1}",
        "[1 2]",
        '{"a":1 "b":2}',
        "//comment\n1",
        "/*c*/1",
        "'single'",
        "truefalse",
        "nullnull",
        "1abc",
        "[]xyz",
        "true false",
        "1 garbage",
        "{} {}",
        "[] []",
        "\x00",
        "\x00{}",
        "{}\x00",
        "[1,2,]\x00",
    ]
)

# ---------------------------------------------------------------------------
# Recursive obj/arr/value construction
# ---------------------------------------------------------------------------

# A "key" is usually a well-formed string, sometimes duplicate-prone.
_KEY = st.one_of(
    _STRING,
    st.sampled_from(['"a"', '"a"', '"a"', '"b"', '"key"', '""']),
)

# Whitespace between tokens (parser skips WS).
_WS = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\t"),
    st.just("\n"),
    st.just("\r"),
    st.sampled_from(["  ", "\r\n", " \t "]),
)

# Composite value strategy built recursively.
# We use st.recursive with a deferred object/array builder.
_value = st.deferred(lambda: _value_strategy)

# Object member: "key" : value  (with optional WS)
_pair = st.builds(
    lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
    _KEY,
    _WS,
    _WS,
    _value,
)

# Object: {} or { pair (, pair)* }  -- bias toward objects with members.
_obj = st.one_of(
    st.just("{}"),
    st.builds(
        lambda w1, members, trailing, w2: "{"
        + w1
        + ",".join(members)
        + trailing
        + w2
        + "}",
        _WS,
        st.lists(_pair, min_size=1, max_size=6),
        st.one_of(st.just(""), st.just(",")),  # single trailing comma allowed
        _WS,
    ),
)

# Array: [] or [ value (, value)* ]  -- single trailing comma allowed.
_arr = st.one_of(
    st.just("[]"),
    st.builds(
        lambda w1, items, trailing, w2: "["
        + w1
        + ",".join(items)
        + trailing
        + w2
        + "]",
        _WS,
        st.lists(_value, min_size=1, max_size=6),
        st.one_of(st.just(""), st.just(",")),
        _WS,
    ),
)

# Deep nesting: strings of open brackets/braces with a simple value inside.
def _deep_nesting():
    depth = st.integers(min_value=1, max_value=64)
    return st.builds(
        lambda d, inner: "[" * d + inner + "]" * d,
        depth,
        st.one_of(
            st.just("0"),
            _STRING,
            st.just("null"),
            st.just("true"),
            st.just("false"),
        ),
    )


_deep_obj_nesting = st.builds(
    lambda d: '{"a":' * d + "0" + "}" * d,
    st.integers(min_value=1, max_value=64),
)

_deep_arr_nesting = st.builds(
    lambda d: "[" * d + "0" + "]" * d,
    st.integers(min_value=1, max_value=128),
)

# Base (non-recursive) values.
_base_value = st.one_of(
    _STRING,
    _NUMBER,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

# Full recursive value strategy: base leaves + obj + arr.
_value_strategy = st.one_of(
    _base_value,
    _obj,
    _arr,
    _deep_nesting(),
    _deep_obj_nesting,
    _deep_arr_nesting,
    _BAD_STRING,
    _MALFORMED_FRAGMENTS,
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

# Bias toward objects with members (the stressed first-pass path) while still
# covering arrays, scalars, and malformed inputs.
_top = st.one_of(
    # Weighted toward objects with members.
    _obj,
    _obj,
    _obj,
    _arr,
    _value,
    _value,
    _base_value,
    _MALFORMED_FRAGMENTS,
)

# Optional surrounding whitespace and trailing junk (parser rejects junk,
# but exercises the "whole input consumed" path).
strategy = st.builds(
    lambda lead, body, trail: lead + body + trail,
    st.one_of(st.just(""), _WS),
    _top,
    st.one_of(st.just(""), _WS, st.just("\x00"), st.just("garbage")),
)
```