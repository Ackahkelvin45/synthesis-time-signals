```python
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

# Characters that force json_serialize_string to emit escape sequences:
# control chars, quote, backslash, and non-ASCII (UTF-8 / \uXXXX paths).
_serialize_char = st.one_of(
    st.sampled_from(['"', "\\", "\n", "\r", "\t", "\b", "\f", "/"]),
    st.characters(min_codepoint=0x00, max_codepoint=0x1F),
    st.characters(min_codepoint=0x7F, max_codepoint=0x7F),
    st.characters(min_codepoint=0x80, max_codepoint=0x7FF),
    st.characters(min_codepoint=0x800, max_codepoint=0xFFFF),
    st.characters(min_codepoint=0x10000, max_codepoint=0x10FFFF),
    st.sampled_from(["\u2028", "\u2029", "\ufeff", "\u0000", "\u001f", "\u007f"]),
)

# A JSON string whose body is dense with characters that exercise the
# serializer's per-character escaping / UTF-8 encoding branches.
_serialize_string = st.lists(
    _serialize_char, min_size=0, max_size=24
).map(lambda cs: '"' + "".join(cs) + '"')

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


# ---------------------------------------------------------------------------
# Serializer-focused strategy: json_serialize_string coverage
# ---------------------------------------------------------------------------

@st.composite
def _serialize_text(draw):
    """Produce JSON text whose strings exercise json_serialize_string."""
    kind = draw(st.integers(min_value=0, max_value=5))
    if kind == 0:
        return draw(_serialize_string)
    if kind == 1:
        return "[" + draw(_serialize_string) + "]"
    if kind == 2:
        return "{" + draw(_serialize_string) + ":" + draw(_serialize_string) + "}"
    if kind == 3:
        n = draw(st.integers(min_value=1, max_value=4))
        items = [draw(_serialize_string) for _ in range(n)]
        return "[" + ",".join(items) + "]"
    if kind == 4:
        n = draw(st.integers(min_value=1, max_value=4))
        pairs = [
            draw(_serialize_string) + ":" + draw(_serialize_string) for _ in range(n)
        ]
        return "{" + ",".join(pairs) + "}"
    return '{"s":' + draw(_serialize_string) + "}"


# ---------------------------------------------------------------------------
# Direct driver for json_serialize_string / json_serialize_to_buffer_r.
# The parser entry point itself is what gets fuzzed, so we produce inputs that
# are valid JSON strings whose bodies contain the exact byte/char classes the
# serializer's branches key off of: ASCII passthrough, '"' and '\\' escapes,
# short escapes (\b \f \n \r \t), control chars -> \u00XX, and multi-byte
# UTF-8 / \uXXXX paths for non-ASCII (2-, 3-, and 4-byte sequences).
# ---------------------------------------------------------------------------

_serialize_body_class = st.sampled_from(
    [
        "a", "Z", "0", "~", " ", "!",
        '"', "\\", "/",
        "\b", "\f", "\n", "\r", "\t",
        "\x00", "\x01", "\x07", "\x0b", "\x0e", "\x1f",
        "\x7f",
        "\u0080", "\u00e9", "\u00ff", "\u07ff",
        "\u0800", "\u2028", "\u2029", "\ufeff", "\uffff",
        "\U00010000", "\U0001d11e", "\U0010ffff",
    ]
)

# A body built from serializer-relevant classes, then rendered as a JSON
# string literal with proper escaping so the *parser* accepts it and passes
# the decoded value on to json_serialize_string.
_serialize_body = st.lists(
    _serialize_body_class, min_size=0, max_size=32
).map("".join)


def _to_json_literal(s):
    # Emit a syntactically valid JSON string literal for arbitrary content,
    # so the parser produces a value the serializer will later re-encode.
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


_serialize_literal = _serialize_body.map(_to_json_literal)


@st.composite
def _serialize_driver(draw):
    """Wrap serializer-relevant strings in structures so the parser builds
    values that json_serialize_string / json_serialize_to_buffer_r must emit."""
    kind = draw(st.integers(min_value=0, max_value=5))
    lit = draw(_serialize_literal)
    if kind == 0:
        return lit
    if kind == 1:
        return "[" + lit + "]"
    if kind == 2:
        return "{" + lit + ":" + lit + "}"
    if kind == 3:
        n = draw(st.integers(min_value=1, max_value=4))
        return "[" + ",".join([draw(_serialize_literal) for _ in range(n)]) + "]"
    if kind == 4:
        n = draw(st.integers(min_value=1, max_value=4))
        pairs = [
            draw(_serialize_literal) + ":" + draw(_serialize_literal)
            for _ in range(n)
        ]
        return "{" + ",".join(pairs) + "}"
    return '{"s":' + lit + "}"


# ---------------------------------------------------------------------------
# Direct driver for json_serialize_string: the fuzzed entry point is the
# parser, but we can force the serializer to run on parsed values by emitting
# a top-level JSON value that the harness will round-trip. To maximize
# json_serialize_string branch coverage we bias heavily toward strings whose
# decoded bodies span every serializer branch: ASCII passthrough, the two
# mandatory escapes, short escapes, control-char \u00XX, and the 2/3/4-byte
# UTF-8 and \uXXXX paths. These are emitted as valid JSON so the parser
# succeeds and the value reaches the serializer.
# ---------------------------------------------------------------------------

_serialize_edge_literals = st.sampled_from(
    [
        '""',
        '"a"',
        '"\\""',
        '"\\\\"',
        '"\\b\\f\\n\\r\\t"',
        '"\\u0000"',
        '"\\u0001\\u001f"',
        '"\\u007f"',
        '"\\u0080"',
        '"\\u07ff"',
        '"\\u0800"',
        '"\\u2028\\u2029"',
        '"\\ufeff"',
        '"\\uffff"',
        '"\\ud834\\udd1e"',
        '"\\ud800"',
        '"\\udc00"',
        '"\\u00e9"',
        '"\\u1234"',
        '"\\uabcd"',
        '"\\uABCD"',
        '"/"',
        '" "',
        '"~"',
        '"\\u000b"',
        '"\\u000e"',
    ]
)


@st.composite
def _serialize_string_driver(draw):
    """Emit valid JSON values containing strings that force every branch of
    json_serialize_string: ASCII passthrough, '"'/backslash escapes, short
    escapes, control -> \\u00XX, and multi-byte UTF-8 / \\uXXXX paths."""
    kind = draw(st.integers(min_value=0, max_value=6))
    lit = draw(st.one_of(_serialize_literal, _serialize_edge_literals))
    if kind == 0:
        return lit
    if kind == 1:
        return "[" + lit + "]"
    if kind == 2:
        return "{" + lit + ":" + lit + "}"
    if kind == 3:
        n = draw(st.integers(min_value=1, max_value=6))
        return "[" + ",".join(
            [draw(st.one_of(_serialize_literal, _serialize_edge_literals))
             for _ in range(n)]
        ) + "]"
    if kind == 4:
        n = draw(st.integers(min_value=1, max_value=6))
        pairs = []
        for _ in range(n):
            k = draw(st.one_of(_serialize_literal, _serialize_edge_literals))
            v = draw(st.one_of(_serialize_literal, _serialize_edge_literals))
            pairs.append(k + ":" + v)
        return "{" + ",".join(pairs) + "}"
    if kind == 5:
        # Mix serializer edge literals with numbers/bools so the serializer
        # walks nested containers and re-emits every string it encounters.
        n = draw(st.integers(min_value=1, max_value=5))
        items = []
        for _ in range(n):
            if draw(st.booleans()):
                items.append(draw(st.one_of(_serialize_literal, _serialize_edge_literals)))
            else:
                items.append(draw(st.one_of(_valid_numbers, st.sampled_from(["true", "false", "null"]))))
        return "[" + ",".join(items) + "]"
    return '{"s":' + lit + "}"


# ---------------------------------------------------------------------------
# json_serialize_string coverage driver.
#
# The serializer is only reached via round-tripping a parsed value. To force
# json_serialize_string's per-character branches, emit valid JSON whose
# decoded string bodies are guaranteed to contain: pure ASCII passthrough,
# '"' and '\\' (mandatory escapes), the short escapes \b \f \n \r \t,
# control chars < 0x20 -> \u00XX, 0x7f, and 2/3/4-byte UTF-8 sequences
# (U+0080..U+FFFF and U+10000..U+10FFFF), plus lone-surrogate \uXXXX forms.
# ---------------------------------------------------------------------------

# Every serializer branch class, as decoded characters.
_ser_branch_chars = [
    "a", "Z", "0", "~", " ", "!",
    '"', "\\",
    "\b", "\f", "\n", "\r", "\t",
    "\x00", "\x01", "\x0b", "\x0e", "\x1f",
    "\x7f",
    "\u0080", "\u00e9", "\u07ff",
    "\u0800", "\u2028", "\ufeff", "\uffff",
    "\U00010000", "\U0001d11e", "\U0010ffff",
]

# A body guaranteed to contain at least one of every branch class, shuffled.
_ser_full_body = st.permutations(_ser_branch_chars).map("".join)

# Random bodies drawn from the branch classes, variable length.
_ser_rand_body = st.lists(
    st.sampled_from(_ser_branch_chars), min_size=0, max_size=40
).map("".join)

_ser_body = st.one_of(_ser_full_body, _ser_rand_body)


def _ser_literal(s):
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


_ser_literal = _ser_body.map(_ser_literal)

# Valid JSON string literals using \uXXXX escapes for surrogates and BMP
# code points, so the parser decodes them into the exact code units the
# serializer must re-encode.
_ser_escape_literal = st.sampled_from(
    [
        '"\\u0000"',
        '"\\u0001\\u0002\\u001f"',
        '"\\u007f"',
        '"\\u0080"',
        '"\\u00e9\\u00ff"',
        '"\\u07ff"',
        '"\\u0800"',
        '"\\u2028\\u2029"',
        '"\\ufeff"',
        '"\\uffff"',
        '"\\ud834\\udd1e"',
        '"\\ud800"',
        '"\\udc00"',
        '"\\uabcd\\uABCD"',
        '"\\u1234"',
        '"\\b\\f\\n\\r\\t"',
        '"\\"\\\\"',
        '"/"',
        '"aZ0~ !"',
    ]
)


@st.composite
def _serialize_roundtrip(draw):
    """Emit valid JSON values whose strings hit every json_serialize_string
    branch, so the parser accepts them and the harness round-trips them
    through json_serialize_string / json_serialize_to_buffer_r."""
    kind = draw(st.integers(min_value=0, max_value=7))
    lit = draw(st.one_of(_ser_literal, _ser_escape_literal))

    if kind == 0:
        return lit
    if kind == 1:
        return "[" + lit + "]"
    if kind == 2:
        return "{" + lit + ":" + lit + "}"
    if kind == 3:
        n = draw(st.integers(min_value=1, max_value=6))
        return "[" + ",".join(
            [draw(st.one_of(_ser_literal, _ser_escape_literal)) for _ in range(n)]
        ) + "]"
    if kind == 4:
        n = draw(st.integers(min_value=1, max_value=6))
        pairs = []
        for _ in range(n):
            k = draw(st.one_of(_ser_literal, _ser_escape_literal))
            v = draw(st.one_of(_ser_literal, _ser_escape_literal))
            pairs.append(k + ":" + v)
        return "{" + ",".join(pairs) + "}"
    if kind == 5:
        # Nested containers so the serializer recurses through
        # json_serialize_to_buffer_r and re-emits each string.
        n = draw(st.integers(min_value=1, max_value=5))
        items = []
        for _ in range(n):
            r = draw(st.integers(min_value=0, max_value=2))
            if r == 0:
                items.append(draw(st.one_of(_ser_literal, _ser_escape_literal)))
            elif r == 1:
                items.append(
                    "[" + draw(st.one_of(_ser_literal, _ser_escape_literal)) + "]"
                )
            else:
                items.append(
                    "{"
                    + draw(st.one_of(_ser_literal, _ser_escape_literal))
                    + ":"
                    + draw(st.one_of(_ser_literal, _ser_escape_literal))
                    + "}"
                )
        return "[" + ",".join(items) + "]"
    if kind == 6:
        # Deeply nested single-key objects to drive the serializer recursion.
        d = draw(st.integers(min_value=1, max_value=32))
        inner = draw(st.one_of(_ser_literal, _ser_escape_literal))
        return '{"k":' * d + inner + "}" * d
    return '{"s":' + lit + "}"


_combined = st.one_of(
    _json_text(),
    _serialize_text(),
    _serialize_driver(),
    _serialize_string_driver(),
    _serialize_roundtrip(),
)

strategy = _combined
```