```python
import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Small helpers / alphabets
# ---------------------------------------------------------------------------

_BARE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

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
# Scalars: date-times
# ---------------------------------------------------------------------------

_date_time = st.one_of(
    st.sampled_from([
        "1979-05-27T07:32:00Z", "1979-05-27T00:32:00-07:00",
        "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27 07:32:00Z", "1979-05-27t07:32:00z",
        "0001-01-01T00:00:00Z", "9999-12-31T23:59:59Z",
        "1979-05-27T07:32:00+13:00", "1979-05-27T07:32:00-13:00",
        "1979-05-27T07:32:00", "1979-05-27T00:32:00.999999",
        "1979-05-27 07:32:00", "1979-05-27t07:32:00",
        "1979-05-27", "0001-01-01", "9999-12-31",
        "07:32:00", "00:32:00.999999", "23:59:59", "00:00:00",
        "1979-02-30", "1979-13-01", "1979-00-00", "1979-02-29",
        "2021-02-29", "9999-99-99",
        "1979-05-27T25:61:61Z",
    ]),
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
    # Full timestamps targeting toml_timestamp_at parsing paths.
    st.builds(
        lambda y, mo, d, h, mi, s, frac, off: (
            f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}"
            + (f".{frac}" if frac else "")
            + off
        ),
        st.integers(min_value=0, max_value=9999),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.sampled_from(["", "0", "999999", "123456789", "000000"]),
        st.sampled_from(["Z", "z", "+00:00", "-07:00", "+13:00", "-13:00", "+99:99"]),
    ),
)

# ---------------------------------------------------------------------------
# Strings
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
    st.sampled_from([
        '""', "''", '"""\n"""', "'''\n'''",
        '"\\u0000"', '"\\U0001F600"', '"\\t\\r\\n"',
        '"x\x01y"', '"tab\there"', '"\\q"', '"unterminated',
        '"\\\\"', '"\\""', "'''raw \\n not escape'''",
        '"""multi\nline"""', "'multi\nline'",
        '"\\uD83D\\uDE00"',
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
# Recursive values
# ---------------------------------------------------------------------------

_scalar_value = st.one_of(
    _string,
    _integer,
    _float,
    _bool,
    _date_time,
)


def _array_from(inner):
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
# Documents
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


_document = st.one_of(
    st.lists(_block(), min_size=0, max_size=5).map(
        lambda blocks: "\n".join(b for b in blocks if b != "")
    ),
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
# UTF-8 / encoding edge cases (targets toml_utf8_to_ucs, toml_rtos, norm_lit_str)
# ---------------------------------------------------------------------------

_utf8_edges = st.sampled_from([
    'a = "\u00e9\u00fc\u4e2d\u6587"\n',
    "a = '\u00e9\u00fc\u4e2d\u6587'\n",
    'a = """\u00e9\u00fc\u4e2d\u6587\U0001f600"""\n',
    "a = '''\u00e9\u00fc\u4e2d\u6587\U0001f600'''\n",
    'a = "\u0080"\n',
    'a = "\u07ff"\n',
    'a = "\u0800"\n',
    'a = "\uffff"\n',
    'a = "\U00010000"\n',
    'a = "\U0010ffff"\n',
    'a = "\\u00e9"\n',
    'a = "\\u4e2d"\n',
    'a = "\\U0001F600"\n',
    'a = "\\uD83D\\uDE00"\n',
    'a = "\\u0000"\n',
    'a = "\\uFFFF"\n',
    'a = "\\U0010FFFF"\n',
    'a = "\\uD800"\n',
    'a = "\\uDFFF"\n',
    'a = "\\uD800x"\n',
    "a = '\\u00e9'\n",
    "a = '\\n\\t'\n",
    "a = 'raw \\\\ backslash'\n",
    "a = '''\n\\u00e9 \\n'''\n",
    "a = '''\\'''\n",
    "a = '\\''\n",
    'a = """line1 \\\nline2"""\n',
    'a = """line1 \\\r\nline2"""\n',
    'a = """\\\n   trimmed"""\n',
    'a = """\\\n\n\n   trimmed"""\n',
    'a = """\\   \n  trimmed"""\n',
    'a = """a\\\n b\\\n c"""\n',
    'a = """\nfirst"""\n',
    'a = """\r\nfirst"""\n',
    "a = '''\nfirst'''\n",
    "a = '''\r\nfirst'''\n",
    'a = """a\r\nb"""\n',
    "a = '''a\r\nb'''\n",
    '"\u00e9" = 1\n',
    "'\u4e2d' = 1\n",
    "# \u00e9\u4e2d\U0001f600\n",
    "\u00e9 = 1\n",
])

# ---------------------------------------------------------------------------
# Raw byte-level UTF-8 edge cases (targets toml_utf8_to_ucs directly).
# These embed raw bytes that are invalid / boundary UTF-8 sequences.
# ---------------------------------------------------------------------------

_raw_utf8_edges = st.sampled_from([
    'a = "' + "\x80" + '"\n',                      # lone continuation
    'a = "' + "\xc0\x80" + '"\n',                  # overlong NUL
    'a = "' + "\xc1\xbf" + '"\n',                  # overlong
    'a = "' + "\xe0\x80\x80" + '"\n',              # overlong 3-byte
    'a = "' + "\xed\xa0\x80" + '"\n',              # surrogate
    'a = "' + "\xf4\x90\x80\x80" + '"\n',          # > U+10FFFF
    'a = "' + "\xf5\x80\x80\x80" + '"\n',          # invalid lead
    'a = "' + "\xff" + '"\n',                      # invalid byte
    'a = "' + "\xc3" + '"\n',                      # truncated 2-byte
    'a = "' + "\xe2\x82" + '"\n',                  # truncated 3-byte
    'a = "' + "\xf0\x9f\x98" + '"\n',              # truncated 4-byte
    'a = "' + "\xc3\xa9" + '"\n',                  # valid 2-byte (é)
    'a = "' + "\xe4\xb8\xad" + '"\n',              # valid 3-byte (中)
    'a = "' + "\xf0\x9f\x98\x80" + '"\n',          # valid 4-byte (😀)
    'a = "' + "\xc2\x80" + '"\n',                  # U+0080 boundary
    'a = "' + "\xdf\xbf" + '"\n',                  # U+07FF boundary
    'a = "' + "\xe0\xa0\x80" + '"\n',              # U+0800 boundary
    'a = "' + "\xef\xbf\xbf" + '"\n',              # U+FFFF boundary
    'a = "' + "\xf0\x90\x80\x80" + '"\n',          # U+10000 boundary
    'a = "' + "\xf4\x8f\xbf\xbf" + '"\n',          # U+10FFFF boundary
    "a = '" + "\xff" + "'\n",                      # invalid in literal
    "a = '''" + "\xc3" + "'''\n",                  # invalid in ml literal
    'a = """' + "\x80" + '"""\n',                  # invalid in ml basic
    "\xff = 1\n",                                  # invalid in key
    "# " + "\xff" + "\n",                          # invalid in comment
])

# ---------------------------------------------------------------------------
# Deep nesting
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_inline_table(depth):
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

strategy = st.one_of(
    _document,
    _deep_nesting,
    _utf8_edges,
    _raw_utf8_edges,
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
    ]),
)
```