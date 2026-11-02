```python
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Small helpers (all return str via .map on tuples)
# ---------------------------------------------------------------------------

def _join(sep):
    return lambda parts: sep.join(parts)


def _concat(parts):
    return "".join(parts)


# Characters safe in bare keys / general text.
_BARE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

_bare_key = st.text(alphabet=_BARE_CHARS, min_size=1, max_size=12)

# Non-ASCII text and control-ish content (never raw NUL).
_text_chars = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    st.characters(min_codepoint=0xA0, max_codepoint=0x2FFF),
    st.sampled_from(["\t", "\x01", "\x1f", "\x7f", "\r"]),
)

# ---------------------------------------------------------------------------
# Strings: all four quoting forms, with escapes
# ---------------------------------------------------------------------------

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\u%04X" % (n & 0xFFFF)
    ),
    st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\U%08X" % n
    ),
)

# content for basic strings: text chars or escapes, but not raw quote/backslash/newline
_basic_body = st.one_of(
    st.text(alphabet=_text_chars, max_size=10),
    _escapes,
)

_basic_string = st.lists(_basic_body, max_size=6).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# literal string: no single quote, no newline
_literal_body = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
        lambda c: c not in "'"
    ),
    max_size=10,
)
_literal_string = _literal_body.map(lambda s: "'" + s + "'")

# multiline basic: """ ... """ ; body may include newlines and escapes
_ml_basic_body = st.one_of(
    st.text(alphabet=_text_chars, max_size=12),
    _escapes,
    st.sampled_from(["\n", "\r\n", '\\\n', '\\\r\n']),
)
_ml_basic_string = st.lists(_ml_basic_body, max_size=6).map(
    lambda parts: '"""' + "".join(parts) + '"""'
)

# multiline literal: ''' ... ''' ; anything except the terminator
_ml_literal_body = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    max_size=12,
)
_ml_literal_string = _ml_literal_body.map(lambda s: "'''" + s + "'''")

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
    st.just('""'),
    st.just("''"),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_digits = st.text("0123456789", min_size=1, max_size=20)

_dec_int = st.one_of(
    _digits,
    _digits.map(lambda d: "0" + d),  # leading zeros (accepted deviation)
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.sampled_from(["0", "+0", "-0", "007", "1_000", "9" * 40]),
)

_hex_int = st.text("0123456789abcdefABCDEF", min_size=1, max_size=16).map(
    lambda s: "0x" + s
)
_oct_int = st.text("01234567", min_size=1, max_size=16).map(lambda s: "0o" + s)
_bin_int = st.text("01", min_size=1, max_size=16).map(lambda s: "0b" + s)

_integer = st.one_of(
    _dec_int,
    _hex_int,
    _oct_int,
    _bin_int,
    st.sampled_from(["0x_1", "0o7", "0b0", "1_2_3", "-0x1F"]),
)

_exp = st.integers(min_value=-400, max_value=400).map(lambda n: "e%d" % n)
_frac = st.text("0123456789", min_size=1, max_size=8).map(lambda s: "." + s)

_float = st.one_of(
    st.builds(lambda i, e: i + e, _digits, _exp),
    st.builds(lambda i, f: i + f, _digits, _frac),
    st.builds(lambda i, f, e: i + f + e, _digits, _frac, _exp),
    st.sampled_from(["1.", ".5", "-1.", "+.5", "1e309", "1e-400", "0.0"]),
    st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
)

# ---------------------------------------------------------------------------
# Booleans and date-times
# ---------------------------------------------------------------------------

_bool = st.sampled_from(["true", "false"])

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_day = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_hour = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_minute = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_second = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

_frac_sec = st.text("0123456789", min_size=1, max_size=6).map(lambda s: "." + s)

_full_date = st.tuples(_year, _month, _day).map(lambda t: "-".join(t))
_partial_time = st.tuples(_hour, _minute, _second).map(lambda t: ":".join(t))
_partial_time_frac = st.tuples(_partial_time, _frac_sec).map(_concat)
_offset = st.one_of(
    st.just("Z"),
    st.tuples(st.sampled_from(["+", "-"]), _hour, _minute).map(
        lambda t: t[0] + t[1] + ":" + t[2]
    ),
)

_local_date = _full_date
_local_time = st.one_of(_partial_time, _partial_time_frac)
_local_date_time = st.tuples(_full_date, st.sampled_from(["T", "t", " "]), _local_time).map(_concat)
_offset_date_time = st.tuples(
    _full_date, st.sampled_from(["T", "t", " "]), _partial_time, _offset
).map(_concat)

_date_time = st.one_of(
    _local_date,
    _local_time,
    _local_date_time,
    _offset_date_time,
    st.sampled_from(["1979-02-30", "1979-05-27 07:32:00Z", "0000-00-00"]),
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_quoted_key = st.one_of(_basic_string, _literal_string, st.just('""'))

_simple_key = st.one_of(_bare_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(
    lambda parts: ".".join(parts)
)

_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _extend(base):
    # base: strategy of leaf value strings
    return st.recursive(
        base,
        lambda children: st.one_of(
            _array_of(children),
            _inline_table_of(children),
        ),
        max_leaves=20,
    )


def _array_of(child):
    return st.lists(child, max_size=5).map(
        lambda items: "[" + ", ".join(items) + "]"
    )


def _inline_table_of(child):
    def kv(pair):
        k, v = pair
        return k + " = " + v

    pair = st.tuples(_simple_key, child)
    return st.lists(pair, max_size=4).map(
        lambda pairs: "{" + ", ".join(kv(p) for p in pairs) + "}"
    )


_leaf_value = st.one_of(
    _string,
    _integer,
    _float,
    _bool,
    _date_time,
)

_value = _extend(_leaf_value)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def _comment():
    return st.text(
        alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
        max_size=20,
    ).map(lambda s: "#" + s)


_key_value_line = st.tuples(_key, _value).map(lambda t: t[0] + " = " + t[1])

_standard_table = st.tuples(_key).map(lambda t: "[" + t[0] + "]")
_array_table = st.tuples(_key).map(lambda t: "[[" + t[0] + "]]")

_header = st.one_of(_standard_table, _array_table)

_line = st.one_of(
    _key_value_line,
    _header,
    _comment(),
)

_document = st.lists(_line, max_size=8).map(lambda lines: "\n".join(lines))

# ---------------------------------------------------------------------------
# Malformed near-valid inputs
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    # missing / doubled delimiters
    st.just("a = [1, 2"),
    st.just("a = [1, 2]]"),
    st.just("a = {b = 1"),
    st.just("a = {b = 1}}"),
    st.just("[table"),
    st.just("[[table]"),
    st.just("a = 1\n[dup]\n[dup]"),
    st.just("a = 1\na = 2"),
    # unterminated strings
    st.just('a = "unterminated'),
    st.just("a = 'unterminated"),
    st.just('a = """unterminated'),
    st.just("a = '''unterminated"),
    # stray tokens / bad escapes
    st.just("a = \\q"),
    st.just("a = 1 2"),
    st.just("= 1"),
    st.just("a ="),
    st.just("a\n= 1"),
    st.just("a = {b = 1\n}"),
    st.just("a = {b = 1,}"),
    st.just("\u00e9 = 1"),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just('a = "x\x01y"'),
    st.just("# comment with \x01 control"),
    st.just("a = 1979-02-30"),
)

# ---------------------------------------------------------------------------
# Deep nesting band (~1500-2048) for arrays and inline tables
# ---------------------------------------------------------------------------

_depth = st.integers(min_value=1500, max_value=2048)

_deep_array = _depth.map(lambda n: "a = " + "[" * n + "]" * n)
_deep_inline = _depth.map(lambda n: "a = " + "{b = " * n + "1" + "}" * n)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _malformed,
    _deep_array,
    _deep_inline,
    st.just(""),
    st.just("# comment only"),
    st.just("[t]"),
    st.just("[[a]]"),
    st.just("a = []"),
    st.just("a = {}"),
    st.just('"" = 1'),
    st.just("a = 1"),  # no trailing newline
    # nested arrays / inline tables as values (exercise recursion in parser)
    st.just("a = [[1, 2], [3, [4]]]"),
    st.just("a = {b = {c = {d = 1}}}"),
    st.just("a = [{b = [1, {c = 2}]}]"),
    # array tables with sub-tables
    st.just("[[a]]\n[a.b]\n[[a]]\n[a.b]"),
    st.just("[a.b.c]\n[a]\n[a.b]"),
    # whitespace / CRLF variations
    st.just("a=1"),
    st.just("a\t=\t1"),
    st.just("a = 1\r\nb = 2\r\n"),
    st.just("  a  =  1  \n  [ t ]  \n"),
)
```