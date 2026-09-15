```python
from hypothesis import strategies as st
import json

# Small helper character sets (no raw NUL)
_ASCII_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_PUNCT = " _-./:;@%&*+=()[]{}<>?^`|~"
_NONASCII = "éü漢字😀Ω≈ç√"
_CONTROL_CHARS = "".join(chr(i) for i in range(1, 32) if i != 0)  # exclude NUL

# Key generators
_unquoted_key = st.text(
    alphabet=_ASCII_LETTERS + _DIGITS + "-_",
    min_size=1,
    max_size=30,
)
_quoted_key_basic = st.text(
    alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS,
    min_size=0,
    max_size=30,
).map(lambda s: '"' + s.replace('"', '\\"').replace("\\", "\\\\") + '"')
_quoted_key_literal = st.text(
    alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS,
    min_size=0,
    max_size=30,
).map(lambda s: "'" + s.replace("'", "''") + "'")  # stick to naive doubling for variety

simple_key = st.one_of(_unquoted_key, _quoted_key_basic, _quoted_key_literal)

dotted_key = st.lists(simple_key, min_size=1, max_size=4).map(lambda parts: ".".join(parts))

# String value forms
_basic_string_content = st.text(
    alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS,
    min_size=0,
    max_size=40,
).map(lambda s: s.replace('"', '\\"').replace("\\", "\\\\"))  # escape quotes and backslashes

_basic_string_with_esc = st.one_of(
    _basic_string_content,
    st.lists(st.sampled_from(['\\n', '\\r', '\\t', '\\b', '\\f', '\\u0000', '\\u263A', '\\U0001F600', '\\\\', '\\"']), min_size=1, max_size=6).map("".join),
)

basic_string = st.one_of(
    _basic_string_with_esc.map(lambda s: '"' + s + '"'),
    # Unterminated variant (for near-valid-but-malformed)
    _basic_string_with_esc.map(lambda s: '"' + s)  # missing closing quote
)

literal_string = st.one_of(
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS, min_size=0, max_size=40).map(lambda s: "'" + s + "'"),
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS, min_size=0, max_size=40).map(lambda s: "'" + s)  # unterminated
)

ml_basic_string = st.one_of(
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS + "\r\n\t", min_size=0, max_size=200).map(lambda s: '"""' + s + '"""'),
    # unterminated multiline
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS + "\r\n\t", min_size=0, max_size=200).map(lambda s: '"""' + s)
)

ml_literal_string = st.one_of(
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS + "\r\n\t", min_size=0, max_size=200).map(lambda s: "'''" + s + "'''"),
    st.text(alphabet=_ASCII_LETTERS + _DIGITS + _PUNCT + _NONASCII + _CONTROL_CHARS + "\r\n\t", min_size=0, max_size=200).map(lambda s: "'''" + s)  # unterminated
)

string_value = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# Integer generators: decimal (with underscores/leading zeros), hex, oct, bin
def _insert_underscores_digits(s):
    if len(s) <= 3:
        return s
    # insert underscores at random positions (not at ends)
    parts = []
    i = 0
    while i < len(s):
        step = min(len(s) - i, max(1, (len(s) // 3)))
        parts.append(s[i : i + step])
        i += step
    return "_".join(parts)

_decimal_int = st.one_of(
    st.integers(min_value=-10 ** 20, max_value=10 ** 20).map(lambda n: str(n)),
    st.integers(min_value=0, max_value=10 ** 20).map(lambda n: (_insert_underscores_digits(str(n)) if n >= 1000 else str(n))),
    # leading zero variants
    st.integers(min_value=0, max_value=999).map(lambda n: ("0" + str(n) if n < 100 else str(n))),
    # extreme long integer
    st.integers(min_value=10 ** 50, max_value=10 ** 100).map(lambda n: str(n)),
)

_hex_int = st.integers(min_value=0, max_value=2 ** 128).map(lambda n: "0x" + _insert_underscores_digits(hex(n)[2:]))
_oct_int = st.integers(min_value=0, max_value=2 ** 128).map(lambda n: "0o" + _insert_underscores_digits(oct(n)[2:]))
_bin_int = st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0b" + _insert_underscores_digits(bin(n)[2:]))

int_value = st.one_of(_decimal_int, _hex_int, _oct_int, _bin_int)

# Float generators (including .5 and 1.)
def _float_with_variants():
    base = st.one_of(
        st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: repr(f)),
        st.integers(min_value=0, max_value=10 ** 12).map(lambda n: str(n) + "." ),  # '1.' style
        st.integers(min_value=0, max_value=10 ** 12).map(lambda n: "." + str(n % 10)),  # '.5' style
        st.integers(min_value=0, max_value=10 ** 308).map(lambda n: str(n) + "e309"),  # extreme exponent style
    )
    specials = st.sampled_from(["inf", "-inf", "+inf", "nan", "+nan", "-nan"])
    return st.one_of(base, specials)
float_value = _float_with_variants()

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date/time variants (may be calendar-invalid)
_year = st.integers(min_value=0, max_value=9999).map(lambda n: f"{n:04d}")
_two = lambda n: f"{n:02d}"
_month = st.integers(min_value=1, max_value=12).map(lambda m: f"{m:02d}")
_day = st.integers(min_value=1, max_value=31).map(lambda d: f"{d:02d}")
_hour = st.integers(min_value=0, max_value=23).map(lambda h: f"{h:02d}")
_minute = st.integers(min_value=0, max_value=59).map(lambda m: f"{m:02d}")
_second = st.integers(min_value=0, max_value=60).map(lambda s: f"{s:02d}")
_frac = st.integers(min_value=0, max_value=999999).map(lambda n: "." + f"{n:06d}")
_offset = st.one_of(st.just("Z"), st.tuples(st.sampled_from(["+", "-"]), _hour, st.just(":"), _minute).map(lambda t: t[0] + t[1] + ":" + t[3]))

date_local = st.tuples(_year, st.sampled_from(["-"]), _month, st.sampled_from(["-"]), _day).map(lambda t: "".join(t))
time_local = st.tuples(_hour, st.just(":"), _minute, st.just(":"), _second, st.one_of(st.just(""), _frac)).map(lambda t: "".join(t))
offset_dt = st.tuples(date_local, st.sampled_from(["T", "t", " "]), time_local, _offset).map(lambda t: t[0] + t[1] + t[2] + t[3])
local_dt = st.tuples(date_local, st.sampled_from(["T", "t", " "]), time_local).map(lambda t: t[0] + t[1] + t[2])
local_date_only = date_local
local_time_only = time_local

date_value = st.one_of(offset_dt, local_dt, local_date_only, local_time_only)

# Base atomic value (string, int, float, bool, date)
atomic_value = st.one_of(string_value, int_value, float_value, bool_value, date_value)

# Use st.recursive to create nested arrays and inline tables that may nest deeply.
def _extend(children):
    # Arrays: allow comments/newlines inside arrays, trailing commas, mixed types, nested arrays
    array_valid = st.builds(
        lambda items: "[" + ", ".join(items) + "]",
        st.lists(children, min_size=0, max_size=6),
    )
    # Malformed arrays: missing closing bracket or doubled delimiter
    array_malformed = st.builds(
        lambda items: "[" + ", ".join(items) + ("]" if st.randoms().example().randrange(2) == 0 else ""),
        st.lists(children, min_size=0, max_size=6),
    )
    array_with_comments = st.builds(
        lambda items: "[" + (", ".join("#" + " comment\n" + v for v in items)) + "]",
        st.lists(children, min_size=0, max_size=4),
    )

    # Inline tables: must not contain newlines; allow trailing comma; empty inline tables.
    def make_inline(kvs):
        body = ", ".join(kvs)
        # allow trailing comma rarely
        if len(kvs) > 0 and st.randoms().example().randrange(4) == 0:
            body = body + ","
        return "{" + body + "}"

    inline_valid = st.builds(
        make_inline,
        st.lists(
            st.tuples(
                simple_key,
                children,
            ).map(lambda t: t[0] + " = " + t[1]),
            min_size=0,
            max_size=6,
        ),
    )

    # inline malformed: include a newline inside (parser rejects newline in inline tables)
    inline_malformed = st.builds(
        lambda kvs: "{" + ("\n".join(kvs)) + "}",
        st.lists(
            st.tuples(
                simple_key,
                children,
            ).map(lambda t: t[0] + " = " + t[1]),
            min_size=1,
            max_size=4,
        ),
    )

    # Allow nested arrays and inline tables and combination
    return st.one_of(array_valid, array_malformed, inline_valid, inline_malformed, array_with_comments)

# Allow deep recursion; parser handles up to ~2048 nested levels. Hypothesis controlling size will avoid causing actual stack overflow here,
# but set max_leaves high to allow deep nesting in generated examples.
nested_value = st.recursive(atomic_value, _extend, max_leaves=2048)

# Expression generators for document: key_value, table, array_table, comment-only
key_value = st.tuples(
    # allow dotted keys often
    st.one_of(dotted_key, simple_key),
    st.just(" = "),
    nested_value,
).map(lambda t: t[0] + t[1] + t[2])

standard_table = st.tuples(
    st.just("["),
    dotted_key,
    st.just("]"),
).map(lambda t: t[0] + t[1] + t[2])

array_table = st.tuples(
    st.just("[["),
    dotted_key,
    st.just("]]"),
).map(lambda t: t[0] + t[1] + t[2])

comment_line = st.text(alphabet=_ASCII_LETTERS + _DIGITS + " _-", min_size=0, max_size=80).map(lambda s: "#" + s)

# stray token / malformed expression: missing equals or stray token
malformed_expr = st.one_of(
    st.tuples(simple_key, nested_value).map(lambda t: t[0] + " " + t[1]),  # missing '='
    st.text(alphabet="!@#$%^&*<>/\\", min_size=1, max_size=10),  # stray token
)

# Build a document: sequence of expressions separated by newlines. Include empty doc, comment-only, no trailing newline, CRLF variants.
_lines = st.lists(
    st.one_of(
        key_value,
        standard_table,
        array_table,
        comment_line,
        malformed_expr,
    ),
    min_size=0,
    max_size=20,
)

# Compose final document with mixed newline styles; include possibility of CRLF
def _join_lines(lines, crlf=False, trailing_newline=True):
    nl = "\r\n" if crlf else "\n"
    if not lines:
        return "" if not trailing_newline else nl if st.randoms().example().randrange(2) == 0 else ""
    doc = nl.join(lines)
    if trailing_newline and st.randoms().example().randrange(2) == 0:
        doc = doc + nl
    return doc

strategy = st.builds(
    lambda lines, crlf, trailing: _join_lines(lines, crlf, trailing),
    _lines,
    st.booleans(),
    st.booleans(),
)
```