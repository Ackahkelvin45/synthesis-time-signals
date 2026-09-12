```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Low-level building blocks
# ---------------------------------------------------------------------------

_hex = "0123456789abcdefABCDEF"

# SAFECODEPOINT: any char except " \ and control chars 0x00-0x1F
# We include a broad sweep of unicode plus explicit control chars (raw bytes).
_safe_chars = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0x7F, max_codepoint=0xFFFF, blacklist_characters='"\\'),
    st.sampled_from(["\x00", "\x01", "\x1f", "\x7f", "\u2028", "\u2029", "\ufeff"]),
)

# Escape sequences: simple escapes and \uXXXX
_simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
_unicode_esc = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet=_hex, min_size=4, max_size=4),
)
# Surrogate escapes (lone high/low) and valid surrogate pairs
_high_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda n: "\\u%04x" % n)
_low_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda n: "\\u%04x" % n)
_surrogate_pair = st.tuples(
    st.integers(min_value=0xD800, max_value=0xDBFF),
    st.integers(min_value=0xDC00, max_value=0xDFFF),
).map(lambda t: "\\u%04x\\u%04x" % t)

_esc = st.one_of(_simple_esc, _unicode_esc, _high_surrogate, _low_surrogate, _surrogate_pair)

_string_body = st.one_of(_safe_chars, _esc)

# A well-formed JSON string literal
_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_string_body, max_size=20),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda a, b: a + b, st.integers(1, 9).map(str), st.text(alphabet="0123456789", max_size=10)),
    st.integers(0, 10**18).map(str),
)

_frac_part = st.one_of(
    st.just(""),
    st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=10)),
)

_exp_part = st.one_of(
    st.just(""),
    st.builds(
        lambda e, s, d: e + s + d,
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=5),
    ),
)

_number = st.one_of(
    # normal
    st.builds(
        lambda neg, i, f, e: neg + i + f + e,
        st.sampled_from(["", "-"]),
        _int_part,
        _frac_part,
        _exp_part,
    ),
    # extreme magnitudes / overflow
    st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e400", "-1e400",
        "1e999999", "1e-999999", "0e0", "-0", "-0.0",
        "1.7976931348623157e308", "1.7976931348623159e308",
        "2.2250738585072014e-308", "5e-324", "4.9e-324",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1E+308", "1E-308",
    ]),
    # lone minus (accepted by this parser)
    st.just("-"),
)

# ---------------------------------------------------------------------------
# Near-valid-but-malformed number forms (still strings)
# ---------------------------------------------------------------------------

_malformed_number = st.sampled_from([
    "+1", "+0", "+1.5", ".5", "-.5", "1.", "01", "00", "0123",
    "-01", "0x1F", "0X1f", "1e", "1e+", "1e-", "--1", "1..2",
    "1.2.3", "1e1e1", "Infinity", "-Infinity", "NaN", "inf", "nan",
    "1_000", "0b101", "1,5", "1 2", "1e309x",
])

# ---------------------------------------------------------------------------
# Malformed strings
# ---------------------------------------------------------------------------

_malformed_string = st.sampled_from([
    '"unterminated',
    '"trailing\\',
    '"bad\\x"',          # invalid escape
    '"\\u12"',           # short unicode escape
    '"\\uZZZZ"',         # non-hex
    '"\\uD800"',         # lone high surrogate
    '"\\uDC00"',         # lone low surrogate
    '"\x00"',            # embedded NUL in string
    '"a\x01b"',          # control char
    '"\n"',              # raw newline in string
    '"\t"',
    "'single quotes'",
    '"\\u0000"',
])

# ---------------------------------------------------------------------------
# Whitespace / noise
# ---------------------------------------------------------------------------

_ws = st.text(alphabet=" \t\n\r", max_size=4)

def _ws_wrap(s):
    return _ws + s + _ws

# ---------------------------------------------------------------------------
# Recursive JSON structure
# ---------------------------------------------------------------------------

def _join(items, sep):
    return sep.join(items)

def _obj_body(pairs):
    """pairs: list of (key, value) string tuples -> object body without braces."""
    return ",".join(k + ":" + v for (k, v) in pairs)

# Base (non-recursive) values
_literals = st.sampled_from(["true", "false", "null", "TRUE", "False", "NULL", "nulll", "tru"])

_scalar_value = st.one_of(
    _string,
    _number,
    _literals,
    _malformed_number,
    _malformed_string,
)

# pair: STRING ':' value  (value filled recursively)
_pair = st.builds(
    lambda k, v: k + ":" + v,
    _string,
    _scalar_value,
)

# We'll build obj/arr recursively using st.recursive.
# A "pair" for the recursive builder needs a recursive value slot; we model
# this by producing a function that takes a value-strategy.

def _make_obj(value_strategy, pair_value_strategy):
    """object strings: {}, {k:v}, {k:v,...}, with optional trailing comma."""
    members = st.builds(
        lambda k, v: k + ":" + v,
        _string,
        pair_value_strategy,
    )
    inner = st.lists(members, min_size=1, max_size=8)

    def build(member_list):
        body = ",".join(member_list)
        return "{" + body + "}"

    def build_trailing(member_list):
        body = ",".join(member_list)
        return "{" + body + ",}"

    normal = st.builds(build, inner)
    trailing = st.builds(build_trailing, inner)
    empty = st.just("{}")
    # duplicate keys: same key repeated
    dup = st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        _string,
        pair_value_strategy,
        pair_value_strategy,
    )
    # malformed objects
    malformed = st.sampled_from([
        "{", "}", "{,}", "{:}", "{a:1}", "{'a':1}", "{\"a\" 1}",
        "{\"a\":}", "{\"a\":1,}", "{\"a\":1,,}", "{\"a\":1 \"b\":2}",
        "{\"a\":1,\"b\"}", "{\"a\":1,}", "{{}}", "{]",
    ])
    return st.one_of(normal, trailing, empty, dup, malformed, st.builds(_ws_wrap, normal))

def _make_arr(value_strategy):
    inner = st.lists(value_strategy, min_size=1, max_size=8)

    def build(vals):
        return "[" + ",".join(vals) + "]"

    def build_trailing(vals):
        return "[" + ",".join(vals) + ",]"

    normal = st.builds(build, inner)
    trailing = st.builds(build_trailing, inner)
    empty = st.just("[]")
    malformed = st.sampled_from([
        "[", "]", "[,]", "[,1]", "[1,,2]", "[1 2]", "[1;2]",
        "[[", "]]", "[1,", "[1", "[[]", "[}", "[1:2]",
    ])
    return st.one_of(normal, trailing, empty, malformed, st.builds(_ws_wrap, normal))

# Build the recursive strategy.
# value = scalar | obj | arr
# obj/arr contain values.

def _build_recursive():
    # We use st.recursive with a base of scalars and an extend function
    # that produces obj/arr given the recursive value strategy.
    def extend(value_strategy):
        obj = _make_obj(value_strategy, value_strategy)
        arr = _make_arr(value_strategy)
        return st.one_of(obj, arr)

    return st.recursive(_scalar_value, extend, max_leaves=60)

_value = _build_recursive()

# ---------------------------------------------------------------------------
# Top-level: json : value EOF
# ---------------------------------------------------------------------------

# Deep nesting stress: many nested objects/arrays (parser has no depth cap).
_deep_nesting = st.one_of(
    # deep arrays
    st.integers(min_value=1, max_value=200).map(lambda n: "[" * n + "]" * n),
    # deep objects
    st.integers(min_value=1, max_value=100).map(
        lambda n: "{" + '"a":{' * n + "1" + "}" * n + "}"
    ),
    # mixed deep
    st.integers(min_value=1, max_value=100).map(
        lambda n: ("[{\"k\":" * n) + "0" + ("}]" * n)
    ),
    # deep with trailing commas
    st.integers(min_value=1, max_value=50).map(
        lambda n: "[" * n + "1," + "]" * n
    ),
)

# Near-valid malformed top-level
_malformed_top = st.sampled_from([
    "", " ", "\x00", "\x00\x00", "null\x00", "{}x", "[]xyz", "1abc",
    "1 garbage", "true false", "tru", "fals", "nul", "{}{}", "[][]",
    "1 2", "01", "+1", ".5", "1.", "0x1F", "--", "1e", "1e+",
    "//comment\n1", "/*c*/1", "'x'", "{a:1}", "[1,2,]", "{\"a\":1,}",
    "{\"a\":1,\"a\":2}", "1e309", "-", "\"\\uD800\"",
    "\"unterminated", "\"\\", "\"\\u12\"",
    "{\"a\":\x00}", "[1,\x00,2]", "\x00{}", "[]\x00",
    "  \t\n\r1  \t\n\r", "{\"a\":1}\n", "[1]\n",
    "\xef\xbb\xbf{}",  # BOM
])

# A top-level value, possibly wrapped with whitespace/noise, possibly malformed.
_top_value = st.one_of(
    _value,
    _deep_nesting,
    _malformed_top,
    st.builds(_ws_wrap, _value),
    # value followed by trailing content (should be rejected)
    st.builds(lambda v: v + "x", _value),
    st.builds(lambda v: v + " ", _value),
    # value with leading garbage
    st.builds(lambda v: " " + v, _value),
)

# Bias toward objects with members (the stressed first-pass path).
# We build a weighted strategy emphasizing objects.
def _weighted():
    obj_heavy = st.one_of(
        _make_obj(_scalar_value, _scalar_value),
        st.builds(lambda v: v, _value),
    )
    return st.one_of(
        st.lists(obj_heavy, min_size=1, max_size=1).map(lambda l: l[0]),
        _top_value,
    )

# Final strategy: mix of everything, biased to objects.
strategy = st.one_of(
    # strong bias: objects with members
    st.builds(
        lambda k, v: "{" + k + ":" + v + "}",
        _string,
        _value,
    ),
    st.builds(
        lambda k1, v1, k2, v2: "{" + k1 + ":" + v1 + "," + k2 + ":" + v2 + "}",
        _string, _value, _string, _value,
    ),
    # duplicate keys
    st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        _string, _value, _value,
    ),
    # trailing comma object
    st.builds(
        lambda k, v: "{" + k + ":" + v + ",}",
        _string,
        _value,
    ),
    # general top-level
    _top_value,
    # deep nesting
    _deep_nesting,
    # malformed
    _malformed_top,
)
```