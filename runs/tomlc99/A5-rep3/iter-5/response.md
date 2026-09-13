```python
import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Small helpers / alphabets
# ---------------------------------------------------------------------------

# Bare key characters allowed by the parser (ASCII only).
_BARE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

# Characters safe to put raw inside strings/comments (no NUL, no newline where
# not allowed).  We deliberately include control chars and non-ASCII.
_RAW_STR_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " _-.,:;/@#$%^&*()+=<>?|~`"
    "\t\x01\x02\x1f\x7f"
    "\u00e9\u00fc\u4e2d\u6587\u2603\U0001f600"
)

_ESCAPE_SEQS = [
    "\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/",
    "\\u0041", "\\u00e9", "\\u0000", "\\uFFFF", "\\uD83D",
    "\\U0001F600", "\\U00000041", "\\U0010FFFF",
    # near-valid / malformed escapes
    "\\q", "\\x41", "\\u12", "\\U0001F6",
]

# ---------------------------------------------------------------------------
# Scalars: integers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.sampled_from([
        "0", "00", "007", "0000", "-0", "+0", "-007", "+007",
        "1_000", "1_0_0", "9_223_372_036_854_775_807",
        "9_223_372_036_854_775_808",
        "18_446_744_073_709_551_615",
        "99999999999999999999999999999999999999999",
        "-99999999999999999999999999999999999999999",
        "1", "-1", "+1", "42", "100", "1234567890",
    ]),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x")),
    st.sampled_from([
        "0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF",
        "0x1_2_3", "0xabcdef", "0xABCDEF", "0x00", "0x0000ff",
        "0xffffffffffffffffffffffffffffffff",
    ]),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0o" + format(n, "o")),
    st.sampled_from([
        "0o0", "0o777", "0o7_7_7", "0o01234567", "0o1777777777777777777777",
    ]),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from([
        "0b0", "0b1", "0b1010", "0b1_0_1", "0b1111111111111111111111111111111111111111111111111111111111111111",
    ]),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# ---------------------------------------------------------------------------
# Scalars: floats
# ---------------------------------------------------------------------------

_float = st.one_of(
    st.sampled_from([
        "0.0", "-0.0", "+0.0", "1.0", "-1.0", "3.141592653589793",
        "1e10", "1E10", "1e+10", "1e-10", "-1e10", "+1e10",
        "6.626e-34", "1_000.000_1", "1e1_0",
        "1.", ".5", "-.5", "+.5", "1.e10", ".5e10", "-.5e-10",
        "1e309", "-1e309", "1e-309", "1e308", "1.7976931348623157e308",
        "0.000000000000000000000001",
        "12345678901234567890.12345678901234567890",
        "1e99999999999999999999",
    ]),
    st.integers(min_value=-10**6, max_value=10**6).map(lambda n: f"{n}.0"),
    st.integers(min_value=-10**6, max_value=10**6).map(lambda n: f"{n}e0"),
    st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
)

# ---------------------------------------------------------------------------
# Scalars: booleans
# ---------------------------------------------------------------------------

_bool = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Scalars: date-times (all four forms, plus calendar-invalid and extremes)
# ---------------------------------------------------------------------------

_date_time = st.one_of(
    st.sampled_from([
        # offset date-time
        "1979-05-27T07:32:00Z", "1979-05-27T00:32:00-07:00",
        "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27 07:32:00Z", "1979-05-27t07:32:00z",
        "0001-01-01T00:00:00Z", "9999-12-31T23:59:59Z",
        "1979-05-27T07:32:00+13:00", "1979-05-27T07:32:00-13:00",
        # local date-time
        "1979-05-27T07:32:00", "1979-05-27T00:32:00.999999",
        "1979-05-27 07:32:00", "1979-05-27t07:32:00",
        # local date
        "1979-05-27", "0001-01-01", "9999-12-31",
        # local time
        "07:32:00", "00:32:00.999999", "23:59:59", "00:00:00",
        # calendar-invalid (parser accepts)
        "1979-02-30", "1979-13-01", "1979-00-00", "1979-02-29",
        "2021-02-29", "9999-99-99",
        "1979-05-27T25:61:61Z",
    ]),
    # randomized but well-formed dates
    st.builds(
        lambda y, m, d: f"{y:04d}-{m:02d}-{d:02d}",
        st.integers(min_value=0, max_value=9999),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ),
    st.builds(
        lambda h, m, s: f"{h:02d}:{m:02d}:{s:02d}",
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ),
)

# ---------------------------------------------------------------------------
# Strings: all four quoting forms with escapes / raw controls / non-ASCII
# ---------------------------------------------------------------------------

def _basic_string_body():
    parts = [
        st.text(alphabet=_RAW_STR_CHARS, min_size=0, max_size=20),
        st.sampled_from(_ESCAPE_SEQS),
    ]
    return st.lists(st.one_of(*parts), min_size=0, max_size=8).map("".join)


_basic_string = _basic_string_body().map(lambda s: '"' + s + '"')

_literal_string = st.text(alphabet=_RAW_STR_CHARS, min_size=0, max_size=20).map(
    lambda s: "'" + s + "'"
)


def _ml_basic_body():
    # multiline basic strings may contain newlines and escaped newlines
    parts = [
        st.text(alphabet=_RAW_STR_CHARS + "\n\r", min_size=0, max_size=20),
        st.sampled_from(_ESCAPE_SEQS + ["\\\n", "\\\r\n"]),
    ]
    return st.lists(st.one_of(*parts), min_size=0, max_size=8).map("".join)


_ml_basic_string = _ml_basic_body().map(lambda s: '"""' + s + '"""')

_ml_literal_string = st.text(
    alphabet=_RAW_STR_CHARS + "\n\r", min_size=0, max_size=20
).map(lambda s: "'''" + s + "'''")

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
    # edge cases
    st.sampled_from([
        '""', "''", '"""\n"""', "'''\n'''",
        '"\\u0000"', '"\\U0001F600"', '"\\t\\r\\n"',
        '"x\x01y"', '"tab\there"', '"\\q"', '"unterminated',
        '"\\\\"', '"\\""', "'''raw \\n not escape'''",
        '"""multi\nline"""', "'multi\nline'",
        '"\\uD83D\\uDE00"',
        # quotes near the delimiter boundary
        '""""', "''''", '""""""',
        '"""x""', '"""x""""', "'''x''", "'''x''''",
        '"""a"b"""', "'''a'b'''",
        '"a\\\nb"', '"a\\\r\nb"',
    ]),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.one_of(
    st.text(alphabet=_BARE_CHARS, min_size=1, max_size=10),
    st.sampled_from(["a", "key", "key1", "key-1", "key_1", "123", "0", "-", "_"]),
)

_quoted_key = st.one_of(
    _basic_string,
    _literal_string,
    st.sampled_from(['""', "''", '"a.b"', '"with space"']),
)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(".".join)

_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

_scalar_value = st.one_of(
    _string,
    _integer,
    _float,
    _bool,
    _date_time,
)


def _array_from(inner):
    """Build an array strategy from an inner value strategy."""
    sep = st.one_of(
        st.just(", "),
        st.just(","),
        st.just(",\n"),
        st.just(",\n# comment\n"),
    )

    def render(values, separators, trailing, leading_nl, trailing_nl):
        if not values:
            return "[" + ("\n" if leading_nl else "") + "]"
        out = "["
        if leading_nl:
            out += "\n"
        for i, v in enumerate(values):
            out += v
            if i < len(values) - 1:
                # `separators` is generated independently of `values`, so it
                # may be shorter than `values`.  Index into it modulo its
                # length to avoid an IndexError while still varying separators.
                out += separators[i % len(separators)]
            elif trailing:
                out += ","
        if trailing_nl:
            out += "\n"
        out += "]"
        return out

    return st.builds(
        render,
        st.lists(inner, min_size=0, max_size=6),
        st.lists(sep, min_size=1, max_size=6),
        st.booleans(),
        st.booleans(),
        st.booleans(),
    )


def _inline_table_from(inner):
    """Build an inline table strategy from an inner value strategy."""
    pair = st.builds(
        lambda k, v: k + " = " + v,
        _key,
        inner,
    )

    def render(pairs, trailing):
        if not pairs:
            return "{}"
        body = ", ".join(pairs)
        if trailing:
            body += ","
        return "{" + body + "}"

    return st.builds(
        render,
        st.lists(pair, min_size=0, max_size=5),
        st.booleans(),
    )


def _extend(inner):
    return st.one_of(
        _array_from(inner),
        _inline_table_from(inner),
    )


_value = st.recursive(_scalar_value, _extend, max_leaves=40)

# ---------------------------------------------------------------------------
# Documents: key/value lines, tables, arrays of tables, comments
# ---------------------------------------------------------------------------

_ws = st.one_of(st.just(""), st.just(" "), st.just("\t"), st.just("  "))

_comment = st.one_of(
    st.just(""),
    st.text(alphabet=_RAW_STR_CHARS + "\x01\x02", min_size=0, max_size=20).map(
        lambda s: "#" + s
    ),
    st.just("#"),
    st.just("# comment with control \x01"),
)

_key_value_line = st.builds(
    lambda k, v, c: k + " = " + v + c,
    _key,
    _value,
    _comment.map(lambda c: ("  " + c) if c else ""),
)

_standard_table = st.builds(
    lambda k, c: "[" + k + "]" + (("  " + c) if c else ""),
    _key,
    _comment,
)

_array_table = st.builds(
    lambda k, c: "[[" + k + "]]" + (("  " + c) if c else ""),
    _key,
    _comment,
)

# A "block" is a run of key/value lines and/or a table header.
def _block():
    lines = st.lists(_key_value_line, min_size=0, max_size=4)
    header = st.one_of(
        _standard_table,
        _array_table,
        st.just(""),
    )

    def render(h, kv_lines):
        out = []
        if h:
            out.append(h)
        out.extend(kv_lines)
        return "\n".join(out)

    return st.builds(render, header, lines)


def _doc_join(blocks):
    return "\n".join(b for b in blocks if b != "")


_document = st.one_of(
    # normal multi-block documents
    st.lists(_block(), min_size=0, max_size=5).map(_doc_join),
    # empty / comment-only documents
    st.sampled_from([
        "",
        "\n",
        "\r\n",
        "# just a comment",
        "# comment\n",
        "\n\n\n",
        "# c1\n# c2\n",
        "[t]\n",
        "[[a]]\n",
        "a = {}\n",
        "a = []\n",
        '"" = 1\n',
    ]),
    # deliberately malformed / near-valid inputs
    st.sampled_from([
        "a = ",
        "a =",
        "a =\n",
        "= 1",
        "a == 1",
        "a = 1 b = 2",
        "a = [1, 2",
        "a = [1, 2]]",
        "a = {b = 1",
        "a = {b = 1}}",
        "a = {b = 1,\n c = 2}",
        "a = {b = 1,}",
        "[t",
        "[t]]",
        "[[t]",
        "[[t]]]",
        "a = \"unterminated",
        "a = 'unterminated",
        "a = \"\"\"unterminated",
        "a = '''unterminated",
        "a.b = 1\na.b = 2",
        "[t]\n[t]",
        "[[t]]\n[[t]]",
        "a = 1\n",
    ]),
)

# ---------------------------------------------------------------------------
# Deep nesting: concentrate interesting depth in ~1500-2048 band.
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_inline_table(depth):
    # nested inline tables: {a = {a = {a = {}}}}
    return "{a = " * depth + "{}" + "}" * depth


_deep_nesting = st.one_of(
    st.integers(min_value=1, max_value=64).map(_deep_array),
    st.sampled_from([
        _deep_array(1500),
        _deep_array(1600),
        _deep_array(1800),
        _deep_array(2000),
        _deep_array(2048),
        _deep_inline_table(1),
        _deep_inline_table(2),
        _deep_inline_table(8),
        _deep_inline_table(64),
        _deep_inline_table(256),
        _deep_inline_table(512),
    ]),
    st.builds(
        lambda d: "a = " + _deep_array(d),
        st.integers(min_value=1500, max_value=2048),
    ),
)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

# IMPROVEMENT: wrap the whole document strategy so that generated documents are
# additionally exercised with a variety of line terminators (LF, CRLF, CR) and
# trailing-newline variations.  Real-world TOML inputs differ in newline style
# and trailing whitespace, and parsers commonly mishandle CR-only streams,
# missing final newlines, and mixed terminators.  This cross-product multiplies
# the reachable input shapes without changing the underlying grammar coverage.
_LINE_TERMINATORS = ["\n", "\r\n", "\r"]


def _relabel_newlines(text, terminator, trailing_newline):
    # Normalise existing newlines to the chosen terminator, then optionally
    # append or strip a trailing newline.  Documents that are already empty
    # are left empty.
    if text == "":
        return text
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    if terminator != "\n":
        normalised = normalised.replace("\n", terminator)
    if trailing_newline:
        if not normalised.endswith(terminator):
            normalised += terminator
    else:
        while normalised.endswith(terminator):
            normalised = normalised[: -len(terminator)]
    return normalised


def _newline_variants(text):
    out = [text]
    for term in _LINE_TERMINATORS:
        for trailing in (True, False):
            out.append(_relabel_newlines(text, term, trailing))
    return out


_document_with_newlines = st.one_of(
    _document,
    _document.map(_newline_variants).flatmap(st.sampled_from),
)

strategy = st.one_of(
    _document_with_newlines,
    _deep_nesting,
    # a few targeted extras that exercise parser realities
    st.sampled_from([
        "a = 007\n",
        "a = 1.\n",
        "a = .5\n",
        'a = "x\x01y"\n',
        "a = {b = 1,}\n",
        "a = 1979-02-30\n",
        "a = 1e309\n",
        "a = 99999999999999999999999999999999999999999999\n",
        "a = -inf\n",
        "a = nan\n",
        "a = true\n",
        "a = false\n",
        "a = 0xDEAD_BEEF\n",
        "a = 0o777\n",
        "a = 0b1010\n",
        "a = 1979-05-27 07:32:00Z\n",
        "a = 07:32:00\n",
        "a = 1979-05-27\n",
        "a = 1979-05-27T07:32:00\n",
        "a = '''\nmulti\nline\n'''\n",
        'a = """\nmulti\nline\n"""\n',
        'a = "\\u0000"\n',
        "a = \"\\q\"\n",
        "a = [1, 2, 3,]\n",
        "a = [\n  1,\n  2,\n]\n",
        "a = {}\n",
        "a = []\n",
        "[t]\n",
        "[[a]]\n[[a]]\n",
        "a.b.c = 1\n",
        '"a.b" = 1\n',
        "'' = 1\n",
        '"" = 1\n',
        "a = 1 # comment\n",
        "# comment with \x01 control\n",
        "a = 1\r\nb = 2\r\n",
        "\ta = 1\n",
        "a = 1",
        # newline-style edge cases
        "a = 1\rb = 2\r",
        "a = 1\r\n\r\nb = 2\r\n",
        "a = 1\n\rb = 2",
        "[t]\r\nk = 1\r\n",
        "a = 1\r",
        "a = 1\r\n",
        "a = 1\n",
        "a = 1",
    ]),
)
```