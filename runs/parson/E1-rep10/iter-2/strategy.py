from hypothesis import strategies as st
import json

# ----------------------------------------------------------------------------
# Basic scalar pieces
# ----------------------------------------------------------------------------

# Safe printable-ish characters for string bodies (no raw NUL, no quotes/backslash).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\x00"\\',
)

# Control characters (0x01-0x1F) that are NOT raw NUL, plus tab/newline etc.
_control_chars = st.characters(
    min_codepoint=1,
    max_codepoint=0x1F,
)

# A variety of escape sequences.
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes explicitly.
_surrogate_escape = st.sampled_from(
    ["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uD83D\\uDE00"]
)

_simple_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_escape = st.one_of(_simple_escapes, _unicode_escape, _surrogate_escape)

# A single string-body token: either a safe char, a control char, or an escape.
_string_token = st.one_of(
    _safe_chars,
    _control_chars,
    _escape,
)

# A raw string body (no surrounding quotes).
_string_body = st.lists(_string_token, max_size=12).map("".join)

# A JSON string literal.
_json_string = _string_body.map(lambda b: '"' + b + '"')

# Include the empty-string edge case.
_json_string = st.one_of(_json_string, st.just('""'))


# ----------------------------------------------------------------------------
# Numbers
# ----------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=1, max_value=9).map(str),
)

_frac_part = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
    st.just(".0"),
)

_exp_part = st.one_of(
    st.just(""),
    st.sampled_from(
        ["e0", "e1", "e309", "e-309", "E+10", "e-1", "e999", "e-999",
         "e308", "e+308", "e-308", "E01", "e00"]
    ),
)

_sign = st.one_of(st.just(""), st.just("-"))


def _make_number(sign, ip, fp, ep):
    return sign + ip + fp + ep


_json_number = st.tuples(_sign, _int_part, _frac_part, _exp_part).map(
    lambda t: _make_number(*t)
)

# Explicit extreme / edge numbers.
_extreme_numbers = st.sampled_from(
    [
        "0", "-0", "1", "-1", "1e309", "-1e309", "1e-309", "1E+308",
        "123456789012345678901234567890",
        "0.000000000000000000000001",
        "1.7976931348623157e308",
        "5e-324",
        "-",
        "-.",
        "+1",
        ".5",
        "01",
        "00",
        "1.",
    ]
)

_json_number = st.one_of(_json_number, _extreme_numbers)


# ----------------------------------------------------------------------------
# Near-valid-but-malformed snippets (leaf-level)
# ----------------------------------------------------------------------------

_malformed_leaf = st.sampled_from(
    [
        '"unterminated',
        '"bad\\x"',
        '"\\u12"',
        '"\\uZZZZ"',
        "tru",
        "fals",
        "nul",
        "TRUE",
        "01",
        ".5",
        "+1",
        "1.",
        "--1",
        "1e",
        "1e+",
        '"',
        "",
    ]
)


# ----------------------------------------------------------------------------
# Recursive structure
# ----------------------------------------------------------------------------

# Leaf values (non-recursive): strings, numbers, literals, malformed bits.
_leaf_value = st.one_of(
    _json_string,
    _json_number,
    st.sampled_from(["true", "false", "null"]),
    _malformed_leaf,
)

# Whitespace (optional, used sparingly).
_ws = st.sampled_from(["", " ", "\n", "\t", "\r\n"])

# A pair: STRING ':' value  (value filled in by recursion).
_pair_key = _json_string


def _make_pair(key, ws1, ws2, value):
    return key + ws1 + ":" + ws2 + value


# Recursive value strategy.
# depth target: concentrate near 2048 but keep generation feasible.
def _value_strategy(draw, depth):
    # Choose a leaf with high probability, recurse otherwise.
    return draw(_leaf_value)


# Use st.recursive for obj/arr.  We can't easily bound depth near 2048 with
# st.recursive alone, so we build a wrapper that occasionally forces deep nesting.

def _build_value(depth, children):
    """children: a strategy for a nested value."""
    leaf = _leaf_value

    # Object with unique-ish keys (duplicates allowed sometimes).
    def obj_strat(d):
        # 0..4 pairs
        n = d.draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "{}"
        parts = []
        for _ in range(n):
            key = d.draw(_pair_key)
            val = d.draw(children)
            parts.append(key + ":" + val)
        joined = ",".join(parts)
        return "{" + joined + "}"

    def arr_strat(d):
        n = d.draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        parts = [d.draw(children) for _ in range(n)]
        return "[" + ",".join(parts) + "]"

    return st.one_of(
        leaf,
        st.builds(lambda d: obj_strat(d), st.just(None)) if False else
        st.deferred(lambda: _object_value(children)),
        st.deferred(lambda: _array_value(children)),
    )


def _object_value(children):
    @st.composite
    def _obj(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "{}"
        parts = []
        for _ in range(n):
            key = draw(_pair_key)
            val = draw(children)
            parts.append(key + ":" + val)
        return "{" + ",".join(parts) + "}"
    return _obj()


def _array_value(children):
    @st.composite
    def _arr(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        parts = [draw(children) for _ in range(n)]
        return "[" + ",".join(parts) + "]"
    return _arr()


# Base recursive strategy: leaf or (obj/arr containing recursive value).
_recursive_value = st.recursive(
    st.one_of(_leaf_value),
    lambda children: st.one_of(
        _object_value(children),
        _array_value(children),
    ),
    max_leaves=40,
)


# ----------------------------------------------------------------------------
# Deep nesting near the 2048 limit
# ----------------------------------------------------------------------------

def _deep_nesting(draw):
    depth = draw(st.integers(min_value=1800, max_value=2050))
    # Choose brackets or braces.
    kind = draw(st.sampled_from(["arr", "obj"]))
    if kind == "arr":
        open_c, close_c = "[", "]"
        inner = draw(st.one_of(_leaf_value, st.just("0")))
        return open_c * depth + inner + close_c * depth
    else:
        open_c, close_c = "{", "}"
        key = draw(_pair_key)
        inner = draw(st.one_of(_leaf_value, st.just("0")))
        # nested objects: {"k":{"k":...0...}}
        prefix = (key + ":") * depth
        return "{" * depth + prefix + inner + close_c * depth


_deep_value = st.composite(_deep_nesting)


# ----------------------------------------------------------------------------
# Malformed structural variants (near-valid)
# ----------------------------------------------------------------------------

_malformed_structural = st.sampled_from(
    [
        '{"a":1,}',
        '[1,2,]',
        '[1,,2]',
        '{"a" 1}',
        '{"a":}',
        '{:1}',
        '[,]',
        '{,}',
        '{"a":1 "b":2}',
        '{"a":1,"a":2}',
        '[1 2]',
        '{"a":1',
        '[1,2',
        '{"a":1}}',
        '[1,2]]',
        '{"a":1}garbage',
        '[]xyz',
        '1abc',
        '1 garbage',
        'null trailing',
        'truefalse',
        '{"a":1,"b":2,"a":3}',
        '{"":0}',
        '{"k":0,"k":1}',
    ]
)


# ----------------------------------------------------------------------------
# Top-level strategy
# ----------------------------------------------------------------------------

_top_value = st.one_of(
    _recursive_value,
    _deep_value,
    _malformed_structural,
    _leaf_value,
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("0"),
    st.just("-"),
    st.just(""),
)

# Occasionally add trailing content (parser ignores it).
_trailing = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\n", "garbage", "xyz", "1", "[]", "null", "/*x*/"]),
)

# Occasionally add leading/trailing whitespace.
_lead_ws = st.sampled_from(["", " ", "\n", "\t", "\r\n"])


def _compose(lead, value, trail):
    return lead + value + trail


strategy = st.tuples(_lead_ws, _top_value, _trailing).map(
    lambda t: _compose(*t)
)