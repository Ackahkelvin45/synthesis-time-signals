from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf / primitive strategies
# ---------------------------------------------------------------------------

# Safe, ordinary string contents (no raw control chars, no raw NUL).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00',
    min_codepoint=0x20,
)

# Escapes that are legal inside a JSON string.
_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))
_unicode_esc = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes (legal as text in the grammar; may be rejected downstream).
_hi_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF).map(
    lambda n: "\\u%04x" % n
)
_lo_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)

# Escaped NUL / control as text (NOT a raw NUL byte).
_escaped_nul = st.just("\\u0000")
_escaped_ctrl = st.integers(min_value=0x01, max_value=0x1F).map(
    lambda n: "\\u%04x" % n
)

_string_piece = st.one_of(
    _safe_chars.map(str),
    _escapes,
    _unicode_esc,
    _hi_surrogate,
    _lo_surrogate,
    _escaped_nul,
    _escaped_ctrl,
)

# Build a quoted JSON string.
_json_string = st.lists(_string_piece, min_size=0, max_size=12).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# ---------------------------------------------------------------------------
# Number strategies
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str).flatmap(
        lambda d: st.lists(
            st.integers(min_value=0, max_value=9).map(str),
            min_size=0, max_size=8,
        ).map(lambda rest: d + "".join(rest))
    ),
    # Extreme magnitudes as literal digit runs.
    st.sampled_from([
        "1" * 309,
        "9" * 320,
        "1234567890123456789012345678901234567890",
        "0" * 1,  # placeholder, replaced below
    ]),
)

# Clean the placeholder-ish values: keep only well-formed int parts.
_int_part = _int_part.filter(lambda s: s == "0" or (s[0] != "0"))

_frac = st.lists(
    st.integers(min_value=0, max_value=9).map(str),
    min_size=1, max_size=8,
).map(lambda ds: "." + "".join(ds))

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.lists(st.integers(min_value=0, max_value=9).map(str),
             min_size=1, max_size=4).map(lambda ds: "".join(ds)),
).map(lambda t: t[0] + t[1] + t[2])

_sign = st.sampled_from(["", "-"])

_number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.none(), _frac),
    st.one_of(st.none(), _exp),
).map(lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or ""))

# Numeric edge cases: overflow, huge exponents, tiny/huge, negative zero.
_extreme_numbers = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "1e-400",
    "1E+309", "1E-309", "1e999999999",
    "0", "-0", "0.0", "-0.0", "0e0", "0E-0",
    "1.7976931348623157e308",
    "2.2250738585072014e-308",
    "1" + "0" * 308,
    "1" + "0" * 400,
    "123456789012345678901234567890",
])

_number_or_extreme = st.one_of(_number, _extreme_numbers)

# ---------------------------------------------------------------------------
# Malformed / near-valid fragments
# ---------------------------------------------------------------------------

# Lone "-" (parser accepts as 0); leading +; ".5"; "1."; leading zeros.
_malformed_numbers = st.sampled_from([
    "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "00", "-01",
    "1e", "1e+", "1e-", "0x1", "1.2.3", "--1", "1..2",
])

# Unterminated strings, bad escapes, raw-looking control text.
_malformed_strings = st.sampled_from([
    '"', '"abc', '"abc\\', '"\\x41"', '"\\u12"', '"\\uZZZZ"',
    '"unterminated', '"a\nb"', '"\\u"',
])

# Structural malformations.
_malformed_struct = st.sampled_from([
    "{", "}", "[", "]", "{,}", "[,]", '{"a":}', '{"a" 1}',
    '{"a":1,}', "[1,]", "[1 2]", '{"a":1 "b":2}', "[1,,2]",
    '{"a"::1}', '{:1}', "[,1]", "[1,,]",
    "tru", "fals", "nul", "TRUE", "Null", "undefined",
])

_malformed = st.one_of(
    _malformed_numbers,
    _malformed_strings,
    _malformed_struct,
)

# Trailing content after a complete value (accepted by this parser).
_trailing = st.sampled_from([
    "abc", " garbage", "xyz", " 123", "null", "{}", "[]", "//x", "/*x*/",
])

# ---------------------------------------------------------------------------
# Recursive JSON value strategy
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the parser's 2048 nesting cap, but keep the
# recursive construction shallow enough to be fast. We use a moderate base
# depth plus explicit deep-nesting generators for the cap region.
_MAX_REC_DEPTH = 6

_leaves = st.one_of(
    _json_string,
    _number_or_extreme,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _malformed,
)

def _value_strategy(depth):
    if depth <= 0:
        return _leaves

    inner = _value_strategy(depth - 1)

    # Object with pairs (may include duplicate keys).
    key = st.one_of(_json_string, _json_string, st.just('"k"'), st.just('"a"'))
    pair = st.tuples(key, inner).map(lambda t: t[0] + ":" + t[1])
    obj = st.one_of(
        st.just("{}"),
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
    )

    # Array.
    arr = st.one_of(
        st.just("[]"),
        st.lists(inner, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
    )

    return st.one_of(_leaves, obj, arr)

_recursive_value = st.recursive(
    _leaves,
    lambda children: st.one_of(
        # object
        st.one_of(
            st.just("{}"),
            st.lists(
                st.tuples(
                    st.one_of(_json_string, st.just('"k"'), st.just('"a"')),
                    children,
                ).map(lambda t: t[0] + ":" + t[1]),
                min_size=1, max_size=4,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
        ),
        # array
        st.one_of(
            st.just("[]"),
            st.lists(children, min_size=1, max_size=4).map(
                lambda vs: "[" + ",".join(vs) + "]"
            ),
        ),
    ),
    max_leaves=_MAX_REC_DEPTH,
)

# ---------------------------------------------------------------------------
# Deep nesting near the 2048 cap
# ---------------------------------------------------------------------------

def _deep_nesting():
    # Depth concentrated near the cap: around 2000-2100, plus a few just over.
    depth = st.one_of(
        st.integers(min_value=1900, max_value=2100),
        st.sampled_from([2047, 2048, 2049, 2050, 3000]),
    )
    return depth.flatmap(lambda d: st.one_of(
        # nested arrays: [ [ [ ... ] ] ]
        st.just("[" * d + "]" * d),
        # nested arrays with a leaf at the bottom
        st.just("[" * d + "0" + "]" * d),
        # nested objects
        st.just('{"a":' * d + "null" + "}" * d),
        # mixed
        st.just('{"a":[' * d + "1" + "]}" * d),
    ))

_deep = _deep_nesting()

# ---------------------------------------------------------------------------
# Duplicate-key objects (expect rejection) and other edge composites
# ---------------------------------------------------------------------------

_dup_keys = st.sampled_from([
    '{"k":0,"k":1}',
    '{"a":1,"a":2,"a":3}',
    '{"x":{"y":1},"x":{"y":2}}',
    '{"k":[1,2],"k":[3,4]}',
    '{"":0,"":1}',
])

_empties = st.sampled_from(["{}", "[]", "{ }", "[ ]", "{}[]", "[]{}"])

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

_value_with_trailing = st.tuples(_recursive_value, _trailing).map(
    lambda t: t[0] + t[1]
)

strategy = st.one_of(
    _recursive_value,
    _value_with_trailing,
    _deep,
    _dup_keys,
    _empties,
    _malformed,
)