```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_bare_key_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

def _bare_key():
    return st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)

_weird_chars = st.one_of(
    st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_categories=("Cs",)),
    st.sampled_from(["\x01", "\x02", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x7f"]),
)

# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

_escape = st.sampled_from([
    "\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0041", "\\u00e9", "\\u20ac", "\\U0001F600", "\\u0000",
    "\\u", "\\u0", "\\u00", "\\u000", "\\uD800", "\\uDFFF",
    "\\U00110000", "\\U00000000", "\\u12345", "\\x41", "\\q", "\\",
    # extra malformed escapes to exercise toml_utf8_to_ucs
    "\\uD8", "\\uDF", "\\uZZZZ", "\\UFFFFFFFF", "\\U0000D800",
    "\\u{41}", "\\u+041", "\\u-041", "\\U0000000", "\\U0001F60",
    # more toml_utf8_to_ucs edge cases: surrogates, overlongs, boundaries
    "\\uD83D", "\\uDE00", "\\uD83D\\uDE00", "\\uDBFF", "\\uDC00",
    "\\uDBFF\\uDFFF", "\\uD800\\uD800", "\\uDC00\\uD800",
    "\\U0000FFFF", "\\U00010000", "\\U0010FFFF", "\\U00110001",
    "\\U0000D8FF", "\\U0000DFFF", "\\U0000DC00",
    "\\u0000\\u0000", "\\U00000041", "\\U0000004",
    "\\u004", "\\u00G0", "\\u0G00", "\\U00G00000",
    "\\U0000000G", "\\u{", "\\U{", "\\u{}", "\\U{}",
    "\\u{110000}", "\\u{D800}", "\\u{10FFFF}",
])

_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters='"\\\n'),
    st.sampled_from(["\t", "\x01", "\x0b", "\x0c", "\x1b", "\x7f"]),
)

_basic_string = st.lists(
    st.one_of(_basic_char, _escape), max_size=8
).map(lambda parts: '"' + "".join(parts) + '"')

_literal_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters="'\n"),
    st.sampled_from(["\t", "\x01", "\x0b", "\x0c", "\x1b", "\x7f"]),
)

_literal_string = st.lists(_literal_char, max_size=8).map(
    lambda parts: "'" + "".join(parts) + "'"
)

_ml_basic_inner = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters='"\\'),
    st.sampled_from(["\n", "\t", "\r", "\x01", "\x1b"]),
    _escape,
)

_ml_basic_string = st.lists(_ml_basic_inner, max_size=10).map(
    lambda parts: '"""' + "".join(parts) + '"""'
)

_ml_literal_inner = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters="'"),
    st.sampled_from(["\n", "\t", "\r", "\x01", "\x1b"]),
)

_ml_literal_string = st.lists(_ml_literal_inner, max_size=10).map(
    lambda parts: "'''" + "".join(parts) + "'''"
)

# Multi-line strings with quote runs / line-ending backslash trimming,
# to exercise norm_lit_str and the multi-line trimming logic.
_ml_quote_run_basic = st.sampled_from([
    '""""', '"""""', '""""""', '"""\\\n"""', '"""a\\\n   b"""',
    '"""line1\nline2"""', '"""\\\r\n"""', '"""\\  \n"""',
    # more whitespace-trimming variants for norm_lit_str
    '"""\\\n   """', '"""\\\n\t"""', '"""\\\n\r\n"""',
    '"""x\\\n   """', '"""\\\n   x"""', '"""  \\\n  y  """',
    '"""a\n\\\n b"""', '"""\\\n\\\n"""', '"""\\\n\r"""',
    '"""\\\n \t """', '"""\\\n\n"""', '"""\\\n  \n  """',
    '"""\\\n   \\\n   """',
    # dedicated norm_lit_str stress: backslash-newline at start/end of every
    # line, mixed CR/LF, trailing whitespace runs, tabs, leading blank lines
    '"""\\\n"""', '"""a\\\n"""', '"""\\\na"""', '"""a\\\n b\\\n c"""',
    '"""\\\n\\\n\\\n"""', '"""\\\r\n\\\r\n"""', '"""\\\r\\\n"""',
    '"""\\\n \r\n \t """', '"""\n\\\n\n"""', '"""\r\\\n\r"""',
    '"""x\n   \\\n   y"""', '"""   \\\n   """', '"""\\\n\n\n"""',
    '"""\\\n\t\t\t"""', '"""a \\\n b \\\n c """',
    '"""\\\n\\\n"""', '"""\\\n \\\n"""', '""" \\\n\\\n """',
    '"""\r\n\\\r\n\r\n"""', '"""\\\n\r\n\r\n"""',
    '"""a\\\n\r\n b"""', '"""\\\n  \\\n   \\\n    """',
    '"""\n\n\\\n\n\n"""', '"""\\\n\r"""', '"""\\\r\n"""',
    '"""\\\t\n"""', '"""\\ \n"""', '"""\\\n\x0b"""',
    # quote-run interactions with trimming
    '"""a""\\\n  ""b"""', '""""\\\n"""', '"""\\\n""""',
    '"""""\\\n"""""',
])

_ml_quote_run_literal = st.sampled_from([
    "''''", "'''''", "''''''", "'''line1\nline2'''", "'''\\\n'''",
    "'''\n'''", "'''\n\n'''", "'''  \n  '''", "'''a\n\nb'''",
    "'''\\\n  '''", "'''\\\n\t'''",
    # literal multiline trimming (no escapes, but blank-line handling)
    "'''\n\n\n'''", "'''\r\n\r\n'''", "'''a\n\n\nb'''",
    "'''\n  \n\t\n'''", "'''\r\n  \r\n'''", "'''\n\r\n\n'''",
    "'''   \n   '''", "'''\t\n\t'''", "'''\n\t \n'''",
    "''''''''", "'''''''''", "'''a''''b'''", "'''''''''",
])

_string_value = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
    _ml_quote_run_basic,
    _ml_quote_run_literal,
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.sampled_from([
        "0", "1", "007", "000", "+0", "-0", "1_000", "1_0_0",
        "9223372036854775807", "9223372036854775808",
        "-9223372036854775808", "99999999999999999999999999999999",
        "1_2_3_4_5",
    ]),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=0xFFFFFFFFFFFFFFFF).map(lambda n: "0x" + format(n, "x")),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF"]),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=0o7777777777777777).map(lambda n: "0o" + format(n, "o")),
    st.sampled_from(["0o0", "0o777", "0o1_2_3", "0o755"]),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from(["0b0", "0b1", "0b1010_1010", "0b11111111"]),
)

_integer_value = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# Dedicated float strategy to exercise toml_rtod_ex thoroughly: exponent
# forms, missing digits, sign edge cases, underscores, huge/tiny exponents.
_float_value = st.one_of(
    st.sampled_from([
        "1.0", "-1.0", "+1.0", "3.14159", "1e10", "1E10", "1e+10", "1e-10",
        "1.5e10", "-1.5E-10", "1.", ".5", "0.0", "-0.0", "1e309", "-1e309",
        "1_000.000_1", "inf", "+inf", "-inf", "nan", "+nan", "-nan",
        "1e0", "0e0", "6.626e-34", "1.7976931348623157e308",
        # toml_rtod_ex edge cases
        "0e", "1e", "1e+", "1e-", "1E+", "1E-", "1.0e", "1.0e+", "1.0e-",
        "1.0e+0", "1.0e-0", "1.0e00", "1.0e+00", "1.0e-00",
        ".0", ".0e0", "-.0", "+.0", "-.5e3", "+.5e-3",
        "1.e0", "1.e+0", "1.e-0", "1.0E+10", "1.0E-10",
        "1e308", "1e-308", "1e-400", "1e400", "-1e400",
        "1_0e1_0", "1_0.0_1e1_0", "1.0_0", "1_0.0",
        "1e_10", "1_e10", "1e1_0", "1e+_10", "1e-_10",
        "1.0e1_0", "1.0e+1_0", "1.0e-1_0",
        "0.0000000000000000000000000000001",
        "123456789012345678901234567890.0",
        "1.0000000000000000000000000001e-300",
        "1e0000000000000000001",
        "1e-0000000000000000001",
        "1.0e0000000000000000001",
        "1.0e-0000000000000000001",
        "1.0e9999999999999999999",
        "1.0e-9999999999999999999",
        "1.0e+9999999999999999999",
        "1.0e-9999999999999999999",
        "nan", "inF", "NaN", "INF", "Infinity", "infinity",
        "1.e", "1.e+", "1.e-", ".e0", ".e", "-.e0",
    ]),
    st.floats(allow_nan=True, allow_infinity=True).map(repr),
)

# ---------------------------------------------------------------------------
# Booleans, date-times
# ---------------------------------------------------------------------------

_bool_value = st.sampled_from(["true", "false"])

# Dedicated date-time strategy to exercise toml_rtots thoroughly.
_date_time_value = st.one_of(
    st.sampled_from([
        "1979-05-27T07:32:00Z",
        "1979-05-27T00:32:00-07:00",
        "1979-05-27T00:32:00+07:00",
        "1979-05-27T07:32:00",
        "1979-05-27T07:32:00.999999",
        "1979-05-27 07:32:00Z",
        "1979-05-27",
        "07:32:00",
        "00:32:00.999999",
        "1979-02-30",
        "0000-00-00",
        "9999-12-31T23:59:59Z",
        "1979-05-27t07:32:00z",
        "1979-05-27T07:32:00.5+00:00",
    ]),
    # systematic toml_rtots edge cases
    st.sampled_from([
        # date-only boundaries
        "0000-01-01", "9999-12-31", "1979-01-01", "1979-12-31",
        "1979-00-00", "1979-13-01", "1979-01-32", "1979-01-00",
        "1979-02-29", "2000-02-29", "2100-02-29", "1900-02-29",
        "1979-04-31", "1979-06-31", "1979-09-31", "1979-11-31",
        "1979-1-1", "79-05-27", "1979-005-27", "1979-05-027",
        "1979-05-27T", "1979-05-27t", "1979-05-27 ",
        # full datetime boundaries
        "1979-05-27T00:00:00", "1979-05-27T23:59:59",
        "1979-05-27T24:00:00", "1979-05-27T23:60:00",
        "1979-05-27T23:59:60", "1979-05-27T23:59:61",
        "1979-05-27T99:99:99", "1979-05-27T-1:00:00",
        # time-only
        "00:00:00", "23:59:59", "24:00:00", "23:60:00", "23:59:60",
        "99:99:99", "0:00:00", "00:0:00", "00:00:0",
        "7:32:00", "07:32:0", "07:3:00",
        "07:32", "07", "7",
        # fractional seconds
        "1979-05-27T07:32:00.0", "1979-05-27T07:32:00.00",
        "1979-05-27T07:32:00.000000", "1979-05-27T07:32:00.0000000",
        "1979-05-27T07:32:00.123456789",
        "1979-05-27T07:32:00.", "1979-05-27T07:32:00.999999999999999999",
        "07:32:00.", "07:32:00.0", "07:32:00.123456789",
        # offset forms
        "1979-05-27T07:32:00+00:00", "1979-05-27T07:32:00-00:00",
        "1979-05-27T07:32:00+23:59", "1979-05-27T07:32:00-23:59",
        "1979-05-27T07:32:00+24:00", "1979-05-27T07:32:00+00:60",
        "1979-05-27T07:32:00+99:99", "1979-05-27T07:32:00+",
        "1979-05-27T07:32:00-", "1979-05-27T07:32:00+0:00",
        "1979-05-27T07:32:00+00:0", "1979-05-27T07:32:00+0000",
        "1979-05-27T07:32:00+00", "1979-05-27T07:32:00+0",
        "1979-05-27T07:32:00Z", "1979-05-27T07:32:00z",
        "1979-05-27T07:32:00ZZ", "1979-05-27T07:32:00Zx",
        "1979-05-27T07:32:00.5Z", "1979-05-27T07:32:00.5+00:00",
        # space separator
        "1979-05-27 07:32:00", "1979-05-27 07:32:00.5",
        "1979-05-27 07:32:00+00:00", "1979-05-27 00:00:00Z",
        # truncated / malformed
        "1979-05-27T07", "1979-05-27T07:", "1979-05-27T07:32",
        "1979-05-27T07:32:", "1979-05-27T07:32:0",
        "1979-05-27T07:32:00.", "1979-05-27T07:32:00+",
        "1979-05-27T07:32:00-", "1979-05-27T07:32:00+0",
        "1979-05-27T07:32:00+00", "1979-05-27T07:32:00+00:",
        "1979-05-27T07:32:00+00:0",
        "1979-05-27T07:32:00Z0", "1979-05-27T07:32:00Z ",
        "1979-05-27T07:32:00.5.5", "1979-05-27T07:32:00+00:00:00",
        "1979-05-27T07:32:00+00:00Z",
        "1979-05-27T07:32:00-00:00Z",
        # non-digit chars sprinkled
        "1979-05-2xT07:32:00Z", "1979-05-27T07:32:00Z",
        "1979-05-27T0x:32:00Z", "1979-05-27T07:3x:00Z",
        "1979-05-27T07:32:0xZ",
        "x979-05-27", "1979x05-27", "1979-05x27", "1979-05-27x",
        "1979-05-27T07:32:00.5x",
        "1979-05-27T07:32:00+0x:00",
        "1979-05-27T07:32:00+00:0x",
        "1979-05-27T07:32:00+00:00x",
        # whitespace variants
        " 1979-05-27", "1979-05-27 ", "1979-05-27T 07:32:00",
        "1979-05-27T07:32:00 ", "1979-05-27 07:32:00 ",
        "1979-05-27T07:32:00.5 ", "1979-05-27T07:32:00+00:00 ",
    ]),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_bare_key(), _quoted_key)

def _dotted_key():
    return st.lists(_simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key())

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

_leaf_value = st.one_of(
    _string_value,
    _integer_value,
    _float_value,
    _bool_value,
    _date_time_value,
)

def _array_from_values(values):
    if not values:
        return "[]"
    return "[" + ", ".join(values) + "]"

def _inline_table_from_pairs(pairs):
    if not pairs:
        return "{}"
    return "{" + ", ".join(k + " = " + v for k, v in pairs) + "}"

@st.composite
def _value(draw, depth=0):
    if depth >= 6:
        return draw(_leaf_value)
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return draw(_leaf_value)
    elif kind == 1:
        n = draw(st.integers(min_value=0, max_value=4))
        elems = [draw(_value(depth + 1)) for _ in range(n)]
        return _array_from_values(elems)
    else:
        n = draw(st.integers(min_value=0, max_value=3))
        pairs = []
        for _ in range(n):
            k = draw(_key)
            v = draw(_value(depth + 1))
            pairs.append((k, v))
        return _inline_table_from_pairs(pairs)

# ---------------------------------------------------------------------------
# Key/value lines, tables, array tables
# ---------------------------------------------------------------------------

def _key_value_line():
    return st.tuples(_key, _value()).map(lambda kv: kv[0] + " = " + kv[1])

def _table_header():
    return st.tuples(_key).map(lambda k: "[" + k[0] + "]")

def _array_table_header():
    return st.tuples(_key).map(lambda k: "[[" + k[0] + "]]")

def _comment_line():
    return st.one_of(
        st.just("#"),
        st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters="\n\r"), max_size=30).map(lambda s: "# " + s),
        st.sampled_from(["# comment", "#\tcomment", "# \x01\x02", "# non-ascii: é"]),
    )

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from([
    'a = [1, 2',
    'a = [1, 2]]',
    'a = {b = 1',
    'a = {b = 1}}',
    '[table',
    '[[table]',
    '[[table]]]',
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    'a = = 1',
    'a b = 1',
    '= 1',
    'a = ',
    'a = ,',
    'a = 1 2',
    'a = "\\q"',
    'a = {b = 1,\nc = 2}',
    'a =\n1',
    'é = 1',
    'a = 1\na = 2',
    '[t]\n[t]',
    'a.b! = 1',
    'a = "\xff\xfe"',
    'a = "\xc3"',
    'a = "\xed\xa0\x80"',
    'a = "\xf0\x9f\x98"',
    'a = "\x80"',
    'a = "\\uD800"',
    'a = "\\uDFFF"',
    'a = "\\U00110000"',
    '\ufeffa = 1',
    'a = 1\rb = 2',
    'a = "\x00"',
    'a = 1979-13-45T99:99:99Z',
    'a = 1979-05-27T07:32:00+99:00',
    'a = 0x',
    'a = 1__0',
    'a = 1.2.3',
    '[]',
    'a = []',
    'a\x01 = 1',
    # extra cases to exercise toml_rtod_ex / toml_rtots / toml_utf8_to_ucs
    'a = 0x1p4',
    'a = 1e',
    'a = 1e+',
    'a = .',
    'a = -.',
    'a = +',
    'a = 1_',
    'a = _1',
    'a = 0b',
    'a = 0o',
    'a = 0b2',
    'a = 0o8',
    'a = 0xg',
    'a = 1979-05-27T',
    'a = 1979-05-27T07:',
    'a = 1979-05-27T07:32',
    'a = 1979-05-27T07:32:00.',
    'a = 1979-05-27T07:32:00+',
    'a = 1979-05-27T07:32:00-',
    'a = 1979-05-27T07:32:00Zx',
    'a = 07:32',
    'a = 7:32:00',
    'a = 1979-5-27',
    'a = "\\u12"',
    'a = "\\u123"',
    'a = "\\U0001F60"',
    'a = "\\uD800\\uDC00"',
    'a = "\\U000000"',
    'a = "\\u000G"',
    # toml_rtots-specific malformed datetimes
    'a = 1979-05-27T24:00:00',
    'a = 1979-05-27T23:60:00',
    'a = 1979-05-27T23:59:60',
    'a = 1979-02-29',
    'a = 2000-02-29',
    'a = 1979-04-31',
    'a = 1979-05-27T07:32:00+24:00',
    'a = 1979-05-27T07:32:00+00:60',
    'a = 1979-05-27T07:32:00.999999999999999999',
    'a = 1979-05-27T07:32:00Zx',
    'a = 1979-05-27t07:32:00z',
    'a = 1979-05-27 07:32:00Z',
    'a = 0000-00-00',
    'a = 9999-12-31T23:59:59Z',
    # toml_rtod_ex-specific malformed floats
    'a = 1e',
    'a = 1e+',
    'a = 1e-',
    'a = 1.0e',
    'a = 1.0e+',
    'a = 1.0e-',
    'a = .e0',
    'a = 1.e',
    'a = 1.e+',
    'a = 1.e-',
    'a = 1e_10',
    'a = 1_e10',
    'a = 1e1_0',
    'a = 1.0e1_0',
    'a = 1.0e+1_0',
    'a = 1.0e-1_0',
    'a = 1.0e9999999999999999999',
    'a = 1.0e-9999999999999999999',
    'a = 1e400',
    'a = -1e400',
    'a = 1e-400',
    # toml_utf8_to_ucs-specific malformed escapes
    'a = "\\uD800"',
    'a = "\\uDBFF\\uDFFF"',
    'a = "\\uD800\\uD800"',
    'a = "\\uDC00\\uD800"',
    'a = "\\U00110000"',
    'a = "\\U0010FFFF"',
    'a = "\\U00010000"',
    'a = "\\u{110000}"',
    'a = "\\u{D800}"',
    'a = "\\u{}"',
    'a = "\\U{}"',
    'a = "\\u004"',
    'a = "\\u00G0"',
    'a = "\\U0000000G"',
    'a = "\\u"',
    'a = "\\U"',
    # norm_lit_str-specific malformed multiline
    'a = """\\\n"""',
    'a = """\\\n   """',
    'a = """\\\n\t"""',
    'a = """\\\r\n"""',
    'a = """\\\r"""',
    'a = """\\  \n"""',
    'a = """\\\t\n"""',
    'a = """\\\n\r\n"""',
    'a = """\\\n \t """',
    'a = """\\\n\n"""',
    'a = """\\\n  \n  """',
    'a = """\\\n   \\\n   """',
    'a = """a\\\n b"""',
    'a = """a\\\n\r\n b"""',
    'a = """\n\\\n\n"""',
    'a = """\r\n\\\r\n\r\n"""',
    'a = """\\\n\x0b"""',
    'a = """\\\n\x0c"""',
    'a = """\\\n\x7f"""',
    'a = """\\\n\x01"""',
    'a = """\\\n\x1b"""',
    'a = """\\\n\x00"""',
    'a = """\\\n \x00 """',
    'a = """\x00\\\n"""',
    'a = """a\x00b"""',
    'a = """\\\n""""',
    'a = """"\\\n"""',
    'a = """""\\\n"""""',
    'a = """\\\n""""""',
    'a = """\r\\\n"""',
    'a = """\\\r\n\r"""',
    'a = """\\\n\r"""',
    'a = """\\\r\r\n"""',
    'a = """\\\n \r """',
    'a = """\\\n \t\r """',
    'a = """x\\\n   \\\n   y"""',
    'a = """\\\n\n\n\n"""',
    'a = """\\\n\t\t\t\t"""',
    'a = """a \\\n b \\\n c """',
    'a = """\\\n \\\n"""',
    'a = """ \\\n\\\n """',
    'a = """\\\n\\\n\\\n\\\n"""',
    'a = """\\\n \r\n"""',
    'a = """\\\n \r"""',
    'a = """\\\n\r \n"""',
    # toml_parse_file-specific: larger malformed documents
    'a = 1\nb = \na = 2',
    '[a]\n[a]\n[a]',
    '[[a]]\n[a]',
    '[a]\n[[a]]',
    'a.b = 1\na.b.c = 2',
    'a = {b = {c = {d = {e = {f = 1}}}}}',
    '[[[[[[[[[[a]]]]]]]]]]',
    'a = [1, [2, [3, [4, [5, [6, [7]]]]]]]',
    'a = """\n' + '\\\n' * 50 + '"""',
    'a = "' + 'x' * 1000 + '"',
    'a = [' + ', '.join(str(i) for i in range(100)) + ']',
    'a = 1\n' * 100,
    '[' + '.'.join('k' + str(i) for i in range(50)) + ']',
    'a = "' + '\\n' * 100 + '"',
    'a = 1' + '\r\n' * 100 + 'b = 2',
    'a = ' + '[' * 50 + ']' * 50,
    'a = ' + '{' * 50 + '}' * 50,
])

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def _line():
    return st.one_of(
        _key_value_line(),
        _table_header(),
        _array_table_header(),
        _comment_line(),
    )

@st.composite
def _document(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    lines = [draw(_line()) for _ in range(n)]
    if