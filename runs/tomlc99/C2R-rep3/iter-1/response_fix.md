```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Character helpers (no NUL anywhere except as an escape sequence)
# ---------------------------------------------------------------------------

_SAFE_ASCII = "".join(chr(c) for c in range(0x20, 0x7F))

# Characters that may appear raw inside strings (parser accepts raw controls,
# but we never emit a raw NUL byte).
_RAW_STRING_CHARS = "".join(
    chr(c)
    for c in list(range(0x01, 0x20)) + list(range(0x20, 0x7F)) + list(range(0x80, 0x200))
    if c != 0
)

_NON_ASCII_TEXT = st.text(
    alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
    min_size=0,
    max_size=6,
)

# ---------------------------------------------------------------------------
# Escapes
# ---------------------------------------------------------------------------

_SIMPLE_ESCAPES = st.sampled_from(["\\b", "\\t", "\\n", "\\f", "\\r", "\\\"", "\\\\", "\\/"])

_UNICODE_ESCAPE = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "\\u%04x" % n
)

_EX_UNICODE_ESCAPE = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda n: "\\U%08x" % n
)

_ESCAPE = st.one_of(_SIMPLE_ESCAPES, _UNICODE_ESCAPE, _EX_UNICODE_ESCAPE)

# ---------------------------------------------------------------------------
# Strings (four quoting forms)
# ---------------------------------------------------------------------------

def _basic_string_body():
    return st.one_of(
        st.text(alphabet=_RAW_STRING_CHARS, min_size=0, max_size=8),
        _NON_ASCII_TEXT,
        _ESCAPE,
    )

_basic_string = st.one_of(
    st.lists(_basic_string_body(), min_size=0, max_size=4).map(lambda p: '"' + "".join(p) + '"'),
)

_literal_string = st.one_of(
    st.lists(
        st.one_of(
            st.text(alphabet="".join(c for c in _RAW_STRING_CHARS if c != "'"), min_size=0, max_size=8),
            _NON_ASCII_TEXT,
        ),
        min_size=0,
        max_size=4,
    ).map(lambda p: "'" + "".join(p) + "'"),
)

def _ml_basic_body():
    return st.one_of(
        st.text(alphabet=_RAW_STRING_CHARS, min_size=0, max_size=8),
        _NON_ASCII_TEXT,
        _ESCAPE,
        st.just("\n"),
        st.just("\r\n"),
        st.just('\\\n'),
    )

_ml_basic_string = st.lists(_ml_basic_body(), min_size=0, max_size=4).map(
    lambda p: '"""' + "".join(p) + '"""'
)

_ml_literal_string = st.lists(
    st.one_of(
        st.text(alphabet="".join(c for c in _RAW_STRING_CHARS if c != "'"), min_size=0, max_size=8),
        _NON_ASCII_TEXT,
        st.just("\n"),
    ),
    min_size=0,
    max_size=4,
).map(lambda p: "'''" + "".join(p) + "'''")

_string_value = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_UNQUOTED_KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

_unquoted_key = st.text(alphabet=_UNQUOTED_KEY_CHARS, min_size=1, max_size=6)

_quoted_key = st.one_of(
    st.lists(
        st.one_of(
            st.text(alphabet="".join(c for c in _RAW_STRING_CHARS if c not in ('"', "\\")), min_size=0, max_size=5),
            _NON_ASCII_TEXT,
            _ESCAPE,
        ),
        min_size=0,
        max_size=3,
    ).map(lambda p: '"' + "".join(p) + '"'),
    st.lists(
        st.one_of(
            st.text(alphabet="".join(c for c in _RAW_STRING_CHARS if c != "'"), min_size=0, max_size=5),
            _NON_ASCII_TEXT,
        ),
        min_size=0,
        max_size=3,
    ).map(lambda p: "'" + "".join(p) + "'"),
)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(lambda p: ".".join(p))

_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_DEC_DIGITS = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _dec_int():
    return st.one_of(
        st.integers(min_value=-10**30, max_value=10**30).map(str),
        _DEC_DIGITS,
        st.just("007"),
        st.just("0000"),
        st.just("1_000_000"),
        st.just("+42"),
        st.just("-0"),
    )

def _hex_int():
    return st.one_of(
        st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8).map(lambda h: "0x" + h),
        st.just("0xDEAD_BEEF"),
        st.just("0x0"),
    )

def _oct_int():
    return st.one_of(
        st.text(alphabet="01234567", min_size=1, max_size=8).map(lambda o: "0o" + o),
        st.just("0o755"),
        st.just("0o0"),
    )

def _bin_int():
    return st.one_of(
        st.text(alphabet="01", min_size=1, max_size=8).map(lambda b: "0b" + b),
        st.just("0b1010_1010"),
        st.just("0b0"),
    )

_integer_value = st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

_FLOAT_EXPONENTS = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda e: "e%+d" % e),
    st.sampled_from(["e0", "E1", "e-1", "E+300", "e309", "e-309", "e999"]),
)

def _float_value():
    mantissa = st.one_of(
        st.integers(min_value=-10**12, max_value=10**12).map(str),
        st.sampled_from(["1.", ".5", "0.0", "3.14159", "1_000.000_1", "0.1"]),
    )
    return st.one_of(
        mantissa,
        st.tuples(mantissa, _FLOAT_EXPONENTS).map(lambda t: t[0] + t[1]),
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    )

# ---------------------------------------------------------------------------
# Booleans and date-times
# ---------------------------------------------------------------------------

_bool_value = st.sampled_from(["true", "false"])

def _digits(n):
    return st.text(alphabet="0123456789", min_size=n, max_size=n)

_year = _digits(4)
_month = _digits(2)
_day = _digits(2)
_hour = _digits(2)
_minute = _digits(2)
_second = _digits(2)

_date = st.tuples(_year, _month, _day).map(lambda t: "%s-%s-%s" % t)

_time_partial = st.tuples(_hour, _minute, _second).map(lambda t: "%s:%s:%s" % t)

_time_frac = st.one_of(_digits(1), _digits(3), _digits(6), _digits(9))

_partial_time = st.one_of(
    _time_partial,
    st.tuples(_time_partial, _time_frac).map(lambda t: t[0] + "." + t[1]),
)

_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(st.sampled_from(["+", "-"]), _hour, _minute).map(
        lambda t: t[0] + t[1] + ":" + t[2]
    ),
)

_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(_date, _delim, _partial_time, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)
_local_date_time = st.tuples(_date, _delim, _partial_time).map(
    lambda t: t[0] + t[1] + t[2]
)
_local_date = _date
_local_time = _partial_time

_date_time_value = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    st.just("1979-02-30"),
    st.just("1979-05-27 07:32:00Z"),
    st.just("07:32:00"),
)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

_value = st.recursive(
    st.one_of(
        _string_value,
        _integer_value,
        _float_value,
        _bool_value,
        _date_time_value,
    ),
    lambda children: st.one_of(
        _array(children),
        _inline_table(children),
    ),
    max_leaves=40,
)

# ---------------------------------------------------------------------------
# Arrays
# ---------------------------------------------------------------------------

def _array(children):
    element = st.one_of(
        children,
        st.just(""),
        st.just(" "),
        st.just("\n"),
        st.just("# comment\n"),
        st.just("\t"),
    )
    return st.lists(element, min_size=0, max_size=5).map(
        lambda parts: "[" + ",".join(parts) + "]"
    )

# ---------------------------------------------------------------------------
# Inline tables
# ---------------------------------------------------------------------------

def _inline_table(children):
    def entry():
        return st.tuples(_key, children).map(lambda t: t[0] + " = " + t[1])

    return st.lists(entry(), min_size=0, max_size=5).map(
        lambda pairs: "{" + ", ".join(pairs) + "}"
    )

# ---------------------------------------------------------------------------
# Malformed / near-valid snippets
# ---------------------------------------------------------------------------

_malformed = st.sampled_from([
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    "a = {b = 1",
    "a = [1, 2",
    "a = 1 2",
    "a = = 1",
    "a =",
    "= 1",
    "a = {b = 1,\n c = 2}",
    "a = {b = 1,}",
    "[unclosed",
    "[[unclosed",
    "a = 1\nb = 2\nb = 3",
    "[t]\n[t]",
    "a = \\q",
    "a = 1\n  = 2",
    "a = 0x",
    "a = 0b2",
    "a = 1e",
    "a = 1.2.3",
    "a = true false",
    "key with spaces = 1",
    "a = [1,,2]",
    "a = {,}",
    "a = {b = 1,,}",
    "a = 1\nb = 2\nb = 3",
    "a = 1\nb = 2\nb = 3",
])

# ---------------------------------------------------------------------------
# Complete documents
# ---------------------------------------------------------------------------

def _comment():
    return st.one_of(
        st.just(""),
        st.text(alphabet=_SAFE_ASCII, min_size=0, max_size=10).map(lambda s: "# " + s),
        st.just("#"),
    )

def _key_value_line():
    def pair():
        return st.tuples(_key, st.one_of(_value, _malformed)).map(
            lambda t: t[0] + " = " + t[1]
        )

    return pair()

def _table_header():
    return st.one_of(
        _key.map(lambda k: "[" + k + "]"),
        _key.map(lambda k: "[[" + k + "]]"),
        st.just("[t]"),
        st.just("[[a]]"),
        st.just('[""]'),
    )

def _line():
    return st.one_of(
        _key_value_line(),
        _table_header(),
        _comment(),
        _malformed,
        st.just(""),
    )

_document = st.lists(_line(), min_size=0, max_size=12).map(lambda lines: "\n".join(lines))

# ---------------------------------------------------------------------------
# Deep nesting (depth band 1500-2048)
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "]" * depth

def _deep_inline_table(depth):
    return "{" * depth + "}" * depth

_deep = st.integers(min_value=1500, max_value=2048).flatmap(
    lambda d: st.one_of(
        st.just("a = " + _deep_array(d)),
        st.just("a = " + _deep_inline_table(d)),
    )
)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _deep,
    _malformed,
    st.just(""),
    st.just("\n"),
    st.just("# comment only\n"),
    st.just("a = 1"),
    st.just("a = 1\n"),
)
```