Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- primitive fragments ----------

_hex = st.characters(whitelist_categories=("Nd", "Ll", "Lu"), min_codepoint=48, max_codepoint=57) | st.sampled_from("abcdefABCDEF")

_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = _hex4.map(lambda h: "\\u" + h)

# surrogate escapes
_surrogate_esc = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD834\\uDD1E", "\\uD800\\uD800", "\\uDC00\\uDC00",
])

# safe code points (not " \\ or control)
_safe = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

# control bytes / NUL allowed inside strings (parser takes length)
_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_string_body_char = st.one_of(_safe, _control, _escapes, _unicode_esc, _surrogate_esc)

_string = st.lists(_string_body_char, max_size=8).map(lambda cs: '"' + "".join(cs) + '"')

# unterminated string (near-valid malformed)
_unterminated_string = st.lists(_string_body_char, min_size=0, max_size=6).map(
    lambda cs: '"' + "".join(cs)
)

# ---------- numbers ----------

_int_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_int = st.tuples(st.integers(1, 9).map(str), _int_digits).map(lambda t: t[0] + t[1])
_int_part = st.one_of(st.just("0"), _nonzero_int)

_frac = st.tuples(st.just("."), st.text("0123456789", min_size=1, max_size=6)).map(
    lambda t: t[0] + t[1]
)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text("0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

_number = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.none(), _frac),
    st.one_of(st.none(), _exp),
).map(lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or ""))

# extreme magnitudes / exponents including overflow
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-999", "1E+308", "1e308", "1e999999",
    "0e0", "-0", "-0.0", "1e01", "1E-01",
    "123456789012345678901234567890",
    "0.0000000000000000000000000001",
    "-1.7976931348623157e309",
    "1e-400", "9" * 40, "-" + "9" * 40,
])

# malformed number forms (parser rejects, but valuable)
_bad_number = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "-", "--1",
    "1..2", "1e", "1e+", "1.2.3", "+.5", "1e1.5",
])

# ---------- structure ----------

_ws = st.text(" \t\n\r", max_size=3)

_leaf = st.one_of(
    _string,
    _number,
    _extreme_number,
    st.sampled_from(["true", "false", "null"]),
)

# malformed scalar-ish tokens
_bad_leaf = st.one_of(
    _unterminated_string,
    _bad_number,
    st.sampled_from(["tru", "nul", "True", "NULL", "falsey", "'x'", "abc"]),
)


@st.composite
def _value(draw, depth):
    if depth <= 0:
        return draw(st.one_of(_leaf, _bad_leaf))
    choice = draw(st.integers(0, 9))
    if choice < 5:
        return draw(st.one_of(_leaf, _bad_leaf))
    elif choice < 8:
        return draw(_obj(depth - 1))
    else:
        return draw(_arr(depth - 1))


@st.composite
def _pair(draw, depth):
    key = draw(_string)
    colon = draw(st.sampled_from([":", ":", ":", ":", "", "::"]))
    val = draw(_value(depth))
    return key + draw(_ws) + colon + draw(_ws) + val


@st.composite
def _obj(draw, depth):
    n = draw(st.integers(0, 5))
    if n == 0:
        return "{}"
    pairs = [draw(_pair(depth)) for _ in range(n)]
    sep = draw(st.sampled_from([",", ",", ", ", ",\n"]))
    body = sep.join(pairs)
    trailing = draw(st.sampled_from(["", ",", ",,"]))
    return "{" + draw(_ws) + body + trailing + draw(_ws) + "}"


@st.composite
def _arr(draw, depth):
    n = draw(st.integers(0, 5))
    if n == 0:
        return "[]"
    vals = [draw(_value(depth)) for _ in range(n)]
    sep = draw(st.sampled_from([",", ",", ", ", ",\n"]))
    body = sep.join(vals)
    trailing = draw(st.sampled_from(["", ",", ",,"]))
    return "[" + draw(_ws) + body + trailing + draw(_ws) + "]"


@st.composite
def _deep_obj(draw):
    depth = draw(st.integers(1, 60))
    inner = draw(_value(0))
    s = inner
    for _ in range(depth):
        s = '{"k":' + s + "}"
    return s


@st.composite
def _deep_arr(draw):
    depth = draw(st.integers(1, 60))
    inner = draw(_value(0))
    s = inner
    for _ in range(depth):
        s = "[" + s + "]"
    return s


@st.composite
def _duplicate_keys(draw):
    n = draw(st.integers(2, 6))
    key = draw(st.one_of(st.just('"a"'), _string))
    vals = [draw(_value(0)) for _ in range(n)]
    body = ",".join(key + ":" + v for v in vals)
    return "{" + body + "}"


_malformed_top = st.sampled_from([
    "",
    " ",
    ",",
    "[,]",
    "[,1]",
    "[1,,2]",
    "{,}",
    "{:1}",
    '{"a"}',
    '{"a":}',
    '{"a" 1}',
    "{a:1}",
    "[1,2",
    '{"a":1',
    "1abc",
    "[]xyz",
    "1 garbage",
    "true false",
    "//x",
    "/* */1",
    "'x'",
    "\x00",
    "[\x00]",
    '{"a":"\x00"}',
    '"\\uD800"',
    '"\\uDC00"',
    "1e309",
    "-",
    "01",
    ".5",
    "+1",
    "1.",
    "1,",
    "[1,]",
    '{"a":1,}',
    '{"a":1,"a":2}',
    "\x00\x00\x00",
    "\x01\x02\x03",
])


@st.composite
def _top(draw):
    choice = draw(st.integers(0, 11))
    if choice == 0:
        return draw(_obj(3))
    elif choice == 1:
        return draw(_arr(3))
    elif choice == 2:
        return draw(_value(3))
    elif choice == 3:
        return draw(_deep_obj())
    elif choice == 4:
        return draw(_deep_arr())
    elif choice == 5:
        return draw(_duplicate_keys())
    elif choice == 6:
        return draw(_malformed_top)
    elif choice == 7:
        # objects with members biased
        return draw(_obj(2))
    elif choice == 8:
        return draw(_obj(4))
    elif choice == 9:
        return draw(_extreme_number)
    elif choice == 10:
        return draw(st.one_of(_bad_leaf, _unterminated_string))
    else:
        return draw(_value(2))


strategy = _top()
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 65.61,
  "region_coverage_pct": 64.87
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.