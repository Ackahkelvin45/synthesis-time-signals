Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters that are safe as raw content inside strings (no NUL, no quote/backslash
# unless escaped).  We allow raw control chars (parser accepts them).
_RAW_STRING_CHARS = st.characters(
    blacklist_categories=["Cs"],  # avoid surrogates
    blacklist_characters="\x00",  # never emit a raw NUL
)

# Characters allowed in comments (no NUL).
_COMMENT_CHARS = st.characters(
    blacklist_categories=["Cs"],
    blacklist_characters="\x00\n",
)

# Bare-key characters per grammar: [A-Za-z0-9_-]+
_BARE_KEY_CHARS = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)

# ---------------------------------------------------------------------------
# Strings (all four quoting forms, escapes, non-ASCII, control bytes)
# ---------------------------------------------------------------------------

_ESCAPE_SEQS = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

# \uXXXX and \UXXXXXXXX escapes (allow \u0000 inside strings)
_UNICODE_ESCAPE = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda cp: "\\u%04X" % cp if cp <= 0xFFFF else "\\U%08X" % cp
)

# A single "unit" inside a basic string: raw char, escape, or unicode escape.
_BASIC_STRING_UNIT = st.one_of(
    _RAW_STRING_CHARS.filter(lambda c: c not in '"\\\n'),
    _ESCAPE_SEQS,
    _UNICODE_ESCAPE,
    st.just("\x01"),  # raw control char (parser accepts)
    st.just("\t"),
)

_BASIC_STRING = st.lists(
    _BASIC_STRING_UNIT, min_size=0, max_size=12
).map(lambda parts: '"' + "".join(parts) + '"')

# Literal string: single quotes, no escapes, no newline, no single quote.
_LITERAL_STRING = st.lists(
    _RAW_STRING_CHARS.filter(lambda c: c not in "'\n"),
    min_size=0,
    max_size=12,
).map(lambda parts: "'" + "".join(parts) + "'")

# Multiline basic string: """ ... """ with optional escapes and newlines.
_ML_BASIC_UNIT = st.one_of(
    _RAW_STRING_CHARS.filter(lambda c: c not in "\\"),
    _ESCAPE_SEQS,
    _UNICODE_ESCAPE,
    st.just("\n"),
    st.just("\r\n"),
    st.just("\t"),
    st.just("\x01"),
)
_ML_BASIC_STRING = st.lists(
    _ML_BASIC_UNIT, min_size=0, max_size=10
).map(lambda parts: '"""' + "".join(parts) + '"""')

# Multiline literal string: ''' ... ''' with anything except the terminator.
_ML_LITERAL_STRING = st.lists(
    _RAW_STRING_CHARS.filter(lambda c: c != "'"),
    min_size=0,
    max_size=10,
).map(lambda parts: "'''" + "".join(parts) + "'''")

_STRING = st.one_of(
    _BASIC_STRING,
    _LITERAL_STRING,
    _ML_BASIC_STRING,
    _ML_LITERAL_STRING,
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_UNQUOTED_KEY = st.lists(
    _BARE_KEY_CHARS, min_size=1, max_size=10
).map(lambda cs: "".join(cs))

_QUOTED_KEY = st.one_of(
    _BASIC_STRING.filter(lambda s: "\n" not in s),
    _LITERAL_STRING,
    st.just('""'),  # empty quoted key
)

_SIMPLE_KEY = st.one_of(_QUOTED_KEY, _UNQUOTED_KEY)

# Dotted key: simple_key (DOT simple_key)+
_DOTTED_KEY = st.lists(
    _SIMPLE_KEY, min_size=2, max_size=4
).map(lambda ks: ".".join(ks))

_KEY = st.one_of(_SIMPLE_KEY, _DOTTED_KEY)

# ---------------------------------------------------------------------------
# Integers (all bases, underscores, extremes, leading zeros)
# ---------------------------------------------------------------------------

_DEC_INT = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.integers(min_value=-10**6, max_value=10**6).map(str),
    # leading zeros (parser accepts)
    st.integers(min_value=0, max_value=999).map(lambda n: "0%03d" % n),
    # underscores
    st.integers(min_value=0, max_value=10**12).map(
        lambda n: "{:,}".format(n).replace(",", "_")
    ),
    st.just("0"),
    st.just("-0"),
    st.just("+0"),
)

_HEX_INT = st.integers(min_value=0, max_value=0xFFFFFFFF).map(
    lambda n: "0x%X" % n
)
_OCT_INT = st.integers(min_value=0, max_value=0o777777).map(
    lambda n: "0o%o" % n
)
_BIN_INT = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "0b" + format(n, "b")
)

_INTEGER = st.one_of(_DEC_INT, _HEX_INT, _OCT_INT, _BIN_INT)

# ---------------------------------------------------------------------------
# Floats (incl. inf/nan, extremes, malformed-ish forms)
# ---------------------------------------------------------------------------

_FLOAT = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(
        [
            "1.",
            ".5",
            "0.0",
            "-0.0",
            "1e10",
            "1E10",
            "1e+10",
            "1e-10",
            "1e309",
            "-1e309",
            "1_000.0",
            "3.14159",
            "1.0e-300",
            "1.0e+300",
        ]
    ),
    st.just("inf"),
    st.just("-inf"),
    st.just("+inf"),
    st.just("nan"),
    st.just("-nan"),
    st.just("+nan"),
)

# ---------------------------------------------------------------------------
# Booleans
# ---------------------------------------------------------------------------

_BOOL = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Date-times (all four forms, including calendar-invalid)
# ---------------------------------------------------------------------------

_YEAR = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_MONTH = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_DAY = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_HOUR = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_MINUTE = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_SECOND = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_SECFRAC = st.integers(min_value=0, max_value=999999).map(lambda n: ".%06d" % n)

_FULL_DATE = st.tuples(_YEAR, _MONTH, _DAY).map(lambda t: "-".join(t))
_PARTIAL_TIME = st.tuples(_HOUR, _MINUTE, _SECOND).map(
    lambda t: ":".join(t)
)
_PARTIAL_TIME_FRAC = st.tuples(_PARTIAL_TIME, _SECFRAC).map(
    lambda t: t[0] + t[1]
)
_OFFSET = st.one_of(
    st.just("Z"),
    st.tuples(
        st.sampled_from(["+", "-"]), _HOUR, _MINUTE
    ).map(lambda t: t[0] + t[1] + ":" + t[2]),
)

_LOCAL_DATE = _FULL_DATE
_LOCAL_TIME = _PARTIAL_TIME_FRAC
_LOCAL_DATE_TIME = st.tuples(
    _FULL_DATE, st.sampled_from(["T", "t", " "]), _PARTIAL_TIME_FRAC
).map(lambda t: t[0] + t[1] + t[2])
_OFFSET_DATE_TIME = st.tuples(
    _FULL_DATE, st.sampled_from(["T", "t", " "]), _PARTIAL_TIME_FRAC, _OFFSET
).map(lambda t: t[0] + t[1] + t[2] + t[3])

_DATE_TIME = st.one_of(
    _OFFSET_DATE_TIME,
    _LOCAL_DATE_TIME,
    _LOCAL_DATE,
    _LOCAL_TIME,
)

# ---------------------------------------------------------------------------
# Recursive productions: value -> array / inline table
# ---------------------------------------------------------------------------

# We build the recursive grammar with st.recursive.  The "leaf" strategy
# produces scalar values; the "extend" strategy produces arrays and inline
# tables that contain values.

_SCALAR = st.one_of(
    _STRING,
    _INTEGER,
    _FLOAT,
    _BOOL,
    _DATE_TIME,
)

# A comment line fragment (no NUL).
_COMMENT = st.lists(
    _COMMENT_CHARS, min_size=0, max_size=20
).map(lambda cs: "#" + "".join(cs))

# Whitespace / newline fragments for arrays.
_WS = st.sampled_from(["", " ", "\t"])
_NL = st.sampled_from(["\n", "\r\n"])

# Recursive value strategy.  Depth band: the parser recurses per nesting level;
# 1500-2048 is the interesting band.  Hypothesis st.recursive controls depth
# via the `max_leaves` parameter, but we also want explicit deep nesting.
# We use st.recursive with a moderate max_leaves and rely on the recursive
# structure to produce nesting.  For targeted deep nesting we add a separate
# strategy that wraps a scalar in many array brackets.

def _array_of(value_st):
    """Build an array strategy: '[' (values sep by ',') ']' with optional
    newlines/comments and trailing comma."""
    def make_array(items):
        # items is a list of value strings
        if not items:
            return "[]"
        sep = st.one_of(
            st.just(", "),
            st.just(","),
            st.just(",\n"),
            st.just(", # c\n"),
        )
        # We can't easily use st inside a map, so just join with a fixed
        # separator and add optional trailing comma/newlines.
        body = ", ".join(items)
        # Randomly add newlines/comments around
        return "[" + body + "]"

    # Use st.lists of value_st
    return st.lists(value_st, min_size=0, max_size=5).map(make_array)


def _inline_table_of(value_st):
    """Build an inline table: '{' key = value (, key = value)* '}'"""
    def make_inline(pairs):
        if not pairs:
            return "{}"
        body = ", ".join("%s = %s" % (k, v) for k, v in pairs)
        return "{" + body + "}"

    pair_st = st.tuples(_KEY, value_st)
    return st.lists(pair_st, min_size=0, max_size=4).map(make_inline)


# st.recursive: base = scalar, extend = array/inline table of recursive value.
_VALUE = st.recursive(
    _SCALAR,
    lambda children: st.one_of(
        _array_of(children),
        _inline_table_of(children),
    ),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Deep nesting strategy (targeted at the 1500-2048 band)
# ---------------------------------------------------------------------------

_DEEP_DEPTH = st.integers(min_value=1500, max_value=2048)

def _deep_array(depth):
    """Build a deeply nested array string of the given depth."""
    # innermost scalar
    inner = "1"
    return "[" * depth + inner + "]" * depth

_DEEP_ARRAY = _DEEP_DEPTH.map(_deep_array)

# Deep inline tables: {a = {a = {a = ... }}}
def _deep_inline(depth):
    inner = "1"
    for _ in range(depth):
        inner = "{a = " + inner + "}"
    return inner

_DEEP_INLINE = _DEEP_DEPTH.map(_deep_inline)

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs (one missing/doubled delimiter, unterminated
# string, stray token)
# ---------------------------------------------------------------------------

_MALFORMED = st.one_of(
    # missing closing bracket
    st.just("a = [1, 2"),
    # doubled closing bracket
    st.just("a = [1, 2]]"),
    # missing closing brace
    st.just("a = {b = 1"),
    # doubled closing brace
    st.just("a = {b = 1}}"),
    # unterminated string
    st.just('a = "unterminated'),
    st.just("a = 'unterminated"),
    # stray token
    st.just("a = 1 2"),
    st.just("a = ,"),
    st.just("= 1"),
    st.just("a ="),
    # newline inside inline table (rejected)
    st.just("a = {b = 1,\nc = 2}"),
    # invalid escape
    st.just('a = "\\q"'),
    # non-ASCII bare key (rejected)
    st.just("café = 1"),
    # duplicate key
    st.just("a = 1\na = 2"),
    # duplicate table
    st.just("[t]\n[t]"),
    # value on next line
    st.just("a =\n1"),
)

# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

# A key/value line: key = value, optionally followed by comment.
_KV_LINE = st.tuples(
    _KEY, _WS, _VALUE, _WS, st.one_of(st.just(""), _COMMENT)
).map(lambda t: "%s%s=%s%s%s" % (t[0], t[1], t[2], t[3], t[4]))

# A standard table header: [key]
_STD_TABLE = _KEY.map(lambda k: "[%s]" % k)

# An array-of-tables header: [[key]]
_ARRAY_TABLE = _KEY.map(lambda k: "[[%s]]" % k)

# A comment-only line.
_COMMENT_LINE = _COMMENT

# A blank line.
_BLANK = st.just("")

# An expression is one of these.
_EXPRESSION = st.one_of(
    _KV_LINE,
    _STD_TABLE,
    _ARRAY_TABLE,
    _COMMENT_LINE,
    _BLANK,
)

# A document is a sequence of expressions separated by newlines.
_DOCUMENT = st.lists(
    _EXPRESSION, min_size=0, max_size=20
).map(lambda lines: "\n".join(lines))

# ---------------------------------------------------------------------------
# Top-level strategy: combine valid documents, deep nesting, malformed inputs,
# and edge cases.
# ---------------------------------------------------------------------------

_EDGE_DOCS = st.sampled_from(
    [
        "",
        "\n",
        "# comment only\n",
        "a = 1",
        "a = 1\n",
        "[t]\n",
        "[[a]]\n",
        "a = []\n",
        "a = {}\n",
        '"" = 1\n',
        "a = 1979-02-30\n",  # calendar-invalid
        "a = 007\n",          # leading zeros
        "a = 1.\n",           # float no frac digits
        "a = .5\n",           # float no leading digit
        "a = {b = 1,}\n",     # trailing comma inline table
        'a = "x\x01y"\n',     # raw control char in string
        "# comment with \x01 control\n",
        "a = 1e309\n",
        "a = 0xFFFFFFFFFFFFFFFF\n",
        "a = 1_000\n",
        "a = inf\n",
        "a = nan\n",
        "a = -inf\n",
        "a = 1979-05-27T07:32:00Z\n",
        "a = 1979-05-27 07:32:00Z\n",
        "a = 07:32:00\n",
        "a = 1979-05-27\n",
        "a = 1979-05-27T07:32:00\n",
        "a = '''\nmulti\nline\n'''\n",
        'a = """\nmulti\nline\n"""\n',
        'a = "\\u0000"\n',  # NUL escape inside string (allowed)
        "a = 1\r\nb = 2\r\n",  # CRLF
        "\ta = 1\n",  # tab indentation
        "a.b.c = 1\n",
        '"quoted key" = 1\n',
        "'literal key' = 1\n",
    ]
)

# Deep nesting docs
_DEEP_DOCS = st.one_of(
    _DEEP_ARRAY.map(lambda s: "a = " + s),
    _DEEP_INLINE.map(lambda s: "a = " + s),
)

strategy = st.one_of(
    _DOCUMENT,
    _EDGE_DOCS,
    _MALFORMED,
    _DEEP_DOCS,
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 71.71,
  "region_coverage_pct": 71.94,
  "least_covered_functions": [
    "toml_utf8_to_ucs (0% of branches)",
    "toml_parse_file (0% of branches)",
    "norm_lit_str (0% of branches)",
    "toml_rtos (0% of branches)",
    "toml_timestamp_at (0% of branches)"
  ]
}

Make EXACTLY ONE change to the strategy: **cover_function** — toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.