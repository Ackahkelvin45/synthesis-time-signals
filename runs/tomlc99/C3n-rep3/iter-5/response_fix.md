```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Low-level character / fragment strategies
# ---------------------------------------------------------------------------

# Characters safe for bare keys (ASCII alnum, '-', '_')
_bare_key_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)

# Characters for string content: printable ASCII + selected non-ASCII + control
# bytes (except NUL).  Raw control bytes are accepted by the target parser.
_string_content_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E),  # printable ASCII
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF).filter(
        lambda c: not (0xD800 <= ord(c) <= 0xDFFF)
    ),  # non-ASCII (excluding surrogates)
    st.integers(min_value=1, max_value=0x08).map(chr),  # control (no NUL)
    st.integers(min_value=0x0B, max_value=0x0C).map(chr),
    st.integers(min_value=0x0E, max_value=0x1F).map(chr),
    st.just("\t"),
)

# Escape sequences for basic strings
_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.integers(min_value=0, max_value=0xFFFF).map(
        lambda n: "\\u%04X" % n
    ),
    st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\U%08X" % n
    ),
)

_basic_string_body = st.one_of(
    st.lists(_string_content_char, max_size=12).map("".join),
    st.lists(_escape, max_size=4).map("".join),
    st.lists(st.one_of(_string_content_char, _escape), max_size=12).map("".join),
)

_literal_string_body = st.lists(
    st.one_of(
        _string_content_char,
        st.just("'"),
    ),
    max_size=12,
).map("".join)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_unquoted_key = st.lists(_bare_key_char, min_size=1, max_size=8).map("".join)

_basic_key = st.builds(
    lambda body: '"' + body + '"',
    _basic_string_body,
)

_literal_key = st.builds(
    lambda body: "'" + body + "'",
    _literal_string_body,
)

_simple_key = st.one_of(_unquoted_key, _basic_key, _literal_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(".".join)

_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------

# --- strings ---
_basic_string = st.builds(lambda b: '"' + b + '"', _basic_string_body)

_ml_basic_string = st.builds(
    lambda b: '"""' + b + '"""',
    st.lists(
        st.one_of(_string_content_char, _escape, st.just("\n")),
        max_size=20,
    ).map("".join),
)

_literal_string = st.builds(lambda b: "'" + b + "'", _literal_string_body)

_ml_literal_string = st.builds(
    lambda b: "'''" + b + "'''",
    st.lists(
        st.one_of(_string_content_char, st.just("\n"), st.just("'")),
        max_size=20,
    ).map("".join),
)

_string_value = st.one_of(
    _basic_string, _ml_basic_string, _literal_string, _ml_literal_string
)

# --- integers ---

# decimal, including leading zeros (accepted by target)
_dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.builds(
        lambda digits: "".join(digits),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=20),
    ),
    st.builds(
        lambda sign, digits: sign + "".join(digits),
        st.sampled_from(["+", "-"]),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=20),
    ),
    st.builds(
        lambda parts: "_".join(parts),
        st.lists(
            st.lists(st.sampled_from("0123456789"), min_size=1, max_size=4).map("".join),
            min_size=2,
            max_size=5,
        ),
    ),
)

_hex_int = st.builds(
    lambda digits: "0x" + "".join(digits),
    st.lists(st.sampled_from("0123456789abcdefABCDEF"), min_size=1, max_size=16),
)

_oct_int = st.builds(
    lambda digits: "0o" + "".join(digits),
    st.lists(st.sampled_from("01234567"), min_size=1, max_size=16),
)

_bin_int = st.builds(
    lambda digits: "0b" + "".join(digits),
    st.lists(st.sampled_from("01"), min_size=1, max_size=32),
)

_integer_value = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# --- floats ---

_float_digits = st.lists(
    st.sampled_from("0123456789"), min_size=1, max_size=10
).map("".join)

_frac_part = st.builds(lambda d: "." + d, _float_digits)

_exp_part = st.builds(
    lambda sign, d: "e" + sign + d,
    st.sampled_from(["", "+", "-"]),
    _float_digits,
)

_float_value = st.one_of(
    st.builds(
        lambda i, f, e: i + f + e,
        _float_digits,
        _frac_part,
        st.one_of(st.just(""), _exp_part),
    ),
    st.builds(lambda i, e: i + e, _float_digits, _exp_part),
    # parser accepts 1. and .5
    st.builds(lambda d: d + ".", _float_digits),
    st.builds(lambda d: "." + d, _float_digits),
    st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    # extreme exponents
    st.builds(
        lambda d, e: d + "e" + e,
        _float_digits,
        st.sampled_from(["309", "-309", "999", "-999", "308", "307"]),
    ),
)

# --- booleans ---
_bool_value = st.sampled_from(["true", "false"])

# --- date-times ---

_two = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_four = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)

_local_date = st.builds(
    lambda y, m, d: y + "-" + m + "-" + d, _four, _two, _two
)

_partial_time = st.builds(
    lambda h, mi, s: h + ":" + mi + ":" + s, _two, _two, _two
)

_offset = st.one_of(
    st.just("Z"),
    st.builds(lambda s, h, mi: s + h + ":" + mi, st.sampled_from(["+", "-"]), _two, _two),
)

_local_time = _partial_time

_local_date_time = st.builds(
    lambda d, sep, t: d + sep + t,
    _local_date,
    st.sampled_from(["T", "t", " "]),
    _partial_time,
)

_offset_date_time = st.builds(
    lambda d, sep, t, o: d + sep + t + o,
    _local_date,
    st.sampled_from(["T", "t", " "]),
    _partial_time,
    _offset,
)

_datetime_value = st.one_of(
    _offset_date_time, _local_date_time, _local_date, _local_time
)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

# We use st.recursive to build nested structures.  The base cases are the
# scalar values; the recursive cases build arrays and inline tables from
# already-generated values.

_scalar_value = st.one_of(
    _string_value,
    _integer_value,
    _float_value,
    _bool_value,
    _datetime_value,
)

def _make_array(inner):
    """Build a TOML array from a strategy of inner value strings."""
    return st.one_of(
        # empty array
        st.just("[]"),
        # single value, optional trailing comma
        st.builds(
            lambda v, tc: "[" + v + tc + "]",
            inner,
            st.sampled_from(["", ","]),
        ),
        # multiple values with commas, optional trailing comma
        st.builds(
            lambda vals, tc: "[" + ", ".join(vals) + tc + "]",
            st.lists(inner, min_size=2, max_size=5),
            st.sampled_from(["", ","]),
        ),
        # multiline array with comments
        st.builds(
            lambda vals: "[\n" + "\n".join(v + "," for v in vals) + "\n]",
            st.lists(inner, min_size=1, max_size=4),
        ),
    )

def _make_inline_table(inner):
    """Build a TOML inline table from a strategy of value strings."""
    def keyval(v):
        return st.builds(
            lambda k: k + " = " + v,
            _key,
        )
    return st.one_of(
        st.just("{}"),
        st.builds(
            lambda kvs, tc: "{" + ", ".join(kvs) + tc + "}",
            st.lists(keyval(inner), min_size=1, max_size=4),
            st.sampled_from(["", ","]),  # trailing comma accepted by target
        ),
    )

# The recursive strategy: depth up to ~2048 is fine, but we concentrate
# interesting depth in the 1500-2048 band for the deep-nesting edge case.
# We'll use st.recursive with a moderate max_leaves and also generate a few
# very deep arrays separately.

_deep_array = st.integers(min_value=1500, max_value=2048).flatmap(
    lambda depth: st.builds(
        lambda d: "[" * d + "]" * d,
        st.just(depth),
    )
)

_recursive_value = st.recursive(
    _scalar_value,
    lambda children: st.one_of(
        _make_array(children),
        _make_inline_table(children),
    ),
    max_leaves=30,
)

_value = st.one_of(_scalar_value, _recursive_value, _deep_array)

# ---------------------------------------------------------------------------
# Key-value pairs, tables, documents
# ---------------------------------------------------------------------------

_key_value = st.builds(
    lambda k, v: k + " = " + v,
    _key,
    _value,
)

_comment = st.builds(
    lambda body: "#" + body,
    st.lists(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x7E),
            st.integers(min_value=1, max_value=0x08).map(chr),
            st.integers(min_value=0x0B, max_value=0x0C).map(chr),
            st.integers(min_value=0x0E, max_value=0x1F).map(chr),
        ),
        max_size=20,
    ).map("".join),
)

_standard_table = st.builds(
    lambda k: "[" + k + "]",
    _key,
)

_array_table = st.builds(
    lambda k: "[[" + k + "]]",
    _key,
)

# A document is a sequence of lines, each being a key-value, table, or comment.
_document_line = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    _comment,
    st.just(""),  # blank line
)

_document = st.lists(_document_line, min_size=0, max_size=15).map(
    lambda lines: "\n".join(lines)
)

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

# One missing or doubled delimiter, unterminated string, stray token, etc.
_malformed = st.one_of(
    # missing closing bracket in table
    st.builds(lambda k: "[" + k, _unquoted_key),
    # doubled closing bracket
    st.builds(lambda k: "[" + k + "]]", _unquoted_key),
    # missing closing bracket in array
    st.builds(lambda v: "[" + v, _scalar_value),
    # unterminated basic string
    st.builds(lambda b: 'a = "' + b, _basic_string_body),
    # unterminated literal string
    st.builds(lambda b: "a = '" + b, _literal_string_body),
    # stray token
    st.sampled_from(["=", "]", "}", ",", ".", "[[", "]]", "a =", "= 1"]),
    # duplicate keys (accepted by grammar but rejected by parser)
    st.builds(
        lambda k, v1, v2: k + " = " + v1 + "\n" + k + " = " + v2,
        _unquoted_key,
        _scalar_value,
        _scalar_value,
    ),
    # duplicate table
    st.builds(
        lambda k: "[" + k + "]\n[" + k + "]",
        _unquoted_key,
    ),
    # newline inside inline table (rejected by parser)
    st.builds(
        lambda k, v: "{" + k + " = " + v + "\n}",
        _unquoted_key,
        _scalar_value,
    ),
    # non-ASCII bare key (rejected)
    st.builds(
        lambda k: k + " = 1",
        st.lists(
            st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF).filter(
                lambda c: not (0xD800 <= ord(c) <= 0xDFFF)
            ),
            min_size=1,
            max_size=5,
        ).map("".join),
    ),
    # value on next line after =
    st.builds(
        lambda k, v: k + " =\n" + v,
        _unquoted_key,
        _scalar_value,
    ),
    # invalid escape
    st.just('a = "\\q"'),
    # empty quoted key
    st.just('"" = 1'),
)

# ---------------------------------------------------------------------------
# UTF-8 decoding edge cases for toml_utf8_to_ucs
# ---------------------------------------------------------------------------

# Raw UTF-8 byte sequences that exercise multi-byte decoders, including
# overlong encodings, truncated sequences, and 4-byte sequences.  These are
# emitted as raw bytes inside string literals and comments so the parser's
# UTF-8 decoder is invoked on each byte.
_utf8_bytes = st.one_of(
    # valid 2-byte (U+0080..U+07FF)
    st.integers(min_value=0x80, max_value=0x7FF).map(
        lambda cp: chr(cp).encode("utf-8")
    ),
    # valid 3-byte (U+0800..U+FFFF)
    st.integers(min_value=0x800, max_value=0xFFFF).filter(
        lambda cp: not (0xD800 <= cp <= 0xDFFF)
    ).map(
        lambda cp: chr(cp).encode("utf-8")
    ),
    # valid 4-byte (U+10000..U+10FFFF)
    st.integers(min_value=0x10000, max_value=0x10FFFF).map(
        lambda cp: chr(cp).encode("utf-8")
    ),
    # truncated 2-byte sequence: lead byte only
    st.integers(min_value=0xC2, max_value=0xDF).map(lambda b: bytes([b])),
    # truncated 3-byte sequence: lead byte only
    st.integers(min_value=0xE0, max_value=0xEF).map(lambda b: bytes([b])),
    # truncated 3-byte sequence: lead + one continuation
    st.builds(
        lambda lead, cont: bytes([lead, cont]),
        st.integers(min_value=0xE0, max_value=0xEF),
        st.integers(min_value=0x80, max_value=0xBF),
    ),
    # truncated 4-byte sequence: lead byte only
    st.integers(min_value=0xF0, max_value=0xF7).map(lambda b: bytes([b])),
    # truncated 4-byte sequence: lead + one continuation
    st.builds(
        lambda lead, cont: bytes([lead, cont]),
        st.integers(min_value=0xF0, max_value=0xF7),
        st.integers(min_value=0x80, max_value=0xBF),
    ),
    # truncated 4-byte sequence: lead + two continuations
    st.builds(
        lambda lead, c1, c2: bytes([lead, c1, c2]),
        st.integers(min_value=0xF0, max_value=0xF7),
        st.integers(min_value=0x80, max_value=0xBF),
        st.integers(min_value=0x80, max_value=0xBF),
    ),
    # overlong 2-byte encoding of an ASCII code point (C0/C1 lead)
    st.builds(
        lambda lead, cont: bytes([lead, cont]),
        st.sampled_from([0xC0, 0xC1]),
        st.integers(min_value=0x80, max_value=0xBF),
    ),
    # overlong 3-byte encoding of a low code point (E0 80..9F)
    st.builds(
        lambda lead, c1, c2: bytes([lead, c1, c2]),
        st.just(0xE0),
        st.integers(min_value=0x80, max_value=0x9F),
        st.integers(min_value=0x80, max_value=0xBF),
    ),
    # overlong 4-byte encoding of a low code point (F0 80..8F)
    st.builds(
        lambda lead, c1, c2, c3: bytes([lead, c1, c2, c3]),
        st.just(0xF0),
        st.integers(min_value=0x80, max_value=0x8F),
        st.integers(min_value=0x80, max_value=0xBF),
        st.integers(min_value=0x80, max_value=0xBF),
    ),
    # surrogate range encoded as 3-byte (ED A0..BF ..)
    st.builds(
        lambda lead, c1, c2: bytes([lead, c1, c2]),
        st.just(0xED),
        st.integers(min_value=0xA0, max_value=0xBF),
        st.integers(min_value=0x80, max_value=0xBF),
    ),
    # code point above U+10FFFF encoded as 4-byte (F4 90..BF ..)
    st.builds(
        lambda lead, c1, c2, c3: bytes([lead, c1, c2, c3]),
        st.just(0xF4),
        st.integers(min_value=0x90, max_value=0xBF),
        st.integers(min_value=0x80, max_value=0xBF),
        st.integers(min_value=0x80, max_value=0xBF),
    ),
    # lone continuation bytes
    st.integers(min_value=0x80, max_value=0xBF).map(lambda b: bytes([b])),
    # invalid lead bytes (F8..FF)
    st.integers(min_value=0xF8, max_value=0xFF).map(lambda b: bytes([b])),
)

_utf8_raw = st.lists(_utf8_bytes, min_size=1, max_size=6).map(
    lambda parts: b"".join(parts)
)

# Place raw UTF-8 byte sequences inside a basic string value, a literal
# string value, and a comment, so the decoder is invoked on the payload.
_utf8_documents = st.one_of(
    st.builds(
        lambda raw: 'a = "' + raw.decode("latin-1") + '"',
        _utf8_raw,
    ),
    st.builds(
        lambda raw: "a = '" + raw.decode("latin-1") + "'",
        _utf8_raw,
    ),
    st.builds(
        lambda raw: "# " + raw.decode("latin-1"),
        _utf8_raw,
    ),
    st.builds(
        lambda raw: '"""' + raw.decode("latin-1") + '"""',
        _utf8_raw,
    ),
)

# ---------------------------------------------------------------------------
# Final strategy: complete documents plus malformed inputs
# ---------------------------------------------------------------------------

# Also include specific edge-case documents that exercise accepted deviations.
_edge_cases = st.sampled_from([
    # leading zeros
    "a = 007",
    # float with no digit after dot
    "a = 1.",
    # float with no leading digit
    "a = .5",
    # raw control char in string
    'a = "x\x01y"',
    # control char in comment
    "# \x01\n",
    # trailing comma in inline table
    "a = {b = 1,}",
    # calendar-invalid date
    "a = 1979-02-30",
    # deep nesting (moderate for safety in this strategy)
    "a = " + "[" * 100 + "]" * 100,
    # empty containers
    "a = []\nb = {}\n[t]\n[[arr]]",
    # mixed-type array
    "a = [1, 'two', 3.0, true, 1979-05-27]",
    # multiline array with comments
    "a = [\n  1, # one\n  2,\n]",
    # super-table after sub-table
    "[a.b]\nx = 1\n[a]\ny = 2",
    # dotted key
    "a.b.c = 1",
    # quoted keys
    '"a b" = 1\n\'c d\' = 2',
    # empty quoted key
    '"" = 1',
    # hex/oct/bin
    "a = 0xDEADBEEF\nb = 0o755\nc = 0b1010",
    # underscores in numbers
    "a = 1_000_000\nb = 0x_FF",
    # inf/nan
    "a = inf\nb = -inf\nc = nan",
    # large exponent
    "a = 1e309",
    # unicode escapes
    'a = "\\u00E9\\U0001F600"',
    # literal and multiline strings
    "a = 'C:\\Users'\nb = \"\"\"line1\nline2\"\"\"\nc = '''raw'''",
    # CRLF
    "a = 1\r\nb = 2",
    # tab indentation
    "\ta = 1",
    # no trailing newline
    "a = 1",
    # comment-only document
    "# just a comment",
    # empty document
    "",
    # 10000-char key (approximate)
    "k" * 10000 + " = 1",
    # raw UTF-8 multi-byte sequences inside strings/comments to exercise
    # the UTF-8 decoder (toml_utf8_to_ucs)
    'a = "\xc3\xa9\xe2\x82\xac\xf0\x9f\x98\x80"',
    'a = "\xc3"',
    'a = "\xe2\x82"',
    'a = "\xf0\x9f\x98"',
    'a = "\xc0\xaf"',
    'a = "\xe0\x80\xaf"',
    'a = "\xf0\x80\x80\xaf"',
    'a = "\xed\xa0\x80"',
    'a = "\xf4\x90\x80\x80"',
    'a = "\x80"',
    'a = "\xff\xfe"',
    "# \xc3\xa9\xe2\x82\xac",
    "a = '\xc3\xa9'",
])

strategy = st.one_of(
    _document,
    _edge_cases,
    _malformed,
    _utf8_documents,
)
```