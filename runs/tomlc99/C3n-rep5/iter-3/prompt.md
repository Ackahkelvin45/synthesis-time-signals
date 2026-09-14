Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Character pools
# ---------------------------------------------------------------------------

_ASCII_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

# non-ASCII unicode text (for strings and quoted keys)
_UNICODE_TEXT = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
    min_codepoint=0x80,
)

# raw control bytes that are NOT NUL (parser accepts raw control chars in strings)
_RAW_CTRL = st.sampled_from(
    [chr(c) for c in range(1, 0x20) if c != 0x00] + ["\x7f"]
)

_ESCAPE_CHARS = st.sampled_from(['"', "\\", "/", "b", "f", "n", "r", "t"])

_ESCAPE = st.one_of(
    _ESCAPE_CHARS.map(lambda c: "\\" + c),
    st.integers(min_value=0, max_value=0xFFFF).map(
        lambda n: "\\u%04x" % n
    ),
    st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\U%08x" % n
    ),
)

# ---------------------------------------------------------------------------
# Strings: all four quoting forms
# ---------------------------------------------------------------------------

_BASIC_BODY_CHAR = st.one_of(
    _ASCII_SAFE.filter(lambda c: c not in '"\\\n\r'),
    _UNICODE_TEXT.filter(lambda c: c not in '"\\\n\r'),
    _RAW_CTRL.filter(lambda c: c not in '"\\\n\r'),
    _ESCAPE,
)

_BASIC_STRING = st.lists(_BASIC_BODY_CHAR, max_size=12).map(
    lambda cs: '"' + "".join(cs) + '"'
)

_LITERAL_BODY_CHAR = st.one_of(
    _ASCII_SAFE.filter(lambda c: c not in "'\n\r"),
    _UNICODE_TEXT.filter(lambda c: c not in "'\n\r"),
    _RAW_CTRL.filter(lambda c: c not in "'\n\r"),
)

_LITERAL_STRING = st.lists(_LITERAL_BODY_CHAR, max_size=12).map(
    lambda cs: "'" + "".join(cs) + "'"
)

_ML_BASIC_BODY_CHAR = st.one_of(
    _ASCII_SAFE,
    _UNICODE_TEXT,
    _RAW_CTRL,
    _ESCAPE,
    st.sampled_from(["\n", "\t"]),
)

_ML_BASIC_STRING = st.lists(_ML_BASIC_BODY_CHAR, max_size=12).map(
    lambda cs: '"""' + "".join(cs) + '"""'
)

_ML_LITERAL_BODY_CHAR = st.one_of(
    _ASCII_SAFE,
    _UNICODE_TEXT,
    _RAW_CTRL,
    st.sampled_from(["\n", "\t"]),
)

_ML_LITERAL_STRING = st.lists(_ML_LITERAL_BODY_CHAR, max_size=12).map(
    lambda cs: "'''" + "".join(cs) + "'''"
)

_STRING = st.one_of(
    _BASIC_STRING,
    _LITERAL_STRING,
    _ML_BASIC_STRING,
    _ML_LITERAL_STRING,
    st.just('""'),
    st.just("''"),
    st.just('""""""'),
    st.just("''''''"),
)

# ---------------------------------------------------------------------------
# Integers
# ---------------------------------------------------------------------------

_DEC_INT = st.one_of(
    st.integers(min_value=-(2 ** 70), max_value=2 ** 70).map(str),
    st.integers(min_value=0, max_value=2 ** 70).map(lambda n: "+" + str(n)),
    st.just("007"),
    st.just("0"),
    st.just("-0"),
    st.just("1_000_000"),
    st.just(str(2 ** 64)),
    st.just(str(-(2 ** 64))),
    st.just(str(2 ** 200)),
)

_HEX_INT = st.one_of(
    st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0x%x" % n),
    st.integers(min_value=0, max_value=2 ** 64).map(
        lambda n: "0x%X" % n
    ),
    st.just("0xDEAD_BEEF"),
    st.just("0x0"),
)

_OCT_INT = st.one_of(
    st.integers(min_value=0, max_value=2 ** 30).map(lambda n: "0o%o" % n),
    st.just("0o0"),
    st.just("0o7_7_7"),
)

_BIN_INT = st.one_of(
    st.integers(min_value=0, max_value=2 ** 32).map(lambda n: "0b" + bin(n)[2:]),
    st.just("0b0"),
    st.just("0b1_0_1"),
)

_INTEGER = st.one_of(_DEC_INT, _HEX_INT, _OCT_INT, _BIN_INT)

# ---------------------------------------------------------------------------
# Floats
# ---------------------------------------------------------------------------

_FLOAT = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.just("1."),
    st.just(".5"),
    st.just("-1."),
    st.just("+.5"),
    st.just("1e309"),
    st.just("1e-309"),
    st.just("1_000.000_1"),
    st.just("6.626e-34"),
    st.just("0.0"),
    st.just("inf"),
    st.just("-inf"),
    st.just("+inf"),
    st.just("nan"),
    st.just("-nan"),
    st.just("+nan"),
)

# ---------------------------------------------------------------------------
# Booleans / date-times
# ---------------------------------------------------------------------------

_BOOL = st.sampled_from(["true", "false"])

_OFFSET_DT = st.one_of(
    st.just("1979-05-27T07:32:00Z"),
    st.just("1979-05-27T00:32:00-07:00"),
    st.just("1979-05-27T00:32:00.999999-07:00"),
    st.just("1979-05-27 07:32:00Z"),
    st.just("1979-02-30T00:00:00Z"),
    st.just("0000-00-00T00:00:00Z"),
)

_LOCAL_DT = st.one_of(
    st.just("1979-05-27T07:32:00"),
    st.just("1979-05-27T00:32:00.999999"),
    st.just("1979-05-27 07:32:00"),
)

_LOCAL_DATE = st.one_of(
    st.just("1979-05-27"),
    st.just("1979-02-30"),
    st.just("0000-00-00"),
)

_LOCAL_TIME = st.one_of(
    st.just("07:32:00"),
    st.just("00:32:00.999999"),
    st.just("99:99:99"),
)

_DATETIME = st.one_of(_OFFSET_DT, _LOCAL_DT, _LOCAL_DATE, _LOCAL_TIME)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_UNQUOTED_KEY = st.one_of(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_",
        ),
        min_size=1,
        max_size=8,
    ),
    st.just("a"),
    st.just("key"),
    st.just("x-1_2"),
    st.just("007"),
    st.just("A" * 10000),
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
# Comments / whitespace
# ---------------------------------------------------------------------------

_COMMENT_BODY = st.one_of(
    _ASCII_SAFE,
    _UNICODE_TEXT,
    _RAW_CTRL,
).filter(lambda c: c != "\n")

_COMMENT = st.lists(_COMMENT_BODY, max_size=20).map(
    lambda cs: "#" + "".join(cs)
)

_WS = st.sampled_from(["", " ", "  ", "\t", " \t "])

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _join_array(items):
    return "[" + ", ".join(items) + "]"


def _join_inline_table(pairs):
    return "{" + ", ".join(pairs) + "}"


# leaf values (non recursive)
_LEAF_VALUE = st.one_of(
    _STRING,
    _INTEGER,
    _FLOAT,
    _BOOL,
    _DATETIME,
)

# recursive value strategies
_value = st.recursive(
    _LEAF_VALUE,
    lambda children: st.one_of(
        st.lists(children, max_size=4).map(_join_array),
        st.lists(
            st.tuples(_KEY, children).map(lambda kc: kc[0] + " = " + kc[1]),
            max_size=4,
        ).map(_join_inline_table),
    ),
    max_leaves=30,
)

# deep nesting concentrated in the 1500-2048 band
def _deep_array(depth):
    return "[" * depth + "1" + "]" * depth


def _deep_inline_table(depth):
    return "{" + "a = " * depth + "1" + "}" * depth


_DEEP_VALUE = st.one_of(
    st.integers(min_value=1500, max_value=2048).map(_deep_array),
    st.integers(min_value=1500, max_value=2048).map(_deep_inline_table),
)

_VALUE = st.one_of(_value, _DEEP_VALUE)

# ---------------------------------------------------------------------------
# Key-value lines
# ---------------------------------------------------------------------------

def _kv_line(key, value):
    return key + " = " + value


_KV = st.tuples(_KEY, _VALUE).map(lambda kv: _kv_line(kv[0], kv[1]))

_KV_WITH_COMMENT = st.tuples(_KV, st.one_of(st.just(""), _COMMENT)).map(
    lambda kc: kc[0] + (" " + kc[1] if kc[1] else "")
)

# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

_STANDARD_TABLE = _KEY.map(lambda k: "[" + k + "]")

_ARRAY_TABLE = _KEY.map(lambda k: "[[" + k + "]]")

_TABLE = st.one_of(_STANDARD_TABLE, _ARRAY_TABLE)

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs (one missing or doubled delimiter, etc.)
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from(
    [
        # unterminated string
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = '''unterminated",
        # missing closing bracket
        "a = [1, 2, 3",
        # missing closing brace
        "a = {b = 1",
        # doubled delimiter
        "a = [1, 2, 3]]",
        "a = {b = 1}}",
        "a = 1 = 2",
        # stray token
        "a = = 1",
        "= 1",
        "a = ",
        "a ",
        # value on next line
        "a =\n1",
        # invalid escape
        'a = "\\q"',
        # newline inside inline table
        "a = {b = 1,\nc = 2}",
        # bare unicode key
        "café = 1",
        # table redefinition
        "[t]\n[t]\n",
        # duplicate key
        "a = 1\na = 2\n",
        # array of tables / table name clash
        "[t]\n[[t]]\n",
        # missing key
        '[""] = 1\n',
        # empty quoted key is fine but empty bare key is not
        " = 1",
        # unterminated array table
        "[[a]",
        # unterminated standard table
        "[a",
        # leading dot
        ".a = 1",
        # trailing dot
        "a. = 1",
        # doubled dot
        "a..b = 1",
    ]
)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

_EMPTY_DOC = st.just("")

_COMMENT_ONLY = _COMMENT

_EMPTY_TABLE = st.one_of(
    st.just("[t]\n"),
    st.just("[[a]]\n"),
    st.just("[a.b.c]\n"),
)

_LINE_END = st.sampled_from(["\n", "\r\n", "\n"])

def _join_lines(lines):
    return "\n".join(lines)


_BODY = st.lists(
    st.one_of(
        _KV_WITH_COMMENT,
        _TABLE,
        _COMMENT,
        st.just(""),
    ),
    min_size=0,
    max_size=8,
).map(_join_lines)

_DOCUMENT = st.one_of(
    _EMPTY_DOC,
    _COMMENT_ONLY,
    _EMPTY_TABLE,
    _BODY,
    _MALFORMED,
    # document with no trailing newline
    _BODY.map(lambda s: s.rstrip("\n")),
    # CRLF document
    _BODY.map(lambda s: s.replace("\n", "\r\n")),
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _DOCUMENT,
    _VALUE,
    _MALFORMED,
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 54.24,
  "region_coverage_pct": 58.23,
  "least_covered_functions": [
    "toml_utf8_to_ucs (0% of branches)",
    "toml_rtots (0% of branches)",
    "toml_rtod_ex (0% of branches)",
    "toml_parse_file (0% of branches)",
    "norm_lit_str (0% of branches)"
  ]
}

Make EXACTLY ONE change to the strategy: **cover_function** — toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.