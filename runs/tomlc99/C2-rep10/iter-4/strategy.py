"""Hypothesis strategy generating TOML documents for fuzzing a C parser.

Covers the full TOML surface described in the prompt, including the parser's
documented deviations (leading zeros, `1.`, `.5`, raw control chars, trailing
commas in inline tables, calendar-invalid dates) and malformed near-valid
inputs. Never emits a raw NUL byte.
"""

from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Low-level character / token building blocks
# ---------------------------------------------------------------------------

# Characters allowed in bare (unquoted) keys.
_BARE_KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

# A few interesting non-ASCII / control characters to sprinkle into strings.
_INTERESTING_CHARS = [
    "\x01", "\x02", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x7f",
    "\t", " ", "!", "#", "=", "[", "]", "{", "}", ",", ".", "\"", "'",
    "\\", "/", "\u00e9", "\u4e2d", "\u6587", "\U0001f600", "\u2028", "\u2029",
]

# Escape sequences valid inside a basic string (one backslash + body).
_ESCAPE_BODIES = ['"', "\\", "/", "b", "f", "n", "r", "t"]
_HEX = "0123456789abcdefABCDEF"


@st.composite
def _hex_digits(draw, n):
    return "".join(draw(st.sampled_from(_HEX)) for _ in range(n))


@st.composite
def _basic_escape(draw):
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        return "\\" + draw(st.sampled_from(_ESCAPE_BODIES))
    if choice == 1:
        return "\\u" + draw(_hex_digits(4))
    if choice == 2:
        return "\\U" + draw(_hex_digits(8))
    # Invalid escape (parser rejects) — useful for negative coverage.
    return "\\" + draw(st.sampled_from("qQzZgwW!@#$%^&*()"))


@st.composite
def _basic_string_char(draw):
    """A single character inside a single-line basic string (no raw newline)."""
    if draw(st.booleans()):
        return draw(_basic_escape())
    return draw(
        st.one_of(
            st.sampled_from(_INTERESTING_CHARS),
            st.characters(
                blacklist_characters='"\\\n\r\x00',
                min_codepoint=1,
                max_codepoint=0x10FFFF,
            ),
        )
    )


@st.composite
def _literal_string_char(draw):
    """A single character inside a single-line literal string."""
    return draw(
        st.one_of(
            st.sampled_from(_INTERESTING_CHARS),
            st.characters(
                blacklist_characters="'\n\r\x00",
                min_codepoint=1,
                max_codepoint=0x10FFFF,
            ),
        )
    )


def _basic_string_body():
    return st.lists(_basic_string_char(), min_size=0, max_size=12).map("".join)


def _literal_string_body():
    return st.lists(_literal_string_char(), min_size=0, max_size=12).map("".join)


# ---------------------------------------------------------------------------
# Strings: all four quoting forms
# ---------------------------------------------------------------------------

@st.composite
def _single_basic_string(draw):
    return '"' + draw(_basic_string_body()) + '"'


@st.composite
def _single_literal_string(draw):
    return "'" + draw(_literal_string_body()) + "'"


@st.composite
def _ml_basic_string(draw):
    # Multiline basic string: allow raw newlines and line-continuations.
    n = draw(st.integers(min_value=0, max_value=10))
    parts = []
    for _ in range(n):
        r = draw(st.integers(min_value=0, max_value=4))
        if r == 0:
            parts.append("\n")
        elif r == 1:
            parts.append("\r\n")
        elif r == 2:
            parts.append("\\\n")  # line continuation
        elif r == 3:
            parts.append(draw(_basic_escape()))
        else:
            parts.append(draw(_basic_string_char()))
    body = "".join(parts)
    # Avoid accidental early termination by a triple quote.
    body = body.replace('"""', '""\\"')
    return '"""' + body + '"""'


@st.composite
def _ml_literal_string(draw):
    n = draw(st.integers(min_value=0, max_value=10))
    parts = []
    for _ in range(n):
        r = draw(st.integers(min_value=0, max_value=3))
        if r == 0:
            parts.append("\n")
        elif r == 1:
            parts.append("\r\n")
        else:
            parts.append(draw(_literal_string_char()))
    body = "".join(parts)
    body = body.replace("'''", "''\\'")
    return "'''" + body + "'''"


@st.composite
def _unterminated_string(draw):
    """A near-valid string missing its closing delimiter."""
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return '"' + draw(_basic_string_body())
    if kind == 1:
        return "'" + draw(_literal_string_body())
    if kind == 2:
        return '"""' + draw(_basic_string_body())
    return "'''" + draw(_literal_string_body())


@st.composite
def _string_value(draw):
    return draw(
        st.one_of(
            _single_basic_string(),
            _single_literal_string(),
            _ml_basic_string(),
            _ml_literal_string(),
            _unterminated_string(),
        )
    )


# ---------------------------------------------------------------------------
# Integers: all bases, underscores, extremes, leading zeros
# ---------------------------------------------------------------------------

_DEC_DIGITS = "0123456789"
_HEX_DIGITS = "0123456789abcdefABCDEF"
_OCT_DIGITS = "01234567"
_BIN_DIGITS = "01"


@st.composite
def _digits_with_underscores(draw, alphabet, max_len=20):
    n = draw(st.integers(min_value=1, max_value=max_len))
    digits = [draw(st.sampled_from(alphabet)) for _ in range(n)]
    out = []
    for i, d in enumerate(digits):
        out.append(d)
        if i < n - 1 and draw(st.integers(min_value=0, max_value=4)) == 0:
            out.append("_")
    return "".join(out)


@st.composite
def _dec_int(draw):
    sign = draw(st.sampled_from(["", "+", "-"]))
    style = draw(st.integers(min_value=0, max_value=3))
    if style == 0:
        # Leading zeros allowed by the parser.
        body = "0" + draw(_digits_with_underscores(_DEC_DIGITS, 8))
    elif style == 1:
        body = draw(_digits_with_underscores(_DEC_DIGITS, 20))
    elif style == 2:
        # Extreme magnitude.
        body = "9" * draw(st.integers(min_value=1, max_value=40))
    else:
        body = draw(st.sampled_from(["0", "7", "007", "000", "1_000_000"]))
    return sign + body


@st.composite
def _hex_int(draw):
    return "0x" + draw(_digits_with_underscores(_HEX_DIGITS, 20))


@st.composite
def _oct_int(draw):
    return "0o" + draw(_digits_with_underscores(_OCT_DIGITS, 20))


@st.composite
def _bin_int(draw):
    return "0b" + draw(_digits_with_underscores(_BIN_DIGITS, 20))


@st.composite
def _integer_value(draw):
    return draw(st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int()))


# ---------------------------------------------------------------------------
# Floats: inf/nan, exponents, extremes, malformed (1., .5)
# ---------------------------------------------------------------------------

@st.composite
def _float_value(draw):
    r = draw(st.integers(min_value=0, max_value=7))
    if r == 0:
        return draw(st.sampled_from(["inf", "+inf", "-inf"]))
    if r == 1:
        return draw(st.sampled_from(["nan", "+nan", "-nan"]))
    if r == 2:
        # No digit after dot (parser accepts).
        return draw(st.sampled_from(["1.", "-1.", "+0.", "0."]))
    if r == 3:
        # No leading digit (parser accepts).
        return draw(st.sampled_from([".5", "-.5", "+.25", ".0"]))
    if r == 4:
        # Extreme exponent.
        exp = draw(st.integers(min_value=-400, max_value=400))
        return draw(st.sampled_from(["1", "9", "0"])) + "e" + str(exp)
    if r == 5:
        mant = draw(_digits_with_underscores(_DEC_DIGITS, 12))
        frac = draw(_digits_with_underscores(_DEC_DIGITS, 12))
        sign = draw(st.sampled_from(["", "+", "-"]))
        return sign + mant + "." + frac
    if r == 6:
        mant = draw(_digits_with_underscores(_DEC_DIGITS, 10))
        frac = draw(_digits_with_underscores(_DEC_DIGITS, 6))
        exp = draw(st.integers(min_value=-300, max_value=300))
        esign = draw(st.sampled_from(["e", "E"]))
        return mant + "." + frac + esign + str(exp)
    return draw(
        st.sampled_from(
            ["1.0", "3.14", "-0.0", "6.626e-34", "1e309", "-1e-309", "1_000.000_1"]
        )
    )


# ---------------------------------------------------------------------------
# Booleans, date-times
# ---------------------------------------------------------------------------

_BOOL = st.sampled_from(["true", "false"])


@st.composite
def _two_digits(draw, lo, hi):
    return "%02d" % draw(st.integers(min_value=lo, max_value=hi))


@st.composite
def _four_digits(draw, lo, hi):
    return "%04d" % draw(st.integers(min_value=lo, max_value=hi))


@st.composite
def _date_part(draw):
    # Include calendar-invalid dates (parser accepts).
    year = draw(_four_digits(0, 9999))
    month = draw(_two_digits(0, 99))
    day = draw(_two_digits(0, 99))
    return "%s-%s-%s" % (year, month, day)


@st.composite
def _time_part(draw):
    hh = draw(_two_digits(0, 99))
    mm = draw(_two_digits(0, 99))
    ss = draw(_two_digits(0, 99))
    base = "%s:%s:%s" % (hh, mm, ss)
    if draw(st.booleans()):
        frac = draw(_digits_with_underscores(_DEC_DIGITS, 9))
        base += "." + frac
    return base


@st.composite
def _offset(draw):
    if draw(st.booleans()):
        return "Z"
    sign = draw(st.sampled_from(["+", "-"]))
    return sign + draw(_two_digits(0, 99)) + ":" + draw(_two_digits(0, 99))


@st.composite
def _local_date_time_value(draw):
    """LOCAL_DATE_TIME: date and time with no offset."""
    sep = draw(st.sampled_from(["T", "t", " "]))
    return draw(_date_part()) + sep + draw(_time_part())


@st.composite
def _date_time_value(draw):
    # Upweight LOCAL_DATE_TIME so it is exercised frequently.
    kind = draw(st.integers(min_value=0, max_value=5))
    date = draw(_date_part())
    time = draw(_time_part())
    if kind == 0:
        return date
    if kind == 1:
        return time
    if kind in (2, 3):
        # LOCAL_DATE_TIME (upweighted).
        sep = draw(st.sampled_from(["T", "t", " "]))
        return date + sep + time
    sep = draw(st.sampled_from(["T", "t", " "]))
    return date + sep + time + draw(_offset())


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def _bare_key():
    return st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=8)


@st.composite
def _quoted_key(draw):
    return draw(st.one_of(_single_basic_string(), _single_literal_string()))


def _simple_key():
    # Empty quoted key "" is allowed; bare keys must be non-empty.
    return st.one_of(_bare_key(), _quoted_key())


@st.composite
def _dotted_key(draw):
    n = draw(st.integers(min_value=2, max_value=4))
    parts = [draw(_simple_key()) for _ in range(n)]
    return ".".join(parts)


@st.composite
def _key(draw):
    if draw(st.integers(min_value=0, max_value=4)) == 0:
        return draw(_dotted_key())
    return draw(_simple_key())


# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# Depth budget for the recursive value grammar. The parser handles ~2048
# levels; concentrate interesting depth in the 1500-2048 band for a fraction
# of inputs, keep the rest shallow for readability.
_DEEP_DEPTH = 1800


@st.composite
def _leaf_value(draw):
    return draw(
        st.one_of(
            _string_value(),
            _integer_value(),
            _float_value(),
            _BOOL,
            _date_time_value(),
        )
    )


@st.composite
def _array_body(draw, value_strategy):
    """An array value, allowing nested arrays / inline tables as elements."""
    n = draw(st.integers(min_value=0, max_value=5))
    elems = [draw(value_strategy) for _ in range(n)]
    # Multiline arrays with comments, or single-line.
    multiline = draw(st.booleans())
    if multiline:
        pieces = []
        for e in elems:
            pieces.append(e)
            pieces.append(",")
            if draw(st.integers(min_value=0, max_value=3)) == 0:
                pieces.append(" # c\n")
            else:
                pieces.append("\n")
        body = "".join(pieces)
        if elems and draw(st.booleans()):
            body += " # trailing\n"
        return "[\n" + body + "]"
    if not elems:
        return "[]"
    sep = ", "
    out = sep.join(elems)
    if draw(st.integers(min_value=0, max_value=3)) == 0:
        out += ","
    return "[" + out + "]"


@st.composite
def _inline_table_body(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=4))
    pairs = []
    for _ in range(n):
        k = draw(_key())
        v = draw(value_strategy)
        pairs.append("%s = %s" % (k, v))
    if not pairs:
        return "{}"
    out = "{ " + ", ".join(pairs)
    if draw(st.integers(min_value=0, max_value=2)) == 0:
        out += ","
    out += " }"
    return out


def _value_grammar():
    """Recursive value strategy: arrays and inline tables nest."""
    return st.recursive(
        _leaf_value(),
        lambda children: st.one_of(
            _array_body(children),
            _inline_table_body(children),
        ),
        max_leaves=40,
    )


_value = _value_grammar()


def _deep_array_value():
    """A deeply nested array (depth in the 1500-2048 band)."""
    return st.integers(min_value=1500, max_value=2048).map(
        lambda d: "[" * d + "]" * d
    )


def _deep_inline_table_value():
    """A deeply nested inline table (depth in the 1500-2048 band)."""
    return st.integers(min_value=1500, max_value=2048).map(
        lambda d: "{a=" * d + "1" + "}" * d
    )


# ---------------------------------------------------------------------------
# Malformed near-valid fragments
# ---------------------------------------------------------------------------

@st.composite
def _malformed_value(draw):
    r = draw(st.integers(min_value=0, max_value=9))
    if r == 0:
        # Missing closing bracket.
        return "[" + draw(_leaf_value())
    if r == 1:
        # Doubled closing bracket.
        return "[" + draw(_leaf_value()) + "]]"
    if r == 2:
        # Missing closing brace.
        return "{ a = " + draw(_leaf_value())
    if r == 3:
        # Stray token after value.
        return draw(_leaf_value()) + " ,,"
    if r == 4:
        # Newline inside inline table (parser rejects).
        return "{ a = 1\n, b = 2 }"
    if r == 5:
        # Bare non-ASCII key (parser rejects).
        return "{\u00e9 = 1}"
    if r == 6:
        # Invalid escape inside a basic string.
        return '"bad\\qescape"'
    if r == 7:
        # Value on the next line after '='.
        return "\n" + draw(_leaf_value())
    if r == 8:
        # Empty value.
        return ""
    return draw(_unterminated_string())


# ---------------------------------------------------------------------------
# Keys/values in a key-value pair (with malformed option)
# ---------------------------------------------------------------------------

@st.composite
def _key_value_line(draw):
    key = draw(_key())
    if draw(st.integers(min_value=0, max_value=6)) == 0:
        value = draw(_malformed_value())
    elif draw(st.integers(min_value=0, max_value=9)) == 0:
        value = draw(_deep_array_value())
    elif draw(st.integers(min_value=0, max_value=9)) == 0:
        value = draw(_deep_inline_table_value())
    else:
        value = draw(_value)
    line = "%s = %s" % (key, value)
    if draw(st.integers(min_value=0, max_value=3)) == 0:
        line += " # comment with \x01 control"
    return line


# ---------------------------------------------------------------------------
# Tables: standard and array-of-tables
# ---------------------------------------------------------------------------

@st.composite
def _table_line(draw):
    key = draw(_key())
    if draw(st.booleans()):
        line = "[[%s]]" % key
    else:
        line = "[%s]" % key
    return line


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

@st.composite
def _line(draw):
    r = draw(st.integers(min_value=0, max_value=9))
    if r <= 4:
        return draw(_key_value_line())
    if r <= 6:
        return draw(_table_line())
    if r == 7:
        # Comment-only line (control chars allowed).
        return "# " + draw(
            st.text(
                alphabet=st.characters(
                    blacklist_characters="\n\r\x00",
                    min_codepoint=1,
                    max_codepoint=0x10FFFF,
                ),
                min_size=0,
                max_size=20,
            )
        )
    if r == 8:
        # Empty line.
        return ""
    # Stray token line (malformed).
    return draw(st.sampled_from(["=", "]", "}", ",", "[[", "]]", "a =", "= 1"]))


@st.composite
def _document(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    lines = [draw(_line()) for _ in range(n)]
    # Occasional duplicate-key / duplicate-table injection.
    if n >= 2 and draw(st.integers(min_value=0, max_value=3)) == 0:
        lines.append(lines[0])
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    text = sep.join(lines)
    # Trailing newline or none (both are valid).
    if draw(st.booleans()):
        text += sep
    return text


# ---------------------------------------------------------------------------
# Duplicate keys / duplicate tables (feature-encoding probe)
# ---------------------------------------------------------------------------

_DUP_KEY_NAMES = ["a", "b", "c", "key", "x1", "foo", "bar", "t", "name", "val"]


@st.composite
def _duplicate_key_document(draw):
    """Documents that deliberately repeat a key (or table) to exercise
    the parser's duplicate-key detection paths."""
    name = draw(st.sampled_from(_DUP_KEY_NAMES))
    other = draw(st.sampled_from(_DUP_KEY_NAMES))
    value_a = draw(_leaf_value())
    value_b = draw(_leaf_value())
    value_c = draw(_leaf_value())
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    style = draw(st.integers(min_value=0, max_value=9))
    if style == 0:
        # Same key twice in the root table.
        lines = ["%s = %s" % (name, value_a), "%s = %s" % (name, value_b)]
    elif style == 1:
        # Same key defined twice inside the same standard table.
        lines = [
            "[%s]" % other,
            "%s = %s" % (name, value_a),
            "%s = %s" % (name, value_b),
        ]
    elif style == 2:
        # Key defined in root, then redefined inside a sub-table.
        lines = [
            "%s = %s" % (name, value_a),
            "[%s]" % other,
            "%s = %s" % (name, value_b),
        ]
    elif style == 3:
        # Duplicate standard table header.
        lines = [
            "[%s]" % name,
            "%s = %s" % (other, value_a),
            "[%s]" % name,
            "%s = %s" % (other, value_b),
        ]
    elif style == 4:
        # Duplicate array-of-tables header (valid TOML, must be accepted).
        lines = [
            "[[%s]]" % name,
            "%s = %s" % (other, value_a),
            "[[%s]]" % name,
            "%s = %s" % (other, value_b),
        ]
    elif style == 5:
        # Same key twice inside an inline table (parser rejects).
        lines = [
            "%s = { %s = %s, %s = %s }"
            % (name, other, value_a, other, value_b)
        ]
    elif style == 6:
        # Dotted key then explicit table that collides.
        lines = [
            "%s.%s = %s" % (name, other, value_a),
            "[%s]" % name,
            "%s = %s" % (other, value_b),
        ]
    elif style == 7:
        # Quoted and bare spellings of the same key.
        lines = [
            "%s = %s" % (name, value_a),
            '"%s" = %s' % (name, value_b),
        ]
    elif style == 8:
        # Three-way duplicate.
        lines = [
            "%s = %s" % (name, value_a),
            "%s = %s" % (name, value_b),
            "%s = %s" % (name, value_c),
        ]
    else:
        # Array-of-tables then standard table with the same name (rejects).
        lines = [
            "[[%s]]" % name,
            "%s = %s" % (other, value_a),
            "[%s]" % name,
            "%s = %s" % (other, value_b),
        ]
    return sep.join(lines) + sep


# ---------------------------------------------------------------------------
# Public strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document(),
    _duplicate_key_document(),
    # Explicit edge cases.
    st.sampled_from(
        [
            "",
            "\n",
            "# only a comment\n",
            "a = 007\n",
            "a = 1.\n",
            "a = .5\n",
            "a = 1979-02-30\n",
            "a = {b = 1,}\n",
            'a = "x\x01y"\n',
            "a = []\n",
            "a = {}\n",
            "[t]\n",
            "[[a]]\n",
            '"" = 1\n',
            "a.b.c = 1\n",
            "a = 1_000\n",
            "a = 0xDEAD_BEEF\n",
            "a = 0o755\n",
            "a = 0b1010\n",
            "a = 1e309\n",
            "a = inf\n",
            "a = nan\n",
            "a = 1979-05-27 07:32:00Z\n",
            "a = 07:32:00\n",
            "a = 1979-05-27\n",
            'a = "\\u0000"\n',
            'a = """\nmulti\nline\n"""\n',
            "a = '''\nliteral\n'''\n",
            "a = [1, 2, 3,]\n",
            "a = [\n  1, # one\n  2,\n]\n",
            # Boolean coverage (bool_ / BOOLEAN production).
            "a = true\n",
            "a = false\n",
            "a = true\nb = false\n",
            "a = [true, false]\n",
            "a = { b = true, c = false }\n",
            "a = true # comment\n",
            "a = true\n[[t]]\na = false\n",
            # LOCAL_DATE_TIME coverage.
            "a = 1979-05-27T07:32:00\n",
            "a = 1979-05-27t07:32:00\n",
            "a = 1979-05-27 07:32:00\n",
            "a = 1979-05-27T00:32:00.999999\n",
            "a = 1979-02-30T34:50:53\n",
            # Duplicate key / table coverage.
            "a = 1\na = 2\n",
            "a = 1\r\na = 2\r\n",
            "[t]\na = 1\na = 2\n",
            "[t]\n[t]\n",
            "a = 1\n[t]\na = 2\n",
            "a.b = 1\n[a]\nb = 2\n",
            'a = 1\n"a" = 2\n',
            "a = { b = 1, b = 2 }\n",
            "[[t]]\na = 1\n[[t]]\na = 2\n",
            "[[t]]\n[t]\n",
            "a = 1\na = 2\na = 3\n",
        ]
    ),
)