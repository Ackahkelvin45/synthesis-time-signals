Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Character classes
# ---------------------------------------------------------------------------

_ASCII_SAFE = st.characters(min_codepoint=0x20, max_codepoint=0x7E)
_BASIC_CHARS = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
        lambda c: c not in '"\\'
    ),
    st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
    st.characters(min_codepoint=0x1F300, max_codepoint=0x1F64F),
    st.sampled_from(["\t", "\x01", "\x02", "\x1f", "\x7f"]),
)

_LITERAL_CHARS = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(lambda c: c != "'"),
    st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
    st.sampled_from(["\t", "\x01", "\x1f"]),
)

_ML_BASIC_CHARS = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
        lambda c: c != '"'
    ),
    st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
    st.sampled_from(["\t", "\n", "\r", "\x01", "\x1f"]),
)

_ML_LITERAL_CHARS = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(lambda c: c != "'"),
    st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
    st.sampled_from(["\t", "\n", "\r", "\x01", "\x1f"]),
)

_UNQUOTED_CHARS = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)

# ---------------------------------------------------------------------------
# Escapes
# ---------------------------------------------------------------------------

_SIMPLE_ESC = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_HEX4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_HEX8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)

_UNICODE_ESC = st.one_of(
    _HEX4.map(lambda h: "\\u" + h),
    _HEX8.map(lambda h: "\\U" + h),
    st.sampled_from(["\\u0000", "\\uD7FF", "\\uFFFF", "\\U00000000", "\\U0010FFFF"]),
)

_ESC = st.one_of(_SIMPLE_ESC, _UNICODE_ESC)

# ---------------------------------------------------------------------------
# Strings (four quoting forms)
# ---------------------------------------------------------------------------

_BASIC_STRING = st.one_of(
    st.lists(st.one_of(_BASIC_CHARS, _ESC), max_size=8).map(
        lambda parts: '"' + "".join(parts) + '"'
    ),
    st.just('""'),
)

_LITERAL_STRING = st.one_of(
    st.lists(_LITERAL_CHARS, max_size=8).map(
        lambda parts: "'" + "".join(parts) + "'"
    ),
    st.just("''"),
)

_ML_BASIC_STRING = st.one_of(
    st.lists(st.one_of(_ML_BASIC_CHARS, _ESC), max_size=8).map(
        lambda parts: '"""' + "".join(parts) + '"""'
    ),
    st.just('""""""'),
)

_ML_LITERAL_STRING = st.one_of(
    st.lists(_ML_LITERAL_CHARS, max_size=8).map(
        lambda parts: "'''" + "".join(parts) + "'''"
    ),
    st.just("''''''"),
)

_STRING = st.one_of(
    _BASIC_STRING, _LITERAL_STRING, _ML_BASIC_STRING, _ML_LITERAL_STRING
)

# Malformed strings: unterminated / doubled delimiters
_MALFORMED_STRING = st.one_of(
    st.lists(_BASIC_CHARS, min_size=0, max_size=6).map(
        lambda parts: '"' + "".join(parts)
    ),
    st.lists(_LITERAL_CHARS, min_size=0, max_size=6).map(
        lambda parts: "'" + "".join(parts)
    ),
    st.just('"unterminated'),
    st.just("'unterminated"),
    st.just('"""abc'),
    st.just("'''abc"),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_DEC_INT = st.one_of(
    st.integers(min_value=-(2 ** 70), max_value=2 ** 70).map(str),
    st.integers(min_value=0, max_value=9).map(str),
    st.sampled_from(
        [
            "0",
            "-0",
            "+0",
            "007",
            "000123",
            "1_000_000",
            "9223372036854775807",
            "9223372036854775808",
            "-9223372036854775808",
            "-9223372036854775809",
            "1" + "0" * 40,
            "9" * 30,
        ]
    ),
)

_HEX_INT = st.one_of(
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=12).map(
        lambda h: "0x" + h
    ),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0x" + "f" * 20]),
)

_OCT_INT = st.one_of(
    st.text(alphabet="01234567", min_size=1, max_size=12).map(lambda o: "0o" + o),
    st.sampled_from(["0o0", "0o777", "0o7_5_5", "0o" + "7" * 20]),
)

_BIN_INT = st.one_of(
    st.text(alphabet="01", min_size=1, max_size=16).map(lambda b: "0b" + b),
    st.sampled_from(["0b0", "0b1010", "0b1_0_1", "0b" + "1" * 40]),
)

_INTEGER = st.one_of(_DEC_INT, _HEX_INT, _OCT_INT, _BIN_INT)

_FLOAT = st.one_of(
    st.sampled_from(
        [
            "1.0",
            "0.0",
            "-0.0",
            "+1.5",
            "1e10",
            "1E10",
            "1e+10",
            "1e-10",
            "1.5e10",
            "1.5E-10",
            "1.",
            ".5",
            "007.5",
            "1_000.000_1",
            "1e309",
            "-1e309",
            "1e-400",
            "3.141592653589793",
            "1" + "0" * 30 + ".0",
        ]
    ),
    st.integers(min_value=-1000, max_value=1000).map(lambda n: f"{n}.0"),
    st.integers(min_value=-100, max_value=100).map(lambda n: f"{n}e{n}"),
)

_INF_NAN = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
)

_FLOATING = st.one_of(_FLOAT, _INF_NAN)

# ---------------------------------------------------------------------------
# Booleans, dates
# ---------------------------------------------------------------------------

_BOOL = st.sampled_from(["true", "false"])

_DATE = st.one_of(
    st.sampled_from(
        [
            "1979-05-27",
            "0000-00-00",
            "1979-02-30",
            "2024-13-45",
            "9999-12-31",
        ]
    ),
    st.tuples(
        st.integers(min_value=0, max_value=9999).map(lambda n: f"{n:04d}"),
        st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
        st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
    ).map(lambda t: t[0] + "-" + t[1] + "-" + t[2]),
)

_TIME = st.one_of(
    st.sampled_from(
        [
            "07:32:00",
            "00:00:00",
            "23:59:59",
            "07:32:00.999",
            "99:99:99",
        ]
    ),
    st.tuples(
        st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
        st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
        st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
    ).map(lambda t: t[0] + ":" + t[1] + ":" + t[2]),
)

_DATE_TIME = st.one_of(
    _DATE,
    _TIME,
    st.tuples(_DATE, _TIME).map(lambda t: t[0] + "T" + t[1]),
    st.tuples(_DATE, _TIME).map(lambda t: t[0] + " " + t[1]),
    st.tuples(_DATE, _TIME).map(lambda t: t[0] + "t" + t[1]),
    st.tuples(_DATE, _TIME).map(lambda t: t[0] + "T" + t[1] + "Z"),
    st.tuples(_DATE, _TIME).map(lambda t: t[0] + "T" + t[1] + "+07:00"),
    st.tuples(_DATE, _TIME).map(lambda t: t[0] + "T" + t[1] + "-05:30"),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_UNQUOTED_KEY = st.one_of(
    st.text(alphabet=list("abcdefghijklmnopqrstuvwxyz0123456789_-"), min_size=1, max_size=10),
    st.text(alphabet=list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), min_size=1, max_size=6),
    st.just("a"),
    st.just("k" * 100),
    st.just("-"),
    st.just("_"),
    st.just("0"),
)

_QUOTED_KEY = st.one_of(
    _BASIC_STRING,
    _LITERAL_STRING,
    st.just('""'),
    st.just("''"),
)

_SIMPLE_KEY = st.one_of(_UNQUOTED_KEY, _QUOTED_KEY)

_DOTTED_KEY = st.lists(_SIMPLE_KEY, min_size=2, max_size=4).map(
    lambda ks: ".".join(ks)
)

_KEY = st.one_of(_SIMPLE_KEY, _DOTTED_KEY)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# We build the recursive value strategy with st.recursive.
# Base values (non-recursive) are all scalars.

_SCALAR = st.one_of(
    _STRING,
    _INTEGER,
    _FLOATING,
    _BOOL,
    _DATE_TIME,
)

# For malformed / near-valid coverage, we add a few "junk" scalars that are
# deliberately not valid TOML values.
_JUNK_VALUE = st.sampled_from(
    [
        "",
        "=",
        "==",
        "[",
        "]",
        "{",
        "}",
        ",",
        ".",
        "true false",
        "0123abc",
        "1.2.3",
        "0x",
        "0b2",
        "1979-05-27T",
        "@",
        "#",
    ]
)

# Inline table key-value pairs: key = value
# We approximate "value" here as a scalar or a shallow recursive value.
# To avoid infinite recursion with st.recursive, we use a two-level approach:
# a shallow value strategy used inside inline tables and arrays, and the
# full recursive one built on top.

def _array_strategy(value_strategy):
    """Build an array around a given value strategy."""
    # Array element: value plus optional trailing comma, optional comment/newline
    elem = value_strategy
    # A few structured variants
    return st.one_of(
        # Empty array
        st.just("[]"),
        # Single element
        elem.map(lambda v: "[" + v + "]"),
        # Multiple elements
        st.lists(elem, min_size=1, max_size=4).map(
            lambda vs: "[" + ", ".join(vs) + "]"
        ),
        # Trailing comma
        elem.map(lambda v: "[" + v + ",]"),
        st.lists(elem, min_size=1, max_size=3).map(
            lambda vs: "[" + ", ".join(vs) + ",]"
        ),
        # Multiline array
        st.lists(elem, min_size=1, max_size=3).map(
            lambda vs: "[\n  " + ",\n  ".join(vs) + ",\n]"
        ),
        # Array with comments
        st.lists(elem, min_size=1, max_size=3).map(
            lambda vs: "[\n  # comment\n  " + ",\n  ".join(vs) + "\n]"
        ),
        # Malformed: missing closing bracket
        elem.map(lambda v: "[" + v),
        # Malformed: doubled closing bracket
        elem.map(lambda v: "[" + v + "]]"),
        # Malformed: stray comma
        st.just("[,]"),
        st.just("[1,,2]"),
    )


def _inline_table_strategy(value_strategy):
    """Build an inline table around a given value strategy."""
    pair = st.tuples(_KEY, value_strategy).map(lambda t: t[0] + " = " + t[1])
    return st.one_of(
        # Empty inline table
        st.just("{}"),
        # Single pair
        pair.map(lambda p: "{" + p + "}"),
        # Multiple pairs
        st.lists(pair, min_size=1, max_size=3).map(
            lambda ps: "{" + ", ".join(ps) + "}"
        ),
        # Trailing comma (accepted by this parser)
        pair.map(lambda p: "{" + p + ",}"),
        st.lists(pair, min_size=1, max_size=3).map(
            lambda ps: "{" + ", ".join(ps) + ",}"
        ),
        # Malformed: missing closing brace
        pair.map(lambda p: "{" + p),
        # Malformed: doubled closing brace
        pair.map(lambda p: "{" + p + "}}"),
        # Malformed: stray comma
        st.just("{,}"),
        # Malformed: newline inside inline table (rejected)
        pair.map(lambda p: "{\n" + p + "\n}"),
    )


# Build the recursive value strategy.
# Leaf values are scalars and junk; recursive constructors are arrays and
# inline tables. We use st.recursive with a moderate max_leaves to keep
# generation fast while allowing deep nesting.

_LEAF = st.one_of(_SCALAR, _JUNK_VALUE)

def _extend(children):
    return st.one_of(_array_strategy(children), _inline_table_strategy(children))

_VALUE = st.recursive(_LEAF, _extend, max_leaves=20)

# ---------------------------------------------------------------------------
# Key-value pairs and expressions
# ---------------------------------------------------------------------------

_KV = st.tuples(_KEY, _VALUE).map(lambda t: t[0] + " = " + t[1])

_COMMENT = st.one_of(
    st.just(""),
    st.text(alphabet=list("abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.!@#$%^&*()"), min_size=1, max_size=30).map(
        lambda s: "# " + s
    ),
    st.just("#"),
    st.just("# " + "\x01" + " control"),
    st.just("# comment with \x7f"),
)

_EXPRESSION = st.one_of(
    _KV.map(lambda kv: kv),
    _COMMENT,
    # Table headers
    _KEY.map(lambda k: "[" + k + "]"),
    _KEY.map(lambda k: "[[" + k + "]]"),
    # Malformed table headers
    _KEY.map(lambda k: "[" + k),
    _KEY.map(lambda k: "[" + k + "]]"),
    _KEY.map(lambda k: "[[" + k + "]"),
    _KEY.map(lambda k: "[" + k + "] trailing"),
)

# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

def _join_lines(lines):
    return "\n".join(lines)


_DOCUMENT = st.one_of(
    # Empty document
    st.just(""),
    # Comment-only
    _COMMENT,
    # Single expression
    _EXPRESSION,
    # Multiple expressions
    st.lists(_EXPRESSION, min_size=1, max_size=8).map(_join_lines),
    # With trailing newline
    st.lists(_EXPRESSION, min_size=1, max_size=8).map(
        lambda ls: "\n".join(ls) + "\n"
    ),
    # With CRLF
    st.lists(_EXPRESSION, min_size=1, max_size=6).map(
        lambda ls: "\r\n".join(ls)
    ),
    # With tab indentation
    st.lists(_EXPRESSION, min_size=1, max_size=6).map(
        lambda ls: "\n".join("\t" + l for l in ls)
    ),
    # Malformed: stray token
    st.lists(_EXPRESSION, min_size=1, max_size=4).map(
        lambda ls: "\n".join(ls) + "\n@"
    ),
    # Malformed: doubled equals
    st.tuples(_KEY, _VALUE).map(lambda t: t[0] + " == " + t[1]),
    # Malformed: missing value
    _KEY.map(lambda k: k + " ="),
    # Malformed: value on next line
    st.tuples(_KEY, _VALUE).map(lambda t: t[0] + " =\n" + t[1]),
    # Malformed: unterminated string value
    st.tuples(_KEY, _MALFORMED_STRING).map(lambda t: t[0] + " = " + t[1]),
    # Duplicate keys (rejected)
    st.tuples(_KEY, _VALUE, _VALUE).map(
        lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[2]
    ),
    # Non-ASCII bare key (rejected)
    st.just("caf\u00e9 = 1"),
    st.just("\u00fcber = 2"),
    # Empty quoted key
    st.just('"" = 1'),
    st.just("'' = 2"),
    # Super-table after sub-table
    st.just("[a.b]\nx = 1\n[a]\ny = 2"),
    # Array of tables
    st.just("[[a]]\nx = 1\n[[a]]\ny = 2"),
    # Table and array of tables with same name (rejected)
    st.just("[a]\nx = 1\n[[a]]\ny = 2"),
    # Dotted key redefining table (rejected)
    st.just("[a]\nb = 1\n[a.b]\nc = 2"),
)

# ---------------------------------------------------------------------------
# Deep nesting: arrays and inline tables up to ~2048 levels
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_inline_table(depth):
    # {a = {a = {a = ... }}}
    return "{a = " * depth + "1" + "}" * depth


_DEEP = st.one_of(
    st.integers(min_value=1500, max_value=2048).map(_deep_array),
    st.integers(min_value=1, max_value=100).map(_deep_array),
    st.integers(min_value=1, max_value=50).map(_deep_inline_table),
    st.integers(min_value=1500, max_value=2048).map(
        lambda d: "a = " + _deep_array(d)
    ),
    st.integers(min_value=1, max_value=100).map(
        lambda d: "a = " + _deep_inline_table(d)
    ),
)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _DOCUMENT,
    _DEEP,
    # A few hand-crafted edge cases
    st.sampled_from(
        [
            "",
            "\n",
            "# only a comment",
            "# only a comment\n",
            "a = 1",
            "a = 1\n",
            "a = 1\r\n",
            "a = 007",
            "a = 1.",
            "a = .5",
            "a = 1e309",
            "a = -1e309",
            "a = inf",
            "a = -inf",
            "a = nan",
            "a = true",
            "a = false",
            "a = 0xDEADBEEF",
            "a = 0o777",
            "a = 0b1010",
            "a = 1_000_000",
            "a = 1979-05-27",
            "a = 07:32:00",
            "a = 1979-05-27T07:32:00",
            "a = 1979-05-27T07:32:00Z",
            "a = 1979-05-27 07:32:00Z",
            "a = 1979-02-30",
            "a = \"x\x01y\"",
            "a = \"\\u0000\"",
            "a = \"\\uFFFF\"",
            "a = \"\\U0010FFFF\"",
            "a = \"\\q\"",
            "a = \"unterminated",
            "a = 'literal'",
            "a = '''ml literal'''",
            'a = """ml basic"""',
            'a = """multi\nline"""',
            "a = []",
            "a = [1, 2, 3]",
            "a = [1, 2, 3,]",
            "a = [[1, 2], [3, 4]]",
            "a = [\n  1,\n  2,\n]",
            "a = [\n  # comment\n  1,\n]",
            "a = {}",
            "a = {b = 1}",
            "a = {b = 1, c = 2}",
            "a = {b = 1,}",
            "a = {b = {c = 1}}",
            "a = {b = 1\n}",
            "[t]",
            "[t]\na = 1",
            "[[t]]",
            "[[t]]\na = 1",
            "[a.b.c]",
            "[a.b.c]\nx = 1",
            '["quoted key"]',
            "['literal key']",
            '"" = 1',
            "'' = 2",
            "a.b = 1",
            "a.b.c = 1",
            "a = 1\na = 2",
            "[a]\n[a]",
            "[[a]]\n[[a]]",
            "[a]\n[[a]]",
            "[a]\nb = 1\n[a.b]\nc = 2",
            "[a.b]\nx = 1\n[a]\ny = 2",
            "caf\u00e9 = 1",
            "\u00fcber = 2",
            "a = 1\n@",
            "a =",
            "a == 1",
            "a =\n1",
            "a = [1,",
            "a = {b = 1",
            "a = [1]]",
            "a = {b = 1}}",
            "a = [,]",
            "a = {,}",
            "a = [1,,2]",
            "a = \"\"\"abc",
            "a = '''abc",
            "a = 'unterminated",
            "a = 1\nb = 2\nc = 3\n",
            "a = 1 # comment\nb = 2 # another\n",
            "# comment with \x01 control",
            "# comment with \x7f",
            "a = \"tab\there\"",
            "a = \"newline\\nhere\"",
            "a = \"quote\\\"here\"",
            "a = \"backslash\\\\here\"",
            "a = \"slash\\/here\"",
            "a = \"unicode\\u00e9\"",
            "a = \"emoji \U0001F600\"",
            "a = \"\u00e9\u00e8\u00ea\"",
            "key" + "x" * 9990 + " = 1",
            "a = " + "[" * 2048 + "]" * 2048,
            "a = " + "{a = " * 50 + "1" + "}" * 50,
        ]
    ),
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 66,
    "reject": 284
  },
  "acceptance_rate": 0.189,
  "max_nesting_depth": 1772,
  "productions_accepted": [
    "BASIC_STRING",
    "COMMENT",
    "DEC_INT",
    "LITERAL_STRING",
    "NL",
    "UNQUOTED_KEY",
    "array_",
    "array_table",
    "array_values",
    "comment",
    "comment_or_nl",
    "document",
    "dotted_key",
    "expression",
    "integer",
    "key",
    "key_value",
    "nl_or_comment",
    "quoted_key",
    "simple_key",
    "standard_table",
    "string",
    "table",
    "unquoted_key",
    "value"
  ],
  "productions_gap": [
    "floating_point",
    "bool_",
    "date_time",
    "inline_table",
    "inline_table_keyvals",
    "inline_table_keyvals_non_empty",
    "BOOLEAN",
    "ML_BASIC_STRING",
    "ML_LITERAL_STRING",
    "FLOAT",
    "INF",
    "NAN",
    "HEX_INT",
    "OCT_INT",
    "BIN_INT",
    "OFFSET_DATE_TIME",
    "LOCAL_DATE_TIME",
    "LOCAL_DATE",
    "LOCAL_TIME"
  ],
  "cap_distance_mass": 0.015,
  "novelty": 19,
  "divergences": 12,
  "divergence_examples": [
    "b'# comment with \\x7f'",
    "b'[\"\\\\U00000000\"]\\n[00000000]\\n# comment with \\x7f'",
    "b'# comment with \\x7f\\n[00000000]\\n# comment with \\x7f'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **add_or_upweight_production** — floating_point.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.