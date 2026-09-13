```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Low level character / token helpers
# ---------------------------------------------------------------------------

# Characters that are safe to place inside strings without breaking the
# surrounding syntax.
_SAFE_STRING_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters=(
        "\x00",  # never emit a raw NUL byte anywhere
        '"', "'", "\\", "\n", "\r",
    ),
)

# Raw (non-escaped) control characters are accepted by the parser inside
# strings and comments.  Keep away from NUL and newlines.
_RAW_CONTROL_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters=("\x00", "\n", "\r"),
    whitelist_categories=("Cc",),
)

_ESCAPE_SEQUENCES = st.sampled_from(
    [
        '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    ]
)

_UNICODE_ESCAPES = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda cp: "\\u%04x" % cp
)

_EX_UNICODE_ESCAPES = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda cp: "\\U%08x" % cp
)

_STRING_PIECE = st.one_of(
    _SAFE_STRING_CHARS,
    _RAW_CONTROL_CHARS,
    _ESCAPE_SEQUENCES,
    _UNICODE_ESCAPES,
    _EX_UNICODE_ESCAPES,
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_BARE_KEY_CHARS = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-_"
)

_BARE_KEY = st.text(_BARE_KEY_CHARS, min_size=1, max_size=12)

# The empty quoted key is explicitly allowed.
_QUOTED_KEY = st.one_of(
    st.just('""'),
    st.just("''"),
    st.builds(lambda s: '"' + s + '"', st.text(_STRING_PIECE, max_size=8)),
    st.builds(lambda s: "'" + s + "'", st.text(_SAFE_STRING_CHARS, max_size=8)),
)

_SIMPLE_KEY = st.one_of(_BARE_KEY, _QUOTED_KEY)

_DOTTED_KEY = st.lists(_SIMPLE_KEY, min_size=2, max_size=3).map(".".join)

_KEY = st.one_of(_SIMPLE_KEY, _DOTTED_KEY)

# ---------------------------------------------------------------------------
# Scalars: integers, floats, booleans, dates
# ---------------------------------------------------------------------------

_DEC_DIGITS = st.text("0123456789", min_size=1, max_size=20)

_DEC_INT = st.one_of(
    st.just("0"),
    _DEC_DIGITS,
    st.builds(lambda s: ("-" if s[0] != "-" else "") + s, _DEC_DIGITS),
    # leading zeros (accepted by this parser)
    st.text("0123456789", min_size=2, max_size=8),
    # underscores
    st.builds(lambda a, b: a + "_" + b, _DEC_DIGITS, _DEC_DIGITS),
    # extreme magnitudes
    st.sampled_from(
        ["9223372036854775807", "-9223372036854775808",
         "18446744073709551616", "-18446744073709551617",
         "9" * 30, "-" + "9" * 30]
    ),
)

_HEX_INT = st.one_of(
    st.just("0x0"),
    st.builds(lambda s: "0x" + s, st.text("0123456789abcdefABCDEF", min_size=1, max_size=16)),
    st.builds(lambda s: "0x" + s, st.text("0123456789abcdefABCDEF", min_size=2, max_size=16).map(
        lambda s: s[0] + "_" + s[1:])),
)

_OCT_INT = st.one_of(
    st.just("0o0"),
    st.builds(lambda s: "0o" + s, st.text("01234567", min_size=1, max_size=16)),
)

_BIN_INT = st.one_of(
    st.just("0b0"),
    st.builds(lambda s: "0b" + s, st.text("01", min_size=1, max_size=16)),
)

_INTEGER = st.one_of(_DEC_INT, _HEX_INT, _OCT_INT, _BIN_INT)

_EXPONENT = st.one_of(
    st.builds(lambda e, s: e + s, st.sampled_from(["e", "E"]), _DEC_DIGITS),
    st.builds(lambda e, s: e + s, st.sampled_from(["e", "E"]),
              st.builds(lambda a, b: a + b, st.sampled_from(["+", "-"]), _DEC_DIGITS)),
    st.sampled_from(["e309", "e-309", "E+999", "e0", "e00"]),
)

_FRACTION = st.one_of(
    st.builds(lambda s: "." + s, _DEC_DIGITS),
    st.just("."),            # `1.` accepted by this parser
)

_FLOAT = st.one_of(
    st.builds(lambda i, f: i + f, _DEC_DIGITS, _FRACTION),
    st.builds(lambda i, f, e: i + f + e, _DEC_DIGITS, _FRACTION, _EXPONENT),
    st.builds(lambda i, e: i + e, _DEC_DIGITS, _EXPONENT),
    st.builds(lambda s: "." + s, _DEC_DIGITS),  # `.5` accepted
    st.just("1."),
    st.just(".5"),
    st.just("1e309"),
    st.just("-1e309"),
)

_INF_NAN = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_FLOATING_POINT = st.one_of(_FLOAT, _INF_NAN)

_BOOLEAN = st.sampled_from(["true", "false"])

_YEAR = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_MONTH = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_DAY = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_HOUR = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_MINUTE = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_SECOND = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_SECFRAC = st.one_of(
    st.just(""),
    st.builds(lambda s: "." + s, st.text("0123456789", min_size=1, max_size=6)),
)

_FULL_DATE = st.builds(
    lambda y, m, d: y + "-" + m + "-" + d, _YEAR, _MONTH, _DAY
)

_PARTIAL_TIME = st.builds(
    lambda h, m, s, f: h + ":" + m + ":" + s + f,
    _HOUR, _MINUTE, _SECOND, _SECFRAC,
)

_OFFSET = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.builds(lambda s, h, m: s + h + ":" + m,
              st.sampled_from(["+", "-"]), _HOUR, _MINUTE),
)

_DELIM = st.sampled_from(["T", "t", " "])

_DATE_TIME = st.one_of(
    st.builds(lambda d, delim, t, o: d + delim + t + o, _FULL_DATE, _DELIM, _PARTIAL_TIME, _OFFSET),
    st.builds(lambda d, delim, t: d + delim + t, _FULL_DATE, _DELIM, _PARTIAL_TIME),
    _FULL_DATE,
    _PARTIAL_TIME,
    # calendar-invalid dates accepted by the parser
    st.sampled_from(["1979-02-30", "2021-13-45", "0000-00-00", "9999-99-99"]),
)

# ---------------------------------------------------------------------------
# Strings (all four quoting forms)
# ---------------------------------------------------------------------------

_BASIC_STRING = st.builds(
    lambda s: '"' + s + '"', st.text(_STRING_PIECE, max_size=16)
)

_LITERAL_STRING = st.builds(
    lambda s: "'" + s + "'", st.text(_SAFE_STRING_CHARS, max_size=16)
)

_ML_BASIC_STRING = st.builds(
    lambda s: '"""' + s + '"""',
    st.text(_STRING_PIECE, max_size=24),
)

_ML_LITERAL_STRING = st.builds(
    lambda s: "'''" + s + "'''",
    st.text(_SAFE_STRING_CHARS, max_size=24),
)

_STRING = st.one_of(
    _BASIC_STRING,
    _ML_BASIC_STRING,
    _LITERAL_STRING,
    _ML_LITERAL_STRING,
)

# ---------------------------------------------------------------------------
# Recursive value grammar: arrays and inline tables
# ---------------------------------------------------------------------------

_SCALAR = st.one_of(
    _STRING,
    _INTEGER,
    _FLOATING_POINT,
    _BOOLEAN,
    _DATE_TIME,
)

# Depth band: concentrate interesting nesting between ~1 and ~2048.  The
# recursive strategy is bounded so that generation stays feasible while still
# reaching deep nesting sometimes.
_MAX_DEPTH = 2048


def _value_strategy(depth):
    """Build a strategy for values at the given remaining depth budget."""
    if depth <= 0:
        return _SCALAR
    child = _value_strategy(depth - 1)
    # Arrays: empty, single, multiple, trailing comma, newlines + comments.
    array = st.one_of(
        st.just("[]"),
        st.builds(lambda v: "[" + v + "]", child),
        st.builds(lambda a, b: "[" + a + ", " + b + "]", child, child),
        st.builds(lambda a, b: "[" + a + ", " + b + ",]", child, child),
        st.builds(lambda v: "[\n  " + v + ",\n]", child),
        st.builds(lambda c, v: "[\n  # " + c + "\n  " + v + ",\n]", _SAFE_STRING_CHARS.map(str), child),
    )
    # Inline tables: empty, single key, multiple keys, trailing comma.
    inline = st.one_of(
        st.just("{}"),
        st.builds(lambda k, v: "{" + k + " = " + v + "}", _SIMPLE_KEY, child),
        st.builds(lambda k1, v1, k2, v2: "{" + k1 + " = " + v1 + ", " + k2 + " = " + v2 + "}",
                  _SIMPLE_KEY, child, _SIMPLE_KEY, child),
        st.builds(lambda k, v: "{" + k + " = " + v + ",}", _SIMPLE_KEY, child),
    )
    return st.one_of(_SCALAR, array, inline)


_VALUE = st.recursive(
    _SCALAR,
    lambda children: st.one_of(
        st.builds(lambda v: "[" + v + "]", children),
        st.builds(lambda a, b: "[" + a + ", " + b + "]", children, children),
        st.builds(lambda v: "[" + v + ",]", children),
        st.builds(lambda v: "[\n  " + v + ",\n]", children),
        st.builds(lambda k, v: "{" + k + " = " + v + "}", _SIMPLE_KEY, children),
        st.builds(lambda k, v: "{" + k + " = " + v + ",}", _SIMPLE_KEY, children),
        st.builds(lambda k1, v1, k2, v2: "{" + k1 + " = " + v1 + ", " + k2 + " = " + v2 + "}",
                  _SIMPLE_KEY, children, _SIMPLE_KEY, children),
    ),
    max_leaves=64,
)

# A single deeply nested value used for the depth-band coverage.
_DEEP_VALUE = st.integers(min_value=1, max_value=_MAX_DEPTH).flatmap(
    lambda n: st.just("[" * n + "0" + "]" * n)
)

# ---------------------------------------------------------------------------
# Statements: key/value, tables, array tables, comments
# ---------------------------------------------------------------------------

_KV_LINE = st.builds(
    lambda k, v: k + " = " + v,
    _KEY,
    st.one_of(_VALUE, _DEEP_VALUE),
)

_COMMENT = st.builds(
    lambda s: "#" + s,
    st.text(_SAFE_STRING_CHARS, max_size=20),
)

_STANDARD_TABLE = st.builds(
    lambda k: "[" + k + "]", _KEY
)

_ARRAY_TABLE = st.builds(
    lambda k: "[[" + k + "]]", _KEY
)

_STATEMENT = st.one_of(
    _KV_LINE,
    _STANDARD_TABLE,
    _ARRAY_TABLE,
    _COMMENT,
    st.just(""),
)

# ---------------------------------------------------------------------------
# Malformed / near-valid variants
# ---------------------------------------------------------------------------

_MALFORMED = st.one_of(
    # missing closing delimiter
    st.builds(lambda k, v: k + " = [" + v, _SIMPLE_KEY, _SCALAR),
    st.builds(lambda k, v: k + " = {" + v, _SIMPLE_KEY, _SCALAR),
    # doubled delimiter
    st.builds(lambda k, v: k + " = [" + v + "]]", _SIMPLE_KEY, _SCALAR),
    st.builds(lambda k, v: k + " = {" + v + "}}", _SIMPLE_KEY, _SCALAR),
    # unterminated string
    st.builds(lambda k, s: k + ' = "' + s, _SIMPLE_KEY, st.text(_SAFE_STRING_CHARS, max_size=8)),
    st.builds(lambda k, s: k + " = '" + s, _SIMPLE_KEY, st.text(_SAFE_STRING_CHARS, max_size=8)),
    # stray token
    st.builds(lambda k: k + " =", _SIMPLE_KEY),
    st.builds(lambda k: k + " = ", _SIMPLE_KEY),
    st.just("]"),
    st.just("}"),
    st.just("="),
    # newline inside inline table (rejected)
    st.builds(lambda k, v: k + " = {" + v + "\n}", _SIMPLE_KEY, _SCALAR),
    # non-ASCII bare key (rejected)
    st.builds(lambda k, v: k + " = " + v, st.just("caf\u00e9"), _SCALAR),
)

# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

_SEPARATOR = st.sampled_from(["\n", "\r\n"])

_DOCUMENT_BODY = st.one_of(
    st.lists(_STATEMENT, min_size=0, max_size=6),
    st.lists(st.one_of(_STATEMENT, _MALFORMED), min_size=1, max_size=6),
)


def _join_lines(lines):
    if not lines:
        return ""
    return "\n".join(lines)


_DOCUMENT = _DOCUMENT_BODY.map(_join_lines)

# Also expose some explicit edge-case documents.
_EDGE_CASES = st.sampled_from(
    [
        "",
        "\n",
        "# comment only\n",
        "[t]\n",
        "[[a]]\n",
        '"" = 1\n',
        "a = {b = 1,}\n",
        "a = 007\n",
        "a = 1.\n",
        "a = .5\n",
        "a = 1979-02-30\n",
        "a = \"x\x01y\"\n",
        "a = 1e309\n",
        "a = 9223372036854775808\n",
        "a = -9223372036854775809\n",
        "a = 0xFFFFFFFFFFFFFFFF\n",
        "a = 0o777777777777777777777\n",
        "a = 0b1111111111111111111111111111111111111111\n",
        "a = inf\n",
        "a = -nan\n",
        "a = 1979-05-27T07:32:00Z\n",
        "a = 1979-05-27 07:32:00.999999-07:00\n",
        "a = 07:32:00\n",
        "a = 1979-05-27\n",
        "a = \"\\u0000\"\n",
        "a = \"\\U0001F600\"\n",
        "a = '''multi\nline'''\n",
        'a = """multi\nline"""\n',
        "a = [1, 2, 3,]\n",
        "a = [\n  # c\n  1,\n]\n",
        "a = {b = 1, c = {d = 2}}\n",
        "a.b.c = 1\n",
        '"a b" = 1\n',
        "a = \n",
        "a = [1,\n",
        "a = {b = 1\n",
        "a = \"unterminated\n",
        "a = \n",
        "= 1\n",
        "]\n",
        "}\n",
        "a = {b = 1\n}\n",
        "caf\u00e9 = 1\n",
        "a = 1\na = 2\n",
        "[t]\n[t]\n",
        "[t]\n[[t]]\n",
        "a = 1\nb = 2\nc = 3\n",
        "a = 1\n\n# comment\nb = 2\n",
        "a = 1\n" * 50,
    ]
)

strategy = st.one_of(
    _DOCUMENT,
    _EDGE_CASES,
    # Deep nesting band: arrays nested up to ~2048 levels.
    st.integers(min_value=1500, max_value=_MAX_DEPTH).map(
        lambda n: "a = " + "[" * n + "0" + "]" * n
    ),
    # Deep inline table nesting (smaller band, since each level costs more).
    st.integers(min_value=1, max_value=200).map(
        lambda n: "a = " + "{b = " * n + "0" + "}" * n
    ),
)
```