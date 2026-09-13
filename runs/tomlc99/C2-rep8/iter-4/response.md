```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A pool of interesting "atoms" for strings/keys/comments.
_SAFE_CHARS = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "-_"
)
_ASCII_TEXT = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " \t!@#$%^&*()_+-=[]{};':\",.<>/?|`~"
)
_NON_ASCII = "éüñ日本Ωπλ☃☂→←↑↓"
_CONTROL = "\x01\x02\x07\x08\x0b\x0c\x1b\x7f"

# Escapes allowed inside basic strings (grammar ESC + UNICODE/EX_UNICODE).
_ESCAPES = [
    "\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0041", "\\u00e9", "\\uFFFF", "\\U0001F600", "\\U0010FFFF",
    "\\u0000", "\\u000a",
]

# ---------------------------------------------------------------------------
# Leaf producers
# ---------------------------------------------------------------------------

def _basic_string_body():
    """Content for a basic (double-quoted) string, no raw newline, no NUL."""
    chars = st.one_of(
        st.text(alphabet=_ASCII_TEXT, min_size=0, max_size=12),
        st.text(alphabet=_NON_ASCII, min_size=0, max_size=8),
        st.text(alphabet=_CONTROL, min_size=0, max_size=4),
        st.sampled_from(_ESCAPES),
    )
    return st.lists(chars, max_size=6).map("".join)


def _literal_string_body():
    """Content for a literal (single-quoted) string: no quote, no newline."""
    chars = st.one_of(
        st.text(alphabet=_ASCII_TEXT, min_size=0, max_size=12),
        st.text(alphabet=_NON_ASCII, min_size=0, max_size=8),
        st.text(alphabet=_CONTROL, min_size=0, max_size=4),
        st.just("\\"),  # backslash is literal here, no escape
    )
    return st.lists(chars, max_size=6).map("".join)


def _ml_basic_body():
    """Multiline basic: allows newlines, escapes, control bytes."""
    chars = st.one_of(
        st.text(alphabet=_ASCII_TEXT + "\n\r", min_size=0, max_size=16),
        st.text(alphabet=_NON_ASCII, min_size=0, max_size=8),
        st.text(alphabet=_CONTROL, min_size=0, max_size=4),
        st.sampled_from(_ESCAPES),
        st.just("\\\n"),  # line-ending backslash (ML_ESC)
    )
    return st.lists(chars, max_size=8).map("".join)


def _ml_literal_body():
    """Multiline literal: any char except the closing triple quote."""
    chars = st.one_of(
        st.text(alphabet=_ASCII_TEXT + "\n\r", min_size=0, max_size=16),
        st.text(alphabet=_NON_ASCII, min_size=0, max_size=8),
        st.text(alphabet=_CONTROL, min_size=0, max_size=4),
        st.just("\\"),
        st.just('"'),
        st.just("''"),
    )
    return st.lists(chars, max_size=8).map("".join)


# ---------------------------------------------------------------------------
# Value strategies
# ---------------------------------------------------------------------------

def _dec_int():
    return st.one_of(
        st.integers(min_value=-10**18, max_value=10**18).map(str),
        st.sampled_from([
            "0", "-0", "+0", "007", "00", "000000000000000000000000",
            "9223372036854775807", "9223372036854775808",
            "-9223372036854775808", "-9223372036854775809",
            "1_000", "1_2_3", "123456789012345678901234567890123456789",
        ]),
        st.integers(min_value=0, max_value=10**9).map(
            lambda n: "{:,}".format(n).replace(",", "_")),
    )


def _hex_int():
    digits = st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=16)
    return st.tuples(st.just("0x"), digits).map("".join)


def _oct_int():
    digits = st.text(alphabet="01234567", min_size=1, max_size=16)
    return st.tuples(st.just("0o"), digits).map("".join)


def _bin_int():
    digits = st.text(alphabet="01", min_size=1, max_size=16)
    return st.tuples(st.just("0b"), digits).map("".join)


def _float():
    return st.one_of(
        st.sampled_from([
            "1.", ".5", "1.5", "0.0", "-0.0", "+1.0",
            "1e10", "1E10", "1e+10", "1e-10", "1.5e10", "1.5E-10",
            "1e309", "-1e309", "1e-309", "1e1000",
            "1_000.000_1", "1_0e1_0",
            "3.141592653589793", "2.2250738585072014e-308",
            "1.7976931348623157e308", "1.8e308",
        ]),
        st.floats(allow_nan=False, allow_infinity=False).map(repr),
    )


def _inf_nan():
    return st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])


def _bool():
    return st.sampled_from(["true", "false"])


def _datetime():
    return st.sampled_from([
        # offset date-time
        "1979-05-27T07:32:00Z",
        "1979-05-27T00:32:00-07:00",
        "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27 07:32:00Z",
        "1979-05-27t07:32:00z",
        # local date-time
        "1979-05-27T07:32:00",
        "1979-05-27T00:32:00.999999",
        "1979-05-27 07:32:00",
        # local date
        "1979-05-27",
        "1979-02-30",   # calendar-invalid but accepted
        "0000-00-00",
        "9999-99-99",
        # local time
        "07:32:00",
        "00:32:00.999999",
        "23:59:59.999999999",
        "99:99:99",
    ])


def _key_simple():
    return st.one_of(
        st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=10),
        st.just(""),
        st.just("a" * 10000),
        st.just("_"),
        st.just("-"),
        st.just("0"),
        st.just("true"),
        st.just("inf"),
        st.just("nan"),
        # quoted keys
        st.tuples(st.just('"'), _basic_string_body(), st.just('"')).map("".join),
        st.tuples(st.just("'"), _literal_string_body(), st.just("'")).map("".join),
    )


def _key():
    simple = _key_simple()
    dotted = st.lists(simple, min_size=2, max_size=4).map(".".join)
    return st.one_of(simple, dotted)


# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

def _leaf_value():
    return st.one_of(
        # strings
        st.tuples(st.just('"'), _basic_string_body(), st.just('"')).map("".join),
        st.tuples(st.just("'"), _literal_string_body(), st.just("'")).map("".join),
        st.tuples(st.just('"""'), _ml_basic_body(), st.just('"""')).map("".join),
        st.tuples(st.just("'''"), _ml_literal_body(), st.just("'''")).map("".join),
        # integers
        _dec_int(), _hex_int(), _oct_int(), _bin_int(),
        # floats
        _float(), _inf_nan(),
        # bool
        _bool(),
        # dates
        _datetime(),
    )


def _array_body(depth):
    """Array element sequence with commas, optional trailing comma, comments."""
    if depth <= 0:
        elems = st.lists(_leaf_value(), min_size=0, max_size=4)
    else:
        elems = st.lists(_value(depth - 1), min_size=0, max_size=4)

    def render(items):
        if not items:
            return ""
        parts = []
        for i, it in enumerate(items):
            parts.append(it)
            if i < len(items) - 1:
                parts.append(", ")
        # occasionally trailing comma, newlines, comments
        s = "".join(parts)
        return s

    def add_fluff(s):
        return s

    return elems.map(render)


def _inline_table_body(depth):
    if depth <= 0:
        pairs = st.lists(
            st.tuples(_key(), _leaf_value()).map(lambda kv: "%s = %s" % kv),
            min_size=0, max_size=4)
    else:
        pairs = st.lists(
            st.tuples(_key(), _value(depth - 1)).map(lambda kv: "%s = %s" % kv),
            min_size=0, max_size=4)

    def render(ps):
        if not ps:
            return ""
        s = ", ".join(ps)
        # trailing comma sometimes (accepted by parser)
        return s

    return pairs.map(render)


def _value(depth):
    """Recursive TOML value strategy."""
    return st.one_of(
        _leaf_value(),
        st.tuples(
            st.just("["),
            _array_body(depth),
            st.just("]"),
        ).map("".join),
        st.tuples(
            st.just("{"),
            _inline_table_body(depth),
            st.just("}"),
        ).map("".join),
    )


# ---------------------------------------------------------------------------
# Document-level strategies
# ---------------------------------------------------------------------------

def _comment():
    return st.one_of(
        st.just(""),
        st.text(alphabet=_ASCII_TEXT + _NON_ASCII + _CONTROL,
                min_size=0, max_size=20).map(lambda s: "# " + s),
    )


def _key_value_line(depth):
    def render(kv):
        k, v, c = kv
        line = "%s = %s" % (k, v)
        if c:
            line += " " + c
        return line
    return st.tuples(_key(), _value(depth), _comment()).map(render)


def _standard_table_line():
    return st.tuples(
        st.just("["), _key(), st.just("]"), _comment()
    ).map(lambda t: t[0] + t[1] + t[2] + ((" " + t[3]) if t[3] else ""))


def _array_table_line():
    return st.tuples(
        st.just("[["), _key(), st.just("]]"), _comment()
    ).map(lambda t: t[0] + t[1] + t[2] + ((" " + t[3]) if t[3] else ""))


def _line(depth):
    return st.one_of(
        _key_value_line(depth),
        _standard_table_line(),
        _array_table_line(),
        _comment(),
    )


def _document(depth):
    n = st.integers(min_value=0, max_value=6)
    lines = n.flatmap(lambda k: st.lists(_line(depth), min_size=k, max_size=k))
    sep = st.sampled_from(["\n", "\r\n"])
    trailing = st.sampled_from(["", "\n"])
    return st.tuples(lines, sep, trailing).map(
        lambda t: t[1].join(t[0]) + t[2])


# ---------------------------------------------------------------------------
# Multiline basic string focused strategy (added: upweight ML_BASIC_STRING)
# ---------------------------------------------------------------------------

def _ml_basic_string_doc():
    """Top-level documents whose values exercise ML_BASIC_STRING heavily."""
    def render(body):
        return 'a = """' + body + '"""'
    return st.tuples(
        st.just("a = \"\"\""),
        _ml_basic_body(),
        st.just("\"\"\""),
    ).map("".join)


def _ml_basic_string_rich_doc():
    """ML_BASIC_STRING with explicit escapes, newlines and line-ending backslash."""
    pieces = st.one_of(
        st.text(alphabet=_ASCII_TEXT, min_size=0, max_size=20),
        st.text(alphabet=_NON_ASCII, min_size=0, max_size=10),
        st.sampled_from(_ESCAPES),
        st.just("\n"),
        st.just("\r\n"),
        st.just("\\\n"),
        st.just("\\\r\n"),
    )
    def render(parts):
        return 'a = """' + "".join(parts) + '"""'
    return st.lists(pieces, min_size=0, max_size=10).map(render)


def _ml_basic_string_keyval_doc():
    """ML_BASIC_STRING as a value inside a small document with comments."""
    def render(t):
        body, comment = t
        line = 'a = """' + body + '"""'
        if comment:
            line += " " + comment
        return line
    return st.tuples(_ml_basic_body(), _comment()).map(render)


def _ml_basic_string_inline_doc():
    """ML_BASIC_STRING inside inline tables and arrays."""
    def render(t):
        return t
    return st.one_of(
        st.tuples(
            st.just('a = ["'),
            _ml_basic_body(),
            st.just('"]'),
        ).map("".join),
        st.tuples(
            st.just('a = {b = """'),
            _ml_basic_body(),
            st.just('"""}'),
        ).map("".join),
    )


# ---------------------------------------------------------------------------
# Malformed / near-valid mutations
# ---------------------------------------------------------------------------

def _malformed():
    base = _document(1)
    return base.map(_mutate)


def _mutate(s):
    """Apply a light mutation that often yields near-valid-but-broken TOML."""
    mutations = [
        lambda x: x + "]",                       # stray closing bracket
        lambda x: "]" + x,                       # stray opening token
        lambda x: x.replace("=", "", 1),         # missing equals
        lambda x: x.replace("=", "==", 1),       # doubled delimiter
        lambda x: x + "\nkey = \"unterminated",  # unterminated string
        lambda x: x + "\nfoo =",                 # missing value
        lambda x: x + "\n= 1",                   # missing key
        lambda x: x + "\nfoo = bar",             # bare word value
        lambda x: x + "\nfoo = \"\\q\"",         # invalid escape
        lambda x: x + "\nfoo = 1\nfoo = 2",      # duplicate key
        lambda x: x + "\n[t]\n[t]",              # duplicate table
        lambda x: x + "\nfoo = {a = 1\n",        # newline inside inline table
        lambda x: x + "\nfoo = \"x\x00y\"",      # NUL escape in string (safe)
        lambda x: x + "\nfoo = \"x\ny\"",        # raw newline in basic string
        lambda x: x + "\nfoo = 1 trailing",      # stray token after value
        lambda x: x + "\nfoo = 1.2.3",           # malformed float
        lambda x: x + "\nfoo = 0x",              # empty hex
        lambda x: x + "\nfoo = 1979-05-27T",     # truncated datetime
        lambda x: x + "\nfoo = [1, 2",           # unterminated array
        lambda x: x + "\nfoo = {a = 1,}",        # trailing comma inline (ok)
    ]
    # pick a deterministic-ish subset based on hashing
    idx = len(s) % len(mutations)
    try:
        return mutations[idx](s)
    except Exception:
        return s


# ---------------------------------------------------------------------------
# Deep nesting band (1500-2048)
# ---------------------------------------------------------------------------

def _deep_array():
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(lambda d: "a = " + "[" * d + "]" * d)


def _deep_inline():
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(
        lambda d: "a = " + "{b = " * d + "1" + "}" * d)


# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

def _empty_or_comment_only():
    return st.one_of(
        st.just(""),
        st.just("\n"),
        st.just("# just a comment"),
        st.just("# comment\n"),
        st.just("\r\n"),
    )


def _full_document():
    return st.one_of(
        _empty_or_comment_only(),
        _document(2),
        _deep_array(),
        _deep_inline(),
        _malformed(),
        # upweight ML_BASIC_STRING productions
        _ml_basic_string_doc(),
        _ml_basic_string_rich_doc(),
        _ml_basic_string_keyval_doc(),
        _ml_basic_string_inline_doc(),
    )


strategy = _full_document()
```