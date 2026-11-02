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
    # lowercase hex digits in escapes (exercises toml_utf8_to_ucs hex parsing)
    st.integers(min_value=0, max_value=0xFFFF).map(lambda cp: "\\u%04x" % cp),
    st.integers(min_value=0x10000, max_value=0x10FFFF).map(
        lambda cp: "\\U%08x" % cp
    ),
    # short / malformed hex escapes to hit error paths
    st.just("\\u0"),
    st.just("\\u00"),
    st.just("\\u000"),
    st.just("\\U0000000"),
    st.just("\\uZZZZ"),
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

# Floats: exercise toml_rtod_ex (exponent handling, sign, fraction, inf/nan)
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
    # explicit exponent forms to drive toml_rtod_ex
    st.tuples(
        st.one_of(st.just(""), st.just("-"), st.just("+")),
        st.text(alphabet="0123456789", min_size=1, max_size=6),
        st.one_of(st.just(""), st.just(".")),
        st.text(alphabet="0123456789", min_size=0, max_size=6),
        st.sampled_from(["e", "E"]),
        st.one_of(st.just(""), st.just("-"), st.just("+")),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(lambda t: "".join(t)),
    # uppercase INF/NAN
    st.sampled_from(["INF", "+INF", "-INF", "NAN", "+NAN", "-NAN"]),
    # underscores in exponent / fraction
    st.just("1_0e1_0"),
    st.just("1.0_1e1_0"),
    # malformed floats
    st.just("1e"),
    st.just("1e+"),
    st.just("1."),
    st.just(".e1"),
    st.just("1__0.0"),
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

# ---------- targeted strategies for uncovered functions ----------
# These aim to exercise toml_utf8_to_ucs, toml_rtots, toml_rtod_ex,
# toml_parse_file, and norm_lit_str.

# toml_utf8_to_ucs: driven by \u/\U escapes (valid + invalid hex, lowercase).
_ucs_escape = st.one_of(
    st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda cp: "\\u%04X" % cp if cp <= 0xFFFF else "\\U%08X" % cp
    ),
    st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda cp: "\\u%04x" % cp if cp <= 0xFFFF else "\\U%08x" % cp
    ),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda cp: "\\u%04X" % cp),
    st.integers(min_value=0x10000, max_value=0x10FFFF).map(
        lambda cp: "\\U%08X" % cp
    ),
    # surrogates
    st.just("\\uD800"),
    st.just("\\uDFFF"),
    st.just("\\uDC00"),
    # malformed
    st.just("\\u"),
    st.just("\\U"),
    st.just("\\u0"),
    st.just("\\U0000"),
    st.just("\\uGGGG"),
)

_ucs_string = st.tuples(
    st.just('"'),
    st.lists(
        st.one_of(
            _ucs_escape,
            st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
            st.characters(min_codepoint=0x1F600, max_codepoint=0x1F64F),
            st.just("abc"),
        ),
        min_size=1,
        max_size=6,
    ).map("".join),
    st.just('"'),
).map(lambda t: "".join(t))

# toml_rtots: date-time parsing from strings.  Feed datetimes as quoted strings
# so the parser routes through toml_rtots.
_rtots_string = st.tuples(
    st.just('"'),
    _datetime,
    st.just('"'),
).map(lambda t: "".join(t))

# norm_lit_str: literal strings, especially with CRLF / newlines in
# multiline literal strings, and multi-byte UTF-8.
_norm_lit_string = st.one_of(
    st.tuples(
        st.just("'''"),
        st.lists(
            st.one_of(
                st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                              blacklist_characters="'"),
                st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
                st.characters(min_codepoint=0x1F600, max_codepoint=0x1F64F),
                st.just("\r\n"),
                st.just("\n"),
                st.just("\t"),
            ),
            min_size=0,
            max_size=10,
        ).map("".join),
        st.just("'''"),
    ).map(lambda t: "".join(t)),
    st.tuples(
        st.just("'"),
        st.lists(
            st.one_of(
                st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                              blacklist_characters="'"),
                st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
                st.characters(min_codepoint=0x1F600, max_codepoint=0x1F64F),
                st.just("\t"),
            ),
            min_size=0,
            max_size=10,
        ).map("".join),
        st.just("'"),
    ).map(lambda t: "".join(t)),
)

# toml_rtod_ex: floats with explicit exponent forms.
_rtod_float = st.tuples(
    st.one_of(st.just(""), st.just("-"), st.just("+")),
    st.text(alphabet="0123456789", min_size=1, max_size=8),
    st.one_of(st.just(""), st.just(".")),
    st.text(alphabet="0123456789", min_size=0, max_size=8),
    st.sampled_from(["e", "E"]),
    st.one_of(st.just(""), st.just("-"), st.just("+")),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map(lambda t: "".join(t))

_targeted_kv = st.tuples(
    st.sampled_from(["a", "k", "x_y", "n"]),
    st.just(" = "),
    st.one_of(
        _ucs_string,
        _rtots_string,
        _norm_lit_string,
        _rtod_float,
    ),
).map(lambda t: "".join(t))

# toml_parse_file: multi-line documents exercising the file-level parsing
# path (header + several key-values + tables + comments + blank lines).
_file_doc = st.lists(
    st.one_of(
        _targeted_kv,
        _key_value,
        _standard_table,
        _array_table,
        _comment,
        st.just(""),
    ),
    min_size=1,
    max_size=12,
).map(_join_lines)

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
    # exercise UTF-8 decoding / escape conversion paths (toml_utf8_to_ucs,
    # toml_rtots, norm_lit_str, toml_rtos) which showed 0% coverage.
    # Multi-line strings with escapes, multi-byte UTF-8, and CRLF content
    # force the parser through those conversion routines.
    st.tuples(
        st.sampled_from(["a", "k", "x_y"]),
        st.just(" = "),
        st.one_of(
            # basic multiline with escapes forcing utf8<->ucs conversion
            st.tuples(
                st.just('"""'),
                st.lists(
                    st.one_of(
                        _escape,
                        _ucs_escape,
                        st.just("\n"),
                        st.just("\r\n"),
                        st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
                        st.characters(min_codepoint=0x1F600, max_codepoint=0x1F64F),
                        st.just('"'),
                    ),
                    min_size=1,
                    max_size=8,
                ).map("".join),
                st.just('"""'),
            ).map(lambda t: "".join(t)),
            # literal multiline with multi-byte UTF-8 + CRLF
            st.tuples(
                st.just("'''"),
                st.lists(
                    st.one_of(
                        st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
                        st.characters(min_codepoint=0x1F600, max_codepoint=0x1F64F),
                        st.just("\r\n"),
                        st.just("\n"),
                    ),
                    min_size=1,
                    max_size=8,
                ).map("".join),
                st.just("'''"),
            ).map(lambda t: "".join(t)),
            # single-line basic string with multi-byte UTF-8 and escapes
            st.tuples(
                st.just('"'),
                st.lists(
                    st.one_of(
                        _escape,
                        _ucs_escape,
                        st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
                        st.characters(min_codepoint=0x1F600, max_codepoint=0x1F64F),
                    ),
                    min_size=1,
                    max_size=8,
                ).map("".join),
                st.just('"'),
            ).map(lambda t: "".join(t)),
        ),
    ).map(lambda t: "".join(t)),
    # targeted per-function strategies
    _targeted_kv,
    _file_doc,
    # targeted value inside a document with surrounding context
    st.tuples(
        st.one_of(st.just(""), _comment),
        _nl,
        _targeted_kv,
        _nl,
        st.one_of(st.just(""), _comment),
    ).map(lambda t: "".join(t)),
)