```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Primitive pieces
# ---------------------------------------------------------------------------

# Safe, ordinary characters for the inside of a JSON string (no raw NUL, no
# unescaped control chars, no quote/backslash which must be escaped).
_SAFE = st.characters(
    blacklist_categories=("Cs", "Cc"),
    blacklist_characters='"\x00',
)
_safe_chars = st.text(_SAFE, min_size=0, max_size=8)

# Escapes that are always legal inside a JSON string.
_ESC = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# \uXXXX escapes, including surrogate ranges and the harmless \u0000 text.
_hex = st.text("0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_esc = st.builds(lambda h: "\\u" + h, _hex)
_surrogate_esc = st.builds(
    lambda h: "\\u" + h,
    st.text("dD", min_size=1, max_size=1).flatmap(
        lambda d: st.text("89abcdefABCDEF", min_size=3, max_size=3)
    ),
)

_esc_piece = st.one_of(_ESC, _unicode_esc, _surrogate_esc)

_string_body = st.one_of(
    _safe_chars,
    st.lists(_esc_piece, min_size=1, max_size=4).map("".join),
    st.lists(st.one_of(_esc_piece, _safe_chars), min_size=0, max_size=6).map("".join),
)

# A well-formed JSON string literal.
_jstring = st.builds(lambda b: '"' + b + '"', _string_body)

# A few fixed-but-interesting string literals.
_fixed_strings = st.sampled_from([
    '""',
    '"\\u0000"',
    '"\\uD800"',
    '"\\uDFFF"',
    '"\\uD800\\uDC00"',
    '"\\uDBFF\\uDFFF"',
    '"a\\u0000b"',
    '"tab\\there"',
    '"quote\\"inside"',
    '"back\\\\slash"',
    '"\\/"',
])


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.text("123456789", min_size=1, max_size=1).flatmap(
        lambda d: st.text("0123456789", min_size=0, max_size=17).map(
            lambda rest: d + rest
        )
    ),
    st.text("0123456789", min_size=1, max_size=30),  # long magnitudes
)

_frac_part = st.builds(lambda d: "." + d, st.text("0123456789", min_size=1, max_size=10))

_exp_part = st.builds(
    lambda s: "e" + s,
    st.one_of(
        st.text("0123456789", min_size=1, max_size=3),
        st.builds(lambda s: s[0] + s[1:], st.text("+-", min_size=1, max_size=1), st.text("0123456789", min_size=1, max_size=3)),
    ),
)

_number = st.builds(
    lambda sign, i, f, e: sign + i + f + e,
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    st.one_of(st.just(""), _frac_part),
    st.one_of(st.just(""), _exp_part),
)

# Extreme / edge numbers (some rejected by the parser, that's expected).
_extreme_numbers = st.sampled_from([
    "0", "-0", "1", "-1",
    "1e309", "-1e309", "1e308", "1e-308", "1e999999",
    "123456789012345678901234567890",
    "-1234567890123456789012345678901234567890",
    "1.7976931348623157e308",
    "5e-324",
    "0.00000000000000000000001",
    "1E+00", "1e01", "1e-01",
    "9223372036854775807",
    "-9223372036854775808",
    "18446744073709551616",
])


# ---------------------------------------------------------------------------
# Near-valid-but-malformed fragments
# ---------------------------------------------------------------------------

_malformed = st.sampled_from([
    # trailing commas
    "[1,]", "[1,2,]", '{"a":1,}', '{"a":1,"b":2,}',
    # missing colons
    '{"a" 1}', '{"a"}', '{"a":}',
    # double commas
    "[1,,2]", '{"a":1,,"b":2}',
    # unterminated strings
    '"abc', '"', '"abc\\', '{"a": "bc',
    # leading +, .5, 01
    "+1", ".5", "-.5", "01", "-01", "00", "1.", "-",
    # stray punctuation
    "[", "]", "{", "}", ",", ":", "[]]",
    # trailing garbage after a complete value (accepted by parser)
    "1abc", "1 garbage", "[]xyz", "{}trailing", "true false", "nullx",
    # bad escapes
    '"\\x41"', '"\\u12"', '"\\uZZZZ"', '"\\uD800"',
    # misc
    "tru", "fals", "nul", "TRUE", "NaN", "Infinity", "-Infinity",
])


# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

# Leaf values (non-recursive).
_leaf = st.one_of(
    _jstring,
    _fixed_strings,
    _number,
    _extreme_numbers,
    st.sampled_from(["true", "false", "null"]),
    _malformed,
)

# Depth control: concentrate near 2048 but also hit shallow depths.
def _depth_choice():
    return st.one_of(
        st.integers(min_value=0, max_value=8),
        st.integers(min_value=2000, max_value=2050),
        st.integers(min_value=1000, max_value=2048),
    )


def _ws():
    return st.text(" \t\n\r", min_size=0, max_size=2)


def _pair(value_strat):
    return st.builds(
        lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
        _jstring,
        _ws(),
        _ws(),
        value_strat,
    )


def _array(value_strat):
    return st.builds(
        lambda w1, items, w2: "[" + w1 + ",".join(items) + w2 + "]",
        _ws(),
        st.lists(value_strat, min_size=0, max_size=5),
        _ws(),
    )


def _object(value_strat):
    return st.builds(
        lambda w1, pairs, w2: "{" + w1 + ",".join(pairs) + w2 + "}",
        _ws(),
        st.lists(_pair(value_strat), min_size=0, max_size=5),
        _ws(),
    )


# Build the recursive strategy.
_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_array(children), _object(children)),
    max_leaves=20,
)


# Deeply nested arrays/objects near the depth limit (built iteratively).
def _deep(depth, opener, closer):
    return opener * depth + closer * depth


_deep_nesting = st.builds(
    lambda d, kind: (
        _deep(d, "[", "]")
        if kind == 0
        else _deep(d, '{"k":', "}")
        if kind == 1
        else _deep(d, '[{"k":', "}]")
    ),
    _depth_choice(),
    st.integers(min_value=0, max_value=2),
)


# Duplicate-key objects (expected rejection by the parser).
_dup_keys = st.builds(
    lambda k, v1, v2: '{"' + k + '":' + v1 + ',"' + k + '":' + v2 + "}",
    st.text("abcxyz", min_size=0, max_size=4),
    _leaf,
    _leaf,
)


# Top-level candidate: a value, optionally with leading/trailing whitespace,
# optionally with trailing content, and sometimes a bare container.
_top = st.one_of(
    _value,
    _deep_nesting,
    _dup_keys,
    _extreme_numbers,
    _malformed,
    st.builds(lambda w1, v, w2: w1 + v + w2, _ws(), _value, _ws()),
    st.builds(lambda v, tail: v + tail, _value, st.sampled_from(
        ["", " ", "\n", "garbage", "0", "]", "}", "null"]
    )),
    st.sampled_from(["{}", "[]", "[[[]]]", '{"":{}}', '{"a":[]}']),
)


def _strip_nul(s: str) -> str:
    # The harness cannot test raw NUL bytes; drop them defensively.
    return s.replace("\x00", "")


strategy = _top.map(_strip_nul)
```