```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

HEX = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(HEX)] * 4)).map("".join)

def _unicode_escape():
    return _hex4().map(lambda h: "\\u" + h)

def _surrogate_escape():
    # lone high/low surrogates and valid pairs
    hi = st.integers(min_value=0xD800, max_value=0xDBFF)
    lo = st.integers(min_value=0xDC00, max_value=0xDFFF)
    single = st.sampled_from([0xD800, 0xDBFF, 0xDC00, 0xDFFF, 0xD834, 0xDD1E])
    return st.one_of(
        single.map(lambda c: "\\u%04x" % c),
        st.tuples(hi, lo).map(lambda t: "\\u%04x\\u%04x" % t),
    )

_SIMPLE_ESC = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _esc():
    return st.one_of(_SIMPLE_ESC, _unicode_escape(), _surrogate_escape())

# safe code points: anything except " \ and control 0x00-0x1F
def _safe_char():
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                      blacklist_categories=("Cs",),
                      blacklist_characters='"\\'),
        # control bytes (including NUL) are allowed by the harness
        st.integers(min_value=0, max_value=0x1F).map(chr),
        st.sampled_from(["\x00", "\x01", "\x1f", "\x7f"]),
    )

def _string_body():
    return st.lists(st.one_of(_safe_char(), _esc()), max_size=12).map("".join)

def _string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.integers(min_value=1, max_value=9).map(str),
    )

def _frac():
    return st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n))

def _exp():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=400).map(str),
    ).map("".join)

def _number():
    sign = st.sampled_from(["", "-"])
    mantissa = st.one_of(
        _int_part(),
        st.tuples(_int_part(), _frac()).map("".join),
    )
    exponent = st.one_of(st.just(""), _exp())
    return st.tuples(sign, mantissa, exponent).map("".join)

def _extreme_number():
    return st.one_of(
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e308"),
        st.just("1e-400"),
        st.just("1e400"),
        st.just("0"),
        st.just("-0"),
        st.just("0.0"),
        st.just("1e01"),
        st.just("1E+01"),
        st.just("123456789012345678901234567890"),
        st.just("-"),
    )

# ---------- malformed / near-valid ----------

def _malformed():
    return st.sampled_from([
        "[1,,2]", "[,]", "[,1]", "[1,2,,]", "{,}", "{,}",
        '{"a" 1}', '{"a":}', '{:1}', '{a:1}', "{'a':1}",
        '"unterminated', '{"a":"unterminated', '[1,2',
        '{"a":1', '}', ']', '[}', '{]',
        "1abc", "[]xyz", "1 garbage", "true false",
        "+1", ".5", "1.", "01", "0x1F", "1e", "1e+", "-.5",
        "//x", "/* */1", "'x'", "tru", "nul", "fals",
        "\x00", "\x00\x00", '"\x00"', '{"\x00":1}',
        "[1,2,]", '{"a":1,}', '{"a":1,"a":2}',
        "1e309", "1e400", "-",
        "\x01\x02\x03", "[\x00]", '{"k":"\x00\x01\x1f"}',
        " ", "\t\n\r", "", "[", "{", '"', "\\", "\\u", "\\u12",
        '{"a":1,,"b":2}', "[1 2]", '{"a"::1}',
    ])

# ---------- recursive structure ----------

_leaf = st.one_of(
    _string(),
    _number(),
    _extreme_number(),
    st.sampled_from(["true", "false", "null"]),
)

def _pair(value):
    return st.tuples(_string(), value).map(lambda t: t[0] + ":" + t[1])

def _obj(value):
    # bias toward objects with members; sometimes empty; sometimes trailing comma
    one = st.builds(lambda p: "{" + p + "}", _pair(value))
    many = st.lists(_pair(value), min_size=2, max_size=6).map(lambda ps: "{" + ",".join(ps) + "}")
    trailing = _pair(value).map(lambda p: "{" + p + ",}")
    empty = st.just("{}")
    dup = st.tuples(_string(), value).map(
        lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[1] + "}"
    )
    return st.one_of(empty, one, many, trailing, dup)

def _arr(value):
    one = st.builds(lambda v: "[" + v + "]", value)
    many = st.lists(value, min_size=2, max_size=6).map(lambda vs: "[" + ",".join(vs) + "]")
    trailing = value.map(lambda v: "[" + v + ",]")
    empty = st.just("[]")
    return st.one_of(empty, one, many, trailing)

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=40,
)

# ---------- top-level strategy ----------

def _deep_nesting():
    # deep object nesting stresses the first-pass memory measurement
    depth = st.integers(min_value=1, max_value=200)
    return depth.map(lambda d: "{" + '"a":{' * d + "0" + "}" * d + "}")

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  "])

def _with_ws(v):
    return st.tuples(_ws, v, _ws).map(lambda t: t[0] + t[1] + t[2])

# ---------- intensified near-crash mutations ----------
# The crashing signature was a UBSan null-pointer-offset in the parse
# function, triggered around empty containers, escaped strings containing
# control bytes, and trailing-comma arrays. Mutate structurally around
# those shapes to intensify the near-crash neighborhood.

# Observed divergences all have the shape of arrays nested inside arrays
# with trailing commas at every level, e.g. b'\r[[[1e309,],],]\t',
# b'[[[{},],],] ', b'[[["",],],]'. Build generators that reproduce and
# vary exactly that "trailing-comma array chain" shape.

_CRASH_SEEDS = [
    '[{},]',
    '[[],]',
    '[]',
    '{}',
    '[{}]',
    '{"a":{}}',
    '[{},\\r\\x1f\\u3D2f]',
    '1e400',
    '[\\r\\x1f\\u3D2f]',
    '{"":{}}',
]

def _crash_mutation():
    # structural mutations around the crashing seeds
    seed = st.sampled_from(_CRASH_SEEDS)
    pad = st.lists(
        st.sampled_from(["[", "]", "{", "}", ",", ":", '"', "\\", "\x00",
                         "\x01", "\x1f", " ", "\t", "\\r", "\\x1f", "\\u3D2f"]),
        min_size=0, max_size=8,
    ).map("".join)
    return st.tuples(seed, pad, pad).map(lambda t: t[1] + t[0] + t[2])

def _deep_empty_nesting():
    # deep nesting of empty containers, plus trailing commas at the leaves
    depth = st.integers(min_value=1, max_value=200)
    opener = st.sampled_from(["[", "{"])
    closer = st.sampled_from(["]", "}"])
    return st.tuples(depth, opener, closer).map(
        lambda t: t[1] * t[0] + "[]" + t[2] * t[0]
    )

def _trailing_comma_chain():
    # arrays/objects ending in trailing commas, nested
    depth = st.integers(min_value=1, max_value=30)
    inner = st.sampled_from(['[],', '{},', '[],', '{}'])
    return st.tuples(depth, inner).map(
        lambda t: "[" * t[0] + t[1] + "]" * t[0]
    )

# NEW: reproduce the exact divergence shape -- a chain of arrays where each
# level closes with a trailing comma, wrapping a scalar/container leaf.
def _trailing_comma_array_chain():
    depth = st.integers(min_value=1, max_value=40)
    leaf = st.one_of(
        st.just("1e309"),
        st.just("1e400"),
        st.just("{}"),
        st.just("[]"),
        st.just('""'),
        st.just("0"),
        st.just("null"),
        st.just("true"),
        st.just(""),
        st.just("\\r\\x1f\\u3D2f"),
    )
    # each nested level: "[" + inner + ",]"
    return st.tuples(depth, leaf).map(
        lambda t: "[" * t[0] + t[1] + ",]" * t[0]
    )

def _escaped_control_string():
    # strings with raw control bytes and escapes, mixed
    body = st.lists(
        st.sampled_from(["\x00", "\x01", "\x1f", "\\r", "\\x1f", "\\u3D2f",
                         "a", "\\u0000", "\\\\", "\\n"]),
        min_size=0, max_size=10,
    ).map("".join)
    return body.map(lambda s: '"' + s + '"')

def _intensified():
    return st.one_of(
        _crash_mutation(),
        _deep_empty_nesting(),
        _trailing_comma_chain(),
        _escaped_control_string(),
        # NEW: exact divergence shape plus whitespace wrappers
        _trailing_comma_array_chain(),
        _with_ws(_trailing_comma_array_chain()),
        # wrapped in arrays/objects to hit container edge cases
        _crash_mutation().map(lambda v: "[" + v + "]"),
        _crash_mutation().map(lambda v: "{" + v + "}"),
        _crash_mutation().map(lambda v: "[" + v + ",]"),
        _crash_mutation().map(lambda v: "{" + v + ",}"),
    )

strategy = st.one_of(
    _value,
    _value.map(lambda v: v + " "),
    _deep_nesting(),
    _malformed(),
    _with_ws(_value),
    _intensified(),
)
```