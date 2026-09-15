from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Strings that are valid JSON string *contents* (no surrounding quotes),
# including escapes, unicode escapes, surrogate escapes, raw control bytes,
# and NUL bytes.  We build these deliberately to hit the parser's edge cases.
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates as raw code points
    blacklist_characters='\\"',
)

_ESCAPES = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_HEX = st.sampled_from("0123456789abcdefABCDEF")


def _unicode_escape():
    return st.tuples(
        st.just("\\u"),
        _HEX,
        _HEX,
        _HEX,
        _HEX,
    ).map("".join)


# Lone surrogate escapes (the parser rejects these).  We include them
# occasionally so the fuzzer can exercise the rejection path.
_LONE_SURROGATE_ESCAPE = st.sampled_from(
    [
        "\\ud800",
        "\\udbff",
        "\\udc00",
        "\\udfff",
        "\\ud83d",  # high surrogate without low
        "\\ude00",  # low surrogate without high
    ]
)

# Valid surrogate pairs (accepted).
_SURROGATE_PAIR = st.tuples(
    st.sampled_from(["\\ud800", "\\ud801", "\\ud83d", "\\udbff"]),
    st.sampled_from(["\\udc00", "\\udc01", "\\udfff", "\\ude00"]),
).map("".join)

# Raw control characters and NUL bytes inside strings.
_RAW_CONTROL = st.sampled_from(
    ["\x00", "\x01", "\x08", "\x0b", "\x0c", "\x1f", "\t", "\n", "\r"]
)

_STRING_CONTENT_CHAR = st.one_of(
    _SAFE_CHARS,
    _ESCAPES,
    _unicode_escape(),
    _SURROGATE_PAIR,
    st.booleans().flatmap(
        lambda use_bad: _LONE_SURROGATE_ESCAPE if use_bad else _SAFE_CHARS
    ),
    _RAW_CONTROL,
)

# A JSON string literal (with quotes).
_json_string = st.lists(_STRING_CONTENT_CHAR, max_size=12).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_DIGITS = st.text("0123456789", min_size=1, max_size=6)

# Normal JSON numbers.
_normal_number = st.one_of(
    st.integers(min_value=-(10**18), max_value=10**18).map(str),
    st.tuples(
        st.booleans().map(lambda neg: "-" if neg else ""),
        _DIGITS,
        st.one_of(
            st.just(""),
            st.tuples(st.just("."), _DIGITS).map("".join),
        ),
        st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from("eE"),
                st.one_of(st.just(""), st.sampled_from("+-")),
                _DIGITS,
            ).map("".join),
        ),
    ).map(lambda t: "".join(t)),
)

# Extreme magnitudes / exponents (including overflow like 1e309).
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e999999999",
        "1e-999999999",
        "0e0",
        "1e01",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1.7976931348623157e308",
        "5e-324",
        "0.0",
        "-0",
        "0",
    ]
)

# Malformed numbers the parser rejects or accepts leniently.
_malformed_number = st.sampled_from(
    [
        "01",       # leading zero (accepted by parser)
        "1.",       # trailing dot (accepted by parser)
        "0x10",     # hex (accepted by parser)
        "-",        # lone minus (rejected)
        "+1",       # leading plus (rejected)
        ".5",       # bare dot (rejected)
        "NaN",      # rejected
        "Infinity", # rejected
        "-Infinity",# rejected
        "1e",       # incomplete exponent (rejected)
        "1e+",      # incomplete exponent (rejected)
        "1.2.3",    # multiple dots (rejected)
        "--1",      # double minus (rejected)
        "00",       # leading zeros (accepted by parser)
        "0.",       # trailing dot (accepted by parser)
    ]
)

_number = st.one_of(_normal_number, _extreme_number, _malformed_number)

# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

_json_value = st.recursive(
    st.one_of(
        _json_string,
        _number,
        st.sampled_from(["true", "false", "null"]),
        # Near-valid-but-malformed literals
        st.sampled_from(["True", "False", "NULL", "nul", "tru", "fals"]),
    ),
    lambda children: st.one_of(
        _make_array(children),
        _make_object(children),
    ),
    max_leaves=20,
)


def _make_array(children):
    """Array: '[' value (',' value)* ']' or '[]'."""
    return st.one_of(
        st.just("[]"),
        st.lists(children, min_size=1, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        # Empty array with whitespace
        st.just("[ ]"),
        st.just("[\n]"),
        # Trailing comma (rejected by parser)
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        ),
        # Double comma (rejected)
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + ",,]"
        ),
        # Missing comma (rejected)
        st.lists(children, min_size=2, max_size=4).map(
            lambda vs: "[" + " ".join(vs) + "]"
        ),
        # Unterminated array
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs)
        ),
    )


def _make_object(children):
    """Object: '{' pair (',' pair)* '}' or '{}'."""
    def _pair(v):
        return st.tuples(_json_string, st.just(":"), v).map("".join)

    pair = children.flatmap(_pair)

    return st.one_of(
        st.just("{}"),
        st.just("{ }"),
        st.just("{\n}"),
        st.lists(pair, min_size=1, max_size=5).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        # Duplicate keys
        st.tuples(
            _json_string,
            st.just(":"),
            children,
            st.just(","),
            _json_string,
            st.just(":"),
            children,
        ).map("".join).map(lambda s: "{" + s + "}"),
        # Trailing comma (rejected)
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + ",}"
        ),
        # Double comma (rejected)
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + ",,}"
        ),
        # Missing colon (rejected)
        st.tuples(_json_string, children).map(
            lambda t: "{" + t[0] + " " + t[1] + "}"
        ),
        # Unquoted key (rejected)
        st.tuples(st.text("abcxyz", min_size=1, max_size=4), st.just(":"), children).map(
            lambda t: "{" + t[0] + t[1] + t[2] + "}"
        ),
        # Single-quoted string (rejected)
        st.tuples(children, st.just(":"), children).map(
            lambda t: "{'" + t[0] + "':" + t[2] + "}"
        ),
        # Unterminated object
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps)
        ),
    )


# ---------------------------------------------------------------------------
# Deep nesting near the 1000-level limit
# ---------------------------------------------------------------------------

def _deep_nesting():
    """Generate deeply nested arrays/objects near the 1000-level limit."""
    depth = st.integers(min_value=990, max_value=1010)
    return depth.flatmap(
        lambda d: st.one_of(
            st.just("[" * d + "]" * d),
            st.just("[" * d + "1" + "]" * d),
            st.just('{"a":' * d + "1" + "}" * d),
            st.just("[" * d + "1" + "]" * (d - 1)),  # unterminated
            st.just("[" * (d + 5) + "1" + "]" * (d + 5)),  # beyond limit
        )
    )


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

_valid_or_near_valid = st.one_of(
    _json_value,
    _deep_nesting(),
    # Bare scalars
    _number,
    _json_string,
    st.sampled_from(["true", "false", "null"]),
    # Empty / whitespace-only (rejected)
    st.just(""),
    st.just("   "),
    st.just("\n\t "),
    # BOM prefix (accepted by parser)
    st.just("\ufeff1"),
    st.just("\ufeff{}"),
    st.just("\ufeff[]"),
    st.just("\ufeff\"x\""),
    # Trailing content after a valid value (accepted)
    st.tuples(_json_value, st.just("abc")).map("".join),
    st.tuples(_json_value, st.just(" 1 2")).map("".join),
    # Two top-level values
    st.tuples(_json_value, st.just(" "), _json_value).map("".join),
    # NUL after a value
    st.tuples(_json_value, st.just("\x00")).map("".join),
    # NUL inside a string
    st.just('"a\x00b"'),
    # Raw control inside a string
    st.just('"a\tb"'),
    st.just('"a\nb"'),
    st.just('"a\rb"'),
    # Lone surrogate escape (rejected)
    st.just('"\\ud800"'),
    st.just('"\\udfff"'),
    # Invalid escape (rejected)
    st.just('"\\x41"'),
    st.just('"\\q"'),
    # Single-quoted string (rejected)
    st.just("'hello'"),
    # Unquoted key (rejected)
    st.just("{key:1}"),
    # Trailing comma (rejected)
    st.just("[1,2,]"),
    st.just('{"a":1,}'),
    # Double comma (rejected)
    st.just("[1,,2]"),
    st.just('{"a":1,,}'),
    # Missing colon (rejected)
    st.just('{"a" 1}'),
    # Unterminated string (rejected)
    st.just('"abc'),
    # Unterminated array/object (rejected)
    st.just("[1,2"),
    st.just('{"a":1'),
    # Leading plus / bare dot / lone minus (rejected)
    st.just("+1"),
    st.just(".5"),
    st.just("-"),
    # NaN / Infinity (rejected)
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    # Hex (accepted)
    st.just("0x10"),
    st.just("0xFF"),
    # Leading zeros (accepted)
    st.just("01"),
    st.just("00"),
    st.just("00123"),
    # Trailing dot (accepted)
    st.just("1."),
    st.just("0."),
    # Extreme magnitudes
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("1e999999999"),
)

strategy = _valid_or_near_valid