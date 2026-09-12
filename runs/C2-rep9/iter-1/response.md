```python
from hypothesis import strategies as st
import json

# ---------- leaf / scalar fragments ----------

# characters safe inside a JSON string (no raw control, no quote, no backslash)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\' + "".join(chr(c) for c in range(0x20)),
)

# raw control bytes / NUL that the parser handles faithfully
_control_char = st.sampled_from(
    [chr(c) for c in range(0x20)] + ["\x00", "\x7f"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4.map(lambda h: "\\u" + h),
    # surrogate escapes
    st.integers(min_value=0xD800, max_value=0xDBFF)
    .map(lambda n: "\\u%04x" % n),
    st.integers(min_value=0xDC00, max_value=0xDFFF)
    .map(lambda n: "\\u%04x" % n),
)

_string_body = st.one_of(
    _safe_char,
    _control_char,
    _escape,
)


@st.composite
def _json_string(draw):
    parts = draw(st.lists(_string_body, max_size=8))
    return '"' + "".join(parts) + '"'


# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_big_magnitude = st.sampled_from(
    ["1e309", "1e-309", "-1e309", "1e999", "-1e999", "1e308", "1e-308",
     "1e1000", "9e999", "1e+309", "0e999999", "123456789012345678901234567890"]
)


@st.composite
def _json_number(draw):
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind == 0:
        return draw(_big_magnitude)
    if kind == 1:
        # lone minus (accepted by parser)
        return "-"
    if kind == 2:
        # integer with optional sign
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(_int_digits)
        return sign + intpart
    if kind == 3:
        # decimal
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(_int_digits)
        frac = draw(st.text(alphabet="0123456789", min_size=1, max_size=6))
        return sign + intpart + "." + frac
    if kind == 4:
        # exponent
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(_int_digits)
        exp_sign = draw(st.sampled_from(["", "+", "-"]))
        exp_digits = draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        return sign + intpart + draw(st.sampled_from(["e", "E"])) + exp_sign + exp_digits
    if kind == 5:
        # decimal + exponent
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(_int_digits)
        frac = draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        exp_sign = draw(st.sampled_from(["", "+", "-"]))
        exp_digits = draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        return (sign + intpart + "." + frac
                + draw(st.sampled_from(["e", "E"])) + exp_sign + exp_digits)
    # malformed-ish number forms (near-valid-but-malformed)
    return draw(st.sampled_from([
        "+1", ".5", "1.", "01", "00", "0x1F", "-.5", "+.5",
        "1e", "1e+", "1e-", "-", "--1", "1..2", "0.", ".0",
    ]))


# ---------- malformed string fragments ----------

_malformed_string = st.sampled_from([
    '"unterminated',
    '"unterminated\\',
    '"bad\\x"',
    '"\\u12"',
    '"\\uZZZZ"',
    '"\\u12G4"',
    '"trailing\\',
    "'single'",
    '"' + "\x00" + 'unterminated',
])


# ---------- recursive JSON value ----------

_json_value = st.deferred(lambda: _json_value_impl())


@st.composite
def _json_value_impl(draw):
    return draw(_json_value_strategy())


def _json_value_strategy():
    scalars = st.one_of(
        _json_string(),
        _json_number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed_string,
    )

    @st.composite
    def _obj(draw):
        # bias toward objects with members
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "{}"
        pairs = [draw(_json_pair()) for _ in range(n)]
        body = ",".join(pairs)
        # occasionally add a single trailing comma (accepted by parser)
        if draw(st.booleans()):
            body = body + ","
        return "{" + body + "}"

    @st.composite
    def _arr(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "[]"
        elems = [draw(_json_value) for _ in range(n)]
        body = ",".join(elems)
        if draw(st.booleans()):
            body = body + ","
        return "[" + body + "]"

    return st.one_of(
        scalars,
        _obj(),
        _arr(),
        _malformed_value(),
    )


@st.composite
def _json_pair(draw):
    key = draw(_json_string())
    # occasionally duplicate-ish key
    val = draw(_json_value)
    if draw(st.booleans()):
        # missing colon variant
        return key + draw(st.sampled_from([" ", ""])) + val
    return key + ":" + val


@st.composite
def _malformed_value(draw):
    return draw(st.sampled_from([
        "{,}", "[,]", "[,1]", "[1,,2]", "{,}",
        "{\"a\":1,,}",
        "{a:1}", "{'a':1}",
        "[1 2]", "{\"a\" 1}",
        "1abc", "[]xyz", "1 garbage", "true false",
        "//comment\n1", "/*c*/1",
        "[1,2",
        "{\"a\":1",
        "\x00", "\x00\x00", "[\x00]", "{\"a\":\x00}",
        "\x01\x02\x03",
    ]))


# ---------- top-level strategy ----------

deep_value = st.recursive(
    _json_value_strategy(),
    lambda children: st.one_of(
        children.map(lambda v: "[" + v + "]"),
        children.map(lambda v: '{"k":' + v + "}"),
        st.lists(children, min_size=1, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]"),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "{" + ",".join('"k%d":%s' % (i, x) for i, x in enumerate(xs)) + "}"
        ),
    ),
    max_leaves=12,
)


@st.composite
def _strategy_impl(draw):
    style = draw(st.integers(min_value=0, max_value=10))
    if style == 0:
        # deep nesting
        return draw(deep_value)
    if style == 1:
        # raw NUL / control bytes
        return draw(st.sampled_from([
            "\x00", "[\x00]", "{\"a\":\x00}", "\x00\x00\x00",
            "[\x01,\x02,\x03]", "{\"k\":\"\x00\"}",
        ]))
    if style == 2:
        # extreme numbers
        return draw(_big_magnitude)
    if style == 3:
        # lone minus
        return "-"
    if style == 4:
        # duplicate keys
        return draw(st.sampled_from([
            '{"a":1,"a":2}', '{"a":1,"a":2,"a":3}',
            '{"x":{"x":{"x":1}}}',
        ]))
    if style == 5:
        # malformed
        return draw(_malformed_value())
    if style == 6:
        # leading whitespace variants
        inner = draw(_json_value)
        return draw(st.sampled_from([" ", "\t", "\n", "\r", "  "])) + inner
    if style == 7:
        # trailing content
        inner = draw(_json_value)
        return inner + draw(st.sampled_from(["x", " ", "garbage", "\x00"]))
    # general value
    return draw(_json_value)


strategy = _strategy_impl()
```