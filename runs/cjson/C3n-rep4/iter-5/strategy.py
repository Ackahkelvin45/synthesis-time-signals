import json
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Scalars and leaves
# ---------------------------------------------------------------------------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"',
    min_codepoint=0x20,
)

_raw_control = st.sampled_from(
    ["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x7f"]
)

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    kind = draw(st.sampled_from(["bmp", "high", "low", "pair"]))
    if kind == "bmp":
        cp = draw(st.integers(min_value=0x0000, max_value=0xD7FF))
        return "\\u%04x" % cp
    if kind == "high":
        cp = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        return "\\u%04x" % cp
    if kind == "low":
        cp = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x" % cp
    hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
    lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
    return "\\u%04x\\u%04x" % (hi, lo)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_extreme_numbers = st.sampled_from(
    [
        "1e309", "-1e309", "1e-309", "0e0", "0", "-0", "0.0", "-0.0",
        "1e1000", "1e-1000", "1E+308", "1e+308", "1e-308",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "0.0000000000000000000001",
        "1.7976931348623157e308",
        "9007199254740993",
        "0.1", "1e01", "1e-01",
    ]
)


@st.composite
def _number(draw):
    choice = draw(st.integers(min_value=0, max_value=5))
    if choice == 0:
        return draw(_extreme_numbers)
    if choice == 1:
        n = draw(st.integers(min_value=-(2 ** 63), max_value=2 ** 63))
        return str(n)
    if choice == 2:
        sign = draw(st.sampled_from(["", "-"]))
        intpart = draw(st.sampled_from(["0", "1", "42", "999999"]))
        frac = draw(st.text(alphabet="0123456789", min_size=1, max_size=8))
        return sign + intpart + "." + frac
    if choice == 3:
        sign = draw(st.sampled_from(["", "-"]))
        mant = draw(st.sampled_from(["1", "0", "3", "12"]))
        e = draw(st.sampled_from(["e", "E"]))
        esign = draw(st.sampled_from(["", "+", "-"]))
        exp = draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        return sign + mant + e + esign + exp
    if choice == 4:
        return draw(
            st.sampled_from(
                [
                    "+1", ".5", "-.5", "01", "007", "1.", "-", "+", "1e",
                    "1e+", "--1", "1..2", "0x", "1.2.3",
                ]
            )
        )
    return draw(st.sampled_from(["0x10", "0xFF", "-0x1", "0x0"]))


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

@st.composite
def _string_body(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    parts = []
    for _ in range(n):
        kind = draw(st.integers(min_value=0, max_value=3))
        if kind == 0:
            parts.append(draw(_safe_chars))
        elif kind == 1:
            parts.append(draw(_simple_escapes))
        elif kind == 2:
            parts.append(draw(_raw_control))
        else:
            parts.append(draw(_unicode_escape()))
    return "".join(parts)


@st.composite
def _string(draw):
    body = draw(_string_body())
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        return '"' + body
    return '"' + body + '"'


# ---------------------------------------------------------------------------
# Recursive structure: value / obj / arr
# ---------------------------------------------------------------------------

_MAX_DEPTH = 1000


def _depth_strategy(max_leaves):
    @st.composite
    def _value(draw):
        return draw(_scalar_or_container(max_leaves))

    return _value


@st.composite
def _scalar_or_container(draw, max_leaves):
    if max_leaves <= 0:
        return draw(_leaf())
    is_container = draw(st.booleans())
    if not is_container:
        return draw(_leaf())
    if draw(st.booleans()):
        return draw(_obj(max_leaves))
    return draw(_arr(max_leaves))


@st.composite
def _leaf(draw):
    choice = draw(st.integers(min_value=0, max_value=5))
    if choice == 0:
        return "null"
    if choice == 1:
        return "true"
    if choice == 2:
        return "false"
    if choice == 3:
        return draw(_number())
    if choice == 4:
        return draw(_string())
    return draw(st.sampled_from(["NaN", "Infinity", "-Infinity", "nul", "tru"]))


@st.composite
def _obj(draw, max_leaves):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "{}"
    pairs = []
    for _ in range(n):
        key = draw(_string())
        val = draw(_scalar_or_container(max_leaves - 1))
        pairs.append(key + ":" + val)
    body = ",".join(pairs)
    r = draw(st.integers(min_value=0, max_value=9))
    if r == 0:
        body = body + "," + body.split(":")[0] + ":" + draw(_leaf())
    elif r == 1:
        return "{" + body + ",}"
    elif r == 2:
        return "{" + body.replace(":", "", 1) + "}"
    return "{" + body + "}"


@st.composite
def _arr(draw, max_leaves):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "[]"
    items = [draw(_scalar_or_container(max_leaves - 1)) for _ in range(n)]
    body = ",".join(items)
    r = draw(st.integers(min_value=0, max_value=9))
    if r == 0:
        return "[" + body + ",]"
    if r == 1:
        return "[" + body + ",," + draw(_leaf()) + "]"
    return "[" + body + "]"


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

def _deep_nesting():
    depth = draw_depth()
    if depth % 2 == 0:
        return "[" * depth + "]" * depth
    return '{"a":' * depth + "null" + "}" * depth


@st.composite
def _draw_depth(draw):
    r = draw(st.integers(min_value=0, max_value=19))
    if r < 12:
        return draw(st.integers(min_value=990, max_value=1010))
    if r < 16:
        return draw(st.integers(min_value=900, max_value=1050))
    return draw(st.integers(min_value=0, max_value=50))


def draw_depth():
    return _draw_depth().example()


@st.composite
def _top_level(draw):
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        depth = draw(_draw_depth())
        if draw(st.booleans()):
            return "[" * depth + "]" * depth
        return '{"a":' * depth + "null" + "}" * depth
    if kind == 1:
        return "\ufeff" + draw(_scalar_or_container(2))
    if kind == 2:
        return draw(_scalar_or_container(2)) + draw(
            st.sampled_from(["abc", " 1 2", "\x00", " , ", "{}"])
        )
    if kind == 3:
        return draw(st.sampled_from(["\x00", "1\x00", "\x00{}", "[]\x00"]))
    if kind == 4:
        return ""
    if kind == 5:
        return draw(st.sampled_from([" ", "\t", "\n", "\r\n", "  \t "]))
    return draw(_scalar_or_container(3))


# ---------------------------------------------------------------------------
# cJSON_Compare coverage: emit scripts that parse and compare two values.
# ---------------------------------------------------------------------------

@st.composite
def _compare_value(draw, depth):
    if depth <= 0:
        return draw(_leaf())
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind <= 2:
        return draw(_leaf())
    if kind == 3:
        n = draw(st.integers(min_value=0, max_value=4))
        items = [draw(_compare_value(depth - 1)) for _ in range(n)]
        return "[" + ",".join(items) + "]"
    if kind == 4:
        n = draw(st.integers(min_value=0, max_value=4))
        pairs = []
        for _ in range(n):
            key = draw(_string())
            val = draw(_compare_value(depth - 1))
            pairs.append(key + ":" + val)
        if pairs and draw(st.integers(min_value=0, max_value=3)) == 0:
            pairs.append(pairs[0])
        return "{" + ",".join(pairs) + "}"
    if kind == 5:
        n = draw(st.integers(min_value=0, max_value=3))
        items = []
        for _ in range(n):
            k = draw(_string())
            v = draw(_compare_value(depth - 1))
            items.append("{" + k + ":" + v + "}")
        return "[" + ",".join(items) + "]"
    n = draw(st.integers(min_value=0, max_value=3))
    pairs = []
    for _ in range(n):
        key = draw(_string())
        val = draw(_compare_value(depth - 1))
        pairs.append(key + ":[" + val + "]")
    return "{" + ",".join(pairs) + "}"


@st.composite
def _compare_script(draw):
    a = draw(_compare_value(3))
    mode = draw(st.integers(min_value=0, max_value=4))
    if mode == 0:
        b = a
    elif mode == 1:
        b = draw(_compare_value(3))
    elif mode == 2:
        b = a
        if b.startswith("[") and b.endswith("]"):
            b = "[" + b[1:-1] + ("," if len(b) > 2 else "") + draw(_leaf()) + "]"
        elif b.startswith("{") and b.endswith("}"):
            inner = b[1:-1]
            extra = draw(_string()) + ":" + draw(_leaf())
            b = "{" + (inner + "," if inner else "") + extra + "}"
        else:
            b = draw(_leaf())
    elif mode == 3:
        s = draw(_string_body())
        b = '"' + s.swapcase() + '"'
        a = '"' + s + '"'
    else:
        b = draw(st.sampled_from(["[]", "{}", "null", "0", '""', "false"]))
    case_sensitive = draw(st.booleans())
    return json.dumps(
        {
            "compare": {
                "a": a,
                "b": b,
                "case_sensitive": case_sensitive,
            }
        }
    )


@st.composite
def _top_level_with_compare(draw):
    if draw(st.integers(min_value=0, max_value=3)) == 0:
        return draw(_compare_script())
    return draw(_top_level())


# ---------------------------------------------------------------------------
# cover_function: cJSON_Compare has 0% branch coverage.  Emit driver
# scripts that parse two values and compare them, exercising every type
# branch (invalid, null, bool, number, string, array, object), the
# equal/unequal paths, and the case-sensitive/case-insensitive paths.
# ---------------------------------------------------------------------------

@st.composite
def _compare_pair(draw):
    kind = draw(st.integers(min_value=0, max_value=11))
    if kind == 0:
        v = draw(st.sampled_from(["null", "true", "false", "0", "1", "-1",
                                  "3.14", '""', '"a"', '"A"']))
        return v, v, draw(st.booleans())
    if kind == 1:
        a = draw(st.sampled_from(["null", "true", "false", "0", "1", '"x"']))
        b = draw(st.sampled_from(["null", "true", "false", "0", "1", '"x"']))
        return a, b, draw(st.booleans())
    if kind == 2:
        n = draw(_number())
        return n, n, draw(st.booleans())
    if kind == 3:
        return draw(_number()), draw(_number()), draw(st.booleans())
    if kind == 4:
        s = draw(_string_body())
        other = s.swapcase() if draw(st.booleans()) else draw(_string_body())
        return ('"' + s + '"', '"' + other + '"', draw(st.booleans()))
    if kind == 5:
        v = draw(_compare_value(2))
        if not (v.startswith("[") and v.endswith("]")):
            v = "[1,2,3]"
        return v, v, draw(st.booleans())
    if kind == 6:
        a = draw(_compare_value(2))
        b = draw(_compare_value(2))
        if not (a.startswith("[") and a.endswith("]")):
            a = "[1]"
        if not (b.startswith("[") and b.endswith("]")):
            b = "[2]"
        return a, b, draw(st.booleans())
    if kind == 7:
        v = draw(_compare_value(2))
        if not (v.startswith("{") and v.endswith("}")):
            v = '{"a":1}'
        return v, v, draw(st.booleans())
    if kind == 8:
        a = draw(_compare_value(2))
        b = draw(_compare_value(2))
        if not (a.startswith("{") and a.endswith("}")):
            a = '{"a":1}'
        if not (b.startswith("{") and b.endswith("}")):
            b = '{"b":2}'
        return a, b, draw(st.booleans())
    if kind == 9:
        a = draw(st.sampled_from(["[1,2]", '{"a":1}', "1", '"s"', "null", "true"]))
        b = draw(st.sampled_from(["[1,2]", '{"a":1}', "1", '"s"', "null", "true"]))
        return a, b, draw(st.booleans())
    if kind == 10:
        key = draw(_string())
        inner = draw(_compare_value(1))
        v = "{" + key + ":[" + inner + "]}"
        return v, v, draw(st.booleans())
    key = draw(_string())
    inner = draw(_compare_value(1))
    a = "{" + key + ":[" + inner + "]}"
    b = "[" + inner + "]"
    return a, b, draw(st.booleans())


@st.composite
def _compare_driver(draw):
    a, b, case_sensitive = draw(_compare_pair())
    return json.dumps(
        {
            "compare": {
                "a": a,
                "b": b,
                "case_sensitive": case_sensitive,
            }
        }
    )


@st.composite
def _top_level_with_compare_and_driver(draw):
    r = draw(st.integers(min_value=0, max_value=9))
    if r < 6:
        return draw(_compare_driver())
    if r < 8:
        return draw(_compare_script())
    return draw(_top_level())


strategy = _top_level_with_compare_and_driver()