```python
from hypothesis import strategies as st
import json

# ---------------- primitives ----------------

def _no_nul(s):
    return s.replace("\x00", "")

_ascii_alpha = st.characters(min_codepoint=65, max_codepoint=90) | st.characters(min_codepoint=97, max_codepoint=122)
_digit = st.characters(min_codepoint=48, max_codepoint=57)

_unquoted_key_char = st.sampled_from(list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"))

unquoted_key = st.lists(_unquoted_key_char, min_size=1, max_size=12).map("".join)

# escapes valid in basic strings
_hex4 = st.lists(st.sampled_from("0123456789abcdefABCDEF"), min_size=4, max_size=4).map("".join)
_hex8 = st.lists(st.sampled_from("0123456789abcdefABCDEF"), min_size=8, max_size=8).map("".join)

simple_esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
unicode_esc = _hex4.map(lambda h: "\\u" + h)
exunicode_esc = _hex8.map(lambda h: "\\U" + h)
esc = simple_esc | unicode_esc | exunicode_esc

# characters allowed in a basic string body (no raw NUL, no quote/backslash/newline)
_basic_body_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(
    lambda c: c not in '"\\\n' and c != "\x00"
)

basic_string_body = st.lists(_basic_body_char | esc, max_size=8).map("".join)
basic_string = basic_string_body.map(lambda b: '"' + b + '"')

# literal string body: no quote, no newline, no NUL
_literal_body_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(
    lambda c: c not in "'\n" and c != "\x00"
)
literal_string = st.lists(_literal_body_char, max_size=8).map(lambda cs: "'" + "".join(cs) + "'")

# multiline basic string: body may contain quotes/newlines, no raw NUL, no triple-quote ambiguity handled loosely
_ml_basic_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(
    lambda c: c not in "\\" and c != "\x00"
)
ml_basic_esc = simple_esc | unicode_esc | exunicode_esc | st.just("\\\n") | st.just("\\\r\n")
ml_basic_body = st.lists(_ml_basic_char | ml_basic_esc, max_size=8).map("".join)
ml_basic_string = ml_basic_body.map(lambda b: '"""' + b + '"""')

_ml_literal_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(lambda c: c != "\x00")
ml_literal_string = st.lists(_ml_literal_char, max_size=8).map(lambda cs: "'''" + "".join(cs) + "'''")

any_string = basic_string | literal_string | ml_basic_string | ml_literal_string

# ---------------- numbers ----------------

_dec_digit = st.sampled_from("0123456789")
_hex_digit = st.sampled_from("0123456789abcdefABCDEF")
_oct_digit = st.sampled_from("01234567")
_bin_digit = st.sampled_from("01")

def _digits_with_underscores(alphabet, min_len=1, max_len=20):
    return st.lists(alphabet, min_size=min_len, max_size=max_len).map("".join)

dec_int_plain = st.lists(_dec_digit, min_size=1, max_size=20).map("".join)
dec_int_underscore = st.lists(_dec_digit, min_size=1, max_size=10).map(
    lambda ds: "_".join(ds)
)
dec_int = (st.one_of(st.just(""), st.sampled_from(["+", "-"]))).flatmap(
    lambda sign: (dec_int_plain | dec_int_underscore | st.just("0") | st.just("007")).map(
        lambda d: sign + d
    )
)
hex_int = st.lists(_hex_digit, min_size=1, max_size=20).map(lambda ds: "0x" + "".join(ds))
oct_int = st.lists(_oct_digit, min_size=1, max_size=20).map(lambda ds: "0o" + "".join(ds))
bin_int = st.lists(_bin_digit, min_size=1, max_size=20).map(lambda ds: "0b" + "".join(ds))
integer = dec_int | hex_int | oct_int | bin_int

_exp = st.lists(_dec_digit, min_size=1, max_size=5).map("".join)
_frac = st.lists(_dec_digit, min_size=0, max_size=10).map("".join)
_sign = st.sampled_from(["", "+", "-"])

float_simple = st.tuples(dec_int_plain, _frac).map(lambda t: t[0] + "." + t[1])
float_exp = st.tuples(dec_int_plain, _frac, st.sampled_from(["e", "E"]), _sign, _exp).map(
    lambda t: t[0] + ("." + t[1] if t[1] else "") + t[2] + t[3] + t[4]
)
float_leading_dot = _frac.map(lambda f: "." + (f or "0"))
float_trailing_dot = dec_int_plain.map(lambda d: d + ".")
inf = st.sampled_from(["inf", "+inf", "-inf"])
nan = st.sampled_from(["nan", "+nan", "-nan"])
floating_point = float_simple | float_exp | float_leading_dot | float_trailing_dot | inf | nan

bool_ = st.sampled_from(["true", "false"])

# ---------------- date-times ----------------

_year = st.lists(_dec_digit, min_size=4, max_size=4).map("".join)
_month = st.lists(_dec_digit, min_size=2, max_size=2).map("".join)
_day = st.lists(_dec_digit, min_size=2, max_size=2).map("".join)
_hour = st.lists(_dec_digit, min_size=2, max_size=2).map("".join)
_minute = st.lists(_dec_digit, min_size=2, max_size=2).map("".join)
_second = st.lists(_dec_digit, min_size=2, max_size=2).map("".join)
_secfrac = st.lists(_dec_digit, min_size=1, max_size=6).map(lambda ds: "." + "".join(ds))

_full_date = st.tuples(_year, _month, _day).map(lambda t: t[0] + "-" + t[1] + "-" + t[2])
_partial_time = st.tuples(_hour, _minute, _second, st.one_of(st.just(""), _secfrac)).map(
    lambda t: t[0] + ":" + t[1] + ":" + t[2] + t[3]
)
_delim = st.sampled_from(["T", "t", " "])
_offset = st.one_of(
    st.just("Z"),
    st.tuples(st.sampled_from(["+", "-"]), _hour, _minute).map(lambda t: t[0] + t[1] + ":" + t[2]),
)
_full_time = st.tuples(_partial_time, _offset).map(lambda t: t[0] + t[1])

offset_date_time = st.tuples(_full_date, _delim, _full_time).map(lambda t: t[0] + t[1] + t[2])
local_date_time = st.tuples(_full_date, _delim, _partial_time).map(lambda t: t[0] + t[1] + t[2])
local_date = _full_date
local_time = _partial_time
date_time = offset_date_time | local_date_time | local_date | local_time

# ---------------- recursive values ----------------

def _value_expr(children):
    return st.one_of(
        any_string,
        integer,
        floating_point,
        bool_,
        date_time,
        children,
    )

def _make_array(inner):
    # array of values, possibly empty, with newlines/comments, trailing comma
    def arr(vals):
        if not vals:
            return st.just("[]")
        sep = st.sampled_from([", ", ",\n", " ,\n  ", ",\r\n"])
        trailing = st.sampled_from(["", ","])
        return st.tuples(
            st.lists(vals, min_size=1, max_size=4),
            sep,
            trailing,
        ).map(lambda t: "[" + t[1].join(t[0]) + t[2] + "]")
    return arr(inner)

def _make_inline_table(inner):
    def itbl(pairs):
        if not pairs:
            return st.just("{}")
        sep = st.sampled_from([", ", ","])
        trailing = st.sampled_from(["", ","])
        return st.tuples(st.lists(pairs, min_size=1, max_size=3), sep, trailing).map(
            lambda t: "{" + t[1].join(t[0]) + t[2] + "}"
        )
    return itbl(inner)

# key strategies
simple_key = unquoted_key | basic_string | literal_string
dotted_key = st.lists(simple_key, min_size=2, max_size=3).map(lambda ks: ".".join(ks))
key = simple_key | dotted_key

def _kv(inner):
    return st.tuples(key, inner).map(lambda t: t[0] + " = " + t[1])

value = st.recursive(
    _value_expr(st.nothing()),
    lambda children: st.one_of(
        _make_array(children),
        _make_inline_table(_kv(children)),
    ),
    max_leaves=12,
)

# ---------------- statements ----------------

def _comment():
    body = st.lists(
        st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(lambda c: c != "\n" and c != "\x00"),
        max_size=10,
    ).map("".join)
    return body.map(lambda b: "#" + b)

comment = _comment()

key_value_line = st.tuples(key, value, st.one_of(st.just(""), comment.map(lambda c: " " + c))).map(
    lambda t: t[0] + " = " + t[1] + t[2]
)

standard_table = st.tuples(key, st.one_of(st.just(""), comment.map(lambda c: " " + c))).map(
    lambda t: "[" + t[0] + "]" + t[1]
)

array_table = st.tuples(key, st.one_of(st.just(""), comment.map(lambda c: " " + c))).map(
    lambda t: "[[" + t[0] + "]]" + t[1]
)

table = standard_table | array_table

statement = key_value_line | table | comment

line_break = st.sampled_from(["\n", "\r\n"])

def _document():
    return st.tuples(
        st.lists(statement, min_size=0, max_size=6),
        line_break,
        st.sampled_from(["", "\n", "\r\n"]),
    ).map(lambda t: t[1].join(t[0]) + t[2])

document = _document()

# ---------------- malformed / edge-case mutations ----------------

def _mutate(doc):
    return st.sampled_from([
        lambda s: s,
        lambda s: s[:-1] if s else s,                       # drop trailing char
        lambda s: s + "]",                                  # stray delimiter
        lambda s: s.replace("[", "[[", 1),                  # doubled delimiter
        lambda s: s + '\n"unterminated = "abc',             # unterminated string
        lambda s: s + "\nstray = @@@",                      # stray token
        lambda s: s + "\n\x01 = 1",                         # control char bare key
        lambda s: s + "\nkey = ",                           # missing value
        lambda s: s + "\nkey = 1.\nkey = 2",                # duplicate key
        lambda s: s + "\n[dup]\n[dup]",                     # duplicate table
        lambda s: s + "\nkey = {a = 1\n}",                  # newline in inline table
        lambda s: s + "\nkey = \"\\q\"",                    # invalid escape
        lambda s: s + "\nkey = 1979-02-30",                 # calendar-invalid date
        lambda s: s + "\nkey = 1e309",                      # huge exponent
        lambda s: s + "\nkey = 99999999999999999999999999", # beyond 64 bits
    ]).map(lambda f: _no_nul(f(doc)))

# deep nesting band
def _deep_array(depth):
    return "[" * depth + "]" * depth

def _deep_inline(depth):
    s = "{}"
    for _ in range(depth):
        s = "{a = " + s + "}"
    return s

deep_nesting = st.one_of(
    st.integers(min_value=0, max_value=2048).map(_deep_array),
    st.integers(min_value=0, max_value=200).map(_deep_inline),
)

# empty / comment-only documents
empty_doc = st.sampled_from(["", "\n", "\r\n", "# only a comment", "# c\n# d\n"])

# ---------------- top-level strategy ----------------

edge_value = st.one_of(
    st.just('""'),
    st.just("''"),
    st.just('"""x"""'),
    st.just("'''x'''"),
    st.just("[]"),
    st.just("{}"),
    st.just("0"),
    st.just("007"),
    st.just("1."),
    st.just(".5"),
    st.just("1e309"),
    st.just("inf"),
    st.just("nan"),
    st.just("1979-05-27"),
    st.just("07:32:00"),
    st.just("1979-05-27T07:32:00Z"),
    st.just("1979-05-27 07:32:00"),
    st.just('"\\u0000"'),
    st.just('"\\U0001F600"'),
    st.just('"x\x01y"'),
    st.just("true"),
)

base_doc = st.one_of(
    empty_doc,
    document,
    st.tuples(key, st.one_of(value, edge_value)).map(lambda t: t[0] + " = " + t[1]),
    deep_nesting.map(lambda d: "k = " + d),
    st.tuples(unquoted_key, deep_nesting).map(lambda t: t[0] + " = " + t[1]),
)

# Exercise UTF-8 decoding / unicode handling paths (toml_utf8_to_ucs,
# timestamp_at, norm_lit_str) with raw multi-byte and edge unicode.
_utf8_chars = st.sampled_from([
    "é", "ñ", "ü", "ß", "Ω", "Ж", "中", "日", "한", "😀", "🎉", "𝕏",
    "\u0080", "\u07ff", "\u0800", "\uffff", "\U00010000", "\U0010ffff",
])

_utf8_string = st.lists(_utf8_chars, min_size=1, max_size=6).map("".join)

unicode_doc = st.one_of(
    # unicode inside basic and literal strings
    _utf8_string.map(lambda s: 'k = "' + s + '"'),
    _utf8_string.map(lambda s: "k = '" + s + "'"),
    _utf8_string.map(lambda s: 'k = """' + s + '"""'),
    _utf8_string.map(lambda s: "k = '''" + s + "'''"),
    # unicode bare keys
    _utf8_string.map(lambda s: s + " = 1"),
    # unicode comments
    _utf8_string.map(lambda s: "# " + s),
    # unicode in table names
    _utf8_string.map(lambda s: "[" + s + "]"),
    # timestamps with fractional offsets
    st.tuples(
        _full_date,
        st.sampled_from(["T", "t", " "]),
        _partial_time,
        st.sampled_from(["Z", "+00:00", "-05:30", "+23:59"]),
    ).map(lambda t: "ts = " + t[0] + t[1] + t[2] + t[3]),
)

# ---------------- targeted coverage for under-covered functions ----------------

# toml_utf8_to_ucs: exercise raw UTF-8 decoding with bytes that stress the
# decoder — valid multi-byte sequences, truncated sequences, overlong forms,
# and lone continuation bytes embedded in string bodies. These are emitted as
# raw code points and as escaped forms.
_utf8_edge_codepoints = st.sampled_from([
    0x01, 0x7F, 0x80, 0x7FF, 0x800, 0xFFFF, 0x10000, 0x10FFFF,
    0xD7FF, 0xE000, 0xFFFD,
])
_utf8_edge_char = _utf8_edge_codepoints.map(chr)

utf8_decode_doc = st.one_of(
    # raw code points in literal and basic strings (norm_lit_str + utf8_to_ucs)
    st.lists(_utf8_edge_char, min_size=1, max_size=8).map(
        lambda cs: "k = '" + "".join(cs) + "'"
    ),
    st.lists(_utf8_edge_char, min_size=1, max_size=8).map(
        lambda cs: 'k = "' + "".join(cs) + '"'
    ),
    # multi-line literal strings exercise norm_lit_str trimming paths
    st.lists(_utf8_edge_char, min_size=1, max_size=8).map(
        lambda cs: "k = '''" + "".join(cs) + "'''"
    ),
    st.lists(_utf8_edge_char, min_size=1, max_size=8).map(
        lambda cs: 'k = """' + "".join(cs) + '"""'
    ),
    # \u escapes covering boundary code points (utf8_to_ucs escape path)
    _utf8_edge_codepoints.map(lambda cp: 'k = "\\u%04X"' % cp if cp <= 0xFFFF else 'k = "\\U%08X"' % cp),
    # literal strings with leading/trailing newlines stress norm_lit_str trimming
    st.just("k = '''\nfirst\nsecond\n'''"),
    st.just("k = '''\r\nfirst\r\nsecond\r\n'''"),
    st.just("k = '''\n\n\n'''"),
    st.just("k = ''''"),
    st.just("k = ''''''"),
)

# toml_timestamp_at: exercise the timestamp parser with many offset/date
# variants including fractional seconds, lowercase t/z, and boundary values.
_ts_date = st.one_of(
    st.tuples(_year, _month, _day).map(lambda t: t[0] + "-" + t[1] + "-" + t[2]),
    st.sampled_from(["0000-01-01", "9999-12-31", "1970-01-01", "2000-02-29", "2001-02-29"]),
)
_ts_time = st.one_of(
    st.tuples(_hour, _minute, _second, st.one_of(st.just(""), _secfrac)).map(
        lambda t: t[0] + ":" + t[1] + ":" + t[2] + t[3]
    ),
    st.sampled_from(["00:00:00", "23:59:60", "12:00:00.999999", "12:00:00.1"]),
)
_ts_offset = st.sampled_from([
    "Z", "z", "+00:00", "-00:00", "+23:59", "-23:59", "+05:30", "-05:30",
])
_ts_delim = st.sampled_from(["T", "t", " "])

timestamp_doc = st.one_of(
    st.tuples(_ts_date, _ts_delim, _ts_time, _ts_offset).map(
        lambda t: "ts = " + t[0] + t[1] + t[2] + t[3]
    ),
    st.tuples(_ts_date, _ts_delim, _ts_time).map(
        lambda t: "ts = " + t[0] + t[1] + t[2]
    ),
    _ts_date.map(lambda d: "ts = " + d),
    _ts_time.map(lambda t: "ts = " + t),
    st.just("ts = 1979-05-27T07:32:00.999999-07:00"),
    st.just("ts = 1979-05-27t07:32:00z"),
    st.just("ts = 1979-05-27 07:32:00.123+00:00"),
)

# norm_lit_str: literal strings with whitespace/newline edge cases exercise
# the trimming logic (leading newline after opening delimiter, etc.).
norm_lit_doc = st.one_of(
    st.just("k = '''\n'''"),
    st.just("k = '''\r\n'''"),
    st.just("k = '''\nhello'''"),
    st.just("k = '''hello\n'''"),
    st.just("k = '''\n\nhello\n\n'''"),
    st.just("k = '''a\nb\nc'''"),
    st.just("k = '''\r\na\r\nb\r\nc\r\n'''"),
    st.just("k = ''''''"),
    st.just("k = '''''''"),
    st.just("k = '''''''''"),
)

# toml_rtos / toml_rtob / toml_rtoi: exercise the "string to value" runtime
# conversions with many numeric and boolean shapes including overflow edges.
_rtos_int = st.one_of(
    st.just("0"), st.just("-0"), st.just("+0"),
    st.just("9223372036854775807"), st.just("-9223372036854775808"),
    st.just("9223372036854775808"), st.just("-9223372036854775809"),
    st.just("18446744073709551615"), st.just("18446744073709551616"),
    st.just("0xFFFFFFFFFFFFFFFF"), st.just("0x10000000000000000"),
    st.just("0o777777777777777777777"), st.just("0b" + "1" * 64),
    st.just("0b" + "1" * 65),
)
_rtos_float = st.one_of(
    st.just("0.0"), st.just("-0.0"), st.just("+0.0"),
    st.just("1e308"), st.just("1e309"), st.just("-1e309"),
    st.just("1.7976931348623157e308"),
    st.just("1.7976931348623159e308"),
    st.just("2.2250738585072014e-308"),
    st.just("4.9e-324"), st.just("5e-324"),
    st.just("inf"), st.just("-inf"), st.just("nan"), st.just("-nan"),
)
rtos_doc = st.one_of(
    _rtos_int.map(lambda v: "k = " + v),
    _rtos_float.map(lambda v: "k = " + v),
    st.sampled_from(["k = true", "k = false", "k = True", "k = FALSE"]),
)

# toml_parse_file: multi-line documents that exercise the file-level parse
# loop across many statements with comments and blank lines interleaved.
def _parse_file_doc():
    return st.tuples(
        st.lists(
            st.one_of(
                statement,
                st.just(""),
                comment,
            ),
            min_size=1,
            max_size=10,
        ),
        line_break,
        st.sampled_from(["", "\n", "\r\n"]),
    ).map(lambda t: t[1].join(t[0]) + t[2])

parse_file_doc = _parse_file_doc()

strategy = st.one_of(
    base_doc,
    base_doc.flatmap(_mutate),
    st.tuples(st.lists(statement, min_size=1, max_size=4), line_break).map(
        lambda t: t[1].join(t[0])
    ),
    st.tuples(key, edge_value).map(lambda t: t[0] + " = " + t[1]),
    unicode_doc,
    utf8_decode_doc,
    timestamp_doc,
    norm_lit_doc,
    rtos_doc,
    parse_file_doc,
).map(_no_nul)
```