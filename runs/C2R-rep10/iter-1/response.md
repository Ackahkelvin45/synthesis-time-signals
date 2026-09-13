```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------- primitives

_hex = "0123456789abcdefABCDEF"

def _esc():
    simple = st.sampled_from(list('"\\/bfnrt'))
    uni = st.tuples(
        st.just("u"),
        st.text(alphabet=_hex, min_size=4, max_size=4),
    ).map(lambda t: "".join(t))
    return st.one_of(simple, uni)

# safe code points: anything except " \ and control chars
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) >= 0x20)

# raw control bytes (incl. NUL) allowed inside strings by parser reality
_control_char = st.sampled_from([chr(i) for i in range(0x00, 0x20)])

# a string body (without quotes) covering escapes, safe chars, control bytes
_str_body = st.one_of(
    _safe_char,
    _control_char,
    _esc(),
)

def _quoted():
    return st.lists(_str_body, max_size=8).map(lambda cs: '"' + "".join(cs) + '"')

# ---------------------------------------------------------------- numbers

def _digits(min_size=1, max_size=6):
    return st.text(alphabet="0123456789", min_size=min_size, max_size=max_size)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits(0, 6)).map(lambda t: t[0] + t[1]),
)

_frac = st.tuples(st.just("."), _digits(1, 6)).map(lambda t: t[0] + t[1])

_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    _digits(1, 4),
).map(lambda t: "".join(t))

# extreme magnitudes
_extreme = st.sampled_from([
    "1e309", "-1e309", "1e400", "1e-400", "1e1000",
    "1e308", "1.7976931348623157e308", "5e-324",
    "0e0", "0e999", "-0", "-0.0", "1E+999",
])

_number = st.one_of(
    _extreme,
    st.tuples(
        st.one_of(st.just(""), st.just("-")),
        _int_part,
        st.one_of(st.just(""), _frac),
        st.one_of(st.just(""), _exp),
    ).map(lambda t: "".join(t)),
)

# ---------------------------------------------------------------- malformed bits

_malformed_number = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "-", "--", "-.5", "1e", "1e+", "1..2",
])

_malformed_string = st.one_of(
    st.just('"unterminated'),
    st.just('"bad\\'),
    st.just('"\\u12"'),
    st.just('"\\x41"'),
    st.just("'single'"),
    st.just('"trailing\\"'),
)

_malformed_punct = st.sampled_from([
    ",", ",,", ":", "::", "{,}", "[,]", "[,1]", "[1,,2]", "{,}",
    "{:1}", '{"a" 1}', '{"a":}', "[1 2]", "]", "}", "garbage", "1abc",
])

# ---------------------------------------------------------------- recursive

def _build(draw, value):
    kind = draw(st.integers(min_value=0, max_value=9))

    if kind <= 1:
        return draw(_quoted())
    if kind <= 3:
        return draw(_number)
    if kind == 4:
        return draw(st.sampled_from(["true", "false", "null"]))
    if kind == 5:
        return draw(_malformed_number)
    if kind == 6:
        return draw(_malformed_string)
    if kind == 7:
        return draw(_malformed_punct)
    if kind == 8:
        # array
        n = draw(st.integers(min_value=0, max_value=6))
        items = [draw(value) for _ in range(n)]
        body = ",".join(items)
        trailing = draw(st.booleans())
        if trailing and items:
            body += ","
        return "[" + body + "]"
    # object (biased: objects with members)
    n = draw(st.integers(min_value=0, max_value=6))
    parts = []
    for _ in range(n):
        k = draw(_quoted())
        v = draw(value)
        parts.append(k + ":" + v)
    body = ",".join(parts)
    trailing = draw(st.booleans())
    if trailing and parts:
        body += ","
    return "{" + body + "}"

_value = st.recursive(
    st.one_of(
        _quoted(),
        _number,
        st.sampled_from(["true", "false", "null"]),
        _malformed_number,
        _malformed_string,
        _malformed_punct,
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=6).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(
            st.tuples(_quoted(), children).map(lambda t: t[0] + ":" + t[1]),
            max_size=6,
        ).map(lambda xs: "{" + ",".join(xs) + "}"),
    ),
    max_leaves=30,
)

# ---------------------------------------------------------------- top-level

def _deep(draw):
    depth = draw(st.integers(min_value=1, max_value=200))
    inner = draw(_value)
    open_c = draw(st.sampled_from(["[", "{"]))
    if open_c == "[":
        return "[" * depth + inner + "]" * depth
    # deep object nesting
    key = '"k":'
    return "{" * depth + key + inner + "}" * depth

def _top(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        return draw(st.sampled_from(["{}", "[]", "null", "true", "false", "0"]))
    if choice == 1:
        return draw(_deep())
    if choice == 2:
        # object with duplicate keys
        k = draw(_quoted())
        v1 = draw(_value)
        v2 = draw(_value)
        return "{" + k + ":" + v1 + "," + k + ":" + v2 + "}"
    if choice == 3:
        return draw(_malformed_punct)
    if choice == 4:
        return draw(_malformed_string)
    if choice == 5:
        return draw(_malformed_number)
    if choice == 6:
        # lone NUL or control bytes
        return draw(st.sampled_from(["\x00", "\x00\x00", "\x1f", "\x0b", "\x0c"]))
    if choice == 7:
        # trailing garbage after complete value
        v = draw(_value)
        g = draw(st.sampled_from(["x", "abc", " garbage", " true", "{}"]))
        return v + g
    if choice == 8:
        # string with NUL / control bytes inside
        inner = draw(st.lists(
            st.one_of(_control_char, _safe_char, _esc()), max_size=6
        ))
        return '"' + "".join(inner) + '"'
    return draw(_value)

strategy = _top()
```