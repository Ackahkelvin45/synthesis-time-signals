from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Characters that are safe inside strings (no NUL). Include control chars,
# non-ASCII, quotes, backslashes, etc.
_SAFE_CHARS = (
    "\t\r\n"
    " !#$%&()*+,-./:;<=>?@[]^_`{|}~"
    "'\"\\"
    "abcXYZ019"
    "\x01\x02\x03\x07\x08\x0b\x0c\x1b\x7f"
    "\u00e9\u4e2d\u6587\U0001F600"
)

# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]
    + ["\\u%04x" % i for i in (0, 1, 9, 0x7F, 0xE9, 0x4E2D)]
    + ["\\U%08x" % i for i in (0, 0x1F600, 0x10FFFF)]
)

# single-line basic string body
_basic_body = st.one_of(
    st.text(alphabet=_SAFE_CHARS, max_size=12).filter(lambda s: "\n" not in s),
    _escapes,
)

_basic_string = st.lists(_basic_body, max_size=6).map(lambda parts: '"' + "".join(parts) + '"')

# literal string (no escapes, no newline)
_literal_string = (
    st.text(alphabet=_SAFE_CHARS, max_size=12)
    .filter(lambda s: "\n" not in s and "'" not in s)
    .map(lambda s: "'" + s + "'")
)

# multiline basic string
_ml_basic_string = st.lists(
    st.one_of(
        st.text(alphabet=_SAFE_CHARS, max_size=10),
        _escapes,
    ),
    max_size=5,
).map(lambda parts: '"""' + "".join(parts) + '"""')

# multiline literal string
_ml_literal_string = st.lists(
    st.text(alphabet=_SAFE_CHARS, max_size=10),
    max_size=5,
).map(lambda parts: "'''" + "".join(parts) + "'''")

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-(2**63), max_value=2**63).map(str),
    st.integers(min_value=-(2**80), max_value=2**80).map(str),
    st.sampled_from(
        [
            "0",
            "007",
            "-0",
            "+0",
            "1_000",
            "1_0_0",
            "9223372036854775807",
            "9223372036854775808",
            "-9223372036854775808",
            "99999999999999999999999999999999999999",
        ]
    ),
)

_hex_int = st.integers(min_value=0, max_value=2**80).map(lambda n: "0x" + format(n, "x"))
_oct_int = st.integers(min_value=0, max_value=2**80).map(lambda n: "0o" + format(n, "o"))
_bin_int = st.integers(min_value=0, max_value=2**80).map(lambda n: "0b" + format(n, "b"))

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(
        [
            "1.",
            ".5",
            "1.0",
            "3.14",
            "1e10",
            "1E10",
            "1e+10",
            "1e-10",
            "1_000.000_1",
            "1e309",
            "-1e309",
            "1.5e-300",
            "0.0",
            "-0.0",
            "+1.0",
            "inf",
            "-inf",
            "+inf",
            "nan",
            "-nan",
            "+nan",
        ]
    ),
)

_bool = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Date-times
# ---------------------------------------------------------------------------

_date = st.builds(
    lambda y, m, d: "%04d-%02d-%02d" % (y, m, d),
    st.integers(min_value=0, max_value=9999),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
)

_time = st.builds(
    lambda h, mi, s, frac: "%02d:%02d:%02d%s" % (h, mi, s, frac),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.one_of(st.just(""), st.integers(min_value=0, max_value=999999).map(lambda n: ".%d" % n)),
)

_offset = st.one_of(
    st.just("Z"),
    st.builds(
        lambda sign, h, m: "%s%02d:%02d" % (sign, h, m),
        st.sampled_from(["+", "-"]),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ),
)

_delim = st.sampled_from(["T", "t", " "])

_offset_datetime = st.tuples(_date, _delim, _time, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)
_local_datetime = st.tuples(_date, _delim, _time).map(lambda t: t[0] + t[1] + t[2])
_local_date = _date
_local_time = _time

_datetime = st.one_of(
    _offset_datetime,
    _local_datetime,
    _local_date,
    _local_time,
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=10,
)

_quoted_key = st.one_of(
    _basic_string,
    _literal_string,
    st.just('""'),
)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Values (recursive)
# ---------------------------------------------------------------------------

_value = st.recursive(
    st.one_of(
        _string,
        _integer,
        _float,
        _bool,
        _datetime,
    ),
    lambda children: st.one_of(
        # arrays
        st.builds(
            lambda inner: "[" + inner + "]",
            st.one_of(
                st.just(""),
                st.lists(children, min_size=1, max_size=5).map(lambda vs: ", ".join(vs)),
                st.lists(children, min_size=1, max_size=5).map(
                    lambda vs: ", ".join(vs) + ","
                ),
                st.lists(children, min_size=1, max_size=5).map(
                    lambda vs: ",\n".join(vs)
                ),
                st.lists(children, min_size=1, max_size=5).map(
                    lambda vs: ", ".join(vs) + " # trailing comment"
                ),
            ),
        ),
        # inline tables
        st.builds(
            lambda inner: "{" + inner + "}",
            st.one_of(
                st.just(""),
                st.lists(
                    st.tuples(_key, children).map(lambda kv: "%s = %s" % (kv[0], kv[1])),
                    min_size=1,
                    max_size=4,
                ).map(lambda kvs: ", ".join(kvs)),
                st.lists(
                    st.tuples(_key, children).map(lambda kv: "%s = %s" % (kv[0], kv[1])),
                    min_size=1,
                    max_size=4,
                ).map(lambda kvs: ", ".join(kvs) + ","),
            ),
        ),
    ),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

_key_value = st.tuples(_key, _value).map(lambda kv: "%s = %s" % (kv[0], kv[1]))

_standard_table = _key.map(lambda k: "[%s]" % k)
_array_table = _key.map(lambda k: "[[%s]]" % k)

_expression = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    st.just(""),
    st.text(alphabet=_SAFE_CHARS, max_size=20).filter(lambda s: "\n" not in s).map(
        lambda s: "# " + s
    ),
)

_document = st.lists(_expression, min_size=0, max_size=15).map(lambda lines: "\n".join(lines))

# ---------------------------------------------------------------------------
# Malformed / edge-case inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        "a = ",
        "a = \"unterminated",
        "a = 'unterminated",
        "a = \"\"\"unterminated",
        "a = '''unterminated",
        "a = [1, 2",
        "a = {b = 1",
        "a = {b = 1,\n c = 2}",
        "a = \"\\q\"",
        "a = 1\nb = 2\na = 3",
        "[t]\n[t]",
        "[[a]]\n[a]",
        "a.b = 1\na.b.c = 2",
        "a = \n1",
        "missing =",
        "= 1",
        "[]",
        "[[]]",
        "a = 1979-02-30",
        "a = 007",
        "a = 1.",
        "a = .5",
        "a = \"x\x01y\"",
        "# comment with \x01 control",
        "a = {b = 1,}",
        "a = [1, 2,]",
        "\n\n\n",
        "a = 1\r\nb = 2",
        "\ta = 1",
        "a = 1",
        "a = \"\"",
        "a = ''",
        "a = \"\"\"\"\"\"",
        "a = ''''''",
        "a = \"\\u0000\"",
        "a = +inf",
        "a = -nan",
        "a = 0x_1",
        "a = 0o8",
        "a = 0b2",
    ]
)

# ---------------------------------------------------------------------------
# Deep nesting (arrays and inline tables) - concentrated in the 1500-2048 band
# ---------------------------------------------------------------------------

_deep_depth = st.integers(min_value=1500, max_value=2048)

_deep_array = _deep_depth.map(lambda d: "a = " + "[" * d + "]" * d)

_deep_inline = _deep_depth.map(lambda d: "a = " + "{b = " * d + "1" + "}" * d)

# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _malformed,
    _deep_array,
    _deep_inline,
    # empty document
    st.just(""),
    # comment-only document
    st.text(alphabet=_SAFE_CHARS, max_size=30)
    .filter(lambda s: "\n" not in s)
    .map(lambda s: "# " + s),
    # document with no trailing newline
    _document.filter(lambda s: s and not s.endswith("\n")),
    # long key
    st.just("k" * 10000 + " = 1"),
    # super-table after sub-table
    st.just("[a.b]\nx = 1\n[a]\ny = 2"),
    # empty table / array of tables
    st.just("[t]"),
    st.just("[[a]]"),
    # empty quoted key
    st.just('"" = 1'),
    # CRLF document
    _document.map(lambda s: s.replace("\n", "\r\n")),
)