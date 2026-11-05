```python
import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Safe, printable characters useful inside JSON strings (no raw NUL, no
# unescaped quote/backslash/control chars unless we deliberately build them).
_safe_chars = st.characters(
    whitelist_categories=("L", "N", "P", "S", "Zs"),
    blacklist_characters='"\x00',
)

_hex = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        # ordinary \uXXXX
        h = "".join(draw(_hex) for _ in range(4))
        return "\\u" + h
    if kind == 1:
        # high surrogate (D800-DBFF)
        h = "D" + draw(st.sampled_from("89AB")) + "".join(draw(_hex) for _ in range(2))
        return "\\u" + h
    if kind == 2:
        # low surrogate (DC00-DFFF)
        h = "D" + draw(st.sampled_from("CDEF")) + "".join(draw(_hex) for _ in range(2))
        return "\\u" + h
    # surrogate pair
    hi = "D" + draw(st.sampled_from("89AB")) + "".join(draw(_hex) for _ in range(2))
    lo = "D" + draw(st.sampled_from("CDEF")) + "".join(draw(_hex) for _ in range(2))
    return "\\u" + hi + "\\u" + lo


@st.composite
def _string_body(draw):
    n = draw(st.integers(min_value=0, max_value=12))
    parts = []
    for _ in range(n):
        c = draw(st.integers(min_value=0, max_value=6))
        if c <= 2:
            parts.append(draw(_safe_chars))
        elif c == 3:
            parts.append(draw(st.sampled_from(['\\"', "\\\\", "\\/", "\\b",
                                               "\\f", "\\n", "\\r", "\\t"])))
        elif c == 4:
            parts.append(draw(_unicode_escape()))
        elif c == 5:
            # \u0000 escape (embedded NUL as text) and other control escapes
            parts.append(draw(st.sampled_from(["\\u0000", "\\u0001", "\\u001f",
                                               "\\u007f"])))
        else:
            parts.append(draw(st.sampled_from(["é", "ü", "€", "😀", " ", "\t"])))
    return "".join(parts)


@st.composite
def _json_string(draw):
    return '"' + draw(_string_body()) + '"'


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

@st.composite
def _number(draw):
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        return "0"
    if kind == 1:
        return "-0"
    if kind == 2:
        return str(draw(st.integers(min_value=-(10 ** 18), max_value=10 ** 18)))
    if kind == 3:
        # big integers
        digits = "".join(draw(st.sampled_from("0123456789"))
                         for _ in range(draw(st.integers(1, 40))))
        digits = digits.lstrip("0") or "0"
        sign = draw(st.sampled_from(["", "-"]))
        return sign + digits
    if kind == 4:
        # decimal
        ip = draw(st.integers(min_value=0, max_value=10 ** 6))
        fp = draw(st.integers(min_value=0, max_value=10 ** 9))
        return "%d.%d" % (ip, fp)
    if kind == 5:
        # exponent
        base = draw(st.sampled_from(["1", "0", "12", "3.5", "-7", "2.25"]))
        sign = draw(st.sampled_from(["", "+", "-"]))
        exp = draw(st.integers(min_value=0, max_value=400))
        e = draw(st.sampled_from(["e", "E"]))
        return base + e + sign + str(exp)
    if kind == 6:
        # overflow-ish
        return draw(st.sampled_from(["1e309", "-1e309", "1e400", "1e-400",
                                     "9e999", "1.0e308", "1.7976931348623159e308"]))
    if kind == 7:
        # near-valid malformed numbers
        return draw(st.sampled_from(["+1", ".5", "-.5", "1.", "01", "-01",
                                     "00", "1e", "1e+", "1.2.3", "--1", "-"]))
    if kind == 8:
        # exponent with leading zeros
        return draw(st.sampled_from(["1e01", "1e007", "0e0", "1E+00", "5e-0"]))
    # tiny / subnormal
    return draw(st.sampled_from(["1e-323", "5e-324", "2.2250738585072014e-308"]))


# ---------------------------------------------------------------------------
# Recursive structure
# ---------------------------------------------------------------------------

def _join(parts):
    return "".join(parts)


@st.composite
def _pair(draw, value):
    return draw(_json_string()) + ":" + draw(value)


def _obj_strategy(value):
    @st.composite
    def _obj(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        if n == 0:
            return "{}"
        pairs = [draw(_pair(value)) for _ in range(n)]
        # occasionally inject duplicate keys / malformed separators
        mode = draw(st.integers(min_value=0, max_value=6))
        if mode == 0 and n >= 1:
            # duplicate key
            pairs = pairs + [pairs[0]]
        if mode == 1:
            return "{" + ",".join(pairs) + ",}"
        if mode == 2:
            return "{" + ",,".join(pairs) + "}"
        if mode == 3:
            # missing colon
            return "{" + draw(_json_string()) + draw(value) + "}"
        if mode == 4:
            return "{" + ",".join(pairs)
        return "{" + ",".join(pairs) + "}"
    return _obj()


def _arr_strategy(value):
    @st.composite
    def _arr(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        if n == 0:
            return "[]"
        elems = [draw(value) for _ in range(n)]
        mode = draw(st.integers(min_value=0, max_value=5))
        if mode == 0:
            return "[" + ",".join(elems) + ",]"
        if mode == 1:
            return "[" + ",,".join(elems) + "]"
        if mode == 2:
            return "[" + ",".join(elems)
        return "[" + ",".join(elems) + "]"
    return _arr()


def _make_value():
    # leaf strategies (no recursion)
    leaves = st.one_of(
        _json_string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )

    def extend(value):
        return st.one_of(_obj_strategy(value), _arr_strategy(value))

    return st.recursive(leaves, extend, max_leaves=40)


# ---------------------------------------------------------------------------
# Deep nesting near the 2048 cap
# ---------------------------------------------------------------------------

@st.composite
def _deep_nesting(draw):
    depth = draw(st.integers(min_value=1, max_value=2100))
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return "[" * depth + "]" * depth
    if kind == 1:
        return "[" * depth + "0" + "]" * depth
    if kind == 2:
        return '{"a":' * depth + "null" + "}" * depth
    return "[" * depth + '"x"' + "]" * depth


# ---------------------------------------------------------------------------
# Malformed / near-valid top-level inputs
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    st.sampled_from([
        "", " ", "\n", ",", ":", "{}", "[]", "true", "false", "null",
        "{", "}", "[", "]", '"', '""', '{"a"}', '{"a":}',
        '["a",]', '[,]', '{"a":1,}', '[1,,2]', '{"a":1,"b"}',
        '{"a" 1}', 'tru', 'fals', 'nul', 'True', 'NULL',
        '{"a":1}garbage', '[]xyz', '1abc', '1 garbage', '-', '-.', '+1',
        '.5', '01', '1.', '1e309', '{"k":0,"k":1}',
        '"unterminated', '"\\', '"\\u12"', '"\\uZZZZ"',
        '"\\uD800"', '"\\uDC00"', '"\\uD800\\uDC00"',
        '"a\x01b"', '"a\x1fb"', '"\\u0000"',
        '{"a":1}{"b":2}', '[1][2]',
    ]),
    st.builds(lambda s: s, _json_string()),
    st.builds(lambda n: n, _number()),
)


# ---------------------------------------------------------------------------
# Public strategy
# ---------------------------------------------------------------------------

_value = _make_value()

_body = st.one_of(
    # well-formed-ish values
    _value,
    # deeply nested near the cap
    _deep_nesting(),
    # malformed / near-valid
    _malformed,
    # trailing content after a complete value (accepted by parser)
    st.tuples(_value, st.sampled_from(["", " ", "x", "garbage", "{}", "[]"]))
    .map(lambda t: t[0] + t[1]),
)


@st.composite
def _top(draw):
    s = draw(_body)
    # guarantee no raw NUL byte anywhere (parser is NUL-terminated)
    if "\x00" in s:
        s = s.replace("\x00", "\\u0000")
    return s


strategy = _top()
```