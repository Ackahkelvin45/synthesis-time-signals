```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic character / token helpers
# ---------------------------------------------------------------------------

def _no_nul(s):
    return s.replace("\x00", "")

# Characters allowed in bare (unquoted) keys.
_bare_key_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)

# Non-ASCII text (safe: only used inside quoted strings/comments).
_unicode_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
    min_size=0,
    max_size=12,
)

_ascii_text = st.text(
    alphabet=st.characters(
        min_codepoint=0x20,
        max_codepoint=0x7E,
        blacklist_characters='\\"\'\x00',
    ),
    min_size=0,
    max_size=12,
)

# Raw control bytes (excluding NUL) for the "accepted raw control char" cases.
_control_byte = st.integers(min_value=1, max_value=0x1F).map(chr)

_escapes = st.sampled_from(
    [
        "\\b", "\\t", "\\n", "\\f", "\\r", "\\\"", "\\\\",
        "\\u0041", "\\u00e9", "\\u0000", "\\uFFFF",
        "\\U0001F600", "\\U00000041",
    ]
)

# ---------------------------------------------------------------------------
# Strings: all four quoting forms
# ---------------------------------------------------------------------------

_basic_string_body = st.one_of(
    _ascii_text,
    _unicode_text,
    _escapes,
    _control_byte,
)

basic_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_basic_string_body, max_size=6),
)

literal_string = st.builds(
    lambda s: "'" + s + "'",
    st.text(
        alphabet=st.characters(
            min_codepoint=0x20,
            max_codepoint=0x7E,
            blacklist_characters="'\x00",
        ),
        max_size=12,
    ),
)

# Multiline basic: allow raw newlines, escapes, everything but a bare """ .
_ml_basic_body = st.one_of(
    _ascii_text,
    _unicode_text,
    _escapes,
    _control_byte,
    st.just("\n"),
    st.just("\r\n"),
    st.just("\\\n"),  # line-ending backslash
)
ml_basic_string = st.builds(
    lambda parts: '"""' + "".join(parts) + '"""',
    st.lists(_ml_basic_body, max_size=6),
)

# Multiline literal: any chars except the closing ''' sequence.
_ml_literal_body = st.one_of(
    st.text(
        alphabet=st.characters(
            min_codepoint=0x01,
            max_codepoint=0x7E,
            blacklist_characters="'\x00",
        ),
        max_size=10,
    ),
    _unicode_text,
    st.just("\n"),
    st.just("\r\n"),
    st.just('"'),
)
ml_literal_string = st.builds(
    lambda parts: "'''" + "".join(parts) + "'''",
    st.lists(_ml_literal_body, max_size=6),
)

any_string = st.one_of(
    basic_string,
    literal_string,
    ml_basic_string,
    ml_literal_string,
)

# ---------------------------------------------------------------------------
# Integers / floats
# ---------------------------------------------------------------------------

_dec_digits = st.text(alphabet="0123456789", min_size=1, max_size=20)

def _dec_int():
    return st.one_of(
        # plain
        st.builds(lambda d: d, _dec_digits),
        # with optional sign
        st.builds(lambda s, d: s + d, st.sampled_from(["", "+", "-"]), _dec_digits),
        # leading zeros (accepted by target)
        st.builds(lambda d: "0" * 3 + d, _dec_digits),
        # underscores
        st.builds(
            lambda a, b: a + "_" + b,
            st.text(alphabet="123456789", min_size=1, max_size=5),
            _dec_digits,
        ),
        # extreme magnitudes
        st.sampled_from(
            [
                "9223372036854775807",
                "9223372036854775808",
                "-9223372036854775808",
                "-9223372036854775809",
                "18446744073709551615",
                "18446744073709551616",
                "99999999999999999999999999999999999999",
                "1_000_000",
                "0",
                "-0",
                "+0",
            ]
        ),
    )

_hex_digits = st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=16)
_oct_digits = st.text(alphabet="01234567", min_size=1, max_size=16)
_bin_digits = st.text(alphabet="01", min_size=1, max_size=16)

_hex_int = st.builds(lambda d: "0x" + d, _hex_digits)
_oct_int = st.builds(lambda d: "0o" + d, _oct_digits)
_bin_int = st.builds(lambda d: "0b" + d, _bin_digits)

any_int = st.one_of(
    _dec_int(),
    _hex_int,
    _oct_int,
    _bin_int,
    st.sampled_from(
        [
            "0xDEADBEEF",
            "0xdead_beef",
            "0o777",
            "0o1_2_3",
            "0b1010",
            "0b1_0_1",
            "0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        ]
    ),
)

_frac_digits = st.text(alphabet="0123456789", min_size=1, max_size=10)
_exp_part = st.builds(
    lambda s, d: s + d,
    st.sampled_from(["e", "E"]),
    st.builds(
        lambda sign, digits: sign + digits,
        st.sampled_from(["", "+", "-"]),
        _dec_digits,
    ),
)

any_float = st.one_of(
    st.builds(lambda a, b: a + "." + b, _dec_digits, _frac_digits),
    st.builds(lambda a, b: a + "." + b, _dec_digits, _frac_digits),  # placeholder
    st.builds(lambda a: a + ".", _dec_digits),  # trailing dot (accepted)
    st.builds(lambda b: "." + b, _frac_digits),  # leading dot (accepted)
    st.builds(
        lambda a, b, e: a + "." + b + e,
        _dec_digits,
        _frac_digits,
        _exp_part,
    ),
    st.builds(lambda a, e: a + e, _dec_digits, _exp_part),
    st.sampled_from(
        [
            "inf", "+inf", "-inf",
            "nan", "+nan", "-nan",
            "1e309",
            "-1e309",
            "1.7976931348623157e308",
            "2.2250738585072014e-308",
            "0.0",
            "-0.0",
            "1.0e+10",
            "1_000.000_1",
        ]
    ),
)

# ---------------------------------------------------------------------------
# Booleans, date-times
# ---------------------------------------------------------------------------

any_bool = st.sampled_from(["true", "false"])

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_day = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_hour = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_minute = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_second = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_secfrac = st.builds(
    lambda d: "." + d,
    st.text(alphabet="0123456789", min_size=1, max_size=6),
)

_full_date = st.builds(lambda y, m, d: y + "-" + m + "-" + d, _year, _month, _day)
_partial_time = st.builds(
    lambda h, mi, s, f: h + ":" + mi + ":" + s + f,
    _hour, _minute, _second,
    st.one_of(st.just(""), _secfrac),
)
_delim = st.sampled_from(["T", "t", " "])
_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.builds(
        lambda s, h, m: s + h + ":" + m,
        st.sampled_from(["+", "-"]),
        _hour,
        _minute,
    ),
)

any_datetime = st.one_of(
    st.builds(lambda d, dl, t: d + dl + t + "Z", _full_date, _delim, _partial_time),
    st.builds(lambda d, dl, t, o: d + dl + t + o, _full_date, _delim, _partial_time, _offset),
    st.builds(lambda d, dl, t: d + dl + t, _full_date, _delim, _partial_time),
    _full_date,
    _partial_time,
    st.sampled_from(
        [
            "1979-05-27T07:32:00Z",
            "1979-05-27 07:32:00Z",
            "1979-05-27T00:32:00-07:00",
            "1979-05-27T00:32:00.999999-07:00",
            "1979-05-27T07:32:00",
            "1979-05-27",
            "07:32:00",
            "00:32:00.999999",
            "1979-02-30",  # calendar-invalid (accepted)
            "1979-13-45",  # calendar-invalid (accepted)
        ]
    ),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-", min_size=1, max_size=10)

_quoted_key = st.one_of(
    basic_string,
    literal_string,
    st.just('""'),  # empty quoted key
)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.builds(
    lambda parts: ".".join(parts),
    st.lists(_simple_key, min_size=2, max_size=4),
)

any_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# A value strategy is recursive; use st.recursive with a base of scalars.
_scalar_value = st.one_of(
    any_string,
    any_int,
    any_float,
    any_bool,
    any_datetime,
)

# Comments, used in arrays.
_comment = st.builds(
    lambda body: "#" + body,
    st.text(
        alphabet=st.characters(
            min_codepoint=0x01,
            max_codepoint=0x7E,
            blacklist_characters="\x00\n",
        ),
        max_size=20,
    ),
)

_ws = st.sampled_from(["", " ", "  ", "\t", " \t "])
_nl = st.sampled_from(["\n", "\r\n"])

def _array_from(value_strategy):
    # Build array text with optional whitespace, newlines, comments,
    # trailing comma.
    def _mk(parts):
        return "[" + "".join(parts) + "]"

    elems = st.lists(
        st.builds(
            lambda pre, v, post, trail: pre + v + post + trail,
            st.one_of(_ws, _nl, _comment + "\n", _nl + _comment + "\n", _ws),
            value_strategy,
            st.one_of(_ws, _nl, _comment + "\n", _nl + _comment + "\n", _ws),
            st.one_of(st.just(","), st.just(","), st.just(","), st.just("")),
        ),
        max_size=5,
    )
    return st.builds(_mk, elems)

def _inline_table_from(value_strategy, key_strategy):
    def _mk(parts):
        return "{" + "".join(parts) + "}"

    def _pair(k, v):
        return k + " = " + v

    pairs = st.lists(
        st.builds(
            lambda pre, k, v, post, trail: pre + _pair(k, v) + post + trail,
            st.one_of(_ws, _ws),
            key_strategy,
            value_strategy,
            st.one_of(_ws, _ws),
            st.one_of(st.just(","), st.just(","), st.just("")),
        ),
        max_size=4,
    )
    return st.builds(_mk, pairs)

# Recursive value: scalars at the base, arrays and inline tables at the
# recursive step. Use a modest recursion depth; the "deep nesting" cases are
# generated separately by explicit repetition below.
_value = st.recursive(
    _scalar_value,
    lambda children: st.one_of(
        _array_from(children),
        _inline_table_from(children, any_key),
    ),
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Deep nesting generators (arrays / inline tables), depth in 1500-2048 band.
# ---------------------------------------------------------------------------

_deep_array = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "[" * n + "]" * n
)

_deep_inline_table = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "{a = " * n + "1" + "}" * n
)

_deep_mixed = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "[" * (n // 2) + "{a = " * (n - n // 2) + "1"
    + "}" * (n - n // 2) + "]" * (n // 2)
)

# ---------------------------------------------------------------------------
# Key/value lines, tables, arrays of tables
# ---------------------------------------------------------------------------

def _key_value(key_strategy, value_strategy):
    def _mk(k, ws1, v, ws2, comment):
        return k + ws1 + "=" + ws2 + v + comment
    return st.builds(
        _mk,
        key_strategy,
        st.sampled_from(["", " ", "  "]),
        value_strategy,
        st.sampled_from(["", " ", "  "]),
        st.one_of(st.just(""), st.builds(lambda c: " #" + c, st.text(
            alphabet=st.characters(min_codepoint=0x01, max_codepoint=0x7E,
                                   blacklist_characters="\x00\n"),
            max_size=10))),
    )

_key_value_line = _key_value(any_key, _value)

_standard_table = st.builds(
    lambda k, c: "[" + k + "]" + c,
    any_key,
    st.one_of(st.just(""), st.builds(lambda t: " #" + t, st.text(
        alphabet=st.characters(min_codepoint=0x01, max_codepoint=0x7E,
                               blacklist_characters="\x00\n"),
        max_size=10))),
)

_array_table = st.builds(
    lambda k, c: "[[" + k + "]]" + c,
    any_key,
    st.one_of(st.just(""), st.builds(lambda t: " #" + t, st.text(
        alphabet=st.characters(min_codepoint=0x01, max_codepoint=0x7E,
                               blacklist_characters="\x00\n"),
        max_size=10))),
)

_comment_line = st.builds(
    lambda body: "#" + body,
    st.text(
        alphabet=st.characters(min_codepoint=0x01, max_codepoint=0x7E,
                               blacklist_characters="\x00\n"),
        max_size=30,
    ),
)

_blank_line = st.just("")

_any_line = st.one_of(
    _key_value_line,
    _standard_table,
    _array_table,
    _comment_line,
    _blank_line,
)

# ---------------------------------------------------------------------------
# Complete documents
# ---------------------------------------------------------------------------

def _join_lines(lines, sep):
    return sep.join(lines)

_document = st.builds(
    lambda lines, sep: _no_nul(_join_lines(lines, sep)),
    st.lists(_any_line, min_size=0, max_size=8),
    st.sampled_from(["\n", "\r\n"]),
)

# Documents that exercise specific features in isolation.
_feature_documents = st.one_of(
    # empty / comment-only
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("# comment\n\n# another\n"),
    # empty containers
    st.just("a = []\n"),
    st.just("a = {}\n"),
    st.just("[t]\n"),
    st.just("[[a]]\n"),
    st.just("[[a]]\n[[a]]\n"),
    # every scalar kind
    st.builds(lambda s: "a = " + s + "\n", _scalar_value),
    # arrays of mixed kinds
    st.builds(lambda s: "a = [" + s + "]\n", _scalar_value),
    # inline table with trailing comma (accepted by target)
    st.just("a = {b = 1,}\n"),
    st.just("a = {b = 1, c = 2,}\n"),
    # empty quoted key
    st.just('"" = 1\n'),
    st.just("'' = 1\n"),
    # dotted key
    st.just("a.b.c = 1\n"),
    st.just("a.b.c.d.e.f = 1\n"),
    # super-table after sub-table
    st.just("[a.b]\nx = 1\n[a]\ny = 2\n"),
    # arrays of tables
    st.just("[[a]]\nx = 1\n[[a]]\nx = 2\n"),
    # deep nesting
    st.builds(lambda s: "a = " + s + "\n", _deep_array),
    st.builds(lambda s: "a = " + s + "\n", _deep_inline_table),
    st.builds(lambda s: "a = " + s + "\n", _deep_mixed),
    # long key
    st.builds(lambda s: s + " = 1\n", st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1000, max_size=10000)),
    # no trailing newline
    st.just("a = 1"),
    # CRLF
    st.just("a = 1\r\nb = 2\r\n"),
    # tab indentation
    st.just("\ta = 1\n\tb = 2\n"),
    # accepted deviations
    st.just("a = 007\n"),
    st.just("a = 1.\n"),
    st.just("a = .5\n"),
    st.just("a = 1979-02-30\n"),
    st.builds(lambda c: 'a = "x' + c + 'y"\n', _control_byte),
    st.builds(lambda c: "# comment with " + c + "\n", _control_byte),
    # unicode escape
    st.just('a = "\\u0041"\n'),
    st.just('a = "\\U0001F600"\n'),
    st.just('a = "\\u0000"\n'),
)

# ---------------------------------------------------------------------------
# Near-valid-but-malformed inputs (one missing/doubled delimiter, etc.)
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    # missing closing bracket
    st.just("a = [1, 2\n"),
    st.just("a = [1, 2,\n"),
    # doubled delimiter
    st.just("a = [[1]]\n"),
    st.just("a = {b = 1}}\n"),
    st.just("a = [1]]\n"),
    st.just("[a]]\n"),
    st.just("[[a]]]\n"),
    # unterminated string
    st.just('a = "unterminated\n'),
    st.just("a = 'unterminated\n"),
    st.just('a = """unterminated\n'),
    st.just("a = '''unterminated\n"),
    # stray token
    st.just("a = 1 2\n"),
    st.just("a = = 1\n"),
    st.just("= 1\n"),
    st.just("a\n"),
    st.just("a =\n"),
    # value on next line
    st.just("a =\n1\n"),
    # invalid escape
    st.just('a = "\\q"\n'),
    st.just('a = "\\x41"\n'),
    # duplicate keys (rejected by target)
    st.just("a = 1\na = 2\n"),
    st.just("[t]\nx = 1\n[t]\ny = 2\n"),
    st.just("a.b = 1\na.b = 2\n"),
    # newline inside inline table (rejected)
    st.just("a = {b = 1,\nc = 2}\n"),
    st.just("a = {\nb = 1}\n"),
    # non-ASCII bare key (rejected)
    st.just("é = 1\n"),
    st.just("aé = 1\n"),
    # table and array of tables same name
    st.just("[a]\n[[a]]\n"),
    st.just("[[a]]\n[a]\n"),
    # bare key with invalid char
    st.just("a b = 1\n"),
    st.just("a$b = 1\n"),
    # missing equals
    st.just("a 1\n"),
    # empty key
    st.just(" = 1\n"),
)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _feature_documents,
    _malformed,
)
```