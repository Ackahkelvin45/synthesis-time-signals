Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

# Characters allowed in bare keys (ASCII only)
_bare_key_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

def _bare_key():
    return st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)

# Non-ASCII and control characters for "weird" strings (but no NUL)
_weird_chars = st.one_of(
    st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_categories=("Cs",)),
    st.sampled_from(["\x01", "\x02", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x7f"]),
)

# ---------------------------------------------------------------------------
# Strings: four quoting forms, escapes, non-ASCII, control chars
# ---------------------------------------------------------------------------

_escape = st.sampled_from([
    "\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0041", "\\u00e9", "\\u20ac", "\\U0001F600", "\\u0000",
])

_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters='"\\\n'),
    st.sampled_from(["\t", "\x01", "\x0b", "\x0c", "\x1b", "\x7f"]),
)

_basic_string = st.lists(
    st.one_of(_basic_char, _escape), max_size=8
).map(lambda parts: '"' + "".join(parts) + '"')

_literal_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters="'\n"),
    st.sampled_from(["\t", "\x01", "\x0b", "\x0c", "\x1b", "\x7f"]),
)

_literal_string = st.lists(_literal_char, max_size=8).map(
    lambda parts: "'" + "".join(parts) + "'"
)

_ml_basic_inner = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters='"\\'),
    st.sampled_from(["\n", "\t", "\r", "\x01", "\x1b"]),
    _escape,
)

_ml_basic_string = st.lists(_ml_basic_inner, max_size=10).map(
    lambda parts: '"""' + "".join(parts) + '"""'
)

_ml_literal_inner = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters="'"),
    st.sampled_from(["\n", "\t", "\r", "\x01", "\x1b"]),
)

_ml_literal_string = st.lists(_ml_literal_inner, max_size=10).map(
    lambda parts: "'''" + "".join(parts) + "'''"
)

_string_value = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------------------------------------------------------------------------
# Numbers: integers (all bases, underscores, extremes), floats
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.sampled_from([
        "0", "1", "007", "000", "+0", "-0", "1_000", "1_0_0",
        "9223372036854775807", "9223372036854775808",
        "-9223372036854775808", "99999999999999999999999999999999",
        "1_2_3_4_5",
    ]),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=0xFFFFFFFFFFFFFFFF).map(lambda n: "0x" + format(n, "x")),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF"]),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=0o7777777777777777).map(lambda n: "0o" + format(n, "o")),
    st.sampled_from(["0o0", "0o777", "0o1_2_3", "0o755"]),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from(["0b0", "0b1", "0b1010_1010", "0b11111111"]),
)

_integer_value = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float_value = st.one_of(
    st.sampled_from([
        "1.0", "-1.0", "+1.0", "3.14159", "1e10", "1E10", "1e+10", "1e-10",
        "1.5e10", "-1.5E-10", "1.", ".5", "0.0", "-0.0", "1e309", "-1e309",
        "1_000.000_1", "inf", "+inf", "-inf", "nan", "+nan", "-nan",
        "1e0", "0e0", "6.626e-34", "1.7976931348623157e308",
    ]),
    st.floats(allow_nan=True, allow_infinity=True).map(repr),
)

# ---------------------------------------------------------------------------
# Booleans, date-times
# ---------------------------------------------------------------------------

_bool_value = st.sampled_from(["true", "false"])

_date_time_value = st.sampled_from([
    "1979-05-27T07:32:00Z",
    "1979-05-27T00:32:00-07:00",
    "1979-05-27T00:32:00+07:00",
    "1979-05-27T07:32:00",
    "1979-05-27T07:32:00.999999",
    "1979-05-27 07:32:00Z",
    "1979-05-27",
    "07:32:00",
    "00:32:00.999999",
    "1979-02-30",
    "0000-00-00",
    "9999-12-31T23:59:59Z",
    "1979-05-27t07:32:00z",
    "1979-05-27T07:32:00.5+00:00",
])

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_bare_key(), _quoted_key)

def _dotted_key():
    return st.lists(_simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key())

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# Depth band 1500-2048 is interesting; but we also want shallow coverage.
_depth_strategy = st.integers(min_value=0, max_value=8)

# We'll build a recursive strategy for values.
# Leaf values are all non-container kinds.
_leaf_value = st.one_of(
    _string_value,
    _integer_value,
    _float_value,
    _bool_value,
    _date_time_value,
)

def _array_from_values(values):
    """values: list of strings already representing TOML values."""
    if not values:
        return "[]"
    return "[" + ", ".join(values) + "]"

def _inline_table_from_pairs(pairs):
    """pairs: list of (key, value) strings."""
    if not pairs:
        return "{}"
    return "{" + ", ".join(k + " = " + v for k, v in pairs) + "}"

# Use @st.composite to build recursive values with controlled depth.
@st.composite
def _value(draw, depth=0):
    if depth >= 6:
        return draw(_leaf_value)
    # choose leaf or container
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return draw(_leaf_value)
    elif kind == 1:
        # array
        n = draw(st.integers(min_value=0, max_value=4))
        elems = [draw(_value(depth + 1)) for _ in range(n)]
        return _array_from_values(elems)
    else:
        # inline table
        n = draw(st.integers(min_value=0, max_value=3))
        pairs = []
        for _ in range(n):
            k = draw(_key)
            v = draw(_value(depth + 1))
            pairs.append((k, v))
        return _inline_table_from_pairs(pairs)

# ---------------------------------------------------------------------------
# Key/value lines, tables, array tables
# ---------------------------------------------------------------------------

def _key_value_line():
    return st.tuples(_key, _value()).map(lambda kv: kv[0] + " = " + kv[1])

def _table_header():
    return st.tuples(_key).map(lambda k: "[" + k[0] + "]")

def _array_table_header():
    return st.tuples(_key).map(lambda k: "[[" + k[0] + "]]")

def _comment_line():
    return st.one_of(
        st.just("#"),
        st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_categories=("Cs",), blacklist_characters="\n\r"), max_size=30).map(lambda s: "# " + s),
        st.sampled_from(["# comment", "#\tcomment", "# \x01\x02", "# non-ascii: é"]),
    )

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from([
    # missing / doubled delimiters
    'a = [1, 2',
    'a = [1, 2]]',
    'a = {b = 1',
    'a = {b = 1}}',
    '[table',
    '[[table]',
    '[[table]]]',
    # unterminated string
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    # stray token
    'a = = 1',
    'a b = 1',
    '= 1',
    'a = ',
    'a = ,',
    'a = 1 2',
    # invalid escape
    'a = "\\q"',
    # newline inside inline table
    'a = {b = 1,\nc = 2}',
    # value on next line
    'a =\n1',
    # non-ASCII bare key
    'é = 1',
    # duplicate keys
    'a = 1\na = 2',
    # duplicate tables
    '[t]\n[t]',
    # bare key with bad chars
    'a.b! = 1',
])

# ---------------------------------------------------------------------------
# Put it all together: documents
# ---------------------------------------------------------------------------

def _line():
    return st.one_of(
        _key_value_line(),
        _table_header(),
        _array_table_header(),
        _comment_line(),
    )

@st.composite
def _document(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    lines = [draw(_line()) for _ in range(n)]
    # Maybe add some empty lines / comments
    if draw(st.booleans()):
        lines.append("")
    # Join with newlines, sometimes CRLF, sometimes no trailing newline
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    doc = sep.join(lines)
    if draw(st.booleans()):
        doc += sep
    # Occasionally produce a malformed document
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        doc = draw(_malformed)
    return doc

# ---------------------------------------------------------------------------
# Deeply nested structures (stress recursion / stack handling)
# ---------------------------------------------------------------------------

@st.composite
def _deep_nesting(draw):
    # Deeply nested arrays and inline tables, targeting the depth band
    # mentioned as interesting (1500-2048) without always going there.
    target = draw(st.integers(min_value=1, max_value=2048))
    kind = draw(st.integers(min_value=0, max_value=2))
    if kind == 0:
        # nested arrays: [[[[...]]]]
        depth = target
        return "[" * depth + "]" * depth
    elif kind == 1:
        # nested inline tables: {a = {a = {...}}}
        depth = target
        inner = "{}"
        for _ in range(depth):
            inner = "{a = " + inner + "}"
        return inner
    else:
        # nested arrays as a value of a key
        depth = target
        return "a = " + "[" * depth + "]" * depth

# ---------------------------------------------------------------------------
# Interleaved structure documents: mix tables, array tables, kv lines with
# realistic nesting so the parser exercises table state machines.
# ---------------------------------------------------------------------------

@st.composite
def _structured_document(draw):
    parts = []
    n_tables = draw(st.integers(min_value=1, max_value=4))
    for _ in range(n_tables):
        base = draw(_bare_key())
        style = draw(st.integers(min_value=0, max_value=2))
        if style == 0:
            parts.append("[" + base + "]")
        elif style == 1:
            parts.append("[[" + base + "]]")
            parts.append("[" + base + "]")
        else:
            parts.append("[a." + base + "]")
        n_kv = draw(st.integers(min_value=0, max_value=3))
        for _ in range(n_kv):
            k = draw(_key)
            v = draw(_value())
            parts.append(k + " = " + v)
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    doc = sep.join(parts)
    if draw(st.booleans()):
        doc += sep
    return doc

# ---------------------------------------------------------------------------
# Whitespace / comment perturbation around otherwise valid documents
# ---------------------------------------------------------------------------

@st.composite
def _whitespace_noise(draw):
    base = draw(_document())
    lines = base.split("\n")
    out = []
    for line in lines:
        if draw(st.booleans()):
            out.append(" " * draw(st.integers(min_value=0, max_value=4)) + line)
        else:
            out.append(line)
        if draw(st.integers(min_value=0, max_value=5)) == 0:
            out.append("# " + draw(st.text(max_size=10)))
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    return sep.join(out)

# The top-level strategy
strategy = st.one_of(
    _document(),
    _malformed,
    _deep_nesting(),
    _structured_document(),
    _whitespace_noise(),
)
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.