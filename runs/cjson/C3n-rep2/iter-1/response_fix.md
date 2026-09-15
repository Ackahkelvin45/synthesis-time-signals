```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

def _esc():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    uni = st.tuples(*([st.sampled_from(list(_hex))] * 4)).map(lambda t: "\\u" + "".join(t))
    return st.one_of(simple, uni)

def _safe_char():
    # SAFECODEPOINT: not " not \ not control
    return st.characters(blacklist_categories=("Cs",),
                         blacklist_characters='"\\').filter(
        lambda c: ord(c) >= 0x20)

def _raw_weird_char():
    # raw control / NUL bytes accepted by the parser inside strings
    return st.one_of(
        st.just("\x00"),
        st.sampled_from(["\t", "\n", "\r", "\x01", "\x1f", "\x7f"]),
        st.characters(blacklist_categories=("Cs",)).filter(
            lambda c: ord(c) < 0x20),
    )

def _string_body():
    return st.one_of(
        st.lists(st.one_of(_safe_char(), _esc(), _raw_weird_char()),
                 max_size=8).map("".join),
        st.just("\\ud800"),      # lone surrogate (rejected)
        st.just("\\udc00"),
        st.just("\\uD83D\\uDE00"),  # valid pair
        st.just("a\x00b"),
        st.just(""),
    )

def _string():
    return _string_body().map(lambda b: '"' + b + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.just("00"),
        st.just("01"),
        st.just("007"),
    )

def _exp():
    return st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=400).map(str),
    ).map(lambda t: t[0] + t[1] + t[2])

def _number():
    sign = st.sampled_from(["", "-"])
    frac = st.one_of(
        st.just(""),
        st.tuples(st.just("."), st.integers(min_value=0, max_value=10**6).map(str))
            .map(lambda t: t[0] + t[1]),
        st.just("."),
        st.just(".5"),
    )
    exp = st.one_of(st.just(""), _exp(), st.just("e309"), st.just("E+999"))
    core = st.tuples(sign, _int_part(), frac, exp).map(lambda t: "".join(t))
    weird = st.sampled_from([
        "0x10", "0X1f", "+1", "-", ".5", "NaN", "Infinity", "1e309",
        "1e-999", "1E+308", "1.", "-0", "1e400", "0x",
    ])
    return st.one_of(core, weird)

# ---------- recursive structure ----------

def _json_value(depth):
    if depth <= 0:
        return st.one_of(_string(), _number(),
                         st.sampled_from(["true", "false", "null"]))
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _obj(depth - 1),
        _arr(depth - 1),
    )

def _pair(depth):
    return st.tuples(_string(), st.just(":"), _json_value(depth)).map(
        lambda t: t[0] + t[1] + t[2])

def _obj(depth):
    body = st.one_of(
        st.just(""),
        st.lists(_pair(depth), min_size=1, max_size=4).map(
            lambda ps: ",".join(ps)),
        # duplicate keys
        st.lists(_string(), min_size=1, max_size=3).map(
            lambda ks: ",".join(k + ":1" for k in ks)),
        # malformed variants
        st.just(","),
        st.just('"a":,'),
        st.just('"a" 1'),
        st.just('"a":1,'),
    )
    return body.map(lambda b: "{" + b + "}")

def _arr(depth):
    body = st.one_of(
        st.just(""),
        st.lists(_json_value(depth), min_size=1, max_size=4).map(
            lambda vs: ",".join(vs)),
        st.just(","),
        st.just("1,"),
        st.just(",1"),
    )
    return body.map(lambda b: "[" + b + "]")

# ---------- depth-focused generators ----------

def _deep(depth):
    """Build exact nesting depth of arrays or objects (iterative)."""
    kind = st.sampled_from(["arr", "obj"])
    return st.tuples(kind, st.just(depth)).map(
        lambda t: _build_deep(t[0], t[1]))

def _build_deep(kind, depth):
    s = "0"
    for _ in range(depth):
        if kind == "arr":
            s = "[" + s + "]"
        else:
            s = '{"a":' + s + "}"
    return s

def _deep_near_limit():
    return st.sampled_from([995, 999, 1000, 1001, 1002, 1010]).flatmap(_deep)

# ---------- malformed / edge top-level ----------

def _malformed():
    return st.sampled_from([
        "", " ", "{", "}", "[", "]", ",", ":", "{,}", "[,]",
        '{"a":1,}', "[1,2,]", '{"a" 1}', "{'a':1}",
        '"unterminated', '"\\x"', '"\\u12"', "tru", "nul", "fals",
        "1 2", "1abc", "\xef\xbb\xbf1", "\x00", "1\x00",
        "01", "1.", "0x10", "1e309", "NaN", "Infinity", "+1", "-", ".5",
        '{"a":1,"a":2}', '{"a":1,"a":2,"a":3}',
        "[[[[[[[[[[0]]]]]]]]]]",
    ])

def _bom_prefix():
    return st.tuples(st.just("\xef\xbb\xbf"), _json_value(2)).map(
        lambda t: t[0] + t[1])

def _trailing():
    return st.tuples(_json_value(2), st.sampled_from(
        ["", "abc", "\x00", " 1 2", "xyz", "\n", "null"])).map(
        lambda t: t[0] + t[1])

# ---------- top-level strategy ----------

@st.composite
def _top(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        return draw(_malformed())
    if choice == 1:
        return draw(_deep_near_limit())
    if choice == 2:
        return draw(_bom_prefix())
    if choice == 3:
        return draw(_trailing())
    if choice == 4:
        return draw(_obj(3))
    if choice == 5:
        return draw(_arr(3))
    if choice == 6:
        return draw(_string())
    if choice == 7:
        return draw(_number())
    if choice == 8:
        return draw(st.sampled_from(["true", "false", "null"]))
    return draw(_json_value(4))

strategy = _top()
```