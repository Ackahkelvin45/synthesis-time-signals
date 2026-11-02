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
    # malformed / partial escapes to exercise error paths
    "\\", "\\u", "\\u12", "\\uZZZZ", "\\U00110000", "\\x41", "\\a",
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
        # malformed integers
        "_1", "1_", "1__0", "+", "-", "01", "0x", "0b", "0o",
        "0xG", "0b2", "0o8", "1.2.3",
    ]),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=0xFFFFFFFFFFFFFFFF).map(lambda n: "0x" + format(n, "x")),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF",
                     "0x", "0xG", "0x1p4", "0X1F"]),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=0o7777777777777777).map(lambda n: "0o" + format(n, "o")),
    st.sampled_from(["0o0", "0o777", "0o1_2_3", "0o755", "0o", "0o8"]),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from(["0b0", "0b1", "0b1010_1010", "0b11111111", "0b", "0b2"]),
)

_integer_value = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float_value = st.one_of(
    st.sampled_from([
        "1.0", "-1.0", "+1.0", "3.14159", "1e10", "1E10", "1e+10", "1e-10",
        "1.5e10", "-1.5E-10", "1.", ".5", "0.0", "-0.0", "1e309", "-1e309",
        "1_000.000_1", "inf", "+inf", "-inf", "nan", "+nan", "-nan",
        "1e0", "0e0", "6.626e-34", "1.7976931348623157e308",
        # malformed floats
        "1e", "1e+", ".", "+.", "1..2", "1.2e", "infinity", "NaN", "1_",
    ]),
    st.floats(allow_nan=True, allow_infinity=True).map(repr),
)

# ---------------------------------------------------------------------------
# Booleans, date-times
# ---------------------------------------------------------------------------

_bool_value = st.sampled_from(["true", "false", "True", "FALSE", "tru", "fals"])

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
    # malformed date-times
    "1979-13-01", "1979-05-32", "24:00:00", "1979-05-27T25:00:00Z",
    "1979-05-27T07:32:00+99:00", "1979-05-27T", "T07:32:00",
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
    # extra edge cases
    'a = [1,]', 'a = [,]', 'a = [,1]', 'a = {,}', 'a = {b=1,}',
    '[]', '[[]]', '[.a]', '[a.]', '[a..b]', 'a. = 1', '.a = 1',
    'a = 1\r', 'a = 1\r\r', '\x00', 'a = \x00', 'a = "\x00"',
    'a = 1 #', 'a = 1#c', 'a=1', 'a=  1', 'a =1',
    'a = truefalse', 'a = true1', 'a = nan1',
    'a = 1\n[t]\n[t]', '[[t]]\n[t]', '[t]\n[[t]]',
    'a = {b = {c = 1}}', 'a = [[1]]', 'a = [{}]',
    'a = """x""""', "a = '''x''''",
    'a = "x" "y"', 'a = 1, 2',
    'a.b.c.d = 1', 'a . b = 1', 'a\t=\t1',
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
# Structured document builder: tables/array-tables with nested key-values.
# This targets the parser's state-machine branches (current table tracking,
# array-of-tables, dotted key resolution) which the flat document strategy
# under-exercises.
# ---------------------------------------------------------------------------

@st.composite
def _structured_document(draw):
    parts = []
    used_tables = set()

    def emit_kv(prefix=""):
        k = draw(_key)
        if prefix:
            k = prefix + "." + k
        return k + " = " + draw(_value())

    n_sections = draw(st.integers(min_value=1, max_value=5))
    for _ in range(n_sections):
        kind = draw(st.integers(min_value=0, max_value=2))
        if kind == 0:
            # plain key-value block under root
            n = draw(st.integers(min_value=1, max_value=3))
            for _ in range(n):
                parts.append(emit_kv())
        elif kind == 1:
            # [table] with keys, sometimes nested sub-tables
            name = draw(_bare_key())
            parts.append("[" + name + "]")
            n = draw(st.integers(min_value=0, max_value=3))
            for _ in range(n):
                parts.append(emit_kv())
            # nested subtable
            if draw(st.booleans()):
                sub = draw(_bare_key())
                parts.append("[" + name + "." + sub + "]")
                for _ in range(draw(st.integers(min_value=0, max_value=2))):
                    parts.append(emit_kv())
        else:
            # [[array of tables]]
            name = draw(_bare_key())
            n_entries = draw(st.integers(min_value=1, max_value=3))
            for _ in range(n_entries):
                parts.append("[[" + name + "]]")
                for _ in range(draw(st.integers(min_value=0, max_value=3))):
                    parts.append(emit_kv())
                # nested subtable within array element
                if draw(st.booleans()):
                    sub = draw(_bare_key())
                    parts.append("[[" + name + "." + sub + "]]")
                    for _ in range(draw(st.integers(min_value=0, max_value=2))):
                        parts.append(emit_kv())
        # occasional comment / blank line between sections
        if draw(st.booleans()):
            parts.append(draw(_comment_line()))
        if draw(st.booleans()):
            parts.append("")

    sep = draw(st.sampled_from(["\n", "\r\n"]))
    doc = sep.join(parts)
    if draw(st.booleans()):
        doc += sep
    return doc

# ---------------------------------------------------------------------------
# NEW: Deep-nesting / structural stress documents.
# These target deep recursion, long dotted keys, large arrays, and
# table/array-table state transitions that the other builders under-exercise.
# ---------------------------------------------------------------------------

@st.composite
def _deep_document(draw):
    parts = []
    # Deeply nested inline arrays / tables
    depth = draw(st.integers(min_value=1, max_value=40))
    if draw(st.booleans()):
        # nested arrays: [[[...]]]
        inner = draw(_leaf_value)
        parts.append("a = " + "[" * depth + inner + "]" * depth)
    else:
        # nested inline tables: {a = {a = {...}}}
        inner = draw(_leaf_value)
        v = inner
        for _ in range(depth):
            v = "{a = " + v + "}"
        parts.append("a = " + v)

    # Long dotted key
    if draw(st.booleans()):
        n = draw(st.integers(min_value=2, max_value=20))
        keys = [draw(_bare_key()) for _ in range(n)]
        parts.append(".".join(keys) + " = " + draw(_value()))

    # Large flat array
    if draw(st.booleans()):
        n = draw(st.integers(min_value=0, max_value=60))
        elems = [draw(_leaf_value) for _ in range(n)]
        parts.append("arr = [" + ", ".join(elems) + "]")

    # Deep table nesting: [a.b.c.d...]
    if draw(st.booleans()):
        n = draw(st.integers(min_value=2, max_value=15))
        keys = [draw(_bare_key()) for _ in range(n)]
        parts.append("[" + ".".join(keys) + "]")
        parts.append("x = " + draw(_value()))

    # Deep array-of-tables nesting: [[a.b.c...]]
    if draw(st.booleans()):
        n = draw(st.integers(min_value=2, max_value=12))
        keys = [draw(_bare_key()) for _ in range(n)]
        parts.append("[[" + ".".join(keys) + "]]")
        parts.append("x = " + draw(_value()))

    # Interleaved table / array-table transitions to stress state machine
    if draw(st.booleans()):
        a = draw(_bare_key())
        b = draw(_bare_key())
        c = draw(_bare_key())
        parts.append("[" + a + "]")
        parts.append("k = 1")
        parts.append("[[" + a + "." + b + "]]")
        parts.append("k = 2")
        parts.append("[[" + a + "." + b + "]]")
        parts.append("k = 3")
        parts.append("[" + a + "." + c + "]")
        parts.append("k = 4")
        parts.append("[" + a + "]")  # redefinition error path
        parts.append("k = 5")

    # Many consecutive array-table entries
    if draw(st.booleans()):
        name = draw(_bare_key())
        n = draw(st.integers(min_value=1, max_value=12))
        for i in range(n):
            parts.append("[[" + name + "]]")
            parts.append("i = " + str(i))
            if draw(st.booleans()):
                parts.append("s = " + draw(_string_value))

    sep = draw(st.sampled_from(["\n", "\r\n"]))
    doc = sep.join(parts)
    if draw(st.booleans()):
        doc += sep
    return doc

# ---------------------------------------------------------------------------
# NEW: Whitespace / trivia perturbations around tokens.
# Targets the parser's whitespace-skipping and comment-handling branches.
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "  ", "\t", " \t ", "   "])

@st.composite
def _whitespace_document(draw):
    # Build key/value lines with randomized whitespace around '=' and tokens.
    n = draw(st.integers(min_value=1, max_value=6))
    parts = []
    for _ in range(n):
        k = draw(_key)
        v = draw(_value())
        lhs = draw(_ws)
        rhs = draw(_ws)
        line = k + lhs + "=" + rhs + v
        # optional trailing comment
        if draw(st.booleans()):
            line += draw(_ws) + "#" + draw(_ws) + draw(_bare_key())
        parts.append(line)
        if draw(st.booleans()):
            parts.append(draw(_ws))
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    doc = sep.join(parts)
    if draw(st.booleans()):
        doc += sep
    return doc

# ---------------------------------------------------------------------------
# NEW: Array / inline-table specific value stress.
# Targets the value-parsing branches (arrays, inline tables) which get
# relatively little coverage from generic documents.
# ---------------------------------------------------------------------------

@st.composite
def _container_value_document(draw):
    parts = []
    n = draw(st.integers(min_value=1, max_value=8))
    for _ in range(n):
        k = draw(_bare_key())
        kind = draw(st.integers(min_value=0, max_value=3))
        if kind == 0:
            # array with mixed elements, optional trailing comma / newlines
            m = draw(st.integers(min_value=0, max_value=6))
            elems = [draw(_leaf_value) for _ in range(m)]
            inner = ", ".join(elems)
            if m and draw(st.booleans()):
                inner += ","
            if draw(st.booleans()) and m:
                inner = inner.replace(",", ",\n", 1)
            parts.append(k + " = [" + inner + "]")
        elif kind == 1:
            # inline table with mixed pairs, optional trailing comma
            m = draw(st.integers(min_value=0, max_value=5))
            pairs = []
            for _ in range(m):
                kk = draw(_key)
                vv = draw(_value())
                pairs.append(kk + " = " + vv)
            inner = ", ".join(pairs)
            if m and draw(st.booleans()):
                inner += ","
            parts.append(k + " = {" + inner + "}")
        elif kind == 2:
            # array of arrays
            m = draw(st.integers(min_value=0, max_value=4))
            subs = []
            for _ in range(m):
                sm = draw(st.integers(min_value=0, max_value=3))
                subs.append("[" + ", ".join(draw(_leaf_value) for _ in range(sm)) + "]")
            parts.append(k + " = [" + ", ".join(subs) + "]")
        else:
            # array of inline tables
            m = draw(st.integers(min_value=0, max_value=4))
            subs = []
            for _ in range(m):
                pairs = []
                for _ in range(draw(st.integers(min_value=0, max_value=3))):
                    pairs.append(draw(_key) + " = " + draw(_value()))
                subs.append("{" + ", ".join(pairs) + "}")
            parts.append(k + " = [" + ", ".join(subs) + "]")
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    doc = sep.join(parts)
    if draw(st.booleans()):
        doc += sep
    return doc

# The top-level strategy
strategy = st.one_of(
    _document(),
    _structured_document(),
    _deep_document(),
    _whitespace_document(),
    _container_value_document(),
    _malformed,
)
```