```python
import json
from hypothesis import strategies as st


# --------------------------------------------------------------------------
# Low-level character / token pieces
# --------------------------------------------------------------------------

# Characters safe for bare (unquoted) keys: A-Za-z0-9_-
_bare_key_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyz"
         "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
         "0123456789_-")
)

_unquoted_key = st.text(_bare_key_char, min_size=1, max_size=12)

# Non-ASCII / odd characters used inside quoted strings
_weird_string_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
    st.sampled_from(["\t", "\r", "\n", "\x01", "\x1f", "\x7f", "\x0b", "\x0c"]),
)

_escape_seq = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
     "\\u0041", "\\u00e9", "\\u0000", "\\U0001F600", "\\U00000041"]
)

# --------------------------------------------------------------------------
# Strings (all four quoting forms)
# --------------------------------------------------------------------------

def _basic_string_body():
    return st.one_of(
        st.text(
            st.one_of(
                st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
                    lambda c: c not in '"\\'
                ),
                st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
                st.sampled_from(["\t", "\x01", "\x1f", "\x7f"]),
            ),
            max_size=20,
        ),
        st.lists(_escape_seq, max_size=4).map("".join),
    )


_basic_string = st.one_of(
    st.just('""'),
    _basic_string_body().map(lambda s: '"' + s + '"'),
)

_literal_string = st.one_of(
    st.just("''"),
    st.text(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
                lambda c: c != "'"
            ),
            st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
            st.sampled_from(["\t", "\x01", "\x1f"]),
        ),
        max_size=20,
    ).map(lambda s: "'" + s + "'"),
)


def _ml_basic_body():
    return st.one_of(
        st.text(
            st.one_of(
                st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
                    lambda c: c not in '"\\'
                ),
                st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
                st.sampled_from(["\n", "\t", "\r", "\x01"]),
            ),
            max_size=30,
        ),
        st.lists(_escape_seq, max_size=4).map("".join),
    )


_ml_basic_string = st.one_of(
    st.just('""""""'),
    _ml_basic_body().map(lambda s: '"""' + s + '"""'),
)

_ml_literal_string = st.one_of(
    st.just("''''''"),
    st.text(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
                lambda c: c != "'"
            ),
            st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
            st.sampled_from(["\n", "\t", "\x01"]),
        ),
        max_size=30,
    ).map(lambda s: "'''" + s + "'''"),
)

_string_value = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# --------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 63), max_value=2 ** 63).map(str),
    st.integers(min_value=-(10 ** 30), max_value=10 ** 30).map(str),
    st.sampled_from(["0", "007", "-0", "+0", "1_000", "1_2_3",
                     "9223372036854775807", "9223372036854775808",
                     "-9223372036854775808", "-9223372036854775809"]),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0x" + format(n, "x")),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF",
                     "0x1_2_3"]),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 32).map(lambda n: "0o" + format(n, "o")),
    st.sampled_from(["0o0", "0o777", "0o7_7_7", "0o01234567"]),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=2 ** 32).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from(["0b0", "0b1", "0b1010_1010", "0b11111111"]),
)

_integer_value = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float_value = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from([
        "1.", ".5", "1.0", "3.14159", "1e10", "1E10", "1e+10", "1e-10",
        "1.5e10", "1.5E-10", "6.02e23", "1e309", "-1e309", "1e-309",
        "0.0", "-0.0", "1_000.000_1", "inf", "-inf", "+inf", "nan",
        "-nan", "+nan", "1e1_0",
    ]),
)

# --------------------------------------------------------------------------
# Booleans / dates
# --------------------------------------------------------------------------

_bool_value = st.sampled_from(["true", "false"])

_date_value = st.one_of(
    st.sampled_from([
        "1979-05-27", "1979-05-27T07:32:00", "1979-05-27T00:32:00.999999",
        "1979-05-27T07:32:00Z", "1979-05-27T07:32:00-07:00",
        "1979-05-27 07:32:00Z", "07:32:00", "00:32:00.999999",
        "1979-02-30", "1979-13-45", "0000-00-00", "9999-99-99",
        "1979-05-27t07:32:00z",
    ]),
    st.builds(
        lambda y, mo, d, h, mi, s: f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}Z",
        y=st.integers(0, 9999),
        mo=st.integers(0, 99),
        d=st.integers(0, 99),
        h=st.integers(0, 99),
        mi=st.integers(0, 99),
        s=st.integers(0, 99),
    ),
)

# --------------------------------------------------------------------------
# Keys
# --------------------------------------------------------------------------

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(".".join)

_key = st.one_of(_simple_key, _dotted_key)

# --------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# --------------------------------------------------------------------------

# A "leaf" value that is non-recursive
_leaf_value = st.one_of(
    _string_value,
    _integer_value,
    _float_value,
    _bool_value,
    _date_value,
)

# Build the recursive value strategy.
# Depth band: concentrate interesting depth around 1-64 for arrays/inline
# tables (the parser recurses per level; deep nesting up to ~2048 parses).
_recursive_value = st.recursive(
    _leaf_value,
    lambda children: st.one_of(
        # Arrays
        st.one_of(
            st.just("[]"),
            st.just("[\n]"),
            st.lists(children, min_size=1, max_size=4).map(
                lambda xs: "[" + ", ".join(xs) + "]"
            ),
            st.lists(children, min_size=1, max_size=4).map(
                lambda xs: "[ " + ", ".join(xs) + ", ]"
            ),
            # multiline array with comments
            st.lists(children, min_size=1, max_size=3).map(
                lambda xs: "[\n  # comment\n  " + ",\n  ".join(xs) + ",\n]"
            ),
        ),
        # Inline tables
        st.one_of(
            st.just("{}"),
            st.lists(
                st.tuples(_key, children),
                min_size=1,
                max_size=4,
            ).map(
                lambda kvs: "{"
                + ", ".join(f"{k} = {v}" for k, v in kvs)
                + "}"
            ),
            st.lists(
                st.tuples(_key, children),
                min_size=1,
                max_size=4,
            ).map(
                lambda kvs: "{"
                + ", ".join(f"{k} = {v}" for k, v in kvs)
                + ",}"
            ),
        ),
    ),
    max_leaves=20,
)

_value = _recursive_value

# --------------------------------------------------------------------------
# Deep nesting: arrays nested N levels (1500-2048 band)
# --------------------------------------------------------------------------

_deep_nesting_depth = st.integers(min_value=1500, max_value=2048)

_deep_array = _deep_nesting_depth.map(
    lambda n: "[" * n + "0" + "]" * n
)

_deep_inline_table = _deep_nesting_depth.map(
    lambda n: "{a = " * n + "0" + "}" * n
)

# --------------------------------------------------------------------------
# Documents: key/value lines, tables, arrays of tables
# --------------------------------------------------------------------------

def _kv_line(key, value):
    return f"{key} = {value}"


_key_value_line = st.builds(_kv_line, _key, _value)

_standard_table = _key.map(lambda k: f"[{k}]")

_array_table = _key.map(lambda k: f"[[{k}]]")

_comment = st.one_of(
    st.just("#"),
    st.just("# comment"),
    st.text(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x7E),
            st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
            st.sampled_from(["\t", "\x01", "\x1f"]),
        ),
        max_size=30,
    ).map(lambda s: "# " + s),
)

_line = st.one_of(
    _key_value_line,
    _standard_table,
    _array_table,
    _comment,
    st.just(""),
)

_document = st.one_of(
    # empty document
    st.just(""),
    st.just("\n"),
    # comment-only
    st.lists(_comment, min_size=1, max_size=3).map("\n".join),
    # normal documents
    st.lists(_line, min_size=1, max_size=8).map("\n".join),
    st.lists(_line, min_size=1, max_size=8).map(lambda ls: "\n".join(ls) + "\n"),
    st.lists(_line, min_size=1, max_size=8).map(lambda ls: "\r\n".join(ls)),
    # with tab indentation
    st.lists(_line, min_size=1, max_size=6).map(
        lambda ls: "\n".join("\t" + l for l in ls)
    ),
    # deep nesting documents
    _deep_array.map(lambda a: "a = " + a),
    _deep_inline_table.map(lambda a: "a = " + a),
)

# --------------------------------------------------------------------------
# Near-valid-but-malformed inputs
# --------------------------------------------------------------------------

_malformed = st.one_of(
    # one missing delimiter
    st.just("a = [1, 2, 3"),
    st.just("a = {b = 1"),
    st.just("[table"),
    st.just("[[array_table]"),
    st.just("a = "),
    st.just("= 1"),
    st.just("a = \"unterminated"),
    st.just("a = 'unterminated"),
    st.just('a = """unterminated'),
    st.just("a = '''unterminated"),
    # doubled delimiter
    st.just("a = [[1, 2, 3]]"),
    st.just("a = {{b = 1}}"),
    st.just("[[[table]]]"),
    st.just("a = 1 = 2"),
    # stray token
    st.just("a = 1 @"),
    st.just("@ = 1"),
    st.just("a = 1 b = 2"),
    st.just("a = [1, 2, ]"),
    st.just("a = {b = 1, c}"),
    st.just("a = {b = 1 c = 2}"),
    # invalid escape
    st.just('a = "\\q"'),
    st.just('a = "\\x41"'),
    # newline inside inline table
    st.just("a = {b = 1,\nc = 2}"),
    # value on next line
    st.just("a =\n1"),
    # bare key with non-ASCII
    st.just("café = 1"),
    st.just("ключ = 1"),
    # duplicate keys
    st.just("a = 1\na = 2"),
    st.just("[t]\na = 1\n[t]\nb = 2"),
    st.just("[[a]]\n[[a]]"),
    st.just("[a]\n[a.b]\n[a]"),
    # table and array of tables with same name
    st.just("[a]\n[[a]]"),
    # redefining table through dotted key
    st.just("[a]\nb = 1\na.c = 2"),
    # raw NUL is forbidden; use escape instead
    st.just('a = "\\u0000"'),
)

# --------------------------------------------------------------------------
# UTF-8 decoding paths (exercises toml_utf8_to_ucs)
# --------------------------------------------------------------------------

# Raw multi-byte UTF-8 sequences embedded directly in strings, including
# overlong encodings, truncated sequences, and lone continuation bytes.
_utf8_sequence = st.one_of(
    # Valid 2-byte (U+0080..U+07FF)
    st.integers(min_value=0x80, max_value=0x7FF).map(
        lambda cp: chr(cp)
    ),
    # Valid 3-byte (U+0800..U+FFFF, excluding surrogates)
    st.integers(min_value=0x800, max_value=0xFFFF).filter(
        lambda cp: not (0xD800 <= cp <= 0xDFFF)
    ).map(chr),
    # Valid 4-byte (U+10000..U+10FFFF)
    st.integers(min_value=0x10000, max_value=0x10FFFF).map(chr),
    # Raw byte sequences as latin-1 decoded strings: these produce the
    # exact bytes when the parser reads them as UTF-8.
    st.lists(
        st.integers(min_value=0x80, max_value=0xFF),
        min_size=1,
        max_size=4,
    ).map(lambda bs: bytes(bs).decode("latin-1")),
    # Truncated multi-byte sequences (lead byte only)
    st.sampled_from(["\xc2", "\xe0", "\xf0", "\xf4"]),
    # Overlong / invalid sequences
    st.sampled_from([
        "\xc0\x80",   # overlong NUL
        "\xc1\xbf",   # overlong
        "\xe0\x80\x80",  # overlong
        "\xf0\x80\x80\x80",  # overlong
        "\xed\xa0\x80",  # surrogate U+D800
        "\xed\xbf\xbf",  # surrogate U+DFFF
        "\xf4\x90\x80\x80",  # > U+10FFFF
        "\xff",          # invalid byte
        "\xfe",          # invalid byte
        "\x80",          # lone continuation
        "\xbf",          # lone continuation
    ]),
)

_utf8_string = st.lists(
    _utf8_sequence, min_size=1, max_size=4
).map(lambda parts: '"' + "".join(parts) + '"')

_utf8_document = st.one_of(
    _utf8_string.map(lambda s: "a = " + s),
    _utf8_string.map(lambda s: "a = " + s + "\n"),
    _utf8_string.map(lambda s: "k = " + s),
    _utf8_string.map(lambda s: "[t]\na = " + s),
)

# --------------------------------------------------------------------------
# Dedicated toml_utf8_to_ucs coverage: raw multi-byte UTF-8 byte sequences
# placed in every string context (basic, literal, multiline, comments, keys)
# to drive the UTF-8 -> UCS conversion routine through all its branches.
# --------------------------------------------------------------------------

def _raw_utf8_bytes():
    """Generate raw UTF-8 byte sequences (valid, overlong, truncated, invalid)."""
    return st.one_of(
        # Valid 2-byte lead + continuation
        st.tuples(
            st.integers(min_value=0xC2, max_value=0xDF),
            st.integers(min_value=0x80, max_value=0xBF),
        ).map(lambda t: bytes(t).decode("latin-1")),
        # Valid 3-byte
        st.tuples(
            st.integers(min_value=0xE0, max_value=0xEF),
            st.integers(min_value=0x80, max_value=0xBF),
            st.integers(min_value=0x80, max_value=0xBF),
        ).map(lambda t: bytes(t).decode("latin-1")),
        # Valid 4-byte
        st.tuples(
            st.integers(min_value=0xF0, max_value=0xF4),
            st.integers(min_value=0x80, max_value=0xBF),
            st.integers(min_value=0x80, max_value=0xBF),
            st.integers(min_value=0x80, max_value=0xBF),
        ).map(lambda t: bytes(t).decode("latin-1")),
        # Overlong 2-byte
        st.tuples(
            st.integers(min_value=0xC0, max_value=0xC1),
            st.integers(min_value=0x80, max_value=0xBF),
        ).map(lambda t: bytes(t).decode("latin-1")),
        # Overlong 3-byte
        st.tuples(
            st.just(0xE0),
            st.integers(min_value=0x80, max_value=0x9F),
            st.integers(min_value=0x80, max_value=0xBF),
        ).map(lambda t: bytes(t).decode("latin-1")),
        # Overlong 4-byte
        st.tuples(
            st.just(0xF0),
            st.integers(min_value=0x80, max_value=0x8F),
            st.integers(min_value=0x80, max_value=0xBF),
            st.integers(min_value=0x80, max_value=0xBF),
        ).map(lambda t: bytes(t).decode("latin-1")),
        # Surrogate range (U+D800..U+DFFF) encoded
        st.tuples(
            st.just(0xED),
            st.integers(min_value=0xA0, max_value=0xBF),
            st.integers(min_value=0x80, max_value=0xBF),
        ).map(lambda t: bytes(t).decode("latin-1")),
        # > U+10FFFF (F4 90..BF ...)
        st.tuples(
            st.just(0xF4),
            st.integers(min_value=0x90, max_value=0xBF),
            st.integers(min_value=0x80, max_value=0xBF),
            st.integers(min_value=0x80, max_value=0xBF),
        ).map(lambda t: bytes(t).decode("latin-1")),
        # Truncated sequences (lead byte only)
        st.sampled_from(["\xc2", "\xdf", "\xe0", "\xef", "\xf0", "\xf4"]),
        # Lone continuation bytes
        st.integers(min_value=0x80, max_value=0xBF).map(
            lambda b: bytes([b]).decode("latin-1")
        ),
        # Invalid lead bytes
        st.sampled_from(["\xff", "\xfe", "\xf5", "\xf8", "\xfc"]),
    )


# A run of raw UTF-8 byte sequences
_utf8_byte_run = st.lists(
    _raw_utf8_bytes(), min_size=1, max_size=6
).map("".join)

# Embed raw UTF-8 bytes in each string context to drive toml_utf8_to_ucs
_utf8_ucs_doc = st.one_of(
    # Basic strings
    _utf8_byte_run.map(lambda s: 'a = "' + s + '"'),
    _utf8_byte_run.map(lambda s: 'a = "' + s + '"\n'),
    # Literal strings
    _utf8_byte_run.map(lambda s: "a = '" + s + "'"),
    # Multiline basic strings
    _utf8_byte_run.map(lambda s: 'a = """' + s + '"""'),
    # Multiline literal strings
    _utf8_byte_run.map(lambda s: "a = '''" + s + "'''"),
    # In comments
    _utf8_byte_run.map(lambda s: "# " + s),
    # In bare context (parser must decode before rejecting)
    _utf8_byte_run.map(lambda s: s),
    _utf8_byte_run.map(lambda s: s + " = 1"),
    # In table headers
    _utf8_byte_run.map(lambda s: "[" + s + "]"),
    _utf8_byte_run.map(lambda s: "[[" + s + "]]"),
    # In keys
    _utf8_byte_run.map(lambda s: s + " = 1\n"),
    # Multiple sequences mixed with ASCII
    _utf8_byte_run.map(lambda s: 'a = "x' + s + 'y"'),
)

# --------------------------------------------------------------------------
# Final strategy
# --------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _malformed,
    _utf8_document,
    _utf8_ucs_doc,
    _value.map(lambda v: "a = " + v),
    _value.map(lambda v: "a = " + v + "\n"),
)
```