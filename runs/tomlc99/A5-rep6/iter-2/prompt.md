Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

# Bare-key characters allowed by the parser: A-Za-z0-9_- (ASCII only).
_bare_key_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)
_bare_key = st.text(_bare_key_char, min_size=1, max_size=12)

# Non-ASCII / weird bare keys (parser REJECTS these) -- used for malformed docs.
_weird_bare_key = st.text(
    st.characters(min_codepoint=0x80, max_codepoint=0x2FF), min_size=1, max_size=6
)

# Escape sequences for basic strings.
_simple_escapes = st.sampled_from(["\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"])
_unicode_escape = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda cp: "\\u%04X" % cp if cp <= 0xFFFF else "\\U%08X" % cp
)
_basic_escape = st.one_of(_simple_escapes, _unicode_escape)

# Characters safe inside basic strings (no raw '"', '\\', or newline; NUL ok as escape).
_basic_body_char = st.one_of(
    st.characters(min_codepoint=0x01, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FF),
    st.sampled_from(["\x01", "\x07", "\x0b", "\x1f"]),
)

_basic_body = st.one_of(_basic_body_char, _basic_escape)

# ---------------------------------------------------------------------------
# Strings of all four quoting forms
# ---------------------------------------------------------------------------

_basic_string = st.lists(_basic_body, max_size=16).map(lambda cs: '"' + "".join(cs) + '"')

_literal_body_char = st.one_of(
    st.characters(min_codepoint=0x01, max_codepoint=0x7E, blacklist_characters="'"),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FF),
    st.sampled_from(["\x01", "\x07", "\x0b", "\x1f"]),
)
_literal_string = st.lists(_literal_body_char, max_size=16).map(
    lambda cs: "'" + "".join(cs) + "'"
)

# Multiline strings: allow newlines but avoid the closing triple quote.
_ml_basic_body_char = st.one_of(
    st.characters(min_codepoint=0x01, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FF),
    st.sampled_from(["\n", "\r\n", "\t", "\x01", "\x1f"]),
    _basic_escape,
)
_ml_basic_string = st.lists(_ml_basic_body_char, max_size=12).map(
    lambda cs: '"""' + "".join(cs) + '"""'
)

_ml_literal_body_char = st.one_of(
    st.characters(min_codepoint=0x01, max_codepoint=0x7E, blacklist_characters="'"),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FF),
    st.sampled_from(["\n", "\r\n", "\t", "\x01", "\x1f"]),
)
_ml_literal_string = st.lists(_ml_literal_body_char, max_size=12).map(
    lambda cs: "'''" + "".join(cs) + "'''"
)

_string = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_int = st.one_of(
    st.integers(min_value=-10**25, max_value=10**25).map(str),
    st.integers(min_value=-(2**63), max_value=2**63 - 1).map(str),
    st.sampled_from(["0", "+0", "-0", "007", "000123", "1_000", "1_2_3", "9" * 40]),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0x%x" % n),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF"]),
)
_oct_int = st.one_of(
    st.integers(min_value=0, max_value=2**40).map(lambda n: "0o%o" % n),
    st.sampled_from(["0o0", "0o777", "0o1_2_3"]),
)
_bin_int = st.one_of(
    st.integers(min_value=0, max_value=2**40).map(lambda n: "0b" + format(n, "b")),
    st.sampled_from(["0b0", "0b1", "0b1010_0101"]),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(
        [
            "1.0",
            "-0.0",
            "+0.0",
            "1e10",
            "1E-10",
            "1e+309",
            "1e-309",
            "1_0.0_1e1_0",
            "1.",
            ".5",
            "-.5",
            "+1.",
            "3.141592653589793",
        ]
    ),
)
_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
_floating = st.one_of(_float, _inf_nan)

_bool = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Date-times (all four forms; parser accepts calendar-invalid dates)
# ---------------------------------------------------------------------------

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_day = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_hh = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_mm = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_ss = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_secfrac = st.integers(min_value=0, max_value=10**9).map(lambda n: ".%09d" % n)

_full_date = st.tuples(_year, _month, _day).map(lambda t: "%s-%s-%s" % t)
_partial_time = st.tuples(_hh, _mm, _ss, st.one_of(st.just(""), _secfrac)).map(
    lambda t: "%s:%s:%s%s" % t
)
_offset = st.one_of(
    st.just("Z"),
    st.tuples(st.sampled_from(["+", "-"]), _hh, _mm).map(
        lambda t: "%s%s:%s" % t
    ),
)
_sep = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(_full_date, _sep, _partial_time, _offset).map(
    lambda t: "%s%s%s%s" % t
)
_local_date_time = st.tuples(_full_date, _sep, _partial_time).map(
    lambda t: "%s%s%s" % t
)
_local_date = _full_date
_local_time = _partial_time

_date_time = st.one_of(
    _offset_date_time, _local_date_time, _local_date, _local_time
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_quoted_key = st.one_of(_basic_string, _literal_string)
_simple_key = st.one_of(_bare_key, _quoted_key, st.just('""'))
_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(".".join)
_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _join_comma(parts):
    return ", ".join(parts)

_scalar_value = st.one_of(
    _string, _integer, _floating, _bool, _date_time
)

# array / inline_table defined via st.recursive below.
def _make_value(children):
    array = st.lists(children, max_size=4).map(
        lambda xs: "[" + ", ".join(xs) + "]"
    )
    array_multiline = st.lists(children, max_size=3).map(
        lambda xs: "[\n" + ",\n".join(xs) + ",\n]" if xs else "[]"
    )
    inline = st.lists(
        st.tuples(_key, children).map(lambda t: "%s = %s" % t),
        max_size=3,
    ).map(lambda xs: "{" + ", ".join(xs) + "}")
    inline_trailing = st.lists(
        st.tuples(_key, children).map(lambda t: "%s = %s" % t),
        min_size=1,
        max_size=3,
    ).map(lambda xs: "{" + ", ".join(xs) + ",}")
    return st.one_of(array, array_multiline, inline, inline_trailing)

_value = st.recursive(_scalar_value, _make_value, max_leaves=12)

# Deep nesting: depth concentrated in the parser's steer band (1500-2048).
_deep_array = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "[" * n + "1" + "]" * n
)
_deep_inline = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "{a = " * n + "1" + "}" * n
)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

_key_value = st.tuples(_key, _value).map(lambda t: "%s = %s" % t)

_comment = st.one_of(
    st.just("#"),
    st.text(
        st.one_of(
            st.characters(min_codepoint=0x01, max_codepoint=0x7E, blacklist_characters="\n"),
            st.characters(min_codepoint=0x80, max_codepoint=0x2FF),
            st.sampled_from(["\t", "\x01", "\x1f"]),
        ),
        max_size=30,
    ).map(lambda s: "#" + s),
)

_table = _key.map(lambda k: "[%s]" % k)
_array_table = _key.map(lambda k: "[[%s]]" % k)

_line = st.one_of(_key_value, _table, _array_table, _comment)

_document = st.one_of(
    st.lists(_line, min_size=0, max_size=8).map(lambda ls: "\n".join(ls)),
    st.lists(_line, min_size=1, max_size=6).map(lambda ls: "\r\n".join(ls)),
    _deep_array,
    _deep_inline,
    st.just(""),
)

# ---------------------------------------------------------------------------
# Near-valid-but-malformed inputs (one missing/doubled delimiter, unterminated
# string, stray token, duplicate key, newline in inline table, bad escape,
# non-ASCII bare key, value on next line).
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    # missing closing delimiter
    st.just('a = "unterminated'),
    st.just("a = 'unterminated"),
    st.just('a = """unterminated'),
    st.just("a = '''unterminated"),
    st.just("a = [1, 2, 3"),
    st.just("a = {b = 1"),
    st.just("[table"),
    st.just("[[array_table"),
    st.just("a = {b = 1, c = 2"),
    # doubled delimiter
    st.just("a = [1, 2, 3]]"),
    st.just("a = {b = 1}}"),
    st.just("a = ]]"),
    st.just("a = }}"),
    st.just("[t]]"),
    # stray token
    st.just("a ="),
    st.just("= 1"),
    st.just("a = = 1"),
    st.just("a 1"),
    st.just("a = 1 2"),
    st.just("a = @invalid"),
    st.just("a = $"),
    st.just("a = 1.2.3"),
    st.just("a = 0x"),
    st.just("a = 0b"),
    st.just("a = 0o"),
    st.just("a = 0xZZ"),
    # invalid escape
    st.just('a = "bad \\q escape"'),
    st.just('a = "\\x41"'),
    # duplicate keys / tables
    st.just("a = 1\na = 2"),
    st.just("[t]\n[t]"),
    st.just("[[a]]\n[a]"),
    st.just("a.b = 1\n[a.b]"),
    # newline inside inline table (REJECTED)
    st.just("a = {b = 1,\nc = 2}"),
    st.just("a = {\nb = 1}"),
    # value on next line
    st.just("a =\n1"),
    # non-ASCII bare key (REJECTED)
    st.tuples(_weird_bare_key, _value).map(lambda t: "%s = %s" % t),
    # bare key outside allowed chars
    st.just("missing = 1"),
    # empty-ish / odd
    st.just("="),
    st.just("[]"),
    st.just("[[]]"),
    st.just("a = ,"),
    st.just("a = [1,,2]"),
)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _malformed,
    # a few explicit edge-case documents
    st.just(""),
    st.just("# only a comment"),
    st.just("# comment with control byte \x01"),
    st.just('a = "\\u0000"'),
    st.just('a = "x\x01y"'),
    st.just("a = 1979-02-30"),
    st.just("a = 1979-05-27 07:32:00Z"),
    st.just("a = {b = 1,}"),
    st.just("a = [1, 2, 3,]"),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just("a = 1e309"),
    st.just("a = 1_000"),
    st.just("a = inf"),
    st.just("a = -nan"),
    st.just('"" = 1'),
    st.just("a = {}"),
    st.just("a = []"),
    st.just("[t]"),
    st.just("[[a]]"),
)
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.