Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- basic character classes ----------

_ws = st.sampled_from([" ", "\t"])
_nl = st.sampled_from(["\n", "\r\n", "\r\n"])
_opt_ws = st.text(alphabet=" \t", max_size=3)

# Safe printable + non-ASCII text (no NUL, no newline, no quote/backslash by default)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\n\r",
)

_basic_inner_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\x00\n\r"\\',
)

_literal_inner_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\n\r'",
)

_comment_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\n\r",
)

_unquoted_key_chars = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
)

# ---------- escapes ----------

_short_escapes = st.sampled_from(["\\b", "\\t", "\\n", "\\f", "\\r", "\\\"", "\\\\", "\\/"])

_unicode_escape = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "\\u%04X" % n
)

_big_unicode_escape = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda n: "\\U%08X" % n
)

_escape = st.one_of(_short_escapes, _unicode_escape, _big_unicode_escape)

# ---------- strings ----------

def _basic_string():
    body = st.lists(
        st.one_of(_basic_inner_chars.map(str), _escape),
        max_size=8,
    ).map("".join)
    return body.map(lambda b: '"' + b + '"')

def _literal_string():
    body = st.lists(_literal_inner_chars.map(str), max_size=8).map("".join)
    return body.map(lambda b: "'" + b + "'")

_ml_basic_body_char = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters='\x00"\\').map(str),
    _escape,
    st.just("\n"),
    st.just("\r\n"),
    st.just('"'),
    st.just('""'),
)

def _ml_basic_string():
    body = st.lists(_ml_basic_body_char, max_size=6).map("".join)
    return body.map(lambda b: '"""' + b + '"""')

_ml_literal_body_char = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00'").map(str),
    st.just("\n"),
    st.just("\r\n"),
    st.just("'"),
    st.just("''"),
)

def _ml_literal_string():
    body = st.lists(_ml_literal_body_char, max_size=6).map("".join)
    return body.map(lambda b: "'''" + b + "'''")

_string = st.one_of(
    _basic_string(),
    _literal_string(),
    _ml_basic_string(),
    _ml_literal_string(),
)

# ---------- numbers ----------

_dec_int = st.one_of(
    st.integers(min_value=-10**20, max_value=10**20).map(str),
    st.sampled_from([
        "0", "007", "-007", "+0", "+42",
        "1_000", "1_0_0", "9223372036854775807",
        "9223372036854775808", "-9223372036854775809",
        "99999999999999999999999999999999999999999",
    ]),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=0xFFFFFFFFFFFFFFFF).map(lambda n: "0x%x" % n),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0x1_2_3"]),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=0o7777777777).map(lambda n: "0o%o" % n),
    st.sampled_from(["0o0", "0o755", "0o1_2_3"]),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from(["0b0", "0b1", "0b1_0_1_0"]),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from([
        "1.0", "1.", ".5", "-.5", "+1.5", "3.14159",
        "1e10", "1E10", "1e+10", "1e-10", "1.5e10",
        "1_000.000_1", "1e309", "-1e309",
        "inf", "+inf", "-inf", "nan", "+nan", "-nan",
    ]),
)

_boolean = st.sampled_from(["true", "false"])

# ---------- date-times ----------

_date = st.sampled_from([
    "1979-05-27", "0000-00-00", "1979-02-30", "9999-12-31",
    "2024-01-01", "1979-13-45",
])

_time = st.sampled_from([
    "07:32:00", "00:00:00", "23:59:59", "07:32:00.999999",
    "99:99:99", "07:32:00.0",
])

_offset = st.sampled_from(["Z", "z", "+00:00", "-07:00", "+23:59", "-00:00"])

_offset_dt = st.tuples(_date, st.sampled_from(["T", "t", " "]), _time, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)

_local_dt = st.tuples(_date, st.sampled_from(["T", "t", " "]), _time).map(
    lambda t: t[0] + t[1] + t[2]
)

_date_time = st.one_of(_offset_dt, _local_dt, _date, _time)

# ---------- keys ----------

_unquoted_key = st.text(alphabet=list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"), min_size=1, max_size=10)

_quoted_key = st.one_of(
    _basic_string(),
    _literal_string(),
    st.just('""'),
    st.just("''"),
)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)

# ---------- recursive values: arrays and inline tables ----------

# We build a recursive strategy. Values inside arrays/inline tables can
# themselves be arrays/inline tables (up to depth limit).

def _scalar_value():
    return st.one_of(
        _string,
        _integer,
        _float,
        _boolean,
        _date_time,
    )

# Forward declaration approach: use st.deferred
_value = st.deferred(lambda: st.one_of(
    _scalar_value(),
    _array,
    _inline_table,
))

# Array: [ ... ] with optional whitespace/newlines/comments between elements
_array_ws = st.text(alphabet=" \t\n\r", max_size=3)

def _array_element():
    return _value

_array = st.lists(
    _array_element(),
    max_size=3,
).map(lambda elems: "[" + ", ".join(elems) + "]")

# Inline table: { key = value, ... }
def _inline_pair():
    return st.tuples(_key, _opt_ws, _value).map(lambda t: t[0] + " = " + t[2])

_inline_table = st.lists(
    _inline_pair(),
    max_size=3,
).map(lambda pairs: "{" + ", ".join(pairs) + "}")

# ---------- key/value lines ----------

def _key_value_line():
    return st.tuples(_key, _opt_ws, _value).map(lambda t: t[0] + " = " + t[2])

# ---------- tables ----------

_standard_table = _key.map(lambda k: "[" + k + "]")
_array_table = _key.map(lambda k: "[[" + k + "]]")

# ---------- comments ----------

def _comment():
    body = st.lists(_comment_chars.map(str), max_size=10).map("".join)
    return body.map(lambda b: "#" + b)

# ---------- document ----------

def _line():
    return st.one_of(
        _key_value_line(),
        _standard_table,
        _array_table,
        _comment(),
        st.just(""),
    )

_document = st.lists(_line(), max_size=8).map(lambda lines: "\n".join(lines))

# ---------- edge-case / malformed documents ----------

_edge_documents = st.sampled_from([
    "",
    "\n",
    "# just a comment",
    "# comment\n",
    "a = 1",
    "a = 1\n",
    "a = 1\na = 2",  # duplicate key -> rejected
    "[t]\n[t]",  # duplicate table -> rejected
    "a = \"unterminated",  # unterminated string
    "a = 'unterminated",  # unterminated literal string
    "a = [1, 2,",  # missing bracket
    "a = [1, 2]]",  # doubled bracket
    "a = {b = 1",  # missing brace
    "a = {b = 1}}",  # doubled brace
    "a = ",  # missing value
    "= 1",  # missing key
    "a = 1 b = 2",  # stray token
    "a = 1,",  # stray comma
    "a = {b = 1\n}",  # newline in inline table -> rejected
    "a = 1\nb = ",  # trailing equals
    "[a]\n[a.b]\n[a]",  # redefined table
    "a = \"\\q\"",  # invalid escape
    "a = 1\n\n\n\nb = 2",  # blank lines
    "\r\na = 1\r\n",  # CRLF
    "  \ta = 1",  # tab indentation
    "a.b.c.d = 1",  # deep dotted key
    "a = 1979-02-30",  # calendar-invalid
    "a = 1e309",  # huge float
    "a = 007",  # leading zeros
    "a = 1.",  # trailing dot float
    "a = .5",  # leading dot float
    "a = {b = 1,}",  # trailing comma inline table
    "a = [1, 2,]",  # trailing comma array
    "a = []",  # empty array
    "a = {}",  # empty inline table
    "[t]",  # empty table
    "[[a]]",  # empty array table
    '"" = 1',  # empty quoted key
    "a = 1\r\nb = 2",  # CRLF
    "\ufeffa = 1",  # BOM
    "a = 2024-01-01T00:00:00Z",
    "a = 2024-01-01 00:00:00Z",
    "a = 00:00:00",
    "a = 0xDEADBEEF",
    "a = 0o755",
    "a = 0b1010",
    "a = 1_000_000",
    "a = inf",
    "a = -inf",
    "a = nan",
    "a = \"\\u0000\"",  # NUL escape is fine
    "a = \"\\U0001F600\"",
    "a = \"line1\nline2\"",  # raw newline in basic string -> rejected
    "a = '''\nmulti\nline\n'''",
    "a = \"\"\"\nmulti\nline\n\"\"\"",
    "a = \"raw\x01control\"",  # raw control char -> accepted by buggy parser
])

# ---------- deep nesting strategy ----------

def _deep_array(depth):
    """Build an array nested `depth` levels."""
    if depth <= 0:
        return st.just("[]")
    inner = st.deferred(lambda: _deep_array(depth - 1))
    return inner.map(lambda s: "[" + s + "]")

def _deep_inline(depth):
    """Build an inline table nested `depth` levels."""
    if depth <= 0:
        return st.just("{}")
    inner = st.deferred(lambda: _deep_inline(depth - 1))
    return inner.map(lambda s: "{a = " + s + "}")

# Use a moderate depth band for interesting recursion (well below stack limit)
_deep_doc = st.integers(min_value=1, max_value=64).flatmap(
    lambda d: st.one_of(
        _deep_array(d).map(lambda s: "a = " + s),
        _deep_inline(d).map(lambda s: "a = " + s),
    )
)

# ---------- top-level strategy ----------

strategy = st.one_of(
    _document,
    _edge_documents,
    _deep_doc,
    _key_value_line(),
    _comment(),
    _array.map(lambda s: "a = " + s),
    _inline_table.map(lambda s: "a = " + s),
    _string.map(lambda s: "a = " + s),
    _integer.map(lambda s: "a = " + s),
    _float.map(lambda s: "a = " + s),
    _boolean.map(lambda s: "a = " + s),
    _date_time.map(lambda s: "a = " + s),
).map(lambda s: s if s == "" or s.endswith("\n") else s + "\n")
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.