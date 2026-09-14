```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Character classes / helpers
# ---------------------------------------------------------------------------

# Non-NUL, non-newline unicode text for basic strings (raw). We allow raw
# control chars (parser accepts them) but never NUL.
_RAW_BASIC_CHARS = st.characters(
    blacklist_categories=("Cs",), blacklist_characters="\x00\n\r\"\\"
)

# Text for literal strings: no quote, no newline, no NUL.
_RAW_LITERAL_CHARS = st.characters(
    blacklist_categories=("Cs",), blacklist_characters="\x00\n\r'"
)

# Comment text: no newline, no NUL.
_COMMENT_CHARS = st.characters(
    blacklist_categories=("Cs",), blacklist_characters="\x00\n\r"
)

# Bare key chars.
_BARE_KEY_CHARS = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)

# ---------------------------------------------------------------------------
# Escapes for basic strings
# ---------------------------------------------------------------------------

_SIMPLE_ESCAPES = st.sampled_from(
    ['\\"', "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]
)


@st.composite
def _unicode_escape(draw):
    kind = draw(st.sampled_from(["u", "U"]))
    if kind == "u":
        code = draw(st.integers(min_value=0, max_value=0xFFFF))
        return "\\u%04X" % code
    else:
        code = draw(st.integers(min_value=0, max_value=0x10FFFF))
        return "\\U%08X" % code


# Escapes that include \u0000 (allowed inside a string).
_ESCAPES = st.one_of(_SIMPLE_ESCAPES, _unicode_escape())


def _basic_string_body_raw():
    return st.lists(
        st.one_of(_ESCAPES, _RAW_BASIC_CHARS.map(str)),
        min_size=0,
        max_size=12,
    ).map("".join)


@st.composite
def _basic_string(draw):
    body = draw(_basic_string_body_raw())
    return '"' + body + '"'


@st.composite
def _literal_string(draw):
    body = draw(
        st.lists(_RAW_LITERAL_CHARS.map(str), min_size=0, max_size=12).map("".join)
    )
    return "'" + body + "'"


# Multiline basic string: content may contain newlines and raw control chars
# but must not contain `"""` and must not end with a backslash before the
# closing delimiter in a way that would swallow it. We keep it simple.
_ML_BASIC_CHARS = st.characters(
    blacklist_categories=("Cs",), blacklist_characters='\x00"\\'
)


@st.composite
def _multiline_basic_string(draw):
    parts = draw(
        st.lists(
            st.one_of(
                _ESCAPES,
                _ML_BASIC_CHARS.map(str),
                st.sampled_from(["\n", "\r\n", "\t", " "]),
                st.just('\\\n'),
            ),
            min_size=0,
            max_size=8,
        )
    )
    body = "".join(parts)
    # Avoid accidental triple-quote termination.
    body = body.replace('"""', '\\"\\"\\"')
    return '"""' + body + '"""'


_ML_LITERAL_CHARS = st.characters(
    blacklist_categories=("Cs",), blacklist_characters="\x00'"
)


@st.composite
def _multiline_literal_string(draw):
    parts = draw(
        st.lists(
            st.one_of(
                _ML_LITERAL_CHARS.map(str),
                st.sampled_from(["\n", "\r\n", "\t", " "]),
            ),
            min_size=0,
            max_size=8,
        )
    )
    body = "".join(parts)
    body = body.replace("'''", "''")
    return "'''" + body + "'''"


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_DEC_DIGITS = st.integers(min_value=0, max_value=9).map(str)


@st.composite
def _dec_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    style = draw(st.integers(min_value=0, max_value=4))
    if style == 0:
        # single digit / leading zeros
        n = draw(st.integers(min_value=0, max_value=6))
        digits = draw(st.lists(_DEC_DIGITS, min_size=1, max_size=6)).__iter__()
        s = "".join(draw(st.lists(_DEC_DIGITS, min_size=1, max_size=6)))
        return sign + s
    if style == 1:
        # underscores
        head = draw(_DEC_DIGITS)
        groups = draw(st.lists(_DEC_DIGITS, min_size=1, max_size=8))
        return sign + head + "".join("_" + g for g in groups)
    if style == 2:
        # extreme magnitudes
        big = draw(st.integers(min_value=10**18, max_value=10**40))
        return sign + str(big)
    if style == 3:
        return sign + "0"
    return sign + str(draw(st.integers(min_value=0, max_value=10**6)))


_HEX_DIGITS = st.sampled_from("0123456789abcdefABCDEF")
_OCT_DIGITS = st.sampled_from("01234567")
_BIN_DIGITS = st.sampled_from("01")


@st.composite
def _radix_int(draw):
    kind = draw(st.sampled_from(["0x", "0o", "0b"]))
    if kind == "0x":
        alphabet = _HEX_DIGITS
    elif kind == "0o":
        alphabet = _OCT_DIGITS
    else:
        alphabet = _BIN_DIGITS
    head = draw(alphabet)
    tail = draw(st.lists(alphabet, min_size=0, max_size=10))
    if tail and draw(st.booleans()):
        out = head
        for c in tail:
            out += ("_" if draw(st.booleans()) else "") + c
        return kind + out
    return kind + head + "".join(tail)


@st.composite
def _float(draw):
    style = draw(st.integers(min_value=0, max_value=6))
    if style == 0:
        return draw(st.sampled_from(["inf", "+inf", "-inf"]))
    if style == 1:
        return draw(st.sampled_from(["nan", "+nan", "-nan"]))
    if style == 2:
        # trailing dot: parser accepts
        return draw(st.sampled_from(["1.", "0.", "123.", "9."]))
    if style == 3:
        # leading dot: parser accepts
        return draw(st.sampled_from([".5", ".0", ".123", ".9"]))
    if style == 4:
        # exponent extremes
        mant = draw(st.sampled_from(["1", "0", "9", "1_0"]))
        exp = draw(
            st.integers(min_value=-400, max_value=400)
        )
        sign = draw(st.sampled_from(["e", "E"]))
        return mant + sign + ("+" if exp >= 0 and draw(st.booleans()) else "") + str(exp)
    if style == 5:
        # normal fractional
        intpart = draw(st.integers(min_value=0, max_value=1000))
        frac = draw(st.integers(min_value=0, max_value=999999))
        return "%d.%d" % (intpart, frac)
    # with underscores
    return draw(st.sampled_from(["1_000.5", "1.0_1", "1e1_0", "0.0", "-0.0"]))


# ---------------------------------------------------------------------------
# Dates / times
# ---------------------------------------------------------------------------

@st.composite
def _date_time(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    year = draw(st.integers(min_value=0, max_value=9999))
    month = draw(st.integers(min_value=0, max_value=99))
    day = draw(st.integers(min_value=0, max_value=99))
    hour = draw(st.integers(min_value=0, max_value=99))
    minute = draw(st.integers(min_value=0, max_value=99))
    second = draw(st.integers(min_value=0, max_value=99))
    frac = ""
    if draw(st.booleans()):
        frac = "." + "".join(
            draw(st.lists(_DEC_DIGITS, min_size=1, max_size=6))
        )
    date = "%04d-%02d-%02d" % (year, month, day)
    time = "%02d:%02d:%02d%s" % (hour, minute, second, frac)
    if kind == 0:
        return date
    if kind == 1:
        return time
    sep = draw(st.sampled_from(["T", "t", " "]))
    if kind == 2:
        return date + sep + time
    off = draw(
        st.one_of(
            st.just("Z"),
            st.just("z"),
            st.tuples(
                st.sampled_from(["+", "-"]),
                st.integers(min_value=0, max_value=23).map(lambda x: "%02d" % x),
                st.integers(min_value=0, max_value=59).map(lambda x: "%02d" % x),
            ).map(lambda t: t[0] + t[1] + ":" + t[2]),
        )
    )
    return date + sep + time + off


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_UNQUOTED_KEY = st.lists(_BARE_KEY_CHARS, min_size=1, max_size=10).map("".join)


@st.composite
def _simple_key(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return draw(_UNQUOTED_KEY)
    if kind == 1:
        return draw(_basic_string())
    if kind == 2:
        return draw(_literal_string())
    # empty quoted key
    return draw(st.sampled_from(['""', "''"]))


@st.composite
def _key(draw):
    if draw(st.booleans()):
        return draw(_simple_key())
    parts = draw(st.lists(_simple_key(), min_size=2, max_size=3))
    return ".".join(parts)


# ---------------------------------------------------------------------------
# Values (recursive)
# ---------------------------------------------------------------------------

_BOOL = st.sampled_from(["true", "false"])


def _scalar_value():
    return st.one_of(
        _basic_string(),
        _literal_string(),
        _multiline_basic_string(),
        _multiline_literal_string(),
        _dec_int(),
        _radix_int(),
        _float(),
        _BOOL,
        _date_time(),
    )


def _value_strategy():
    return st.recursive(
        _scalar_value(),
        lambda children: st.one_of(
            _array(children),
            _inline_table(children),
        ),
        max_leaves=20,
    )


@st.composite
def _array(draw, child):
    n = draw(st.integers(min_value=0, max_value=4))
    parts = []
    for _ in range(n):
        parts.append(draw(child))
    sep = draw(st.sampled_from([", ", ",\n", ", # c\n", " , "]))
    trailing = draw(st.sampled_from(["", ",", ",\n", ", # t\n"]))
    body = sep.join(parts)
    if parts and trailing:
        body = body + trailing
    elif not parts:
        body = draw(st.sampled_from(["", "\n", " # empty\n", "\n# c\n"]))
    return "[" + body + "]"


@st.composite
def _inline_table(draw, child):
    n = draw(st.integers(min_value=0, max_value=3))
    pairs = []
    for _ in range(n):
        k = draw(_key())
        v = draw(child)
        pairs.append(k + " = " + v)
    trailing = draw(st.sampled_from(["", ","]))
    body = ", ".join(pairs)
    if pairs and trailing:
        body = body + trailing
    return "{" + body + "}"


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@st.composite
def _key_value_line(draw):
    k = draw(_key())
    v = draw(_value_strategy())
    comment = draw(st.sampled_from(["", " # c", " #", "#x"]))
    sep = draw(st.sampled_from([" ", "  ", "\t", ""]))
    return k + sep + "=" + sep + v + comment


@st.composite
def _table_header(draw):
    k = draw(_key())
    if draw(st.booleans()):
        return "[[" + k + "]]"
    return "[" + k + "]"


@st.composite
def _expression(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return draw(_key_value_line())
    if kind == 1:
        return draw(_table_header())
    if kind == 2:
        return draw(st.sampled_from(["", "# comment", "#", "# "]))
    return draw(_key_value_line())


def _document():
    return st.lists(_expression(), min_size=0, max_size=8).map(
        lambda lines: "\n".join(lines)
    )


# ---------------------------------------------------------------------------
# Malformed / near-valid variants
# ---------------------------------------------------------------------------

@st.composite
def _malformed(draw):
    base = draw(_document())
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        # unterminated string
        return 'a = "unterminated'
    if kind == 1:
        # missing bracket
        return "[table\nkey = 1"
    if kind == 2:
        # doubled delimiter
        return "a = [[1, 2]"
    if kind == 3:
        # stray token
        return "a = 1 2 3"
    if kind == 4:
        # value on next line
        return "a =\n1"
    if kind == 5:
        # invalid escape
        return 'a = "bad \\q escape"'
    if kind == 6:
        # newline inside inline table
        return "a = {b = 1,\nc = 2}"
    if kind == 7:
        # duplicate keys
        return "a = 1\na = 2"
    if kind == 8:
        # non-ascii bare key
        return "caf\u00e9 = 1"
    # doubled equals
    return "a == 1"


# ---------------------------------------------------------------------------
# Deep nesting in the interesting band (1500-2048)
# ---------------------------------------------------------------------------

@st.composite
def _deep_nesting(draw):
    depth = draw(st.integers(min_value=1500, max_value=2048))
    kind = draw(st.sampled_from(["array", "inline", "mixed"]))
    if kind == "array":
        return "a = " + "[" * depth + "]" * depth
    if kind == "inline":
        return "a = " + "{b = " * depth + "1" + "}" * depth
    # mixed
    half = depth // 2
    return "a = " + "[{b = " * half + "1" + "}]" * half


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

def _edge_case():
    return st.sampled_from(
        [
            "",
            "\n",
            "# only a comment",
            "# comment\n",
            "a = 007",
            "a = 1.",
            "a = .5",
            'a = "x\x01y"',
            "a = {b = 1,}",
            "a = 1979-02-30",
            "a = [1, 2,]",
            "a = []",
            "a = {}",
            "[t]",
            "[[a]]",
            '"" = 1',
            "a = 1e309",
            "a = 1_000",
            "a = 0xDEAD_BEEF",
            "a = 0o777",
            "a = 0b1010_1010",
            "a = inf",
            "a = -inf",
            "a = nan",
            "a = 1979-05-27 07:32:00Z",
            "a = 1979-05-27T07:32:00",
            "a = 07:32:00",
            "a = 1979-05-27",
            "a = \"\\u0000\"",
            'a = "\\U0010FFFF"',
            "a = '''multi\nline'''",
            'a = """multi\nline"""',
            "a.b.c = 1",
            "a = 1 # trailing comment",
            "a = 1\r\nb = 2",
            "\ta = 1",
            "a = 1",
            # malformed
            'a = "unterminated',
            "[table\nkey = 1",
            "a = 1 2 3",
            "a =\n1",
            'a = "bad \\q escape"',
            "a = {b = 1,\nc = 2}",
            "a = 1\na = 2",
            "caf\u00e9 = 1",
            "a == 1",
            # NUL-free but control bytes
            "a = \"\x07\x1b\"",
            "# control \x01 in comment",
        ]
    )


strategy = st.one_of(
    _edge_case(),
    _document(),
    _malformed(),
    _deep_nesting(),
)
```