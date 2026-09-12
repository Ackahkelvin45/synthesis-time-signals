Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic leaf strategies
# ---------------------------------------------------------------------------

# Characters that are safe inside a JSON string (no raw NUL / control chars).
_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\"\\",
)

_ESCAPES = st.sampled_from(
    [
        "\\\"",
        "\\\\",
        "\\/",
        "\\b",
        "\\f",
        "\\n",
        "\\r",
        "\\t",
    ]
)

_HEX = "0123456789abcdefABCDEF"

_unicode_escape = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet=_HEX, min_size=4, max_size=4),
)

# Surrogate escapes and other interesting \uXXXX values.
_surrogate_escape = st.sampled_from(
    [
        "\\uD800",
        "\\uDBFF",
        "\\uDC00",
        "\\uDFFF",
        "\\uD83D\\uDE00",  # valid surrogate pair
        "\\uD800\\uD800",  # invalid pairing
        "\\u0000",         # NUL as escape is fine
        "\\u001f",
        "\\u007f",
        "\\u00e9",
        "\\uFFFF",
        "\\uabcd",
    ]
)

_string_body_char = st.one_of(_SAFE, _ESCAPES, _unicode_escape, _surrogate_escape)

# A well-formed JSON string literal.
_wellformed_string = st.builds(
    lambda body: '"' + body + '"',
    st.lists(_string_body_char, max_size=12).map("".join),
)

# A malformed / unterminated string.
_unterminated_string = st.builds(
    lambda body: '"' + body,
    st.lists(_string_body_char, max_size=12).map("".join),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.builds(
        lambda first, rest: first + rest,
        st.integers(min_value=1, max_value=9).map(str),
        st.text(alphabet="0123456789", max_size=6),
    ),
)

_frac = st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=6))

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

_wellformed_number = st.builds(
    lambda sign, ip, fp, ep: sign + ip + fp + ep,
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

# Extreme magnitudes / exponents including overflow like 1e309.
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e308",
        "1e-308",
        "1e1000",
        "-1e1000",
        "1E309",
        "1e+309",
        "0e0",
        "0e999",
        "-0",
        "-0.0",
        "123456789012345678901234567890",
        "1.7976931348623157e308",
        "1.7976931348623159e308",
        "2.2250738585072014e-308",
        "5e-324",
        "1e-400",
    ]
)

# Near-valid-but-malformed numbers (leading +, .5, 01, lone -, etc.).
_malformed_number = st.sampled_from(
    [
        "+1",
        "+0",
        ".5",
        "-.5",
        "1.",
        "-1.",
        "01",
        "00",
        "-01",
        "1.2.3",
        "1e",
        "1e+",
        "1e-",
        "1E",
        "--1",
        "-",
        "-.",
        "-e5",
        "1_000",
        "0x10",
        "Infinity",
        "-Infinity",
        "NaN",
    ]
)

_number = st.one_of(
    _wellformed_number,
    _extreme_number,
    _malformed_number,
)

# ---------------------------------------------------------------------------
# Recursive values
# ---------------------------------------------------------------------------

_whitespace = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

# Keys: mostly well-formed strings, sometimes duplicates are produced by
# callers by reusing a small key pool.
_key_pool = [
    '"a"',
    '"b"',
    '"key"',
    '"x"',
    '"dup"',
    '"\\u0000"',
    '""',
    '"\\n"',
]


def _obj_pair(value):
    key = st.sampled_from(_key_pool)
    colon = st.sampled_from([":", ":", ":", " : ", "\t:\n"])
    sep = st.sampled_from([",", ",", ", ", " , "])
    return st.builds(
        lambda k, c, v, s: k + c + v + s,
        key,
        colon,
        value,
        sep,
    )


def _arr_item(value):
    sep = st.sampled_from([",", ",", ", ", " , "])
    return st.builds(lambda v, s: v + s, value, sep)


def _obj(value):
    # Empty object, or pairs (possibly with duplicates via key pool).
    pairs = st.lists(_obj_pair(value), min_size=0, max_size=5).map(lambda ps: "".join(ps))
    pairs = pairs.map(lambda s: s.rstrip(" ,") if s else s)
    return st.builds(
        lambda inner: "{" + inner + "}",
        st.one_of(st.just(""), pairs),
    )


def _arr(value):
    items = st.lists(_arr_item(value), min_size=0, max_size=5).map(lambda xs: "".join(xs))
    items = items.map(lambda s: s.rstrip(" ,") if s else s)
    return st.builds(
        lambda inner: "[" + inner + "]",
        st.one_of(st.just(""), items),
    )


# ---------------------------------------------------------------------------
# Deep nesting near the 2048 limit
# ---------------------------------------------------------------------------

def _deep_nesting():
    # Concentrate interesting depth near 2048, plus some smaller depths.
    near = st.integers(min_value=2000, max_value=2050)
    small = st.integers(min_value=1, max_value=64)
    depth = st.one_of(near, small, st.just(2047), st.just(2048), st.just(2049))
    return st.builds(
        lambda d, opener, closer: opener * d + closer * d,
        depth,
        st.sampled_from(["[", "{"]),
        st.sampled_from(["]", "}"]),
    )


# ---------------------------------------------------------------------------
# Near-valid-but-malformed whole documents
# ---------------------------------------------------------------------------

_malformed_doc = st.sampled_from(
    [
        "{,}",
        "[,]",
        "[1,,2]",
        "{\"a\":1,,}",
        "{\"a\" 1}",
        "{\"a\":}",
        "{:1}",
        "{1:2}",
        "[1 2]",
        "{\"a\":1 \"b\":2}",
        "{\"a\":1,}",
        "[1,2,]",
        "{",
        "[",
        "}",
        "]",
        "{]",
        "[}",
        "\"unterminated",
        "{\"a\":\"unterminated}",
        "tru",
        "fals",
        "nul",
        "TRUE",
        "True",
        "NULL",
        "01",
        "1abc",
        "1 garbage",
        "[]xyz",
        "{}extra",
        "null trailing",
    ]
)

# ---------------------------------------------------------------------------
# Recursive value / document strategies
# ---------------------------------------------------------------------------

_value = st.recursive(
    st.one_of(
        _wellformed_string,
        _unterminated_string,
        _number,
        st.sampled_from(["true", "false", "null"]),
    ),
    lambda children: st.one_of(
        _obj(children),
        _arr(children),
    ),
    max_leaves=20,
)

# Broaden exploration: generate a wider variety of accepted top-level
# structures (nested mixes, wider/longer containers, assorted whitespace
# layouts, and richer scalar combinations) to diversify accepted documents.
_broad_value = st.recursive(
    st.one_of(
        _wellformed_string,
        _number,
        st.sampled_from(["true", "false", "null"]),
    ),
    lambda children: st.one_of(
        st.builds(
            lambda inner: "{" + inner + "}",
            st.lists(
                st.builds(
                    lambda k, c, v, s: k + c + v + s,
                    st.sampled_from(_key_pool),
                    st.sampled_from([":", " : ", "\t:\n"]),
                    children,
                    st.sampled_from([",", ", ", " , "]),
                ),
                min_size=0,
                max_size=12,
            ).map(lambda ps: "".join(ps).rstrip(" ,")),
        ),
        st.builds(
            lambda inner: "[" + inner + "]",
            st.lists(
                st.builds(
                    lambda v, s: v + s,
                    children,
                    st.sampled_from([",", ", ", " , "]),
                ),
                min_size=0,
                max_size=12,
            ).map(lambda xs: "".join(xs).rstrip(" ,")),
        ),
    ),
    max_leaves=60,
)

_broad_document = st.one_of(
    _broad_value,
    st.builds(
        lambda ws1, v, ws2: ws1 + v + ws2,
        _whitespace,
        _broad_value,
        _whitespace,
    ),
    st.builds(
        lambda v, t: v + t,
        _broad_value,
        st.sampled_from(["", " ", "\n", "\t", " ", "  "]),
    ),
)

_document = st.one_of(
    _value,
    _broad_document,
    _deep_nesting(),
    _malformed_doc,
    # Trailing content after a complete value (accepted by parson).
    st.builds(
        lambda v, t: v + t,
        _value,
        st.sampled_from(["", " ", "abc", "xyz", "garbage", " 1 2 3", "/*x*/"]),
    ),
)

# ---------------------------------------------------------------------------
# Final strategy: strings only, no raw NUL bytes.
# ---------------------------------------------------------------------------

def _strip_nul(s: str) -> str:
    # Raw NUL is untestable (NUL-terminated API); \u0000 escape is fine.
    return s.replace("\x00", "")


strategy = _document.map(_strip_nul)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 127,
    "reject": 223
  },
  "acceptance_rate": 0.363,
  "max_nesting_depth": 2049,
  "productions_accepted": [
    "array",
    "false",
    "null",
    "number",
    "object",
    "string",
    "true"
  ],
  "productions_gap": [],
  "cap_distance_mass": 0.031,
  "novelty": 21,
  "divergences": 54,
  "divergence_examples": [
    "b'{} 1 2 3'",
    "b'{}abc'",
    "b'{}garbage'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **generate_nesting_toward_cap** — target depth 1500-2048.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.