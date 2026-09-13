from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Low-level character pools (no raw NUL anywhere)
# ---------------------------------------------------------------------------

_bare_key_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

_ascii_printable = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    " !\"#$%&'()*+,-./:;<=>?@[]^_`{|}~"
)

_control_chars = "".join(chr(c) for c in range(1, 32) if c != 0x0a) + "\x7f"

_unicode_chars = "".join(
    chr(c) for c in (0x00e9, 0x00fc, 0x4e2d, 0x6587, 0x0416, 0x05d0, 0x1f600, 0x2603)
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)

_dotted_key = st.lists(_unquoted_key, min_size=2, max_size=4).map(".".join)

# ---------------------------------------------------------------------------
# Strings: all four quoting forms
# ---------------------------------------------------------------------------

_esc_short = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])


def _unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\u%04X" % n if n <= 0xFFFF else "\\U%08X" % n
    )


_esc = st.one_of(_esc_short, _unicode_escape())

_basic_body_char = st.one_of(
    st.text(alphabet=_ascii_printable + _unicode_chars, min_size=1, max_size=1),
    st.sampled_from(list(_control_chars)),
    _esc,
)

_basic_string = (
    st.lists(_basic_body_char, max_size=10)
    .map("".join)
    .map(lambda s: '"' + s + '"')
)

_literal_string = (
    st.text(alphabet=_ascii_printable.replace("'", "") + _unicode_chars + _control_chars,
            max_size=10)
    .map(lambda s: "'" + s + "'")
)


def _ml_basic_body():
    piece = st.one_of(
        st.text(alphabet=_ascii_printable + _unicode_chars + "\n\t", min_size=1, max_size=1),
        st.sampled_from(list(_control_chars)),
        _esc,
    )
    return st.lists(piece, max_size=12).map("".join)


_ml_basic_string = _ml_basic_body().map(lambda s: '"""' + s + '"""')

_ml_literal_body = st.text(
    alphabet=_ascii_printable + _unicode_chars + _control_chars + "\n\t",
    max_size=12,
)
_ml_literal_string = _ml_literal_body.map(lambda s: "'''" + s + "'''")

_string = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-(10 ** 30), max_value=10 ** 30).map(str),
    st.sampled_from(["0", "007", "-0", "+0", "1_000", "9" * 40, "-" + "9" * 40]),
)

_hex_int = st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0x%x" % n)
_oct_int = st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0o%o" % n)
_bin_int = st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0b" + format(n, "b"))

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.sampled_from([
        "1.", ".5", "1.0", "-1.5", "+0.0", "1e309", "-1e-309", "6.626e-34",
        "3.14159", "1_000.000_1", "0.0", "1e10", "1E+2", "1.0e-2",
    ]),
    st.integers(min_value=0, max_value=10 ** 12).map(lambda n: "%d.0" % n),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_floating_point = st.one_of(_float, _inf_nan)

# ---------------------------------------------------------------------------
# Booleans and date-times
# ---------------------------------------------------------------------------

_bool = st.sampled_from(["true", "false"])


def _two(minv, maxv):
    return st.integers(min_value=minv, max_value=maxv).map(lambda n: "%02d" % n)


_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = _two(0, 99)
_day = _two(0, 99)
_hour = _two(0, 99)
_minute = _two(0, 99)
_second = _two(0, 99)

_full_date = st.tuples(_year, _month, _day).map(lambda t: "%s-%s-%s" % t)
_partial_time = st.tuples(_hour, _minute, _second).map(lambda t: "%s:%s:%s" % t)
_secfrac = st.integers(min_value=0, max_value=999999).map(lambda n: ".%d" % n)
_offset = st.one_of(
    st.sampled_from(["Z", "z"]),
    st.tuples(st.sampled_from(["+", "-"]), _hour, _minute).map(
        lambda t: "%s%s:%s" % t
    ),
)
_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(_full_date, _delim, _partial_time, _offset).map(
    lambda t: "%s%s%s%s" % t
)
_local_date_time = st.tuples(_full_date, _delim, _partial_time).map(
    lambda t: "%s%s%s" % t
)
_local_date = _full_date
_local_time = st.tuples(_partial_time, st.one_of(st.just(""), _secfrac)).map(
    lambda t: "%s%s" % t
)

_date_time = st.one_of(
    _offset_date_time, _local_date_time, _local_date, _local_time
)

# ---------------------------------------------------------------------------
# Malformed fragments (near-valid)
# ---------------------------------------------------------------------------

_malformed_value = st.sampled_from([
    '"unterminated',
    "'unterminated",
    '"""unterminated',
    "'''unterminated",
    '"bad \\q escape"',
    "= 1",
    "1 =",
    "@invalid",
    "key",
    "[unclosed",
    "{unclosed",
    "]]",
    "a = = 1",
])

# ---------------------------------------------------------------------------
# Recursive value grammar
# ---------------------------------------------------------------------------

_scalar = st.one_of(
    _string,
    _integer,
    _floating_point,
    _bool,
    _date_time,
    _malformed_value,
)

_ws = st.sampled_from(["", " ", "  ", "\t"])


def _array(children):
    elems = st.lists(
        st.tuples(_ws, children, _ws, st.sampled_from([",", ",", ""])),
        max_size=6,
    ).map(lambda items: "".join("".join(t) for t in items))
    return st.tuples(elems, st.sampled_from(["", ",", ", "])).map(
        lambda t: "[" + t[0] + t[1] + "]"
    )


def _inline_table(children):
    pair = st.tuples(
        _unquoted_key, st.just(" = "), children
    ).map(lambda t: "".join(t))
    pairs = st.lists(pair, max_size=5).map(lambda xs: ", ".join(xs))
    return st.tuples(pairs, st.sampled_from(["", ","])).map(
        lambda t: "{" + t[0] + t[1] + "}"
    )


_value = st.recursive(
    _scalar,
    lambda children: st.one_of(_array(children), _inline_table(children)),
    max_leaves=40,
)

# ---------------------------------------------------------------------------
# Key/value lines, tables, documents
# ---------------------------------------------------------------------------

_simple_key = st.one_of(
    _unquoted_key,
    _basic_string,
    _literal_string,
)

_key = st.one_of(
    _simple_key,
    _dotted_key,
    st.lists(_simple_key, min_size=2, max_size=3).map(".".join),
)

_key_value = st.tuples(_key, st.just(" = "), _value).map(lambda t: "".join(t))

_comment = st.one_of(
    st.just(""),
    st.text(
        alphabet=_ascii_printable + _unicode_chars + _control_chars,
        max_size=20,
    ).map(lambda s: "#" + s.replace("\n", " ")),
)

_table_name = st.lists(_simple_key, min_size=1, max_size=3).map(".".join)

_standard_table = _table_name.map(lambda n: "[" + n + "]")
_array_table = _table_name.map(lambda n: "[[" + n + "]]")

def _line():
    body = st.one_of(
        _key_value,
        _standard_table,
        _array_table,
        st.just(""),
    )
    return st.tuples(body, st.sampled_from(["", " ", "  "]), _comment).map(
        lambda t: t[0] + t[1] + t[2]
    )

_eol = st.sampled_from(["\n", "\r\n"])

_document = st.lists(_line(), max_size=8).map(
    lambda lines: "\n".join(lines)
)

# ---------------------------------------------------------------------------
# Deep nesting stress (within the 1500-2048 band)
# ---------------------------------------------------------------------------

_deep_array = st.integers(min_value=1500, max_value=2048).map(
    lambda d: "[" * d + "1" + "]" * d
)

_deep_inline = st.integers(min_value=1500, max_value=2048).map(
    lambda d: "{a = " * d + "1" + "}" * d
)

_deep = st.one_of(_deep_array, _deep_inline).map(lambda v: "k = " + v)

# ---------------------------------------------------------------------------
# Extra hand-picked edge cases
# ---------------------------------------------------------------------------

_edge_cases = st.sampled_from([
    "",
    "\n",
    "# only a comment",
    "[t]\n",
    "[[a]]\n[[a]]\n",
    '"" = 1',
    "a = {b = 1,}",
    "a = 1979-02-30",
    "a = 007",
    "a = 1.",
    "a = .5",
    'a = "x\x01y"',
    "a = [1, 2, 3,]",
    "a = []\n[t]\n",
    "a = {}\n",
    "a.b.c = 1",
    "a = 1e309",
    "a = " + "k" * 10000 + " = 1" if False else "a = 1",
    "a = 1",  # no trailing newline
    "a = 1\na = 2",  # duplicate key
    "[t]\n[t]",  # duplicate table
    'a = "\\u0000"',
    "a = \"\"\"multi\nline\"\"\"",
    "a = '''multi\nline'''",
    "a = [\n  1, # c\n  2,\n]",
    "a = 1979-05-27 07:32:00Z",
    "a = 07:32:00",
    "a = +inf",
    "a = 0xDEAD_BEEF",
    "a = 0o755",
    "a = 0b1010_1010",
])

# ---------------------------------------------------------------------------
# Structural / lexical edge cases targeting uncovered parser branches
# ---------------------------------------------------------------------------

_structural_edge_cases = st.sampled_from([
    # CRLF and mixed line endings
    "a = 1\r\nb = 2\r\n",
    "a = 1\r\n",
    "\r\n",
    "a = 1\rb = 2",
    # Bare CR as line terminator
    "a = 1\rb = 2\r",
    # Whitespace-only and blank-line heavy documents
    "   \n\t\n  \n",
    "\t\t\t",
    "a = 1\n\n\n\nb = 2",
    # Comments in tricky positions
    "#\n[t]\n#\n",
    "[t] # comment\n",
    "[[t]] # comment\n",
    "#comment with \r carriage\r\n",
    "a = 1 # comment\r\n",
    # Table headers with whitespace inside brackets
    "[ t ]\n",
    "[ a . b ]\n",
    "[[ t ]]\n",
    "[t.u.v.w]\n",
    "[a.b]\n[a.b.c]\n",
    "[a]\n[a.b]\n",
    "[a.b]\n[a]\n",
    # Empty and degenerate table names
    "[]\n",
    "[[]]\n",
    "[.]\n",
    "[..]\n",
    "[a.]\n",
    "[.a]\n",
    # Dotted keys with whitespace around dots
    "a . b = 1",
    "a. b = 1",
    "a .b = 1",
    "a . b . c = 1",
    # Keys that are quoted strings
    '"a" = 1',
    "'a' = 1",
    '"" = 1',
    "'' = 1",
    '"a.b" = 1',
    '"a".b = 1',
    # Key/value with no spaces around '='
    "a=1",
    "a= 1",
    "a =1",
    "a\t=\t1",
    # Multi-line basic string with backslash line continuation
    'a = """line \\\n  continued"""',
    'a = """\\\n   trimmed"""',
    'a = """\\   \n   ws"""',
    # Multi-line literal string with quotes inside
    "a = '''has ' single'''",
    "a = '''has '' two'''",
    'a = """has " one"""',
    'a = """has "" two"""',
    # Escapes at end of basic string
    'a = "end \\\\"',
    'a = "\\u00e9"',
    'a = "\\U0001F600"',
    # Arrays with newlines and comments inside
    "a = [\n1,\n2,\n]",
    "a = [\n# c\n1,\n]",
    "a = [1,,2]",
    "a = [,]",
    "a = [ , ]",
    # Inline tables with newlines
    "a = {\n b = 1\n}",
    "a = {b = 1\n, c = 2}",
    "a = {,}",
    # Numbers with underscores in invalid positions
    "a = _1",
    "a = 1_",
    "a = 0x_1",
    "a = 0x1_",
    "a = 1__0",
    "a = 0b_",
    "a = 0o_",
    # Leading zeros and signs
    "a = 00",
    "a = 01",
    "a = +1",
    "a = -1",
    "a = +0.0",
    "a = -0.0",
    # Floats with bad exponents
    "a = 1e",
    "a = 1e+",
    "a = 1e-",
    "a = 1.e5",
    "a = .e5",
    "a = 1.2.3",
    # Datetimes with lowercase t/z and fractional seconds
    "a = 1979-05-27t07:32:00z",
    "a = 1979-05-27 07:32:00.999999-07:00",
    "a = 1979-05-27T00:32:00.999999-07:00",
    "a = 1979-05-27T07:32:00+07:00",
    "a = 1979-05-27T07:32:00-00:00",
    # Out-of-range datetime components
    "a = 0000-00-00T00:00:00Z",
    "a = 9999-99-99T99:99:99Z",
    # Keys/values with control characters
    "a\x01 = 1",
    "a = 1\x01",
    # Very long bare key
    "a" * 1000 + " = 1",
    # Value that is just a bare key (invalid)
    "a = b",
    # Nested arrays
    "a = [[1, 2], [3, 4]]",
    "a = {b = {c = 1}}",
    # Trailing garbage after value
    "a = 1 xyz",
    "a = true false",
    # Duplicate inline table key
    "a = {b = 1, b = 2}",
    # BOM-like prefix
    "\ufeffa = 1",
    # Just a table header with no newline
    "[t]",
    "[[t]]",
    # Empty document with only whitespace
    " ",
    "\t",
    "\r",
])

_strategy = st.one_of(
    _document,
    _deep,
    _edge_cases,
    _structural_edge_cases,
)

strategy = _strategy