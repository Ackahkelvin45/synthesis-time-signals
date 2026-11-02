from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

def _nz_text(alphabet, min_size=0, max_size=12):
    return st.text(alphabet=alphabet, min_size=min_size, max_size=max_size)


# Characters that are safe-ish for bare keys
_BARE_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

_unquoted_key = st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=16)

# Escapes allowed in basic strings
_SIMPLE_ESC = ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]


def _unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda cp: "\\u%04X" % cp if cp <= 0xFFFF else "\\U%08X" % cp
    )


_escape = st.one_of(
    st.sampled_from(_SIMPLE_ESC),
    _unicode_escape(),
    st.just("\\u0000"),
    st.just("\\uD800"),
    st.just("\\uDFFF"),
    st.just("\\U0010FFFF"),
)

# characters inside basic string: printable, non-ASCII, control (raw), tab
_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
    st.integers(min_value=0, max_value=0x08).map(chr),
    st.integers(min_value=0x0B, max_value=0x0C).map(chr),
    st.integers(min_value=0x0E, max_value=0x1F).map(chr),
    st.just("\t"),
)

_basic_content = st.lists(
    st.one_of(_basic_char, _escape), min_size=0, max_size=8
).map("".join)

_basic_string = _basic_content.map(lambda s: '"' + s + '"')

# literal strings: no escapes, no single quote, no newline
_literal_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="'"),
    st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
    st.integers(min_value=1, max_value=0x08).map(chr),
    st.integers(min_value=0x0B, max_value=0x0C).map(chr),
    st.integers(min_value=0x0E, max_value=0x1F).map(chr),
    st.just("\t"),
)
_literal_content = st.lists(_literal_char, min_size=0, max_size=8).map("".join)
_literal_string = _literal_content.map(lambda s: "'" + s + "'")

# multiline basic strings: allow newlines, escapes, quotes (not triple)
_ml_basic_char = st.one_of(
    _basic_char,
    st.just("\n"),
    st.just("\r\n"),
    st.just('"'),
    st.just('""'),
)
_ml_basic_content = st.lists(_ml_basic_char, min_size=0, max_size=6).map("".join)
_ml_basic_string = _ml_basic_content.map(lambda s: '"""' + s + '"""')

# multiline literal strings: allow newlines, quotes, apostrophes
_ml_literal_char = st.one_of(
    _literal_char,
    st.just("\n"),
    st.just("\r\n"),
    st.just("'"),
    st.just("''"),
)
_ml_literal_content = st.lists(_ml_literal_char, min_size=0, max_size=6).map("".join)
_ml_literal_string = _ml_literal_content.map(lambda s: "'''" + s + "'''")

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------- numbers ----------

_dec_digits = st.text(alphabet="0123456789", min_size=1, max_size=20)

_dec_int = st.one_of(
    st.integers(min_value=-(2**80), max_value=2**80).map(str),
    st.just("0"),
    st.just("007"),
    st.just("-0"),
    st.just("+0"),
    _dec_digits,
    _dec_digits.map(lambda s: "-" + s),
    st.just("1_000_000"),
    st.just("9" * 40),
    st.just("-" + "9" * 40),
)

_hex_int = st.one_of(
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=20).map(
        lambda s: "0x" + s
    ),
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=20).map(
        lambda s: "0X" + s
    ),
    st.text(alphabet="0123456789abcdefABCDEF_", min_size=1, max_size=20).map(
        lambda s: "0x" + s
    ),
    st.just("0x0"),
    st.just("0xFFFFFFFFFFFFFFFF"),
    st.just("0xDEADBEEF"),
    st.just("0xdead_beef"),
    st.just("0x_1"),
    st.just("0x"),
)
_oct_int = st.one_of(
    st.text(alphabet="01234567_", min_size=1, max_size=20).map(
        lambda s: "0o" + s
    ),
    st.just("0o0"),
    st.just("0o"),
    st.just("0o777777777777777777777"),
)
_bin_int = st.one_of(
    st.text(alphabet="01_", min_size=1, max_size=32).map(lambda s: "0b" + s),
    st.just("0b0"),
    st.just("0b"),
    st.just("0b1111111111111111111111111111111111111111111111111111111111111111"),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.just("1.0"),
    st.just("-1.0"),
    st.just("+1.0"),
    st.just("1."),
    st.just(".5"),
    st.just("0.0"),
    st.just("1e10"),
    st.just("1E-10"),
    st.just("1e+309"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("3.14159"),
    st.just("1_000.000_1"),
    st.just("6.626e-34"),
    st.just("224_617.445_991_228"),
    st.just("inf"),
    st.just("+inf"),
    st.just("-inf"),
    st.just("nan"),
    st.just("+nan"),
    st.just("-nan"),
    st.tuples(
        st.one_of(st.just(""), st.just("-"), st.just("+")),
        st.text(alphabet="0123456789", min_size=1, max_size=6),
        st.just("."),
        st.text(alphabet="0123456789", min_size=0, max_size=6),
    ).map(lambda t: "".join(t)),
)

# ---------- booleans ----------

_bool = st.sampled_from(["true", "false"])

# ---------- date-times ----------

_two = st.text(alphabet="0123456789", min_size=2, max_size=2)
_four = st.text(alphabet="0123456789", min_size=4, max_size=4)
_secfrac = st.text(alphabet="0123456789", min_size=1, max_size=6).map(lambda s: "." + s)
_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(
        st.sampled_from(["+", "-"]), _two, st.just(":"), _two
    ).map(lambda t: "".join(t)),
)
_partial_time = st.tuples(
    _two, st.just(":"), _two, st.just(":"), _two,
    st.one_of(st.just(""), _secfrac),
).map(lambda t: "".join(t))
_full_date = st.tuples(_four, st.just("-"), _two, st.just("-"), _two).map(
    lambda t: "".join(t)
)
_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(
    _full_date, _delim, _partial_time, _offset
).map(lambda t: "".join(t))
_local_date_time = st.tuples(_full_date, _delim, _partial_time).map(
    lambda t: "".join(t)
)
_local_date = _full_date
_local_time = _partial_time

_datetime = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    # calendar-invalid dates that the parser accepts
    st.just("1979-02-30"),
    st.just("2000-13-45"),
    st.just("0000-00-00"),
    st.just("1979-05-27 07:32:00Z"),
    st.just("1979-05-27T07:32:00"),
    st.just("07:32:00"),
    st.just("1979-05-27"),
)

# ---------- keys ----------

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(
    lambda parts: ".".join(parts)
)

_key = st.one_of(_simple_key, _dotted_key)

# ---------- recursive values: arrays and inline tables ----------
# Use st.recursive for the value grammar.

_value = st.deferred(lambda: _value_strategy)

_scalar = st.one_of(
    _string,
    _integer,
    _float,
    _bool,
    _datetime,
)

_array_inner = st.one_of(
    st.just(""),
    st.lists(
        st.tuples(_value, st.just(",")).map(lambda t: "".join(t)),
        min_size=1,
        max_size=4,
    ).map("".join),
    st.lists(
        st.tuples(_value, st.just(",")).map(lambda t: "".join(t)),
        min_size=1,
        max_size=4,
    ).map(lambda parts: "".join(parts) + ","),  # trailing comma
)

_array = _array_inner.map(lambda s: "[" + s + "]")

# inline table: at least non-empty; allow trailing comma (accepted by parser)
_inline_kv = st.tuples(
    _key, st.just(" = "), _value
).map(lambda t: "".join(t))

_inline_body = st.one_of(
    st.just(""),
    st.lists(_inline_kv, min_size=1, max_size=3).map(lambda xs: ", ".join(xs)),
    st.lists(_inline_kv, min_size=1, max_size=3).map(
        lambda xs: ", ".join(xs) + ","
    ),
)

_inline_table = _inline_body.map(lambda s: "{" + s + "}")

_value_strategy = st.one_of(_scalar, _array, _inline_table)

# ---------- deep nesting: arrays and inline tables up to ~2048 levels ----------

# Build deep nested arrays in the "interesting" band 1500-2048.
_deep_depth = st.integers(min_value=1500, max_value=2048)

_deep_array = _deep_depth.map(
    lambda d: "[" * d + "]" * d
)

_deep_inline = _deep_depth.map(
    lambda d: "{a = " * d + "1" + "}" * d
)

# ---------- comments, whitespace, lines ----------

_comment_body = st.one_of(
    st.text(
        alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
        min_size=0,
        max_size=20,
    ),
    st.text(
        alphabet=st.characters(min_codepoint=0x01, max_codepoint=0x08),
        min_size=0,
        max_size=8,
    ),
    st.text(
        alphabet=st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
        min_size=0,
        max_size=8,
    ),
)

_comment = _comment_body.map(lambda s: "#" + s)

_nl = st.sampled_from(["\n", "\r\n"])

# ---------- key-value pairs ----------

_key_value = st.tuples(
    _key,
    st.just(" = "),
    st.one_of(_value, _deep_array, _deep_inline),
    st.one_of(st.just(""), st.tuples(st.just(" "), _comment).map(lambda t: "".join(t))),
).map(lambda t: "".join(t))

# ---------- tables ----------

_standard_table = _key.map(lambda k: "[" + k + "]")

_array_table = _key.map(lambda k: "[[" + k + "]]")

# ---------- malformed / near-valid variants ----------

_malformed = st.one_of(
    # unterminated string
    st.just('a = "unterminated'),
    st.just("a = 'unterminated"),
    st.just('a = """unterminated'),
    # missing delimiter
    st.just("a = [1, 2"),
    st.just("a = {b = 1"),
    st.just("[table"),
    st.just("[[array"),
    # doubled delimiter
    st.just("a = [1, 2]]"),
    st.just("a = {b = 1}}"),
    st.just("[[table]]]"),
    # stray token
    st.just("a = 1 2 3"),
    st.just("a = @invalid"),
    st.just("a = = 1"),
    st.just("a b = 1"),
    st.just("a = "),
    st.just("= 1"),
    # invalid escape
    st.just('a = "\\q"'),
    # value on next line
    st.just("a =\n1"),
    # newline inside inline table
    st.just("a = {b = 1,\nc = 2}"),
    # duplicate key
    st.just("a = 1\na = 2"),
    # duplicate table
    st.just("[t]\n[t]"),
    # table + array table same name
    st.just("[t]\n[[t]]"),
    # non-ASCII bare key
    st.just("caf\u00e9 = 1"),
    # bare key with invalid char
    st.just("a$b = 1"),
)

# ---------- document assembly ----------

def _join_lines(lines):
    return "\n".join(lines)


_expression = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    _comment,
    st.just(""),
)

_document_lines = st.lists(_expression, min_size=0, max_size=10)

_document = _document_lines.map(_join_lines)

# empty / comment-only documents
_special_docs = st.one_of(
    st.just(""),
    st.just("\n"),
    st.just("\r\n"),
    st.just("# just a comment"),
    st.just("# comment\n"),
    st.just("# c1\n# c2\n"),
    st.just("[t]"),
    st.just("[[a]]"),
    st.just('"" = 1'),
    st.just("a = {b = 1,}"),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just('a = "x\x01y"'),
    st.just("# comment with \x01 control"),
    st.just("a = 1979-02-30"),
    st.just("a = 1e309"),
    st.just("a = " + "9" * 100),
    st.just("a = -" + "9" * 100),
    st.just('a = "\\u0000"'),
    st.just('a = "\\U0010FFFF"'),
    st.just("a = [1, 2, 3,]"),
    st.just("a = [\n  1,\n  2,\n]"),
    st.just("a = [\n  # comment\n  1,\n]"),
    st.just("a = { b = 1, c = 2 }"),
    st.just("a.b.c = 1"),
    st.just('a."b".c = 1'),
    st.just("[a.b.c]"),
    st.just("[a]\n[a.b]"),
    st.just("[a.b]\n[a]"),
    st.just("[[a]]\n[[a]]"),
    st.just("a = 1" + "\n" * 3 + "b = 2"),
    st.just("\ta = 1"),
    st.just("a\t=\t1"),
    st.just("a = 1\r\nb = 2\r\n"),
    st.just("a = " + "x" * 10000),
    st.just('a = "' + "x" * 10000 + '"'),
)

# ---------- production-gap targeted documents ----------
# The last run showed these productions were never accepted; add focused
# generators to exercise them directly.

_gap_docs = st.one_of(
    # BOOLEAN / bool_ (previously a coverage gap)
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        _bool,
    ).map(lambda t: "".join(t)),
    st.just("a = true"),
    st.just("a = false"),
    st.just("a = true\nb = false"),
    st.just("[t]\nx = true"),
    st.just("a = [true, false]"),
    st.just("a = {b = true, c = false}"),
    # ML_BASIC_STRING / ML_LITERAL_STRING
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        st.one_of(_ml_basic_string, _ml_literal_string),
    ).map(lambda t: "".join(t)),
    st.just('a = """\n"""'),
    st.just("a = '''\n'''"),
    st.just('a = """\\\n   line"""'),
    st.just("a = '''line1\nline2'''"),
    # INF / NAN
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    ).map(lambda t: "".join(t)),
    # HEX_INT / OCT_INT / BIN_INT (HEX_INT was the remaining gap)
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        _hex_int,
    ).map(lambda t: "".join(t)),
    st.just("a = 0xDEADBEEF"),
    st.just("a = 0x0"),
    st.just("a = 0xFFFFFFFFFFFFFFFF"),
    st.just("a = 0xdead_beef"),
    st.just("[t]\nx = 0x1F"),
    st.just("a = [0x1, 0x2]"),
    st.just("a = {b = 0x1, c = 0x2}"),
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        st.one_of(_oct_int, _bin_int),
    ).map(lambda t: "".join(t)),
    # OFFSET_DATE_TIME / LOCAL_DATE_TIME / LOCAL_TIME
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        st.one_of(_offset_date_time, _local_date_time, _local_time),
    ).map(lambda t: "".join(t)),
    # tables with these values
    st.tuples(
        _standard_table,
        _nl,
        _key_value,
    ).map(lambda t: "".join(t)),
)

# ---------- targeted divergence probes ----------
# The last run reported many divergences (parser accepted things the grammar
# would reject, or vice-versa). Focus on the classes seen in the divergence
# examples plus common TOML edge cases.

_divergence_probes = st.one_of(
    # calendar-invalid dates: parser accepts
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        st.one_of(
            st.just("1979-02-30"),
            st.just("2000-13-45"),
            st.just("0000-00-00"),
            st.just("2021-02-29"),
            st.just("9999-99-99"),
        ),
    ).map(lambda t: "".join(t)),
    # raw control chars inside basic strings
    st.tuples(
        _unquoted_key,
        st.just(' = "'),
        st.one_of(
            st.just("\x00"),
            st.just("\x01"),
            st.just("\x1f"),
            st.just("\x7f"),
            st.just("\x80"),
        ),
        st.just('"'),
    ).map(lambda t: "".join(t)),
    # trailing comma in inline table
    st.tuples(
        _unquoted_key,
        st.just(" = {"),
        _unquoted_key,
        st.just(" = "),
        _value,
        st.just(",}"),
    ).map(lambda t: "".join(t)),
    # leading zeros in integers
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        st.sampled_from(["00", "01", "007", "-00", "+00", "0_0", "0_1"]),
    ).map(lambda t: "".join(t)),
    # underscores in odd places
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        st.sampled_from(
            ["_1", "1_", "1__2", "0x_1", "0b_1", "0o_1", "1_.0", "1._0"]
        ),
    ).map(lambda t: "".join(t)),
    # plus sign on non-inf floats
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        st.sampled_from(["+0", "+1", "+1.0", "+1e10", "+0x1", "+0b1"]),
    ).map(lambda t: "".join(t)),
    # bare CR handling
    st.tuples(
        _unquoted_key,
        st.just(" = "),
        _value,
        st.just("\r"),
        _unquoted_key,
        st.just(" = "),
        _value,
    ).map(lambda t: "".join(t)),
    # empty quoted keys and dotted empties
    st.sampled_from(
        [
            '"" = 1',
            "'' = 1",
            '""."" = 1',
            "[a]\n[a]",
            "[[a]]\n[a]",
            "[a]\n[[a]]",
            "a.b = 1\na.b.c = 2",
            "a = 1\n[a]",
            "[a]\nb = 1\n[a.b]",
        ]
    ),
    # mixed newline styles
    st.tuples(
        _key_value,
        st.sampled_from(["\n", "\r\n", "\r"]),
        _key_value,
    ).map(lambda t: t[0] + t[1] + t[2]),
    # unicode escapes: lone surrogates, out of range
    st.sampled_from(
        [
            'a = "\\uD800"',
            'a = "\\uDFFF"',
            'a = "\\uDC00"',
            'a = "\\U00110000"',
            'a = "\\u"',
            'a = "\\u12"',
            'a = "\\uZZZZ"',
            'a = "\\x41"',
            'a = "\\e"',
        ]
    ),
    # multiline string edge cases
    st.sampled_from(
        [
            'a = """"""',
            "a = ''''''",
            'a = """\\"""',
            'a = """a"b"""',
            "a = '''a'b'''",
            'a = """\\\n"""',
            'a = """\r\n"""',
            'a = """\\\r\n"""',
        ]
    ),
    # time edge cases
    st.sampled_from(
        [
            "a = 24:00:00",
            "a = 23:59:60",
            "a = 00:00:00.999999999",
            "a = 1:2:3",
            "a = 07:32:00Z",
            "a = 07:32:00+24:00",
            "a = 1979-05-27T07:32:00+99:99",
            "a = 1979-05-27t07:32:00z",
        ]
    ),
    # table header oddities
    st.sampled_from(
        [
            "[]",
            "[[]]",
            "[ ]",
            "[a.]",
            "[.a]",
            "[a..b]",
            "[[a.b]]",
            "[a] # trailing comment",
            "[a]x",
            "[a] x",
            "a = 1 # c\n[t]",
        ]
    ),
)

# ---------- top-level strategy ----------

# Mix: complete documents, deep nesting, special/edge docs, malformed inputs,
# production-gap targeted documents, and divergence probes.
strategy = st.one_of(
    _document,
    _special_docs,
    _gap_docs,
    _divergence_probes,
    _deep_array.map(lambda s: "a = " + s),
    _deep_inline.map(lambda s: "a = " + s),
    _malformed,
    st.tuples(
        st.one_of(_document, _special_docs, _gap_docs, _divergence_probes),
        _nl,
        _malformed,
    ).map(lambda t: t[0] + t[1] + t[2]),
    # ensure no trailing newline sometimes
    st.tuples(
        st.one_of(_document, _special_docs, _gap_docs, _divergence_probes),
        st.just("\n"),
    ).map(lambda t: t[0] + t[1]),
)