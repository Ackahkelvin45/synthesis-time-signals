```python
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
    # invalid / near-miss escapes to probe error handling
    st.just("\\q"),
    st.just("\\x41"),
    st.just("\\u12"),
    st.just("\\U0001"),
    st.just("\\ "),
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
    st.text(alphabet="0123456789abcdefABCDEF_", min_size=1, max_size=20).map(
        lambda s: "0x" + s
    ),
    st.just("0x0"),
    st.just("0xFFFFFFFFFFFFFFFF"),
)
_oct_int = st.text(alphabet="01234567_", min_size=1, max_size=20).map(
    lambda s: "0o" + s
)
_bin_int = st.text(alphabet="01_", min_size=1, max_size=32).map(lambda s: "0b" + s)

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

# ---------- top-level strategy ----------

# Mix: complete documents, deep nesting, special/edge docs, malformed inputs
strategy = st.one_of(
    _document,
    _special_docs,
    _deep_array.map(lambda s: "a = " + s),
    _deep_inline.map(lambda s: "a = " + s),
    _malformed,
    st.tuples(
        st.one_of(_document, _special_docs),
        _nl,
        _malformed,
    ).map(lambda t: t[0] + t[1] + t[2]),
    # ensure no trailing newline sometimes
    st.tuples(
        st.one_of(_document, _special_docs),
        st.just("\n"),
    ).map(lambda t: t[0] + t[1]),
    # long homogeneous documents: stress line/entry accumulation
    st.integers(min_value=50, max_value=500).map(
        lambda n: "\n".join("k%d = %d" % (i, i) for i in range(n))
    ),
    # many array elements
    st.integers(min_value=50, max_value=500).map(
        lambda n: "a = [" + ", ".join(str(i) for i in range(n)) + "]"
    ),
    # many inline-table entries
    st.integers(min_value=20, max_value=200).map(
        lambda n: "a = {" + ", ".join("k%d = %d" % (i, i) for i in range(n)) + "}"
    ),
    # many nested tables
    st.integers(min_value=20, max_value=200).map(
        lambda n: "\n".join("[" + ".".join("t%d" % j for j in range(i + 1)) + "]" for i in range(n))
    ),
    # many array-of-tables
    st.integers(min_value=20, max_value=200).map(
        lambda n: "\n".join("[[a]]" for _ in range(n))
    ),
    # many comments
    st.integers(min_value=50, max_value=500).map(
        lambda n: "\n".join("# comment %d" % i for i in range(n))
    ),
    # deep dotted keys
    st.integers(min_value=20, max_value=200).map(
        lambda n: ".".join("k%d" % i for i in range(n)) + " = 1"
    ),
    # long strings of various kinds
    st.integers(min_value=1000, max_value=100000).map(
        lambda n: 'a = "' + "x" * n + '"'
    ),
    st.integers(min_value=1000, max_value=100000).map(
        lambda n: "a = '" + "x" * n + "'"
    ),
    st.integers(min_value=1000, max_value=50000).map(
        lambda n: 'a = """' + "x" * n + '"""'
    ),
    # long comment line
    st.integers(min_value=1000, max_value=100000).map(
        lambda n: "#" + "x" * n
    ),
    # long bare key
    st.integers(min_value=1000, max_value=100000).map(
        lambda n: "a" * n + " = 1"
    ),
    # deeply nested inline tables (moderate)
    st.integers(min_value=50, max_value=500).map(
        lambda d: "a = " + "{b = " * d + "1" + "}" * d
    ),
    # deeply nested arrays (moderate)
    st.integers(min_value=50, max_value=500).map(
        lambda d: "a = " + "[" * d + "]" * d
    ),
    # TOML documents with nested-table chains and mixed content: exercise
    # table-header state, key redefinition, and value parsing together.
    st.integers(min_value=1, max_value=40).map(
        lambda n: "\n".join(
            ("[t%d]" % i) + "\n" + "k%d = %d" % (i, i)
            + (("\narr = [" + ", ".join(str(j) for j in range(i % 5 + 1)) + "]") if i % 3 == 0 else "")
            for i in range(n)
        )
    ),
    # interleaved array-of-tables with per-table keys
    st.integers(min_value=1, max_value=40).map(
        lambda n: "\n".join(
            "[[items]]\nid = %d\nname = \"item%d\"\ntags = [\"a\", \"b\"]" % (i, i)
            for i in range(n)
        )
    ),
    # keys with quoted dotted segments and inline tables as values
    st.integers(min_value=1, max_value=30).map(
        lambda n: "\n".join(
            'a."b%d".c = {%s}' % (i, ", ".join('k%d = %d' % (j, j) for j in range(i % 4 + 1)))
            for i in range(n)
        )
    ),
    # ---------- IMPROVED: targeted grammar-boundary fuzzing ----------
    # CRLF-only documents and mixed line endings (parser line-ending handling)
    st.integers(min_value=1, max_value=200).map(
        lambda n: "\r\n".join("k%d = %d" % (i, i) for i in range(n)) + "\r\n"
    ),
    st.integers(min_value=1, max_value=100).map(
        lambda n: "".join(
            ("k%d = %d" % (i, i)) + ("\r\n" if i % 2 else "\n")
            for i in range(n)
        )
    ),
    # bare CR line endings (invalid per spec, must be rejected/handled)
    st.integers(min_value=1, max_value=50).map(
        lambda n: "\r".join("k%d = %d" % (i, i) for i in range(n))
    ),
    # multiline strings with leading newline trimming and embedded quotes
    st.integers(min_value=0, max_value=40).map(
        lambda n: 'a = """\n' + "\n".join("line %d" % i for i in range(n)) + '"""'
    ),
    st.integers(min_value=0, max_value=40).map(
        lambda n: "a = '''\n" + "\n".join("line %d" % i for i in range(n)) + "'''"
    ),
    # multiline strings containing near-triple quote runs
    st.integers(min_value=1, max_value=20).map(
        lambda n: 'a = """' + ('"' * (n % 2) + "x") * n + '"""'
    ),
    # mixed-type arrays exercising per-element dispatch
    st.lists(
        st.sampled_from(
            ["1", "1.5", "true", "false", '"s"', "'l'", "1979-05-27",
             "[1,2]", "{a = 1}", "inf", "nan", "0x10", "0o7", "0b1"]
        ),
        min_size=1,
        max_size=30,
    ).map(lambda xs: "a = [" + ", ".join(xs) + "]"),
    # heterogeneous inline tables with mixed value kinds
    st.lists(
        st.tuples(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
            st.sampled_from(
                ["1", "1.5", "true", '"s"', "[1,2]", "{x = 1}", "1979-05-27T00:00:00Z"]
            ),
        ),
        min_size=1,
        max_size=20,
    ).map(lambda kvs: "a = {" + ", ".join("%s = %s" % kv for kv in kvs) + "}"),
    # whitespace fuzzing around tokens (tabs, spaces, mixed)
    st.tuples(
        st.text(alphabet=" \t", min_size=0, max_size=4),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
        st.text(alphabet=" \t", min_size=0, max_size=4),
        st.just("="),
        st.text(alphabet=" \t", min_size=0, max_size=4),
        st.integers(min_value=0, max_value=100).map(str),
    ).map(lambda t: "".join(t)),
    # keys at boundary lengths (0, 1, and very long) and edge dotted keys
    st.sampled_from([
        'a = 1',
        '"" = 1',
        "'' = 1",
        'a."" = 1',
        '"" . b = 1',
        'a."b" = 1',
        '"a.b" = 1',
        "a.b.c.d.e.f.g.h = 1",
        'a = 1\n"" = 2',
        "a = 1\n'' = 2",
    ]),
    # table/array-table header edge cases
    st.sampled_from([
        "[]",
        "[[]]",
        "[.]",
        "[a.]",
        "[.a]",
        "[[a.] ]",
        "[ a ]",
        "[a . b]",
        '[a."b"]',
        "[\"a\"]",
        "['a']",
        "[a]\n[a.b]\n[a.b.c]",
        "[[a]]\n[a.b]",
        "[a.b]\n[[a]]",
    ]),
    # comment edge cases: at EOF without newline, control chars, CR inside
    st.integers(min_value=0, max_value=30).map(
        lambda n: "#" + "c" * n
    ),
    st.just("#"),
    st.just("#\r\n"),
    st.just("#\r"),
    st.just("a = 1 # trailing comment"),
    st.just("a = 1# no space comment"),
    # numeric boundary values: max/min ints, exponent extremes, underscores
    st.sampled_from([
        "a = 9223372036854775807",
        "a = -9223372036854775808",
        "a = 18446744073709551615",
        "a = 0x7FFFFFFFFFFFFFFF",
        "a = 0xFFFFFFFFFFFFFFFF",
        "a = 0o777777777777777777777",
        "a = 0b" + "1" * 64,
        "a = 1e-400",
        "a = 1e400",
        "a = -0.0",
        "a = +0.0",
        "a = 1_2_3",
        "a = 1__2",
        "a = _1",
        "a = 1_",
        "a = 0x_1",
        "a = 0o_1",
        "a = 0b_1",
        "a = 01",
        "a = 0x",
        "a = 0o",
        "a = 0b",
        "a = 0xg",
        "a = 0o8",
        "a = 0b2",
    ]),
    # datetime edge cases: leap seconds, extreme offsets, fractional precision
    st.sampled_from([
        "a = 1979-05-27T07:32:00.999999Z",
        "a = 1979-05-27T07:32:60Z",
        "a = 1979-05-27T23:59:60Z",
        "a = 1979-05-27T07:32:00+23:59",
        "a = 1979-05-27T07:32:00-23:59",
        "a = 1979-05-27T07:32:00.123456789",
        "a = 0000-01-01T00:00:00Z",
        "a = 9999-12-31T23:59:59Z",
        "a = 1979-05-27T07:32",
        "a = 1979-05-27T07",
        "a = 1979-05",
        "a = 07:32",
        "a = 07:32:00.999999",
    ]),
    # control-character fuzzing in strings and comments
    st.lists(
        st.integers(min_value=0, max_value=0x1F).map(chr),
        min_size=1,
        max_size=10,
    ).map(lambda cs: 'a = "' + "".join(cs) + '"'),
    st.lists(
        st.integers(min_value=0, max_value=0x1F).map(chr),
        min_size=1,
        max_size=10,
    ).map(lambda cs: "#" + "".join(cs)),
    # BOM and unusual leading bytes
    st.sampled_from([
        "\ufeffa = 1",
        "\ufeff",
        "\ufeff# comment",
        "\ufeff[table]",
    ]),
    # very long unbroken tokens (lexer buffer boundary probing)
    st.integers(min_value=1000, max_value=200000).map(
        lambda n: "a = " + "1" * n
    ),
    st.integers(min_value=1000, max_value=200000).map(
        lambda n: "#" + "x" * n
    ),
    # deeply nested mixed structures (arrays containing inline tables etc.)
    st.integers(min_value=10, max_value=100).map(
        lambda d: "a = " + "[{b = " * d + "1" + "}]" * d
    ),
    # arrays with trailing commas and comments interleaved
    st.integers(min_value=1, max_value=50).map(
        lambda n: "a = [\n" + "\n".join("  %d," % i for i in range(n)) + "\n]"
    ),
    # keys that look like numbers/dates (parser must not confuse them)
    st.sampled_from([
        "1979-05-27 = 1",
        "1 = 2",
        "true = 1",
        "false = 1",
        "inf = 1",
        "nan = 1",
        "0x10 = 1",
    ]),
    # empty-value / whitespace-only edge documents
    st.sampled_from([
        " ",
        "\t",
        "\n\n\n",
        "   \n   \n",
        "\r\n\r\n",
        "\t\r\n\t",
    ]),
)
```