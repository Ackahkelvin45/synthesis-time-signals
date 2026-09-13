from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Characters that are safe-ish inside strings but stress escapes / non-ASCII.
_TEXT_CHARS = (
    "abcxyzABCXYZ0123456789 _-.:/+=*!?@#$%^&()[]{}<>|~`"
    "\u00e9\u00fc\u00f1\u4e2d\u6587\u65e5\u672c\u97e9\u56fd\u0416\u05d0\u0627\u03b1\u03c9"
    "\u2603\u2764\U0001f600\U0001f680"
    "\x01\x02\x07\x08\x0b\x0c\x0e\x1b\x7f"
    "\t"
)

_ESCAPES = [
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u001f", "\\u007f", "\\u00e9", "\\u4e2d", "\\uffff",
    "\\U0001f600", "\\U0010ffff", "\\q", "\\x41", "\\", "\\u12", "\\U0000000",
]


def _escaped_basic_body():
    """Body content for a basic string (raw chars + escapes)."""
    return st.one_of(
        st.text(alphabet=_TEXT_CHARS, min_size=0, max_size=12),
        st.sampled_from(_ESCAPES),
        st.lists(
            st.one_of(
                st.text(alphabet=_TEXT_CHARS, min_size=0, max_size=4),
                st.sampled_from(_ESCAPES),
            ),
            min_size=0,
            max_size=4,
        ).map("".join),
    )


def _literal_body():
    """Body for a literal string: no backslash-escape semantics, no quote."""
    alphabet = _TEXT_CHARS.replace("'", "")
    return st.text(alphabet=alphabet, min_size=0, max_size=12)


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------

bare_key = st.one_of(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
            min_size=1, max_size=10),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
            min_size=1, max_size=1),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
            min_size=100, max_size=200),  # long key
)

quoted_key = st.one_of(
    _escaped_basic_body().map(lambda b: '"' + b + '"'),
    _literal_body().map(lambda b: "'" + b + "'"),
    st.just('""'),  # empty quoted key
)

simple_key = st.one_of(bare_key, quoted_key)

dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(".".join)

key = st.one_of(simple_key, dotted_key)

# -- strings -----------------------------------------------------------------

basic_string = _escaped_basic_body().map(lambda b: '"' + b + '"')
literal_string = _literal_body().map(lambda b: "'" + b + "'")

ml_basic_body = st.one_of(
    st.text(alphabet=_TEXT_CHARS + "\n\r", min_size=0, max_size=20),
    st.lists(
        st.one_of(
            st.text(alphabet=_TEXT_CHARS + "\n\r", min_size=0, max_size=6),
            st.sampled_from(_ESCAPES + ["\\\n", "\\\r\n"]),
        ),
        min_size=0, max_size=4,
    ).map("".join),
)
ml_basic_string = ml_basic_body.map(lambda b: '"""' + b + '"""')

ml_literal_body = st.text(
    alphabet=_TEXT_CHARS.replace("'", "") + "\n\r", min_size=0, max_size=20)
ml_literal_string = ml_literal_body.map(lambda b: "'''" + b + "'''")

string_value = st.one_of(
    basic_string, literal_string, ml_basic_string, ml_literal_string,
)

# -- integers ----------------------------------------------------------------

dec_int = st.one_of(
    st.integers(min_value=-(2**70), max_value=2**70).map(str),
    st.integers(min_value=0, max_value=255).map(lambda n: "0" + str(n)),  # leading zero
    st.sampled_from(["0", "+0", "-0", "007", "000", "1_000", "1_2_3",
                     "9223372036854775807", "9223372036854775808",
                     "-9223372036854775808", "18446744073709551616",
                     "99999999999999999999999999999999999999"]),
)

hex_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x")),
    st.sampled_from(["0x0", "0xdeadbeef", "0xDEAD_BEEF", "0xffffffffffffffff",
                     "0x1_2_3", "0xABCDEF0123456789"]),
)

oct_int = st.one_of(
    st.integers(min_value=0, max_value=2**63).map(lambda n: "0o" + format(n, "o")),
    st.sampled_from(["0o0", "0o777", "0o1_7_7", "0o12345670123456701234"]),
)

bin_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from(["0b0", "0b1", "0b1_0_1_0", "0b" + "1" * 64]),
)

integer_value = st.one_of(dec_int, hex_int, oct_int, bin_int)

# -- floats ------------------------------------------------------------------

float_value = st.one_of(
    st.sampled_from([
        "1.0", "-1.0", "+1.0", "0.0", "-0.0", "1.", ".5", "-.5", "+.5",
        "1e10", "1E10", "1e+10", "1e-10", "1.5e10", "1.5E-10",
        "1e309", "-1e309", "1e-400", "3.141592653589793",
        "1_000.000_1", "6.02e23", "1e1_0",
        "inf", "+inf", "-inf", "nan", "+nan", "-nan",
        "0.000000000000000000001", "123456789012345678901234567890.123456789",
    ]),
    st.floats(allow_nan=True, allow_infinity=True).map(repr),
)

# -- booleans ----------------------------------------------------------------

bool_value = st.sampled_from(["true", "false"])

# -- dates -------------------------------------------------------------------

date_value = st.one_of(
    st.sampled_from([
        "1979-05-27T07:32:00Z",
        "1979-05-27t07:32:00z",
        "1979-05-27 07:32:00Z",
        "1979-05-27T00:32:00-07:00",
        "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27T07:32:00",
        "1979-05-27T00:32:00.999999",
        "1979-05-27",
        "07:32:00",
        "00:32:00.999999",
        "1979-02-30",       # calendar-invalid, accepted
        "0000-00-00",
        "1979-13-45T99:99:99Z",
        "1979-05-27 07:32:00",
        "2024-02-29T23:59:60Z",
    ]),
    st.tuples(
        st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
    ).map(lambda t: "%s-%s-%s" % t),
)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

simple_scalar = st.one_of(
    string_value, integer_value, float_value, bool_value, date_value,
)


def _join_value_list(values):
    return "[" + ", ".join(values) + "]"


def _join_value_list_trailing(values):
    return "[" + ", ".join(values) + ",]"


def _join_inline_table(pairs):
    return "{" + ", ".join(pairs) + "}"


def _join_inline_table_trailing(pairs):
    return "{" + ", ".join(pairs) + ",}"


def _multiline_array(values):
    if not values:
        return "[\n]"
    body = ",\n".join("  " + v for v in values)
    return "[\n" + body + ",\n]"


def _empty_or_comment_array():
    return st.sampled_from([
        "[]", "[ ]", "[\n]", "[\n\n]", "[# c\n]", "[\n# c\n]",
    ])


# Build recursive value strategy.
value = st.recursive(
    simple_scalar,
    lambda children: st.one_of(
        # arrays
        st.lists(children, min_size=0, max_size=4).map(_join_value_list),
        st.lists(children, min_size=1, max_size=4).map(_join_value_list_trailing),
        st.lists(children, min_size=1, max_size=4).map(_multiline_array),
        _empty_or_comment_array(),
        # inline tables
        st.lists(
            st.tuples(simple_key, children).map(lambda t: t[0] + " = " + t[1]),
            min_size=0, max_size=3,
        ).map(_join_inline_table),
        st.lists(
            st.tuples(simple_key, children).map(lambda t: t[0] + " = " + t[1]),
            min_size=1, max_size=3,
        ).map(_join_inline_table_trailing),
    ),
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Deep nesting in the 1500-2048 band
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_inline_table(depth):
    # {a = {a = {a = 1}}} ... nested
    return "{" + "a = {" * (depth - 1) + "a = 1" + "}" * (depth - 1) + "}"


def _deep_array_with_value(depth, inner):
    return "[" * depth + inner + "]" * depth


deep_depth = st.integers(min_value=1500, max_value=2048)

deep_value = st.one_of(
    deep_depth.map(_deep_array),
    deep_depth.map(_deep_inline_table),
    st.tuples(deep_depth, simple_scalar).map(
        lambda t: _deep_array_with_value(t[0], t[1])),
)

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

malformed_value = st.sampled_from([
    # unterminated strings
    '"unterminated', "'unterminated", '"""unterminated', "'''unterminated",
    # missing / doubled delimiters
    "[1, 2", "[1, 2,", "{a = 1", "{a = 1,", "]", "}", "]]", "}}",
    "[[]", "[]]", "{}}", "{{}}",
    # stray tokens
    "=", "==", "a", "a =", "a == 1", "a = = 1", ",", ".", "a = ,",
    "a = [1,,2]", "a = {,}", "a = {b = }", "a = {b}",
    # invalid escapes
    '"\\q"', '"\\x41"', '"\\u12"', '"\\U0000000"',
    # bare unicode key
    "caf\u00e9 = 1", "\u4e2d\u6587 = 1",
    # newline in inline table
    "{a = 1\nb = 2}", "{a = 1,\nb = 2}",
    # value on next line
    "a =\n1",
    # bad numbers
    "0x", "0o", "0b", "0xG", "0o8", "0b2", "1.2.3", "1e", "1e+",
    # duplicate-ish / table weirdness
    "[t]\n[t]", "a = 1\na = 2",
])

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

comment_line = st.one_of(
    st.just("#"),
    st.text(alphabet=_TEXT_CHARS + "\x01\x02\x7f", min_size=0, max_size=20)
      .map(lambda s: "# " + s),
)

key_value_line = st.tuples(key, value).map(lambda t: t[0] + " = " + t[1])

malformed_line = st.one_of(
    malformed_value,
    st.tuples(key, malformed_value).map(lambda t: t[0] + " = " + t[1]),
)

table_header = key.map(lambda k: "[" + k + "]")
array_table_header = key.map(lambda k: "[[" + k + "]]")

line = st.one_of(
    key_value_line,
    comment_line,
    st.just(""),
    table_header,
    array_table_header,
    malformed_line,
)

document = st.lists(line, min_size=0, max_size=12).map("\n".join)

# documents that specifically exercise deep nesting (single key/value)
deep_document = st.tuples(key, deep_value).map(lambda t: t[0] + " = " + t[1])

# documents with an explicit table + keys
structured_document = st.tuples(
    table_header,
    st.lists(key_value_line, min_size=0, max_size=5).map("\n".join),
).map(lambda t: t[0] + "\n" + t[1])

# CRLF / tab indentation variants
crlf_document = document.map(lambda d: d.replace("\n", "\r\n"))
tab_document = st.lists(line, min_size=1, max_size=8).map(
    lambda ls: "\n".join("\t" + l if l and not l.startswith("[") else l for l in ls))

# malformed-only document (single line, near-valid)
malformed_document = malformed_value

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    document,
    structured_document,
    deep_document,
    crlf_document,
    tab_document,
    malformed_document,
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("# comment without newline"),
    # exercise parser branches around table headers, dotted keys, and
    # whitespace/comment handling that the line-based generator rarely hits.
    st.sampled_from([
        "[a.b.c]\nx = 1\n[a.b.d]\ny = 2\n",
        "[[a.b]]\nx = 1\n[[a.b]]\ny = 2\n",
        "[a]\n[a.b]\n[a.b.c]\n",
        "a.b.c = 1\na.b.d = 2\n",
        "a . b . c = 1\n",
        "a.b = 1\n[a]\nc = 2\n[a.b]\nd = 3\n",
        "[a]\n# comment\n[a.b]\n",
        "  [a]  \n  x = 1  \n",
        "\n\n[a]\n\nx = 1\n\n",
        "[a]\r\nx = 1\r\n",
        "a = 1 # trailing comment\n",
        "a = 1#no space comment\n",
        "a = [1, 2, 3] # c\n",
        "a = {b = 1, c = 2}\n",
        "a = {b = {c = 1}}\n",
        "a = [[1], [2]]\n",
        "a = [{b = 1}]\n",
        "a = \"\"\"\nmulti\nline\n\"\"\"\n",
        "a = '''\nmulti\nline\n'''\n",
        "a = \"\"\"\\\n  continued\"\"\"\n",
        "[a.b.c.d.e.f.g]\nx = 1\n",
        "[[a]]\n[[a]]\n[[a]]\n[[a]]\n",
        "a = 1\n[b]\nc = 2\n[[d]]\ne = 3\n",
        "x.y.z = {a = 1, b = [1, 2]}\n",
        "[a]\nb.c = 1\n",
        "a = \"\"\n",
        "a = ''\n",
        "a = \"\\u00e9\\U0001f600\"\n",
        "a = 1979-05-27T07:32:00Z\n",
        "a = 0x1_2\n",
        "a = true\n",
        "a = inf\n",
    ]),
)