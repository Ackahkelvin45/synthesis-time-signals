from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf strategies
# ---------------------------------------------------------------------------

# Numeric literals: valid JSON numbers plus extreme magnitudes / exponents.
_valid_int = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**12).map(str),
    st.integers(min_value=-(10**12), max_value=-1).map(str),
    st.integers(min_value=10**300, max_value=10**320).map(str),
    st.integers(min_value=-(10**320), max_value=-(10**300)).map(str),
)

_frac = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.one_of(st.just(""), st.sampled_from(["+", "-"])),
        st.integers(min_value=0, max_value=400).map(str),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_number_strategy = st.one_of(
    # normal-ish numbers
    st.tuples(
        st.one_of(st.just(""), st.just("-")),
        _valid_int,
        st.one_of(st.just(""), _frac.map(lambda f: "." + f)),
        _exp,
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    # overflow / underflow magnitudes
    st.sampled_from([
        "1e309", "-1e309", "1e308", "1e-309", "1e-400",
        "1E309", "1e+309", "1e99999", "0e999999",
        "1.7976931348623157e309",
        "-1.7976931348623157e309",
    ]),
    # malformed numbers (near-valid)
    st.sampled_from([
        "-", "+", ".", ".5", "5.", "01", "00", "-01", "+1",
        "1.", "1.e5", "1e", "1e+", "--1", "1_000",
    ]),
)

# String contents: safe chars, escapes, unicode escapes, surrogates, controls.
_safe_char = st.characters(
    whitelist_categories=("Lu", "Ll", "Nd", "Po", "Sm", "Sc", "So"),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) >= 0x20)

_escape = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
])

_unicode_escape = st.tuples(
    st.just("\\u"),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: format(n, "04x")),
).map(lambda t: t[0] + t[1])

_surrogate_escape = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD800\\uDC00",  # valid surrogate pair
    "\\uD83D\\uDE00",  # emoji
    "\\uD800x",        # lone high surrogate + char
    "\\uDC00\\uD800",  # reversed pair
    "\\u0000",         # NUL escape (fine, six chars)
    "\\u001f", "\\u007f", "\\uffff", "\\uFFFF",
])

_string_inner = st.one_of(
    _safe_char,
    _escape,
    _unicode_escape,
    _surrogate_escape,
    st.just("\\u0000"),
    st.just("\\u001F"),
)

_json_string = st.lists(_string_inner, max_size=12).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# Near-valid-but-malformed strings (unterminated, bad escapes).
_malformed_string = st.one_of(
    st.just('"'),
    st.just('"abc'),
    st.just('"abc\\'),
    st.just('"\\x41"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('"a\nb"'),  # raw control char inside string
    st.just('"a\tb"'),
)

# ---------------------------------------------------------------------------
# Recursive structure
# ---------------------------------------------------------------------------

# A "key" is a JSON string (may be duplicated by the generator on purpose).
_key = _json_string

# Depth budget: concentrate near MAX_NESTING=2048 but also sample small depths.
def _depth_strategy():
    return st.one_of(
        st.integers(min_value=0, max_value=8),          # shallow
        st.integers(min_value=9, max_value=64),         # medium
        st.integers(min_value=65, max_value=1024),      # deep
        st.integers(min_value=1025, max_value=2048),    # near the cap
        st.integers(min_value=2049, max_value=2100),    # just past the cap
    )

# Leaf values (non-recursive).
_leaf_value = st.one_of(
    _json_string,
    _number_strategy,
    st.sampled_from(["true", "false", "null"]),
)

# Malformed fragments to sprinkle at the value level.
_malformed_value = st.sampled_from([
    "", "tru", "fals", "nul", "True", "NULL", "undefined",
    ",", ":", "]", "}", "'x'",
])

# Build the recursive strategy.  We use st.recursive with a bounded depth.
def _make_value(depth):
    """Return a strategy for a JSON value with at most `depth` nesting."""
    if depth <= 0:
        return st.one_of(_leaf_value, _malformed_value)
    inner = st.deferred(lambda: _make_value(depth - 1))
    pair = st.tuples(_key, st.just(":"), inner).map(
        lambda t: t[0] + t[1] + t[2]
    )
    obj = st.one_of(
        st.just("{}"),
        st.tuples(
            st.just("{"),
            st.lists(pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # duplicate keys deliberately
        st.tuples(
            st.just("{"),
            _key,
            st.just(":"),
            inner,
            st.just(","),
            _key,
            st.just(":"),
            inner,
            st.just("}"),
        ).map(lambda t: "".join(t)),
        # malformed object
        st.sampled_from([
            "{", "}", "{,}", '{"a"}', '{"a":}', '{"a":1,}',
            '{"a":1 "b":2}', '{1:2}',
        ]),
    )
    arr = st.one_of(
        st.just("[]"),
        st.tuples(
            st.just("["),
            st.lists(inner, min_size=1, max_size=4).map(lambda vs: ",".join(vs)),
            st.just("]"),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.sampled_from([
            "[", "]", "[,]", "[1,]", "[1 2]", "[1,,2]",
        ]),
    )
    return st.one_of(_leaf_value, _malformed_value, obj, arr)


# Depth-controlled top-level strategy.
@st.composite
def _json_text(draw):
    depth = draw(_depth_strategy())
    # For large depths, build a simple nested chain rather than a full tree,
    # to avoid combinatorial blow-up while still hitting the cap.
    if depth > 64:
        kind = draw(st.sampled_from(["array", "object", "mixed"]))
        if kind == "array":
            return "[" * depth + "]" * depth
        if kind == "object":
            # {"a":{"a":{...}}} style
            return '{"a":' * depth + "null" + "}" * depth
        # mixed
        left = "[{" * (depth // 2)
        right = "}]" * (depth // 2)
        return left + "null" + right
    # Otherwise build a real recursive value.
    value_strat = _make_value(depth)
    text = draw(value_strat)
    # Occasionally append trailing content (parser ignores it).
    if draw(st.booleans()):
        text += draw(st.sampled_from([
            " ", "\n", "garbage", "1abc", "[]xyz", "/*c*/", "//c",
        ]))
    return text


# ---------------------------------------------------------------------------
# Extra edge-case strings (explicit, high-value)
# ---------------------------------------------------------------------------

_explicit_edge_cases = st.sampled_from([
    "",
    " ",
    "\n",
    "null",
    "true",
    "false",
    "0",
    "-",
    "-.",
    ".5",
    "1.",
    "+1",
    "01",
    "1e309",
    "-1e309",
    "1e-309",
    "1e999",
    "{}",
    "[]",
    '{"k":0,"k":1}',
    '{"a":1,"a":2,"b":3}',
    '{"":""}',
    '{"\\u0000":1}',
    '["\\uD800"]',
    '["\\uD800\\uDC00"]',
    '["\\uDC00\\uD800"]',
    '"\\u0000"',
    '"\\uFFFF"',
    '"\\uD83D\\uDE00"',
    '"a\\u0000b"',
    '"unterminated',
    '{"a":}',
    '{"a" 1}',
    '{,}',
    '[1,]',
    '[1 2]',
    '[,1]',
    '{"a":1}garbage',
    '1garbage',
    '[]xyz',
    '{"a":{"b":{"c":[1,2,3]}}}',
    '[' * 2047 + ']' * 2047,
    '[' * 2048 + ']' * 2048,
    '[' * 2049 + ']' * 2049,
    '{"a":' * 2047 + 'null' + '}' * 2047,
    '{"a":' * 2048 + 'null' + '}' * 2048,
    '{"a":' * 2049 + 'null' + '}' * 2049,
    '[' * 2050 + ']' * 2050,
    '{"a":' * 2050 + 'null' + '}' * 2050,
    # nested with content at the bottom
    '[' * 1024 + '1' + ']' * 1024,
    '{"a":' * 1024 + '1' + '}' * 1024,
    # whitespace variants
    "  \t\n\r  null  \t\n\r ",
    "\t{}\n",
    # numbers at extremes
    "1.7976931348623157e308",
    "-1.7976931348623157e308",
    "5e-324",
    "2.2250738585072014e-308",
    "1e-400",
    "1e400",
    "0e0",
    "0E0",
    "0e+0",
    "0e-0",
    "1E+01",
    "1e01",
    "-0",
    "-0.0",
    "-0e0",
    # ------------------------------------------------------------------
    # NEW: whitespace / control / structural variants that exercise
    # parser branches around whitespace skipping, BOM handling, and
    # separator/terminator handling that the previous corpus missed.
    # ------------------------------------------------------------------
    "\ufeff{}",
    "\ufeff[]",
    "\ufeffnull",
    "{\"a\":\n1}",
    "{\"a\":\r\n1}",
    "[\n1,\n2\n]",
    "[\r1\r]",
    "{\t\"a\"\t:\t1\t}",
    "\x0b{}",   # vertical tab before value
    "\x0c{}",   # form feed before value
    "\x0b[]",
    "\x0c[]",
    "{\"a\":\x0b1}",
    "{\"a\":\x0c1}",
    "[1,\x0b2]",
    "[1,\x0c2]",
    "\x00{}",
    "\x00[]",
    "{} \x00",
    "[] \x00",
    # deep nesting with whitespace at each level
    "[\n" * 8 + "1" + "\n]" * 8,
    "{\"a\":\n" * 8 + "1" + "\n}" * 8,
    # numbers with many exponent digits (overflow path)
    "1e" + "9" * 50,
    "1e-" + "9" * 50,
    "1e+" + "9" * 50,
    "1E" + "9" * 50,
    # very long fractional part
    "1." + "0" * 100 + "1",
    "0." + "9" * 100,
    # strings with many escapes
    '"' + "\\n" * 50 + '"',
    '"' + "\\u0041" * 50 + '"',
    # large flat arrays / objects to hit accumulation branches
    "[" + ",".join("0" for _ in range(64)) + "]",
    "{" + ",".join('"k%d":0' % i for i in range(64)) + "}",
    # empty-key / empty-value edge combos
    '{"":0}',
    '{"a":""}',
    '{"":""}',
    '["",""]',
    # literals with trailing whitespace at top level
    "null ",
    "true\t",
    "false\n",
    "null\r",
    # just whitespace
    "\t",
    "\r",
    "\n",
    "\r\n",
    " ",
    # unusual but legal separators around tokens
    "[\t1\t,\t2\t]",
    "{\t\"a\"\t:\t1\t,\t\"b\"\t:\t2\t}",
])


# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _json_text(),
    _explicit_edge_cases,
)