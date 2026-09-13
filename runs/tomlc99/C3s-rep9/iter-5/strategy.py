from hypothesis import strategies as st

# ---------- helpers ----------

_ASCII_PRINTABLE = [chr(c) for c in range(0x20, 0x7F)]
_WS = [" ", "\t"]


def _join(parts):
    return "".join(parts)


# ---------- strings ----------

_basic_char = st.one_of(
    st.sampled_from(_ASCII_PRINTABLE),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
    st.sampled_from(["\x01", "\x02", "\x07", "\x0b", "\x0c", "\x7f"]),
)

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04X" % n),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\U%08X" % n),
)

_basic_body = st.one_of(_basic_char, _escapes)

_basic_string = st.lists(_basic_body, max_size=12).map(
    lambda xs: '"' + "".join(xs) + '"'
)

_literal_char = st.one_of(
    st.sampled_from(_ASCII_PRINTABLE),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
    st.sampled_from(["\x01", "\x02", "\x07", "\x0b", "\x0c", "\x7f"]),
)

_literal_string = st.lists(_literal_char, max_size=12).map(
    lambda xs: "'" + "".join(xs) + "'"
)

_ml_basic_string = st.lists(
    st.one_of(_basic_char, _escapes, st.sampled_from(["\n", "\r\n"])),
    max_size=10,
).map(lambda xs: '"""' + "".join(xs) + '"""')

_ml_literal_string = st.lists(
    st.one_of(_literal_char, st.sampled_from(["\n", "\r\n"])),
    max_size=10,
).map(lambda xs: "'''" + "".join(xs) + "'''")

_string = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# ---------- numbers ----------

_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 63), max_value=2 ** 63).map(str),
    st.integers(min_value=-(2 ** 200), max_value=2 ** 200).map(str),
    st.integers(min_value=0, max_value=10 ** 30).map(lambda n: str(n)),
    st.sampled_from(["0", "007", "-0", "+0", "000000", "1_000", "1_2_3"]),
)

_hex_int = st.integers(min_value=0, max_value=2 ** 128).map(lambda n: "0x%x" % n)
_oct_int = st.integers(min_value=0, max_value=2 ** 128).map(lambda n: "0o%o" % n)
_bin_int = st.integers(min_value=0, max_value=2 ** 128).map(lambda n: "0b" + bin(n)[2:])

_underscored = st.one_of(
    st.sampled_from(["0x1_2", "0o7_7", "0b1_0", "1_0_0"]),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int, _underscored)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: "%.17g" % f),
    st.sampled_from(
        [
            "1.",
            ".5",
            "0.0",
            "-0.0",
            "1e10",
            "1E-10",
            "1e+10",
            "1_0.0_1",
            "1e309",
            "-1e309",
            "1e-400",
            "3.141592653589793",
            "1.0e+308",
        ]
    ),
    st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
)

# ---------- booleans ----------

_boolean = st.sampled_from(["true", "false"])

# ---------- date-times ----------

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_day = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_hour = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_minute = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_second = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

_full_date = st.tuples(_year, _month, _day).map(lambda t: "%s-%s-%s" % t)
_partial_time = st.tuples(_hour, _minute, _second).map(
    lambda t: "%s:%s:%s" % t
)
_secfrac = st.integers(min_value=0, max_value=10 ** 9).map(lambda n: ".%d" % n)

_offset = st.one_of(
    st.sampled_from(["Z", "z"]),
    st.tuples(st.sampled_from(["+", "-"]), _hour, _minute).map(
        lambda t: "%s%s:%s" % t
    ),
)

_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(
    _full_date, _delim, _partial_time, _secfrac, _offset
).map(lambda t: "%s%s%s%s%s" % t)

_local_date_time = st.tuples(_full_date, _delim, _partial_time, _secfrac).map(
    lambda t: "%s%s%s%s" % t
)

_local_date = _full_date
_local_time = st.tuples(_partial_time, _secfrac).map(lambda t: "%s%s" % t)

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    st.sampled_from(
        [
            "1979-05-27T07:32:00Z",
            "1979-05-27 07:32:00Z",
            "1979-05-27T00:32:00-07:00",
            "1979-05-27T00:32:00.999999-07:00",
            "1979-05-27",
            "07:32:00",
            "00:32:00.999999",
            "1979-02-30",
            "0000-00-00",
        ]
    ),
)

# ---------- keys ----------

_unquoted_key = st.one_of(
    st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
        min_size=1,
        max_size=10,
    ),
    st.sampled_from(["a", "key", "k1", "A-B_c", "0", "123", "x" * 100]),
)

_quoted_key = st.one_of(
    _basic_string,
    _literal_string,
    st.just('""'),
    st.just("''"),
)

_simple_key = st.one_of(_quoted_key, _unquoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(
    lambda ks: ".".join(ks)
)

_key = st.one_of(_simple_key, _dotted_key)


# ---------- recursive values ----------

def _make_value_expr():
    # placeholder to build recursive strategy lazily
    return st.deferred(lambda: _value)


# We use st.recursive to build arrays and inline tables.
# Leaves: scalars. Bases: lists (arrays) and inline tables.

_scalar = st.one_of(
    _string,
    _integer,
    _float,
    _boolean,
    _date_time,
)

_comment_text = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\n\r",
        ),
        max_size=20,
    ),
    st.just(""),
)

_comment = _comment_text.map(lambda s: "#" + s)


def _array_from(values):
    # values: list of strings (already rendered)
    if not values:
        return "[]"
    inner = ", ".join(values)
    return "[" + inner + "]"


def _inline_table_from(pairs):
    # pairs: list of (keystr, valstr)
    if not pairs:
        return "{}"
    inner = ", ".join("%s = %s" % (k, v) for (k, v) in pairs)
    return "{" + inner + "}"


def _mk_value(children):
    array_leaf = st.lists(children, max_size=4).map(_array_from)
    inline_leaf = st.lists(
        st.tuples(_key, children), max_size=4
    ).map(_inline_table_from)
    return st.one_of(array_leaf, inline_leaf)


_value = st.recursive(_scalar, _mk_value, max_leaves=32)


# ---------- key-value pairs ----------

_key_value = st.tuples(_key, _value).map(lambda t: "%s = %s" % t)


# ---------- tables ----------

_standard_table = _key.map(lambda k: "[%s]" % k)
_array_table = _key.map(lambda k: "[[%s]]" % k)


# ---------- malformed variants ----------

_malformed_string = st.sampled_from(
    [
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = '''unterminated",
        'a = "bad \\q escape"',
        'a = "trailing\\"',
        "a = 1 = 2",
        "a = ",
        "= 1",
        "a = {b = 1",
        "a = [1, 2",
        "a = [1, 2]]",
        "a = }",
        "a = ]",
        "[table",
        "[[table]",
        "a = 1\nb = 2\nc =",
        "a = 1\nb = 2\nc = = 3",
        "a b = 1",
        "a. b = 1",
        "a .b = 1",
        "a = 1\na = 2",
        "[t]\n[t]",
        "a = {b = 1\n}",
        "a = 1 2 3",
        "a = true false",
        "\x00a = 1",
    ]
)


def _stray_token():
    return st.sampled_from(["@", "$", "%", "&", "!", "?", "~", "^", "`"])


_stray = _stray_token().map(lambda s: "a = " + s)


# ---------- document assembly ----------

def _line_with_comment(kv):
    return kv + " # comment"


_line = st.one_of(
    _key_value,
    _key_value.map(_line_with_comment),
    _comment,
    _standard_table,
    _array_table,
)


_document = st.lists(_line, min_size=0, max_size=8).map(
    lambda lines: "\n".join(lines)
)

_document_with_blank = st.lists(
    st.one_of(_line, st.just("")), min_size=0, max_size=10
).map(lambda lines: "\n".join(lines))

_document_crlf = st.lists(_line, min_size=0, max_size=6).map(
    lambda lines: "\r\n".join(lines)
)

_document_no_trailing_nl = _document

_document_with_trailing_nl = _document.map(lambda s: s + "\n")

_deep_array = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "a = " + "[" * n + "]" * n
)

_deep_inline = st.integers(min_value=200, max_value=500).map(
    lambda n: "a = " + "{b = " * n + "1" + "}" * n
)

_deep_array_value = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "a = " + "[" * n + "1" + "]" * n
)


_duplicate_keys = st.sampled_from(
    [
        "a = 1\na = 2",
        "[t]\nx = 1\n[t]\ny = 2",
        "a.b = 1\na.b = 2",
        "[t]\n[t.a]\n[t]",
        "a = 1\n[a]",
        "[a]\n[[a]]",
    ]
)


_big_key = st.just("k" * 10000 + " = 1")

_empty_containers = st.sampled_from(
    [
        "a = []",
        "a = {}",
        "[t]",
        "[[a]]",
        'a = ""',
        "a = ''",
        'a = """"""',
        "a = ''''''",
    ]
)


# Newly added edge cases targeting parser branches that the existing
# strategy rarely/never exercised: bare CR line endings, form-feed and
# vertical-tab whitespace, mixed CRLF/CR/LF documents, key/value
# separators with unusual surrounding whitespace, dotted keys with
# whitespace around the dot, quoted dotted keys, arrays with trailing
# commas / newlines, inline tables with trailing commas and newlines,
# heterogeneous arrays, multiline basic strings with line-ending
# backslash continuation, and inline comments adjacent to values.
_extra_edge_cases = st.one_of(
    # bare CR line endings
    st.sampled_from(
        [
            "a = 1\rb = 2",
            "a = 1\r\nb = 2\rc = 3",
            "[t]\rx = 1",
            "a = 1\r",
            "\ra = 1",
        ]
    ),
    # unusual whitespace characters between tokens
    st.sampled_from(
        [
            "a\x0b= 1",
            "a = \x0b1",
            "a = 1\x0c",
            "a\x0c= 1",
            "\x0ca = 1",
            "a\t=\t1",
            "a = 1\t# c",
            "a = [\x0b1\x0b,\x0b2\x0b]",
            "a = {\x0bb\x0b=\x0b1\x0b}",
        ]
    ),
    # mixed line endings in one document
    st.sampled_from(
        [
            "a = 1\r\nb = 2\nc = 3\rd = 4",
            "[t]\r\nx = 1\r\ny = 2\n",
            "a = 1\n\rb = 2",
        ]
    ),
    # dotted keys with whitespace around the dot
    st.sampled_from(
        [
            "a . b = 1",
            "a. b = 1",
            "a .b = 1",
            "a\t.\tb = 1",
            "a.b.c = 1",
            "a . b . c = 1",
            "[a . b]",
            "[a . b]\nc = 1",
        ]
    ),
    # quoted keys inside dotted keys
    st.sampled_from(
        [
            '"a".b = 1',
            'a."b" = 1',
            "'a'.'b' = 1",
            '"a.b".c = 1',
            '"a".b.c = 1',
            '["a"."b"]',
        ]
    ),
    # arrays: trailing commas, newlines, mixed types
    st.sampled_from(
        [
            "a = [1,]",
            "a = [1, 2,]",
            "a = [\n1,\n2,\n]",
            "a = [\n]",
            "a = [\r\n1\r\n]",
            "a = [1, 'x', true, 1979-05-27]",
            "a = [[1], [2, 3], []]",
            "a = [{b = 1}, {c = 2}]",
            "a = [1, # c\n2]",
            "a = [ ]",
        ]
    ),
    # inline tables: trailing commas, newlines, nested
    st.sampled_from(
        [
            "a = {b = 1,}",
            "a = {b = 1, c = 2,}",
            "a = {\nb = 1,\n}",
            "a = {\r\nb = 1\r\n}",
            "a = {b = {c = 1}}",
            "a = {b = [1, 2], c = {d = 3}}",
            "a = { }",
            "a = {b = 1 # c\n}",
        ]
    ),
    # multiline basic string line-ending backslash continuation
    st.sampled_from(
        [
            'a = """line1 \\\nline2"""',
            'a = """line1 \\\r\nline2"""',
            'a = """line1 \\\n   line2"""',
            'a = """\\\n"""',
            'a = """a\\\nb"""',
        ]
    ),
    # comments in unusual positions
    st.sampled_from(
        [
            "#only comment",
            "#\na = 1",
            "a = 1 # trailing",
            "a = 1  # double space",
            "\t# indented comment",
            "[t] # after table",
            "[[t]] # after array table",
            "a = 1\n# between\nb = 2",
        ]
    ),
    # whitespace-only / empty-ish documents
    st.sampled_from(
        [
            "",
            "\n",
            "\r\n",
            "\r",
            "   ",
            "\t\t",
            "\n\n\n",
            " \n \n ",
        ]
    ),
    # value/key boundary stress
    st.sampled_from(
        [
            "a=1",
            "a= 1",
            "a =1",
            "a\t=\t1",
            "a = true",
            "a=true",
            "a = false",
            "a = 1979-05-27T07:32:00Z",
            "a=1979-05-27",
        ]
    ),
)


_edge_cases = st.one_of(
    _malformed_string,
    _stray,
    _duplicate_keys,
    _big_key,
    _empty_containers,
    _deep_array,
    _deep_inline,
    _deep_array_value,
    _extra_edge_cases,
)


# NEW: branches the generator previously never reached — control
# characters inside strings, \u/\U escapes with invalid/surrogate
# values, unterminated multiline strings with embedded quotes,
# CRLF inside multiline strings, escape-at-EOF, table headers with
# quoted keys, dotted array-of-tables with whitespace, and
# key/value pairs split across CR-only line endings.
_more_edge_cases = st.sampled_from(
    [
        # control chars and DEL, NUL inside quoted strings
        'a = "x\x00y"',
        'a = "x\x01y"',
        'a = "x\x7fy"',
        "a = 'x\x00y'",
        "a = 'x\x7fy'",
        'a = """x\x00y"""',
        "a = '''x\x00y'''",
        # escapes with surrogate / out-of-range codepoints
        'a = "\\uD800"',
        'a = "\\uDFFF"',
        'a = "\\u0000"',
        'a = "\\U00110000"',
        'a = "\\UFFFFFFFF"',
        'a = "\\uD83D\\uDE00"',
        'a = "\\U0001F600"',
        # unterminated multiline strings containing quotes
        'a = """x"',
        'a = """x""',
        "a = '''x'",
        "a = '''x''",
        'a = """\n',
        "a = '''\n",
        # CRLF inside multiline strings
        'a = """line1\r\nline2"""',
        "a = '''line1\r\nline2'''",
        'a = """a\rb"""',
        # escape at end of input
        'a = "\\',
        "a = '\\",
        'a = "\\u',
        'a = "\\u12',
        'a = "\\U0000000',
        # quoted keys in table headers
        '["a"]',
        "['a']",
        '["a"."b"]',
        '["a".b]',
        "[[\"a\"]]",
        "[['a']]",
        '[""]',
        "['']",
        # array-of-tables with dotted keys and whitespace
        "[[a . b]]",
        "[[ a.b ]]",
        "[[a.b.c]]\nx = 1",
        "[a.b]\n[a.b.c]\n[[a.b.d]]",
        # key/value split across CR-only lines
        "a\r=\r1",
        "a =\r1",
        "a\r= 1",
        # bare tokens that look like values but are invalid
        "a = 0x",
        "a = 0o",
        "a = 0b",
        "a = 0x_",
        "a = 1__0",
        "a = _1",
        "a = 1_",
        "a = +",
        "a = -",
        "a = .",
        "a = ..",
        "a = 1.",
        "a = 1.e",
        "a = 1e",
        "a = 1e+",
        "a = 1e-",
        "a = 1979-",
        "a = 1979-05-",
        "a = 1979-05-27T",
        "a = 1979-05-27T07:",
        "a = 1979-05-27T07:32:",
        "a = 1979-05-27T07:32:00.",
        "a = 1979-05-27T07:32:00+",
        "a = 1979-05-27T07:32:00+07:",
        # deeply nested unbalanced closers
        "a = ]]]",
        "a = }}}",
        "a = []]",
        "a = {}}",
        "a = [{]",
        "a = {[}]",
        # multiple equals and separators
        "a = = 1",
        "a == 1",
        "a = 1 =",
        "a b c = 1",
        # BOM and unicode whitespace variants
        "\ufeff",
        "\ufeff\ufeffa = 1",
        "a = 1\n\ufeffb = 2",
        "a\u00a0= 1",
        "a =\u00a01",
        "a\u2028= 1",
        # lone surrogates / noncharacters in literal strings
        "a = '\ud800'",
        "a = '\ufffe'",
        "a = '\uffff'",
        # empty quoted keys and dotted edge forms
        '"" = 1',
        "'' = 1",
        '""."" = 1',
        "a. = 1",
        ".a = 1",
        "a..b = 1",
        "[.]",
        "[a.]",
        "[.a]",
        "[[.]]",
        # trailing content after tables / values
        "[t] x = 1",
        "[[t]] y = 2",
        "a = 1 b = 2",
        "a = trueb",
        "a = 1true",
        "a = 1979-05-27x",
        # multiline string with only line endings
        'a = """\r\n\r\n"""',
        "a = '''\n\n'''",
        # comments with control characters
        "#\x00comment",
        "#\x7fcomment",
        "a = 1 #\x00",
        "# \ud800",
    ]
)


_edge_cases = st.one_of(
    _edge_cases,
    _more_edge_cases,
)


strategy = st.one_of(
    _document,
    _document_with_blank,
    _document_crlf,
    _document_with_trailing_nl,
    _edge_cases,
    # NEW: exercise parser branches around table headers and
    # key/value separators that the existing generators never reach:
    # whitespace inside table headers, empty/whitespace-only headers,
    # array-of-tables with dotted keys, headers followed immediately
    # by EOF, and values that are bare table-header-like tokens.
    st.sampled_from(
        [
            "[ a ]",
            "[a ]",
            "[ a]",
            "[\ta\t]",
            "[]",
            "[ ]",
            "[\t]",
            "[[]]",
            "[[ ]]",
            "[[a.b]]",
            "[[a . b]]",
            "[a.b.c.d]",
            "[[a.b.c]]",
            "[",
            "[[",
            "]]",
            "[a",
            "[[a",
            "a = [",
            "a = {",
            "a = {b",
            "a = {b =",
            "a = {b = 1",
            "a = {b = 1,",
            "a = {b = 1, c",
            "a = [1,",
            "a = [1, 2",
            "a = 1\n[",
            "a = 1\n[[",
            "[t\n",
            "[[t\n",
            "[t]x",
            "[[t]]x",
            "[t] a = 1",
            "a = 1 [t]",
            "a = 1\n[t]\n",
            "a = 1\n[[t]]\n",
            "\ufeffa = 1",
            "a = 1\ufeff",
            "a = \ufeff1",
        ]
    ),
)