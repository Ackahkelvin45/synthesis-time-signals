```python
from hypothesis import strategies as st
import json

# --- leaf tokens ---

# Safe, well-formed string bodies (no raw NUL, no raw control chars).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_unicode_escapes = _hex4.map(lambda h: "\\u" + h)

# Surrogate pair escapes and lone surrogates (parser may accept or reject).
_surrogate_escapes = st.sampled_from(
    [
        "\\ud83d\\ude00",  # valid pair
        "\\uD83D\\uDE00",
        "\\ud800",  # lone high surrogate
        "\\udfff",  # lone low surrogate
        "\\u0000",  # escaped NUL inside string (allowed)
        "\\u001f",
        "\\uFFFF",
        "\\u00e9",
    ]
)

_string_body_piece = st.one_of(
    _safe_chars,
    _escapes,
    _unicode_escapes,
    _surrogate_escapes,
)

# Well-formed JSON string literal.
_string_literal = st.lists(_string_body_piece, max_size=6).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# Unterminated string (malformed).
_unterminated_string = st.lists(_string_body_piece, min_size=0, max_size=5).map(
    lambda parts: '"' + "".join(parts)
)

# --- numbers ---

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero_leading = st.text(alphabet="123456789", min_size=1, max_size=1).flatmap(
    lambda first: st.tuples(
        st.just(first), st.text(alphabet="0123456789", min_size=0, max_size=5)
    )
).map(lambda t: t[0] + t[1])

_int_part = st.one_of(st.just("0"), _nonzero_leading)

_frac_part = st.text(alphabet="0123456789", min_size=1, max_size=6).map(
    lambda d: "." + d
)

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

# Extreme magnitudes / exponents, including overflow like 1e309.
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e308",
        "1e-309",
        "1e999999",
        "-1e999999",
        "0e0",
        "0e999",
        "1E+308",
        "1E-308",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1.7976931348623157e308",
        "2.2250738585072014e-308",
        "5e-324",
        "1e-400",
    ]
)

# Malformed / lenient numbers.
_malformed_number = st.sampled_from(
    [
        "-",
        "-.",
        "+1",
        ".5",
        "1.",
        "01",
        "00",
        "-01",
        "1e",
        "1e+",
        "1e-",
        "--1",
        "1.2.3",
        "+.5",
        "1e++1",
    ]
)

_number = st.one_of(
    st.builds(
        lambda sign, ip, fp, ep: sign + ip + fp + ep,
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac_part),
        st.one_of(st.just(""), _exp_part),
    ),
    _extreme_number,
    _malformed_number,
)

# --- malformed fragments ---

_malformed_string = _unterminated_string

_punctuation_junk = st.sampled_from(
    [
        ",,",
        ",]",
        ",}",
        "::",
        ":,",
        "[]]",
        "{}}",
        "[[",
        "]]",
        "{{",
        "}}",
        '{"a"}',
        '{"a":}',
        '{"a":,}',
        '{"a" "b"}',
        "{:1}",
        "[,]",
        "[1,]",
        "[,1]",
        '{"a":1,}',
    ]
)

_trailing_content = st.sampled_from(
    ["abc", " garbage", "xyz", " 123", "null", "]", "}", "//", "/*"]
)

# --- recursive value/obj/arr ---

# Depth concentrated near the parser cap (~2048). We build recursive structures
# with modest per-level expansion and allow occasional deep chains.
_MAX_LEAF = 4
_MAX_CONTAINER = 3

_value_leaves = st.one_of(
    _string_literal,
    _number,
    st.sampled_from(["true", "false", "null"]),
    _malformed_string,
    _malformed_number,
    _punctuation_junk,
)

_key = st.one_of(
    _string_literal,
    _unterminated_string,
    st.sampled_from(['"k"', '"a"', '"key"', '"\\u0000"', '""']),
)

# Duplicate-key objects: build pairs with repeated keys.
_duplicate_key_pair = st.builds(
    lambda k, v: k + ":" + v,
    st.just('"k"'),
    _value_leaves,
)

_pair = st.builds(
    lambda k, v: k + ":" + v,
    _key,
    _value_leaves,
)

# Recursive strategy for values.
_value = st.recursive(
    _value_leaves,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=_MAX_CONTAINER).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        # array with trailing comma sometimes
        st.lists(children, min_size=1, max_size=_MAX_CONTAINER).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        ),
        st.lists(
            st.one_of(_pair, _duplicate_key_pair),
            min_size=0,
            max_size=_MAX_CONTAINER,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
        # object with trailing comma
        st.lists(
            st.one_of(_pair, _duplicate_key_pair),
            min_size=1,
            max_size=_MAX_CONTAINER,
        ).map(lambda ps: "{" + ",".join(ps) + ",}"),
        # missing colon
        st.tuples(_key, children).map(lambda t: "{" + t[0] + t[1] + "}"),
        # double comma in array
        st.lists(children, min_size=2, max_size=_MAX_CONTAINER).map(
            lambda vs: "[" + vs[0] + ",," + ",".join(vs[1:]) + "]"
        ),
    ),
    max_leaves=30,
)

# Deep nesting near the 2048 cap: build chains of brackets.
_deep_nesting = st.integers(min_value=1, max_value=2100).flatmap(
    lambda depth: st.one_of(
        st.just("[" * depth + "]" * depth),
        st.just("[" * depth),
        st.just("[" * depth + "1" + "]" * depth),
        st.just('{"a":' * depth + "1" + "}" * depth),
        st.just("[" * depth + "]" * (depth - 1)),
    )
)

# Top-level values plus trailing content (accepted by parser).
_top = st.one_of(
    _value,
    _deep_nesting,
    st.tuples(_value, _trailing_content).map(lambda t: t[0] + t[1]),
    st.just(""),
    st.just(" "),
    st.just("{}"),
    st.just("[]"),
    st.just("-"),
    st.just("-."),
    st.just("null"),
    st.just("true"),
    _punctuation_junk,
    _malformed_number,
    _unterminated_string,
    _extreme_number,
)

# Ensure no raw NUL byte ever appears.
_no_nul = st.text().filter(lambda s: "\x00" not in s)

strategy = _top.filter(lambda s: "\x00" not in s)
```