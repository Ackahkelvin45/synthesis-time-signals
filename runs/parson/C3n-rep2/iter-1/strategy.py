from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------

# A safe, non-NUL, non-control raw character for string bodies.
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
).filter(lambda c: ord(c) not in range(0x00, 0x20) and c not in '"\\')

# Escape sequences permitted by the grammar, plus surrogate / \u0000 escapes.
_escapes = st.sampled_from(
    [
        '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
        "\\u0000", "\\u001f", "\\uFFFF", "\\uD800", "\\uDC00",
        "\\uD834\\uDD1E", "\\u00e9", "\\u1234", "\\uABCD", "\\uabcd",
        "\\u000a", "\\u000d",
    ]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_uni_escape = _hex4.map(lambda h: "\\u" + h)

_string_body = st.one_of(
    st.lists(_safe_char, min_size=0, max_size=12).map("".join),
    st.lists(st.one_of(_escapes, _uni_escape), min_size=0, max_size=8).map("".join),
    st.lists(
        st.one_of(_safe_char, _escapes, _uni_escape), min_size=0, max_size=12
    ).map("".join),
)

# Quoted string with valid escaping, plus malformed variants.
_string = _string_body.map(lambda s: '"' + s + '"')

_malformed_string = st.one_of(
    _string_body.map(lambda s: '"' + s),                      # unterminated
    _string_body.map(lambda s: '"' + s + "\n"),               # newline in string
    _string_body.map(lambda s: '"' + s + "'"),                # wrong quote
    st.just('"'),
    st.just('"\\'),
    st.just('"\\u12"'),                                       # short \u escape
    st.just('"\\x41"'),                                       # bad escape
    st.just('"unterminated'),
)

# ---------------------------------------------------------------------------
# Numbers: valid, extreme, and malformed
# ---------------------------------------------------------------------------

_valid_numbers = st.one_of(
    st.integers(min_value=-(2 ** 63), max_value=2 ** 63).map(str),
    st.just("0"),
    st.just("-0"),
    st.just("0.0"),
    st.sampled_from(
        [
            "1e309", "-1e309", "1e308", "-1e308", "1e-309", "1e-999",
            "1E+400", "1e+000", "0e0", "0e999",
            "1.7976931348623157e308",
            "4.9406564584124654e-324",
            "2.2250738585072014e-308",
            "123456789012345678901234567890",
            "0.000000000000000000000001",
            "-0.0",
            "1e01",
            "1E-01",
            "9" * 40,
            "-" + "9" * 40,
            "1." + "0" * 100,
            "0." + "0" * 100 + "1",
        ]
    ),
    st.from_regex(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?", fullmatch=True),
)

_malformed_numbers = st.sampled_from(
    [
        "+1", ".5", "1.", "01", "-01", "00", "1..2", "1e", "1e+", "1e-",
        "--1", "-", "-.", ".", "1.2.3", "0x10", "1_000", "1,2",
        "1e309extra", "NaN", "Infinity", "-Infinity", "1e999999999",
    ]
)

_number = st.one_of(_valid_numbers, _malformed_numbers)

# ---------------------------------------------------------------------------
# Recursive structure
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])


@st.composite
def _json_value(draw, depth):
    """Build a JSON value with a bounded recursion budget."""
    if depth <= 0:
        return draw(st.one_of(_string, _number, st.sampled_from(["true", "false", "null"])))

    leaf = st.one_of(
        _string,
        _number,
        st.sampled_from(["true", "false", "null"]),
        _malformed_string,
    )

    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return draw(leaf)

    if kind == 1:
        # array
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        items = [draw(_json_value(depth - 1)) for _ in range(n)]
        sep = draw(st.sampled_from([",", ", ", " , "]))
        inner = sep.join(items)
        if draw(st.booleans()):
            inner = inner + draw(st.sampled_from([",", " ,", ", "]))  # trailing comma
        return "[" + inner + "]"

    # object
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "{}"
    pairs = []
    used = set()
    for _ in range(n):
        key = draw(_string)
        if draw(st.booleans()) and used:
            key = draw(st.sampled_from(sorted(used)))  # duplicate key
        used.add(key)
        val = draw(_json_value(depth - 1))
        colon = draw(st.sampled_from([":", ":", " :", ": "]))
        if draw(st.booleans()):
            colon = draw(st.sampled_from(["", " ", ";"]))  # missing/bad colon
        pairs.append(key + colon + val)
    sep = draw(st.sampled_from([",", ", ", " , "]))
    inner = sep.join(pairs)
    if draw(st.booleans()):
        inner = inner + draw(st.sampled_from([",", " ,"]))  # trailing comma
    return "{" + inner + "}"


# Depth distribution: concentrate near the parser's 2048 cap.
_deep_depth = st.one_of(
    st.integers(min_value=1, max_value=8),
    st.integers(min_value=16, max_value=64),
    st.integers(min_value=1000, max_value=2100),
    st.sampled_from([2046, 2047, 2048, 2049, 2050, 2100, 3000]),
)


@st.composite
def _deep_nesting(draw):
    d = draw(_deep_depth)
    opener, closer = draw(st.sampled_from([("[", "]"), ("{", "}"), ("[", "]")]))
    if opener == "[":
        body = draw(st.one_of(_number, _string, st.sampled_from(["true", "false", "null"])))
    else:
        key = draw(_string)
        body = key + ":" + draw(st.one_of(_number, _string, st.sampled_from(["null"])))
    return opener * d + body + closer * d


# ---------------------------------------------------------------------------
# Near-valid-but-malformed top-level fragments
# ---------------------------------------------------------------------------

_malformed_top = st.sampled_from(
    [
        "",
        " ",
        ",",
        "[,]",
        "[1,,2]",
        "[1,2,]",
        "{,}",
        '{"a":1,}',
        '{"a" 1}',
        '{"a":}',
        '{:1}',
        '{"a":1 "b":2}',
        "{'a':1}",
        "{a:1}",
        "[1 2]",
        "[",
        "]",
        "{",
        "}",
        "[[",
        "]]",
        '"',
        "'",
        "nul",
        "tru",
        "fals",
        "TRUE",
        "None",
        "undefined",
    ]
)


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

@st.composite
def _json_text(draw):
    kind = draw(st.integers(min_value=0, max_value=9))

    if kind == 0:
        return draw(_deep_nesting())

    if kind == 1:
        return draw(_malformed_top)

    if kind == 2:
        # trailing content after a complete value (parser accepts)
        base = draw(_json_value(draw(st.integers(min_value=0, max_value=3))))
        tail = draw(st.sampled_from(["", "abc", " garbage", "xyz", "1", "{}", "[]", "//c", "/*x*/"]))
        return base + tail

    if kind == 3:
        # duplicate keys at top level
        k = draw(_string)
        v1 = draw(_json_value(1))
        v2 = draw(_json_value(1))
        return "{" + k + ":" + v1 + "," + k + ":" + v2 + "}"

    if kind == 4:
        # extreme numbers alone / wrapped
        num = draw(st.one_of(_valid_numbers, _malformed_numbers))
        wrap = draw(st.integers(min_value=0, max_value=2))
        if wrap == 0:
            return num
        if wrap == 1:
            return "[" + num + "]"
        return '{"n":' + num + "}"

    if kind == 5:
        # lone sign / lenient tokens
        return draw(st.sampled_from(["-", "-.", "+", ".", ".5", "1.", "01", "-01"]))

    if kind == 6:
        # string-heavy: escapes, surrogates, \u0000
        return draw(_string)

    if kind == 7:
        # whitespace-padded value
        v = draw(_json_value(draw(st.integers(min_value=0, max_value=2))))
        return draw(_ws) + v + draw(_ws)

    if kind == 8:
        # malformed string at top level
        return draw(_malformed_string)

    return draw(_json_value(draw(st.integers(min_value=0, max_value=4))))


strategy = _json_text()