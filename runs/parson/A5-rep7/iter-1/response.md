```python
import json

from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

# Characters that are safe to place inside a JSON string body without escaping.
_safe_ascii = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x7E,
    blacklist_characters='"\\',
)
# Some non-ASCII code points (valid in the grammar as SAFECODEPOINT).
_safe_unicode = st.characters(
    min_codepoint=0x80,
    max_codepoint=0x10FFFF,
    blacklist_categories=("Cs",),  # exclude lone surrogates
)
_safe_body_char = st.one_of(_safe_ascii, _safe_unicode)

# Escape sequences allowed by ESC.
_short_escapes = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.lists(_hex_digit, min_size=4, max_size=4).map("".join)

# Interesting \uXXXX values: control chars, surrogates, boundary code points.
_interesting_hex4 = st.sampled_from(
    [
        "0000",  # NUL escape (six chars, fine)
        "0001",
        "001F",
        "007F",
        "0080",
        "00FF",
        "07FF",
        "0800",
        "D7FF",
        "D800",  # high surrogate
        "DBFF",
        "DC00",  # low surrogate
        "DFFF",
        "E000",
        "FFFD",
        "FFFE",
        "FFFF",
        "10FFFF",
        "1F600",
        "000a",
        "ABCD",
        "abcd",
    ]
)

_unicode_escape = st.one_of(_interesting_hex4, _hex4).map(lambda h: "\\u" + h)

_escaped_char = st.one_of(_short_escapes, _unicode_escape)

# A single element of a JSON string body: either a safe char or an escape.
_string_piece = st.one_of(_safe_body_char, _escaped_char)

# Deliberately malformed string bodies (for near-valid inputs).
_malformed_string_bodies = st.sampled_from(
    [
        '"unterminated',
        '"trailing backslash\\',
        '"bad escape \\x"',
        '"short unicode \\u12"',
        '"non-hex unicode \\uZZZZ"',
        '"\\u"',
        '"\\"',
        '"\\uD800"',  # lone surrogate escape
        '"\\uDC00"',
        '"\\uD800\\uD800"',
        '"embedded \\u0000 nul escape"',
    ]
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).flatmap(
        lambda first: st.lists(
            st.integers(min_value=0, max_value=9).map(str),
            min_size=0,
            max_size=18,
        ).map(lambda rest: str(first) + "".join(rest))
    ),
)

_frac_part = st.lists(
    st.integers(min_value=0, max_value=9).map(str),
    min_size=1,
    max_size=18,
).map(lambda ds: "." + "".join(ds))

_exp_part = st.builds(
    lambda sign, digits: "e" + sign + digits,
    st.sampled_from(["", "+", "-"]),
    st.lists(
        st.integers(min_value=0, max_value=9).map(str),
        min_size=1,
        max_size=4,
    ).map("".join),
)

# Extreme numeric magnitudes / exponents (overflow, underflow, huge).
_extreme_numbers = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e400",
        "1e-400",
        "1E309",
        "1e+309",
        "1e308",
        "1.7976931348623157e308",
        "1.7976931348623159e308",
        "5e-324",
        "4.9e-324",
        "1e1000",
        "-1e1000",
        "0e999999999999999999999",
        "1234567890123456789012345678901234567890",
        "0.00000000000000000000000000000001",
        "1.0e0",
        "0e0",
        "0E-0",
        "1e000000000000000000000000000000000000000000000000000000000000000001",
    ]
)

# Near-valid-but-malformed numbers.
_malformed_numbers = st.sampled_from(
    [
        "01",
        "007",
        "-01",
        "+1",
        "+0",
        ".5",
        "-.5",
        "1.",
        "-",
        "-.",
        "1.e5",
        "1e",
        "1e+",
        "1e-",
        "0x10",
        "1_000",
        "NaN",
        "Infinity",
        "-Infinity",
        "inf",
        "--1",
        "1..2",
        "1e1.5",
    ]
)

_number = st.one_of(
    st.builds(
        lambda sign, i, f, e: sign + i + f + e,
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac_part),
        st.one_of(st.just(""), _exp_part),
    ),
    _extreme_numbers,
    _malformed_numbers,
)

# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

_string = st.one_of(
    st.lists(_string_piece, min_size=0, max_size=12).map(
        lambda pieces: '"' + "".join(pieces) + '"'
    ),
    _malformed_string_bodies,
)

# ---------------------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------------------

# Key material for objects (used to make duplicate keys likely).
_key = st.one_of(
    st.sampled_from(["k", "key", "a", "b", "x", "name", "id", "0", ""]),
    st.lists(_string_piece, min_size=0, max_size=4).map(
        lambda pieces: "".join(pieces)
    ),
)


def _pair(key):
    return st.builds(
        lambda k, v: '"' + k + '":' + v,
        st.just(key),
        _value,
    )


def _make_obj(children):
    """children is a strategy of value-strategies used for recursion."""
    # Empty object.
    empty = st.just("{}")
    # Object with pairs, some sharing keys to trigger duplicate-key rejection.
    pair_strat = _key.flatmap(_pair)
    body = st.lists(pair_strat, min_size=1, max_size=6).map(
        lambda ps: "{" + ",".join(ps) + "}"
    )
    # Duplicate keys explicitly.
    dup = st.builds(
        lambda k, v1, v2: '{"' + k + '":' + v1 + ',"' + k + '":' + v2 + "}",
        _key,
        children,
        children,
    )
    # Malformed object variants.
    malformed = st.sampled_from(
        [
            "{",
            "}",
            '{"a"}',
            '{"a":}',
            '{"a":1,}',
            '{,"a":1}',
            '{"a":1,,"b":2}',
            "{'a':1}",
            "{a:1}",
            '{"a" 1}',
            '{"a":1 "b":2}',
            '{"a":1,',
            "{\\u0000:1}",
        ]
    )
    return st.one_of(empty, body, dup, malformed)


def _make_arr(children):
    empty = st.just("[]")
    body = st.lists(children, min_size=1, max_size=8).map(
        lambda vs: "[" + ",".join(vs) + "]"
    )
    malformed = st.sampled_from(
        [
            "[",
            "]",
            "[1,]",
            "[,1]",
            "[1,,2]",
            "[1 2]",
            "[1;2]",
            "[",
            "[]]",
            "[[",
        ]
    )
    return st.one_of(empty, body, malformed)


_literals = st.sampled_from(["true", "false", "null"])

# Recursive value strategy.  We keep depth bounded (max_leaves) and then bias
# depth toward the parser's 2048 nesting cap with a separate deep-nesting
# strategy applied at the top level.
_value = st.recursive(
    st.one_of(_string, _number, _literals),
    lambda children: st.one_of(_make_arr(children), _make_obj(children)),
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Depth-focused strategies near the parser's MAX_NESTING = 2048
# ---------------------------------------------------------------------------

# A "simple" filler value that won't itself recurse.
_leaf = st.one_of(st.just("0"), st.just("null"), st.just('""'), st.just("true"))

# Depths concentrated near (but not far beyond) 2048.
_near_cap_depth = st.one_of(
    st.integers(min_value=1, max_value=8),
    st.integers(min_value=2000, max_value=2050),
    st.sampled_from([2047, 2048, 2049, 2050, 2100]),
)


def _nested(depth, open_ch, close_ch):
    return open_ch * depth + "0" + close_ch * depth


_deep_nesting = _near_cap_depth.flatmap(
    lambda d: st.one_of(
        st.just(_nested(d, "[", "]")),
        st.just(_nested(d, '{"a":', "}")),
        st.just("[" * d + "]" * d),
        st.just("[" * d),  # unterminated deep
        st.just('{"a":' * d + "0" + "}" * d),
    )
)

# ---------------------------------------------------------------------------
# Near-valid / malformed whole-document variants
# ---------------------------------------------------------------------------

_malformed_docs = st.sampled_from(
    [
        "",
        " ",
        "\n",
        "\t\r\n ",
        ",",
        ":",
        "{,}",
        "[,]",
        "tru",
        "fals",
        "nul",
        "TRUE",
        "Null",
        "1abc",
        "1 garbage",
        "[]xyz",
        "{}trailing",
        '{"a":1}{"b":2}',
        "null null",
        "[1,2,3] extra",
        '"unterminated',
        "'single'",
        "/* comment */",
        "// comment\n1",
        "/* unterminated",
        "[1,2,3",
        '{"a":',
        "\\u0000",
        "0x00",
        "0\x00",  # NOTE: contains raw NUL -> harness will SKIP; kept out below
    ]
)

# Remove any entry that contains a raw NUL byte (harness skips those).
_malformed_docs = _malformed_docs.filter(lambda s: "\x00" not in s)

# ---------------------------------------------------------------------------
# Whitespace decoration (WS is skipped by the grammar)
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", " \t\n\r"])


def _decorate(text):
    return st.builds(
        lambda a, b, c: a + c + b,
        _ws,
        _ws,
        st.just(text),
    )


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

def _top_level():
    value_doc = st.one_of(_value, _deep_nesting)
    decorated = value_doc.flatmap(_decorate)
    return st.one_of(
        decorated,
        _deep_nesting,
        _malformed_docs,
        # A fully random JSON-ish document (mostly valid).
        st.recursive(
            st.one_of(_string, _number, _literals),
            lambda children: st.one_of(
                st.lists(children, min_size=0, max_size=6).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                st.lists(
                    st.builds(
                        lambda k, v: '"' + k + '":' + v,
                        st.lists(_string_piece, min_size=0, max_size=4).map(
                            lambda ps: "".join(ps)
                        ),
                        children,
                    ),
                    min_size=0,
                    max_size=6,
                ).map(lambda ps: "{" + ",".join(ps) + "}"),
            ),
            max_leaves=40,
        ),
    )


strategy = _top_level().filter(lambda s: "\x00" not in s)
```