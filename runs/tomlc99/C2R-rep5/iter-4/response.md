```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic character / token pieces
# ---------------------------------------------------------------------------

# Safe ASCII letters/digits for bare keys
_BARE_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

# Characters allowed in basic strings (no raw NUL, no unescaped quote/backslash/newline)
_BASIC_STRING_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " !#$%&()*+,-./:;<=>?@[]^_`{|}~"
    "\t"
)

# Control characters that the parser accepts raw inside strings (except NUL)
_RAW_CONTROL_CHARS = "".join(chr(c) for c in range(1, 32) if c != 10) + "\x7f"

_LITERAL_STRING_CHARS = _BASIC_STRING_CHARS + "'" + '"' + "\\"

# Non-ASCII text (valid UTF-8, no NUL)
_NON_ASCII = "".join(
    chr(c) for c in (0x00E9, 0x00FC, 0x4E2D, 0x6587, 0x0416, 0x03B1, 0x1F600, 0x10FFFF)
)

# Escape sequences valid in basic strings
_ESCAPES = ['\\"', "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/", "\\u0000", "\\u0041", "\\uFFFF", "\\U0001F600"]


def _basic_string_body():
    """Random body content for a basic (double-quoted) string."""
    return st.one_of(
        st.text(alphabet=_BASIC_STRING_CHARS, max_size=20),
        st.lists(
            st.one_of(
                st.text(alphabet=_BASIC_STRING_CHARS, max_size=5),
                st.sampled_from(_ESCAPES),
                st.sampled_from(_NON_ASCII),
                st.sampled_from(_RAW_CONTROL_CHARS),
            ),
            max_size=8,
        ).map("".join),
    )


def _literal_string_body():
    return st.one_of(
        st.text(alphabet=_LITERAL_STRING_CHARS, max_size=20),
        st.lists(
            st.one_of(
                st.text(alphabet=_LITERAL_STRING_CHARS, max_size=5),
                st.sampled_from(_NON_ASCII),
                st.sampled_from(_RAW_CONTROL_CHARS),
            ),
            max_size=8,
        ).map("".join),
    )


# ---------------------------------------------------------------------------
# Value leaves
# ---------------------------------------------------------------------------

_DEC_INT = st.one_of(
    st.integers(min_value=-(2**63), max_value=2**63 - 1).map(str),
    st.integers(min_value=-(2**200), max_value=2**200).map(str),
    st.sampled_from(["0", "-0", "+0", "007", "000123", "1_000", "1_0_0", "9" * 30]),
)

_HEX_INT = st.one_of(
    st.integers(min_value=0, max_value=2**64 - 1).map(lambda n: "0x" + format(n, "x")),
    st.sampled_from(["0x0", "0xDEAD_BEEF", "0xdeadbeef", "0x" + "f" * 40]),
)

_OCT_INT = st.one_of(
    st.integers(min_value=0, max_value=2**32 - 1).map(lambda n: "0o" + format(n, "o")),
    st.sampled_from(["0o0", "0o777", "0o1_2_3"]),
)

_BIN_INT = st.one_of(
    st.integers(min_value=0, max_value=2**32 - 1).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from(["0b0", "0b1010", "0b1_0_1"]),
)

_INTEGER = st.one_of(_DEC_INT, _HEX_INT, _OCT_INT, _BIN_INT)

_FLOAT = st.one_of(
    st.sampled_from(
        [
            "1.0",
            "-1.0",
            "+1.0",
            "0.0",
            "1.",
            ".5",
            "1e10",
            "1E10",
            "1e+10",
            "1e-10",
            "1.5e10",
            "1.5E+10",
            "-1.5e-10",
            "1e309",
            "-1e309",
            "1_000.000_1",
            "3.14159",
            "0.1",
            "1e0",
        ]
    ),
    st.integers(min_value=-(2**60), max_value=2**60).map(lambda n: str(n) + ".0"),
)

_INF_NAN = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

# Upweighted NAN production
_NAN = st.one_of(
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
    st.sampled_from(["nan", "+nan", "-nan"]),
)

_FLOATING = st.one_of(_FLOAT, _INF_NAN, _NAN)

# Upweighted boolean production: bool_ / BOOLEAN
_BOOL = st.one_of(
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
)

_DATE_TIME = st.one_of(
    st.sampled_from(
        [
            "1979-05-27T07:32:00Z",
            "1979-05-27T00:32:00-07:00",
            "1979-05-27T00:32:00.999999-07:00",
            "1979-05-27 07:32:00Z",
            "1979-05-27T07:32:00",
            "1979-05-27T07:32:00.999999",
            "1979-05-27",
            "07:32:00",
            "07:32:00.999999",
            "1979-02-30",
            "0000-00-00",
            "9999-99-99T99:99:99Z",
            "1979-05-27t07:32:00z",
        ]
    ),
    st.builds(
        lambda y, m, d: "%04d-%02d-%02d" % (y, m, d),
        st.integers(min_value=0, max_value=9999),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ),
)

_STRING = st.one_of(
    _basic_string_body().map(lambda b: '"' + b + '"'),
    _literal_string_body().map(lambda b: "'" + b + "'"),
    st.one_of(
        st.text(alphabet=_BASIC_STRING_CHARS + "\n", max_size=20),
        st.lists(
            st.one_of(
                st.text(alphabet=_BASIC_STRING_CHARS + "\n", max_size=5),
                st.sampled_from(_ESCAPES),
                st.sampled_from(_NON_ASCII),
            ),
            max_size=6,
        ).map("".join),
    ).map(lambda b: '"""' + b + '"""'),
    st.one_of(
        st.text(alphabet=_LITERAL_STRING_CHARS + "\n", max_size=20),
        st.lists(
            st.one_of(
                st.text(alphabet=_LITERAL_STRING_CHARS + "\n", max_size=5),
                st.sampled_from(_NON_ASCII),
            ),
            max_size=6,
        ).map("".join),
    ).map(lambda b: "'''" + b + "'''"),
)

# Malformed string variants (unterminated / stray escapes)
_BAD_STRING = st.sampled_from(
    [
        '"unterminated',
        "'unterminated",
        '"""unterminated',
        "'''unterminated",
        '"bad\\qescape"',
        '"trailing backslash\\"',
        '"\\u12"',
    ]
)

_VALUE_LEAF = st.one_of(
    _STRING,
    _INTEGER,
    _FLOATING,
    _BOOL,
    _DATE_TIME,
    _BAD_STRING,
)


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_UNQUOTED_KEY = st.one_of(
    st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=10),
    st.sampled_from(["a", "key", "1234", "a-b_c", "true", "inf", "nan", "-", "_"]),
    st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=10000),
)

_QUOTED_KEY = st.one_of(
    _basic_string_body().map(lambda b: '"' + b + '"'),
    _literal_string_body().map(lambda b: "'" + b + "'"),
    st.just('""'),
    st.just("''"),
)

_SIMPLE_KEY = st.one_of(_UNQUOTED_KEY, _QUOTED_KEY)

_DOTTED_KEY = st.lists(_SIMPLE_KEY, min_size=2, max_size=4).map(".".join)

_KEY = st.one_of(_SIMPLE_KEY, _DOTTED_KEY)


# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# Depth band: concentrate interesting depth in the 1500-2048 range.
_deep_depth = st.integers(min_value=1500, max_value=2048)

_value = st.recursive(
    _VALUE_LEAF,
    lambda children: st.one_of(
        # arrays
        st.lists(
            st.one_of(children, _VALUE_LEAF),
            max_size=5,
        ).map(lambda xs: "[" + ", ".join(xs) + "]"),
        # arrays with trailing comma
        st.lists(
            st.one_of(children, _VALUE_LEAF),
            min_size=1,
            max_size=4,
        ).map(lambda xs: "[" + ", ".join(xs) + ",]"),
        # multiline arrays with comments
        st.lists(
            st.one_of(children, _VALUE_LEAF),
            max_size=4,
        ).map(lambda xs: "[\n  # comment\n  " + ",\n  ".join(xs) + "\n]"),
        # empty array
        st.just("[]"),
        # inline tables
        st.lists(
            st.tuples(_KEY, st.one_of(children, _VALUE_LEAF)),
            max_size=4,
        ).map(lambda kvs: "{" + ", ".join(k + " = " + v for k, v in kvs) + "}"),
        # inline table with trailing comma
        st.lists(
            st.tuples(_KEY, st.one_of(children, _VALUE_LEAF)),
            min_size=1,
            max_size=3,
        ).map(lambda kvs: "{" + ", ".join(k + " = " + v for k, v in kvs) + ",}"),
        # empty inline table
        st.just("{}"),
    ),
    max_leaves=30,
)


def _deeply_nested_array():
    """Build an array nested to a depth in the 1500-2048 band."""
    return st.builds(
        lambda n: "[" * n + "1" + "]" * n,
        _deep_depth,
    )


def _deeply_nested_inline_table():
    return st.builds(
        lambda n: "{a = " * n + "1" + "}" * n,
        st.integers(min_value=1500, max_value=2048),
    )


_VALUE = st.one_of(
    _value,
    _deeply_nested_array(),
    _deeply_nested_inline_table(),
)


# ---------------------------------------------------------------------------
# Key/value lines, tables, documents
# ---------------------------------------------------------------------------

_KV_LINE = st.builds(
    lambda k, v: k + " = " + v,
    _KEY,
    _VALUE,
)

_COMMENT = st.one_of(
    st.just("#"),
    st.text(alphabet=_BASIC_STRING_CHARS + _RAW_CONTROL_CHARS, max_size=30).map(lambda s: "# " + s),
)

_TABLE_HEADER = _KEY.map(lambda k: "[" + k + "]")
_ARRAY_TABLE_HEADER = _KEY.map(lambda k: "[[" + k + "]]")

_STANDARD_TABLE = st.builds(
    lambda h, body: h + "\n" + body,
    _TABLE_HEADER,
    st.lists(_KV_LINE, min_size=0, max_size=4).map("\n".join),
)

_ARRAY_TABLE = st.builds(
    lambda h, body: h + "\n" + body,
    _ARRAY_TABLE_HEADER,
    st.lists(_KV_LINE, min_size=0, max_size=4).map("\n".join),
)

# Near-valid-but-malformed fragments
_MALFORMED = st.sampled_from(
    [
        "a = ",
        "a =",
        "= 1",
        "a 1",
        "[unclosed",
        "[[unclosed",
        "a = [1, 2",
        "a = {b = 1",
        "a = 1 b = 2",
        "a = 1\nb =",
        "[t]\n[t]\n",
        "a = 1\na = 2\n",
        "a = {b = 1,\nc = 2}",
        "a = [1,\n2]",
        "a = \"unterminated",
        "a = 'unterminated",
        "a = \"\"\"unterminated",
        "a = '''unterminated",
        "a = 1\n=",
        "a.b = 1\na.b = 2\n",
        "[t]\na = 1\n[t]\nb = 2\n",
        "a = {b = 1,}",
        "a = 007",
        "a = 1.",
        "a = .5",
        "a = 1979-02-30",
        "a = \"x\x01y\"",
        "# comment with \x01 control",
        "a = 1  # trailing comment",
        "a = [1, 2,]",
        "a = {b = 1, c = 2,}",
        "a = +inf",
        "a = -nan",
        "a = 0xDEAD_BEEF",
        "a = 0o777",
        "a = 0b1010",
        "a = 1e309",
        "a = 999999999999999999999999999999",
        '"" = 1',
        "'' = 1",
        "a = \"\\u0041\"",
        "a = \"\\U0001F600\"",
    ]
)


def _document():
    """Compose a complete TOML document."""
    parts = st.one_of(
        # key/value lines
        st.lists(_KV_LINE, min_size=1, max_size=6).map("\n".join),
        # tables
        st.lists(st.one_of(_STANDARD_TABLE, _ARRAY_TABLE), min_size=1, max_size=3).map("\n\n".join),
        # mixed: kv lines then tables
        st.tuples(
            st.lists(_KV_LINE, min_size=0, max_size=3).map("\n".join),
            st.lists(st.one_of(_STANDARD_TABLE, _ARRAY_TABLE), min_size=1, max_size=2).map("\n\n".join),
        ).map(lambda t: (t[0] + "\n\n" + t[1]) if t[0] else t[1]),
        # comments only
        st.lists(_COMMENT, min_size=0, max_size=4).map("\n".join),
        # empty document
        st.just(""),
        # malformed
        _MALFORMED,
    )

    return st.builds(
        lambda body, trailing_nl: body + ("\n" if trailing_nl else ""),
        parts,
        st.booleans(),
    )


strategy = _document()
```