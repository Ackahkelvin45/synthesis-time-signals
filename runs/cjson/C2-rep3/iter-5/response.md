```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters that are safe inside a JSON string per the grammar.
SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\",
)

# Raw control / NUL bytes (the parser accepts these inside strings).
RAW_CONTROL = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\t", "\n", "\x0b", "\x0c", "\r", "\x1f", "\x7f"]
)

HEX = "0123456789abcdefABCDEF"
hex_char = st.sampled_from(list(HEX))


@st.composite
def _unicode_escape(draw):
    kind = draw(st.integers(min_value=0, max_value=5))
    if kind == 0:
        # lone high surrogate
        return "\\ud800"
    if kind == 1:
        # lone low surrogate
        return "\\udc00"
    if kind == 2:
        # valid surrogate pair
        hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x\\u%04x" % (hi, lo)
    if kind == 3:
        # reversed surrogate pair (malformed)
        return "\\udc00\\ud800"
    if kind == 4:
        # arbitrary 4 hex digits
        return "\\u" + "".join(draw(hex_char) for _ in range(4))
    # uppercase hex escape
    return "\\u" + "".join(draw(st.sampled_from(list("0123456789ABCDEF"))) for _ in range(4))


@st.composite
def _string_body(draw):
    n = draw(st.integers(min_value=0, max_value=12))
    parts = []
    for _ in range(n):
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 4:
            parts.append(draw(SAFE))
        elif choice == 5:
            parts.append(draw(RAW_CONTROL))
        elif choice == 6:
            parts.append(draw(_unicode_escape()))
        elif choice == 7:
            parts.append(draw(st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])))
        elif choice == 8:
            # invalid escape
            parts.append(draw(st.sampled_from(["\\x", "\\'", "\\ ", "\\u12", "\\uZZZZ"])))
        else:
            parts.append(draw(st.sampled_from(["\u00e9", "\u2603", "\U0001f600", "\u2028"])))
    return "".join(parts)


@st.composite
def json_string(draw):
    body = draw(_string_body())
    if draw(st.booleans()):
        return '"' + body + '"'
    # unterminated string
    return '"' + body


# ---------------------------------------------------------------------------
# Numbers (including deviations and extreme magnitudes)
# ---------------------------------------------------------------------------

@st.composite
def json_number(draw):
    kind = draw(st.integers(min_value=0, max_value=9))

    if kind == 0:
        # plain integer
        return str(draw(st.integers(min_value=-10**6, max_value=10**6)))
    if kind == 1:
        # leading zeros (accepted deviation)
        return "0" + str(draw(st.integers(min_value=0, max_value=999)))
    if kind == 2:
        # trailing dot (accepted deviation)
        return str(draw(st.integers(min_value=0, max_value=999))) + "."
    if kind == 3:
        # hex number (accepted deviation)
        return draw(st.sampled_from(["0x10", "0XFF", "0xdeadBEEF", "-0x1", "0x0"]))
    if kind == 4:
        # extreme exponents / overflow
        mant = draw(st.sampled_from(["1", "9", "0", "-1", "123456789"]))
        exp = draw(st.sampled_from(["309", "308", "400", "1000", "-400", "99999999", "01"]))
        sign = draw(st.sampled_from(["", "+", "-"]))
        return mant + "e" + sign + exp
    if kind == 5:
        # lone minus (rejected)
        return "-"
    if kind == 6:
        # leading plus (rejected)
        return "+" + str(draw(st.integers(min_value=0, max_value=99)))
    if kind == 7:
        # bare .5 (rejected)
        return "." + str(draw(st.integers(min_value=0, max_value=99)))
    if kind == 8:
        # NaN / Infinity words (rejected)
        return draw(st.sampled_from(["NaN", "-NaN", "Infinity", "-Infinity"]))
    # normal float
    return str(draw(st.floats(allow_nan=False, allow_infinity=False))) if draw(st.booleans()) else (
        str(draw(st.integers(min_value=-1000, max_value=1000)))
        + "."
        + str(draw(st.integers(min_value=0, max_value=999)))
    )


# ---------------------------------------------------------------------------
# Whitespace and malformed separators
# ---------------------------------------------------------------------------

WS = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \n\t "])

MALFORMED_SEP = st.sampled_from([",,", ", ,", ":", ",", "::", "}", "]", ""])


# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

def _depth_capped_values():
    """Return a recursive strategy for JSON values with controlled depth."""
    # leaf values
    leaves = st.one_of(
        json_string(),
        json_number(),
        st.sampled_from(["true", "false", "null", "TRUE", "False", "NULL", "nul"]),
    )

    def extend(children):
        # children is a strategy producing JSON value strings
        arr = st.lists(children, min_size=0, max_size=4).map(
            lambda xs: "[" + ",".join(xs) + "]"
        )
        # arrays with odd separators / trailing comma variants
        arr_bad = st.lists(children, min_size=1, max_size=3).map(
            lambda xs: "[" + ",".join(xs) + ",]"
        )
        arr_ws = st.lists(children, min_size=0, max_size=3).map(
            lambda xs: "[" + " , ".join(xs) + "]"
        )

        @st.composite
        def _obj(draw):
            pairs = draw(st.lists(children, min_size=0, max_size=4))
            keys = draw(st.lists(json_string(), min_size=len(pairs), max_size=len(pairs)))
            parts = []
            for k, v in zip(keys, pairs):
                sep = draw(st.sampled_from([":", " : ", ":", "::"]))
                parts.append(k + sep + v)
            body = ",".join(parts)
            if draw(st.booleans()):
                # duplicate keys
                if parts:
                    body = body + "," + parts[0]
            return "{" + body + "}"

        @st.composite
        def _obj_bad(draw):
            pairs = draw(st.lists(children, min_size=1, max_size=3))
            keys = draw(st.lists(json_string(), min_size=len(pairs), max_size=len(pairs)))
            parts = []
            for k, v in zip(keys, pairs):
                parts.append(k + ":" + v)
            body = ",".join(parts)
            ending = draw(st.sampled_from([",}", ", }", "}", "]", ""]))
            return "{" + body + ending

        # Explicitly exercise the `pair` production (key : value) with
        # well-formed and near-valid pair spellings.
        @st.composite
        def _pair(draw):
            key = draw(json_string())
            val = draw(children)
            sep = draw(st.sampled_from([":", " : ", ":", ": ", " :"]))
            return key + sep + val

        @st.composite
        def _obj_pairs(draw):
            n = draw(st.integers(min_value=1, max_value=4))
            parts = [draw(_pair()) for _ in range(n)]
            return "{" + ",".join(parts) + "}"

        return st.one_of(arr, arr_bad, arr_ws, _obj(), _obj_bad(), _pair(), _obj_pairs())

    return st.recursive(leaves, extend, max_leaves=40)


_json_value = _depth_capped_values()


# ---------------------------------------------------------------------------
# Deep nesting near the 1000-level limit
# ---------------------------------------------------------------------------

@st.composite
def deep_nesting(draw):
    depth = draw(
        st.one_of(
            st.just(0),
            st.just(1),
            st.just(2),
            st.integers(min_value=700, max_value=950),
            st.integers(min_value=700, max_value=950),
        )
    )
    open_ch = draw(st.sampled_from(["[", "{"]))
    if open_ch == "[":
        return "[" * depth + "]" * depth
    # objects require keys
    if depth == 0:
        return "{}"
    return "{" + '"k":' * depth + "null" + "}" * depth


# ---------------------------------------------------------------------------
# Near-valid-but-malformed top-level inputs
# ---------------------------------------------------------------------------

FRAGMENTS = st.sampled_from(
    [
        "{,}",
        "[,]",
        "[1,,2]",
        '{"a" 1}',
        '{"a":}',
        "{:1}",
        '{"a":1,}',
        "[1 2]",
        "{'a':1}",
        "{a:1}",
        "'single'",
        '"unterminated',
        "\\",
        "]",
        "}",
        "",
        " ",
        "\x00",
        "1\x00",
        '"a\x00b"',
        "\ufeff1",
        "\ufeff{}",
        "1abc",
        "1 2",
        "01",
        "1.",
        "0x10",
        "-",
        "+1",
        ".5",
        "NaN",
        "Infinity",
        '"\\ud800"',
        '"\\udc00"',
        '"\\u12"',
        '{"a":1,"a":2}',
        # pair-focused fragments
        '"a":1',
        '"a" : 1',
        '"a"::1',
        '"a":',
        ':1',
        '"k":"v"',
    ]
)


@st.composite
def malformed(draw):
    n = draw(st.integers(min_value=1, max_value=3))
    return "".join(draw(FRAGMENTS) for _ in range(n))


# ---------------------------------------------------------------------------
# Explicit `pair` production (key : value), both bare and inside an object
# ---------------------------------------------------------------------------

@st.composite
def pair_production(draw):
    key = draw(json_string())
    val = draw(_json_value)
    sep = draw(st.sampled_from([":", " : ", ": ", " :", "::", ":"]))
    pair = key + sep + val
    if draw(st.booleans()):
        return pair
    n = draw(st.integers(min_value=1, max_value=3))
    extra = [draw(pair_production_inner()) for _ in range(n)]
    return "{" + ",".join([pair] + extra) + "}"


@st.composite
def pair_production_inner(draw):
    key = draw(json_string())
    val = draw(_json_value)
    sep = draw(st.sampled_from([":", " : ", ": ", " :", "::", ":"]))
    return key + sep + val


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

@st.composite
def _top(draw):
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        return draw(_json_value)
    if kind == 1:
        return draw(deep_nesting())
    if kind == 2:
        return draw(malformed())
    if kind == 3:
        # value with trailing junk
        return draw(_json_value) + draw(st.sampled_from(["abc", " 1 2", "\x00", "}", "]"]))
    if kind == 4:
        # BOM prefixed
        return "\ufeff" + draw(_json_value)
    if kind == 5:
        # whitespace padded
        return draw(WS) + draw(_json_value) + draw(WS)
    if kind == 6:
        # raw NUL inside a string value
        body = draw(_string_body())
        return '"' + body + "\x00" + body + '"'
    if kind == 7:
        # explicit pair production: key : value, bare and inside an object
        key = draw(json_string())
        val = draw(_json_value)
        sep = draw(st.sampled_from([":", " : ", ": ", " :", "::"]))
        pair = key + sep + val
        if draw(st.booleans()):
            return pair
        return "{" + pair + "}"
    if kind == 8:
        # dedicated pair production (bare pair or object of pairs)
        return draw(pair_production())
    # empty / trivial
    return draw(st.sampled_from(["", " ", "{}", "[]", "null", "true", "false", "0"]))


strategy = _top()
```