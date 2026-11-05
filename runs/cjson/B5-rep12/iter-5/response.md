```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Primitive pieces
# ---------------------------------------------------------------------------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

# Fragments used inside JSON strings.
_str_frag = st.one_of(
    _safe_chars,
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04x" % n),
    st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda n: "\\u%04x" % n),
    st.integers(min_value=0, max_value=0x1F).map(chr),
    st.just("\x00"),
    st.integers(min_value=0x20, max_value=0x10FFFF).filter(
        lambda n: not (0xD800 <= n <= 0xDFFF)
    ).map(chr),
)

_string_body = st.lists(_str_frag, max_size=8).map("".join)

_string = st.builds(lambda b: '"' + b + '"', _string_body)

# Some near-malformed strings (unterminated, bad escapes, single quotes).
_bad_string = st.one_of(
    _string_body.map(lambda b: '"' + b),                 # unterminated
    st.just('"\\q"'),
    st.just('"\\u12"'),
    st.just("'abc'"),
    st.just('"\\ud800"'),                                # lone surrogate
    st.just('"\\udfff"'),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10 ** 6).map(str),
    st.integers(min_value=0, max_value=999).map(lambda n: "0" + str(n)),  # leading zeros
    st.just("0x10"),
    st.just("0XFF"),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10 ** 6).map(lambda n: "." + str(n)),
    st.just("."),                                        # trailing dot
)

_exp = st.one_of(
    st.just(""),
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.integers(min_value=0, max_value=999).map(lambda n: "E+" + str(n)),
    st.just("e309"),
    st.just("e-309"),
    st.just("e999999"),
)

_number = st.builds(
    lambda sign, i, f, e: sign + i + f + e,
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    _frac,
    _exp,
)

_bad_number = st.one_of(
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# ---------------------------------------------------------------------------
# Whitespace
# ---------------------------------------------------------------------------

_ws = st.lists(
    st.sampled_from([" ", "\t", "\n", "\r", "\x00"]),
    max_size=3,
).map("".join)

# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

_key = st.one_of(_string, _bad_string)

_pair = st.tuples(_key, _ws, st.just(":"), _ws).map("".join)

# We build pairs as (key:value) strings via a composite so value can be recursive.
@st.composite
def _obj(draw, value_st):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "{" + draw(_ws) + "}"
    pairs = []
    for _ in range(n):
        k = draw(_key)
        v = draw(value_st)
        pairs.append(k + draw(_ws) + ":" + draw(_ws) + v)
    sep = draw(st.sampled_from([",", ",", ",", ",,", ""]))
    body = sep.join(pairs)
    trailing = draw(st.one_of(st.just(""), st.just(",")))
    return "{" + draw(_ws) + body + trailing + draw(_ws) + "}"

@st.composite
def _arr(draw, value_st):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "[" + draw(_ws) + "]"
    vals = [draw(value_st) for _ in range(n)]
    sep = draw(st.sampled_from([",", ",", ",", ",,", ""]))
    body = sep.join(vals)
    trailing = draw(st.one_of(st.just(""), st.just(",")))
    return "[" + draw(_ws) + body + trailing + draw(_ws) + "]"

_leaf = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _bad_string,
    _bad_number,
)

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Deep nesting near the 1000-level limit
# ---------------------------------------------------------------------------

@st.composite
def _deep(draw):
    depth = draw(st.integers(min_value=990, max_value=1002))
    kind = draw(st.sampled_from(["arr", "obj"]))
    if kind == "arr":
        inner = draw(_leaf)
        return "[" * depth + inner + "]" * depth
    else:
        inner = draw(_leaf)
        return '{"k":' * depth + inner + "}" * depth

# ---------------------------------------------------------------------------
# Malformed / structural edge cases
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    st.just(""),
    st.just("{"),
    st.just("["),
    st.just("}"),
    st.just("]"),
    st.just('{"a" 1}'),          # missing colon
    st.just('{"a":1,}'),         # trailing comma obj
    st.just('[1,]'),             # trailing comma arr
    st.just('[1,,2]'),           # double comma
    st.just('{,}'),
    st.just('{"a":}'),
    st.just('"abc'),             # unterminated
    st.just('{a:1}'),            # unquoted key
    st.just("{'a':1}"),          # single quoted
    st.just("\ufeff"),           # lone BOM
    st.just("1abc"),             # trailing content
    st.just("1 2"),
    st.just("\x00"),
    st.just("null\x00"),
)

# BOM prefix option
_bom = st.one_of(st.just(""), st.just("\ufeff"))

# Trailing content (accepted; still interesting)
_trailer = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("abc"),
    st.just("\x00"),
    st.just(" 1 2 "),
)

@st.composite
def _full(draw):
    core = draw(st.one_of(_value, _deep(), _malformed))
    # Bias toward exercising parser structure: occasionally append extra junk.
    extra = draw(st.one_of(st.just(""), st.just("}"), st.just("]"), st.just(",")))
    return draw(_bom) + core + extra + draw(_trailer)

strategy = _full()
```