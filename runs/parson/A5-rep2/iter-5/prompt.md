Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters that are safe inside JSON strings (no raw quote, no backslash,
# no control chars 0x00-0x1F).  We never emit a raw NUL byte.
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07'
    '\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17'
    '\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

# Escape sequences permitted by the grammar (ESC fragment).
_SIMPLE_ESCAPES = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_HEX = "0123456789abcdefABCDEF"
_hex4 = st.text(alphabet=_HEX, min_size=4, max_size=4)
_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes and other boundary code points.
_SURROGATE_ESCAPES = st.sampled_from(
    [
        "\\ud800", "\\udbff", "\\udc00", "\\udfff",
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
        "\\u0000", "\\u001f", "\\u007f", "\\uffff",
        "\\u00e9", "\\u20ac", "\\u4e2d",
    ]
)

_STRING_BODY = st.one_of(
    _SAFE_CHARS,
    _SIMPLE_ESCAPES,
    _unicode_escape,
    _SURROGATE_ESCAPES,
)

# Allow longer strings so the parser's string-buffer growth paths get
# exercised, and occasionally emit very long strings near buffer boundaries.
_string = st.one_of(
    st.lists(_STRING_BODY, max_size=12).map("".join).map(lambda s: '"' + s + '"'),
    st.lists(_STRING_BODY, min_size=64, max_size=256).map("".join).map(lambda s: '"' + s + '"'),
    st.integers(min_value=100, max_value=70000).map(lambda n: '"' + "a" * n + '"'),
)

# ---------------------------------------------------------------------------
# Numbers: legal, extreme, and near-valid-but-malformed
# ---------------------------------------------------------------------------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

_FRAC = st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n).zfill(1))

_EXP = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=400).map(str),
)

_legal_number = st.builds(
    lambda neg, i, f, e: neg + i + f + e,
    st.sampled_from(["", "-"]),
    _INT,
    st.one_of(st.just(""), _FRAC),
    st.one_of(st.just(""), _EXP),
)

# Extreme magnitudes / exponents, including overflow like 1e309.
_extreme_numbers = st.sampled_from(
    [
        "1e309", "-1e309", "1E309", "1e308", "1e-309", "1e999999",
        "-1e999999", "0e0", "0e999", "1e+308", "1e-308",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1.7976931348623157e309",
        "2.2250738585072014e-308",
        "1e2147483647", "1e-2147483648",
        "0.0000000000000000000000000000001",
        "99999999999999999999999999999999999999",
    ]
)

# Malformed numbers the parser may be lenient about (leading +, .5, 1., lone -).
_malformed_numbers = st.sampled_from(
    [
        "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "-01", "00",
        "1.e5", "0x1f", "1_000", "--1", "1..2", "1e", "1e+", "1e-",
    ]
)

_number = st.one_of(_legal_number, _extreme_numbers, _malformed_numbers)

# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

_ATOM = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

# Whitespace that the grammar skips.
_WS = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t "])

# Duplicate keys: same key twice (parser rejects these).
_dup_pair = st.builds(
    lambda k, v1, v2, ws: ws + k + ws + ":" + ws + v1 + ws + "," + ws + k + ws + ":" + ws + v2 + ws,
    _string,
    _ATOM,
    _ATOM,
    _WS,
)

_json_value = st.recursive(
    _ATOM,
    lambda children: st.one_of(
        # Arrays
        st.builds(
            lambda ws, vals: ws + "[" + ws + ("," + ws).join(vals) + ws + "]",
            _WS,
            st.lists(children, min_size=0, max_size=5),
        ),
        # Objects
        st.builds(
            lambda ws, pairs: ws + "{" + ws + ("," + ws).join(pairs) + ws + "}",
            _WS,
            st.lists(
                st.builds(
                    lambda k, v, w: w + k + w + ":" + w + v + w,
                    _string,
                    children,
                    _WS,
                ),
                min_size=0,
                max_size=5,
            ),
        ),
        # Object with duplicate keys
        st.builds(
            lambda ws, p: ws + "{" + ws + p + ws + "}",
            _WS,
            _dup_pair,
        ),
    ),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Deep nesting near the parser's MAX_NESTING = 2048 limit
# ---------------------------------------------------------------------------

# Concentrate depth near 2048: a mix of small, medium, and near-limit depths.
_DEPTHS = st.one_of(
    st.integers(min_value=0, max_value=10),
    st.integers(min_value=1000, max_value=2100),
    st.sampled_from([2000, 2040, 2047, 2048, 2049, 2050, 2100, 3000]),
)

_deep_nesting = st.builds(
    lambda d, opener, closer, inner: opener * d + inner + closer * d,
    _DEPTHS,
    st.sampled_from(["[", "{"]),
    st.sampled_from(["]", "}"]),
    st.one_of(st.just(""), _ATOM),
)

# A well-formed deep array/object (balanced) near the limit.
_deep_balanced = _DEPTHS.map(
    lambda d: "[" * d + "0" + "]" * d
)

_deep_balanced_obj = _DEPTHS.map(
    lambda d: '{"k":' * d + "0" + "}" * d
)

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        # double commas / trailing commas
        "[1,,2]", "[,]", "[1,]", '{"a":1,,}', '{"a":1,}', "{,}",
        "[1,2,]", '{"a":1,"b":2,}',
        # missing colons
        '{"a" 1}', '{"a"}', '{"a":}', '{:1}', '{"a":1 "b":2}',
        # unterminated strings
        '"abc', '"', '{"a":"abc}', '["abc]', '"abc\\"',
        # unterminated containers
        "[1,2", '{"a":1', "[", "{", "[[[", "{{{",
        # stray closers
        "]", "}", "[}]", "{]}", "[]]", "{}]",
        # leading +/.5/01
        "+1", ".5", "01", "-01", "1.", "-", "-.",
        # misc
        "[1 2]", "truefalse", "nul", "tru", "fals",
        "{\"a\":}", "{\"a\":,}", "[,1]",
        '{"a":1}garbage', "1abc", "[]xyz", "nullnull",
        "\"\\u12\"", "\"\\uGGGG\"", "\"\\x41\"", "\"\\\"",
    ]
)

# Trailing content after a complete value (parser accepts).
_trailing = st.builds(
    lambda v, t: v + t,
    _json_value,
    st.sampled_from(["", " ", "garbage", "xyz", "1abc", "[]", "{}", "null", "\n", "\t"]),
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _json_value,
    _deep_nesting,
    _deep_balanced,
    _deep_balanced_obj,
    _malformed,
    _trailing,
    _extreme_numbers,
    _malformed_numbers,
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("{}"),
    st.just("[]"),
    st.just('""'),
    st.just("0"),
    st.just('{"k":0,"k":1}'),
    st.just("1e309"),
    st.just("[" * 2048 + "0" + "]" * 2048),
    st.just("[" * 2049 + "0" + "]" * 2049),
)
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.