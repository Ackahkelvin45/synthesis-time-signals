import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Low-level lexical fragments
# ---------------------------------------------------------------------------

# Characters that may appear unescaped inside a JSON string per the grammar.
# We deliberately do NOT include raw NUL/control bytes here (those are added
# separately as edge cases).
_SAFE_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " .,;:!?#$%&*()-_=+[]{}<>|~^`'@"
    "/"
)

_safe_char = st.sampled_from(list(_SAFE_CHARS))

# Escapes the grammar allows.
_escape = st.sampled_from(list('"\\/bfnrt'))

_hex_digit = st.sampled_from(list("0123456789abcdefABCDEF"))

_unicode_escape = st.tuples(
    st.just("u"),
    _hex_digit, _hex_digit, _hex_digit, _hex_digit,
).map(lambda t: "".join(t))

# A valid escape sequence (backslash + something).
_valid_escape = st.one_of(
    _escape.map(lambda c: "\\" + c),
    _unicode_escape.map(lambda s: "\\" + s),
)

# A string body chunk: either a safe char or a valid escape.
_string_chunk = st.one_of(_safe_char, _valid_escape)

# Raw control / NUL bytes that the parser accepts inside strings but the
# grammar forbids.  Include NUL explicitly and a few control chars.
_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f"])

# Body of a string: a mix of normal chunks, raw controls, and edge escapes.
_string_body = st.one_of(
    st.lists(_string_chunk, max_size=12).map("".join),
    st.lists(
        st.one_of(_string_chunk, _raw_control), max_size=12
    ).map("".join),
    # Lone surrogate escapes are REJECTED by the parser -> good malformed case.
    st.just("\\ud800"),
    st.just("\\udfff"),
    st.just("\\uD800\\uDC00"),  # valid surrogate pair
)

# A well-formed JSON string (quoted).
_string = _string_body.map(lambda b: '"' + b + '"')

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

# Integers, including leading-zero deviations the parser accepts.
_int_digits = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=0, max_value=10**18).map(str),
    # leading zeros (accepted by parser, rejected by grammar)
    st.integers(min_value=1, max_value=99).map(lambda n: "0" + str(n)),
)

_fraction = st.one_of(
    st.just(""),
    st.tuples(st.just("."), st.integers(min_value=0, max_value=10**12).map(str))
    .map(lambda t: "".join(t)),
    # trailing dot (accepted by parser)
    st.just("."),
)

_exponent = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=9999).map(str),
    ).map(lambda t: "".join(t)),
)

_sign = st.sampled_from(["", "-"])

_number = st.tuples(_sign, _int_digits, _fraction, _exponent).map(
    lambda t: "".join(t)
)

# Extreme magnitudes / special numeric edge cases.
_extreme_number = st.sampled_from(
    [
        "1e309", "-1e309", "1e-309", "1e9999", "-1e9999",
        "0e0", "-0", "-0.0", "0.0", "1.", "-1.", "01", "-01", "007",
        "0x10", "0xdeadBEEF", "-0x1", "1e+01", "1E-01",
        "123456789012345678901234567890",
        "1.7976931348623157e308",
        "5e-324",
    ]
)

# Malformed numbers the parser is expected to reject.
_malformed_number = st.sampled_from(
    [
        "+1", ".5", "-.5", "1..2", "1e", "1e+", "-", "--1",
        "NaN", "Infinity", "-Infinity", "nan", "inf",
    ]
)

# ---------------------------------------------------------------------------
# Whitespace
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t "])

# ---------------------------------------------------------------------------
# Recursive JSON value strategy
# ---------------------------------------------------------------------------

# Leaf values (non-container).
_leaf = st.one_of(
    _string,
    _number,
    _extreme_number,
    st.sampled_from(["true", "false", "null"]),
)

# Malformed leaf fragments (near-valid but broken).
_malformed_leaf = st.one_of(
    _malformed_number,
    st.just('"unterminated'),
    st.just('"bad\\xescape"'),
    st.just("'single'"),
    st.just("tru"),
    st.just("nul"),
    st.just(""),
)

# A "pair" key: strings, plus duplicate-key edge cases handled by the caller.
_key = _string

# We build the recursive structure with st.recursive so that depth can be
# controlled and concentrated near the parser's 1000-level limit.

# Base (non-recursive) value.
_base_value = _leaf

# One level of container construction, given a strategy for inner values.
def _extend(value_st):
    # Object members: key : value
    pair = st.tuples(_key, _ws, st.just(":"), _ws, value_st).map(
        lambda t: "".join(t)
    )
    # Object with zero or more pairs.
    obj = st.one_of(
        st.just("{}"),
        st.tuples(
            st.just("{"),
            _ws,
            st.lists(pair, min_size=1, max_size=4).map(
                lambda ps: ("," + _ws_dummy()).join(ps) if False else ",".join(ps)
            ),
            _ws,
            st.just("}"),
        ).map(lambda t: "".join(t)),
        # duplicate-key object
        st.tuples(
            st.just('{"a":'),
            value_st,
            st.just(',"a":'),
            value_st,
            st.just("}"),
        ).map(lambda t: "".join(t)),
    )

    # Array with zero or more values.
    arr = st.one_of(
        st.just("[]"),
        st.tuples(
            st.just("["),
            _ws,
            st.lists(value_st, min_size=1, max_size=4).map(",".join),
            _ws,
            st.just("]"),
        ).map(lambda t: "".join(t)),
    )

    return st.one_of(obj, arr)


# Helper used above to avoid a tuple-join pitfall; returns a plain string.
def _ws_dummy():
    return ""


# Recursive strategy with a modest default depth; we then add explicit
# deep-nesting cases separately (near the 1000 limit).
_recursive_value = st.recursive(
    _base_value,
    _extend,
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Deep nesting near the parser's ~1000-level limit
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_object(depth):
    return '{"a":' * depth + "null" + "}" * depth


# Depths concentrated near the limit: accepted at 1000, rejected at 1001.
_deep_nesting = st.sampled_from(
    [
        _deep_array(1),
        _deep_array(10),
        _deep_array(100),
        _deep_array(500),
        _deep_array(999),
        _deep_array(1000),
        _deep_array(1001),
        _deep_array(1002),
        _deep_object(1),
        _deep_object(100),
        _deep_object(999),
        _deep_object(1000),
        _deep_object(1001),
        _deep_object(1002),
        # mixed nesting
        "[" * 500 + '{"a":' * 500 + "null" + "}" * 500 + "]" * 500,
        "[" * 501 + '{"a":' * 500 + "null" + "}" * 500 + "]" * 501,
    ]
)

# ---------------------------------------------------------------------------
# Malformed / near-valid structures
# ---------------------------------------------------------------------------

_malformed_structure = st.sampled_from(
    [
        # trailing commas (rejected)
        "[1,2,]",
        '{"a":1,}',
        "[,]",
        "{,}",
        # double commas
        "[1,,2]",
        '{"a":1,,"b":2}',
        # missing colon
        '{"a" 1}',
        '{"a"}',
        "{:1}",
        # missing comma
        "[1 2]",
        '{"a":1 "b":2}',
        # unbalanced
        "[1,2",
        '{"a":1',
        "[1,2]]",
        '{"a":1}}',
        # bad strings
        '"unterminated',
        '"bad\\x"',
        "'single'",
        "{unquoted:1}",
        # empty / whitespace-only
        "",
        "   ",
        "\n",
        # trailing content after valid value (ACCEPTED by parser)
        "1abc",
        "1 2",
        "null null",
        '{"a":1}garbage',
        "[1,2]extra",
        # BOM (accepted)
        "\ufeff1",
        "\ufeff{}",
        # raw NUL after a value (accepted)
        "1\x00",
        "\x00",
        # lone minus / plus
        "-",
        "+",
        "+1",
        ".5",
        "-.5",
    ]
)

# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

# A JSON document: optional leading BOM, value, optional trailing content.
_leading_bom = st.sampled_from(["", "\ufeff"])

_trailing_junk = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\n", "\t", "abc", "1", "null", "extra", "\x00"]),
)

_document = st.tuples(
    _leading_bom,
    st.one_of(_recursive_value, _deep_nesting),
    _trailing_junk,
).map(lambda t: "".join(t))

# Booleans were a production gap in the last run; upweight them so `true`
# and `false` are exercised as standalone documents and as leaf values.
_bool_literal = st.sampled_from(["true", "false"])

_bool_document = st.tuples(
    _leading_bom,
    _bool_literal,
    _trailing_junk,
).map(lambda t: "".join(t))

_bool_leaf_value = _bool_literal

# Whole strategy: valid-ish documents, malformed structures, malformed leaves.
strategy = st.one_of(
    _document,
    _malformed_structure,
    _malformed_leaf,
    # bare edge values
    st.one_of(_extreme_number, _number, _string),
    # upweighted boolean productions
    _bool_document,
    _bool_leaf_value,
)