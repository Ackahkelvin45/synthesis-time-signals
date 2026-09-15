```python
from hypothesis import strategies as st
import json

# Helper alphabets (ASCII only where appropriate)
_ASCII_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_UNQUOTED_ALLOWED = _ASCII_LETTERS + _DIGITS + "-_"
_PUNCT = "!@#$%^&*()[]{}<>?/\\|;:+-_=,."

# Control characters to include inside strings (explicitly exclude NUL = \x00)
_CONTROL_CHARS = "".join(chr(i) for i in range(1, 32) if i not in (10, 13, 0))

# Helper to insert underscores deterministically
def _with_underscores(s: str, count: int) -> str:
    if not s or count <= 0:
        return s
    step = max(1, len(s) // (count + 1))
    parts = []
    i = 0
    inserted = 0
    while i < len(s):
        end = i + step
        parts.append(s[i:end])
        i = end
        if inserted < count and i < len(s):
            parts.append("_")
            inserted += 1
    return "".join(parts)

# Basic small utilities as Hypothesis building blocks
_empty = st.just("")
_ws = st.sampled_from(["", " ", "  ", "\t", "    "])
_comment = st.builds(lambda c: ("#"+c) if c is not None else "", st.one_of(st.text(_ASCII_LETTERS+_DIGITS+" ", max_size=30), st.just("")))

# Key strategies
_unquoted_key = st.one_of(
    st.text(_UNQUOTED_ALLOWED, min_size=1, max_size=30),
    # occasionally produce extremely long key (10k chars)
    st.text(_UNQUOTED_ALLOWED, min_size=1000, max_size=10000).map(lambda s: s[:10000]),
    # produce non-ASCII bare keys (expected to be rejected by parser)
    st.text(min_size=1, max_size=10).filter(lambda s: any(ord(c) > 127 for c in s))
)

_basic_string_key = st.one_of(
    # empty quoted key and short quoted keys
    st.just('""'),
    st.text(_UNQUOTED_ALLOWED + _PUNCT + _CONTROL_CHARS, min_size=0, max_size=30).map(lambda s: json.dumps(s))
)
_literal_string_key = st.text(_UNQUOTED_ALLOWED + _PUNCT, min_size=0, max_size=30).map(lambda s: "'" + s.replace("'", "") + "'")

simple_key = st.one_of(_unquoted_key, _basic_string_key, _literal_string_key)

dotted_key = st.one_of(
    simple_key,
    st.lists(simple_key, min_size=2, max_size=5).map(lambda parts: ".".join(parts))
)

# String value strategies
# Ensure NO raw NUL '\x00' in produced strings; we may emit the six-character escape "\u0000".
_basic_string_content = st.text(_ASCII_LETTERS + _DIGITS + " .,;:-/@" + _CONTROL_CHARS + "\\", min_size=0, max_size=40).filter(lambda s: '\x00' not in s).map(
    lambda s: s.replace('"', '\\"').replace("\n", ""))  # basic string cannot contain raw newline in BASIC_STRING
_basic_string_with_escapes = st.lists(
    st.one_of(
        st.text(_ASCII_LETTERS + _DIGITS + " ", min_size=1, max_size=6),
        st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\\\', '\\"', '\\/', '\\u0000', '\\U0001F600', '\\q'])
    ),
    min_size=0, max_size=10
).map("".join).map(lambda s: '"' + s + '"')

_basic_string_raw = _basic_string_content.map(lambda s: '"' + s + '"')
_basic_string_unterminated = _basic_string_content.map(lambda s: '"' + s)  # unterminated variant

_ml_basic_string = st.lists(
    st.one_of(st.text(_ASCII_LETTERS + _DIGITS + " " + _PUNCT + _CONTROL_CHARS + "\n", min_size=0, max_size=80),
              st.sampled_from(['\\\n', '\\n', '\\t', '\\u0000', '\\q'])),
    min_size=0, max_size=6
).map("".join).map(lambda s: '"""' + s + '"""')

_literal_string = st.text(_ASCII_LETTERS + _DIGITS + " " + _PUNCT + _CONTROL_CHARS.replace("'", ""), min_size=0, max_size=40).map(lambda s: "'" + s + "'")
_ml_literal_string = st.text(min_size=0, max_size=120).map(lambda s: "'''" + s + "'''")

string_value = st.one_of(
    _basic_string_raw,
    _basic_string_with_escapes,
    _basic_string_unterminated,  # unterminated
    _ml_basic_string,
    _literal_string,
    _ml_literal_string
)

# Integer strategies across bases with underscores and extremes
_digits_text = st.text(_DIGITS, min_size=1, max_size=40)
_decimal_int = st.tuples(st.sampled_from(["", "+", "-"]), _digits_text, st.integers(min_value=0, max_value=6)).map(
    lambda tup: tup[0] + _with_underscores(tup[1], tup[2])
)

_hex_digit_chars = "0123456789abcdefABCDEF"
_hex_text = st.text(_hex_digit_chars, min_size=1, max_size=30)
_hex_int = st.tuples(st.sampled_from(["", "+", "-"]), _hex_text, st.integers(min_value=0, max_value=6)).map(
    lambda tup: tup[0] + "0x" + _with_underscores(tup[1], tup[2])
)

_oct_text = st.text("01234567", min_size=1, max_size=30)
_oct_int = st.tuples(st.sampled_from(["", "+", "-"]), _oct_text, st.integers(min_value=0, max_value=6)).map(
    lambda tup: tup[0] + "0o" + _with_underscores(tup[1], tup[2])
)

_bin_text = st.text("01", min_size=1, max_size=64)
_bin_int = st.tuples(st.sampled_from(["", "+", "-"]), _bin_text, st.integers(min_value=0, max_value=6)).map(
    lambda tup: tup[0] + "0b" + _with_underscores(tup[1], tup[2])
)

integer_value = st.one_of(
    _decimal_int,
    _hex_int,
    _oct_int,
    _bin_int,
    # extreme magnitudes (many digits)
    st.integers(min_value=10**50, max_value=10**200).map(str),
    st.just("007")  # leading zeros edge case
)

# Floating point including inf/nan, .5, 1., large exponents
_frac_int = st.text(_DIGITS, min_size=1, max_size=30)
_float_normal = st.tuples(
    st.sampled_from(["", "+", "-"]),
    _frac_int,  # integer part or empty
    st.sampled_from(["." + _with_underscores.__name__ if False else "."]),  # placeholder to vary forms
    _frac_int,
    st.sampled_from(["", "e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=400)
).map(lambda tup: (
    # form possibilities: 1.234, 1., .5, 1e10, 1.23e-5
    (tup[0] + tup[1] + "." + tup[3] if tup[1] else tup[0] + "." + tup[3]) +
    (("e" + tup[5] + str(tup[6])) if tup[4] else "")
))

_float_edge = st.sampled_from(["1.", ".5", "1e309", "+inf", "-inf", "nan", "+nan", "-nan"])
float_value = st.one_of(_float_normal, _float_edge)

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date-time forms (may be calendar-invalid; that's allowed)
def _pad(n):
    return str(n).zfill(2)

_date_full = st.tuples(
    st.integers(0, 9999),  # year
    st.integers(1, 12),
    st.integers(1, 31),
    st.integers(0, 23),
    st.integers(0, 59),
    st.integers(0, 59),
    st.sampled_from(["Z", "+00:00", "-05:00", "+12:30", ""])
).map(lambda t: "{}-{}-{}T{}:{}:{}{}".format(str(t[0]).zfill(4), _pad(t[1]), _pad(t[2]), _pad(t[3]), _pad(t[4]), _pad(t[5]), t[6]))

_date_local_time = st.tuples(
    st.integers(0, 9999),
    st.integers(1, 12),
    st.integers(1, 31),
    st.integers(0, 23),
    st.integers(0, 59),
    st.integers(0, 59)
).map(lambda t: "{}-{}-{} {}:{}:{}".format(str(t[0]).zfill(4), _pad(t[1]), _pad(t[2]), _pad(t[3]), _pad(t[4]), _pad(t[5])))

date_time_value = st.one_of(_date_full, _date_local_time, st.text(_DIGITS + "-:TtZ+", min_size=5, max_size=30))

# Base leaf values: strings, numbers, booleans, datetimes
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_time_value
)

# Recursive containers: arrays and inline tables (they will accept s as already-stringified values)
def _array_builder(s):
    # elements may be interleaved with comments or newlines
    elems = st.lists(st.one_of(s, st.builds(lambda c: "#"+c, st.text(max_size=20)), st.just("\n")), min_size=0, max_size=6)
    return elems.map(lambda lst: "[" + ", ".join(x for x in lst if x is not None and x != "") + ("," if (len(lst) > 0 and (len(lst) % 5 == 0)) else "") + "]")

def _inline_table_builder(s):
    # generate key/value pairs using dotted or simple keys; trailing comma allowed; sometimes include newline inside (causes rejection)
    kv = st.lists(st.tuples(
        st.one_of(simple_key, dotted_key, st.text(_ASCII_LETTERS + _DIGITS, min_size=1, max_size=20)),
        s
    ), min_size=0, max_size=6)
    def mk(kv_list):
        parts = []
        for k, v in kv_list:
            parts.append(f"{k} = {v}")
        joiner = ", "
        result = "{"
        result += joiner.join(parts)
        # sometimes emit trailing comma
        if len(kv_list) and (len(kv_list) % 3 == 0):
            result += ","
        # occasionally inject a newline inside inline table to produce a malformed inline table case
        if len(kv_list) and (len(kv_list) % 5 == 0):
            result = result.replace("{", "{\n", 1)
            result = result + "\n}"
        else:
            result += "}"
        return result
    return kv.map(mk)

# Build recursive value strategy allowing deep nesting
value_strategy = st.recursive(
    base_value.map(lambda s: s if isinstance(s, str) else str(s)),
    lambda inner: st.one_of(
        _array_builder(inner),
        _inline_table_builder(inner)
    ),
    max_leaves=256
)

# Expressions: key-value, tables, array-of-tables, comments, malformed variants
# Key-value lines
key_value = st.tuples(
    st.one_of(dotted_key, simple_key, st.text(_UNQUOTED_ALLOWED, min_size=1, max_size=10000)),  # include extremely long key
    _ws,
    st.just("="),
    _ws,
    value_strategy,
    st.one_of(st.just(""), _comment)
).map(lambda tup: f"{tup[0]}{tup[1]}{tup[2]}{tup[3]}{tup[4]}{(' ' + tup[5]) if tup[5] else ''}".rstrip())

# Table headers
standard_table = st.tuples(st.just("["), dotted_key, st.just("]"), st.one_of(st.just(""), _comment)).map(
    lambda t: t[0] + t[1] + t[2] + ((" " + t[3]) if t[3] else "")
)
array_table = st.tuples(st.just("[["), dotted_key, st.just("]]"), st.one_of(st.just(""), _comment)).map(
    lambda t: t[0] + t[1] + t[2] + ((" " + t[3]) if t[3] else "")
)

# Malformed headers and stray tokens
malformed_header = st.one_of(
    st.tuples(st.just("["), dotted_key, st.just("")).map(lambda t: t[0] + t[1]),  # missing closing bracket
    st.tuples(st.just("[["), dotted_key, st.just("]")).map(lambda t: t[0] + t[1] + t[2]),  # doubled/dangling bracket
    st.just("] unexpected")
)

# Stray/malformed expressions
stray_token = st.sampled_from(["=", "==", "]]]", "[[["])
unterminated_keyval = st.tuples(simple_key, _ws, st.just("="), _ws, string_value).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])  # some may be unterminated strings

expression = st.one_of(
    key_value,
    standard_table,
    array_table,
    _comment.map(lambda s: s if s else ""),  # comment or empty
    malformed_header,
    stray_token,
    unterminated_keyval
)

# Document: sequence of expressions, include empty and comment-only documents
document = st.lists(expression, min_size=0, max_size=20).map(lambda lines: "\n".join(lines))

# Top-level strategy producing str values: ensure no raw NULs
strategy = document.filter(lambda s: '\x00' not in s)
```