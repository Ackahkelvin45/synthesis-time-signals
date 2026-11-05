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

# ---------------- UTF-8 / encoding edge cases ----------------
# Exercise toml_utf8_to_ucs: valid multi-byte sequences, malformed
# continuation bytes, overlong encodings, truncated sequences, and
# lone continuation bytes embedded in strings and keys.

_utf8_valid = st.sampled_from([
    "\u00e9",       # 2-byte
    "\u20ac",       # 3-byte
    "\U0001F600",   # 4-byte
    "\u0080",
    "\u07ff",
    "\u0800",
    "\uffff",
])

# Raw bytes that are invalid UTF-8, expressed as surrogate-escaped
# strings that Python will encode as the raw bytes when written out.
_utf8_invalid = st.sampled_from([
    "\udc80",           # lone continuation byte 0x80
    "\udcc0",           # 0xC0 (overlong lead)
    "\udce0\udc80",     # truncated 3-byte
    "\udcf0\udc80\udc80",  # truncated 4-byte
    "\udcf8",           # 5-byte lead (invalid in UTF-8)
    "\udcfc",           # 6-byte lead (invalid in UTF-8)
    "\udcff",           # 0xFF
    "\udcc3",           # truncated 2-byte lead alone
    "\udce0\udc80\udc80",  # overlong NUL
])

_utf8_any = _utf8_valid | _utf8_invalid

utf8_string = st.lists(_utf8_any, min_size=1, max_size=6).map(
    lambda cs: '"' + "".join(cs) + '"'
)
utf8_literal = st.lists(_utf8_any, min_size=1, max_size=6).map(
    lambda cs: "'" + "".join(cs) + "'"
)
utf8_key = st.lists(_utf8_any, min_size=1, max_size=6).map("".join)

utf8_doc = st.tuples(
    st.sampled_from(["k", "key", "a.b"]),
    utf8_string | utf8_literal,
).map(lambda t: t[0] + " = " + t[1])

utf8_key_doc = st.tuples(utf8_key, st.just("1")).map(lambda t: t[0] + " = " + t[1])

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
    utf8_doc,
    utf8_key_doc,
)

# ---------------- targeted UTF-8 / parser-path coverage ----------------
# The previous run showed toml_utf8_to_ucs at 0% branch coverage. The
# existing _utf8_* values were rarely placed where the parser actually
# decodes them (bare keys, table headers, raw document text). We add
# dedicated strategies that exercise each byte-length branch of the
# decoder, including the length-check failures (len < 1..5) and the
# invalid-continuation-byte paths, plus the 5/6-byte lead branches.

# Valid sequences spanning every decoder length branch.
_utf8_valid_by_len = st.one_of(
    st.sampled_from(["A", "\x7f"]),                    # 1-byte (0xxxxxxx)
    st.sampled_from(["\u0080", "\u07ff", "\u00e9"]),   # 2-byte (110xxxxx)
    st.sampled_from(["\u0800", "\uffff", "\u20ac"]),   # 3-byte (1110xxxx)
    st.sampled_from(["\U00010000", "\U0001F600", "\U0010FFFF"]),  # 4-byte
)

# Truncated sequences (trigger "len < N" early returns).
_utf8_truncated = st.sampled_from([
    "\udcc3",                   # 2-byte lead, 0 continuation bytes
    "\udce0",                   # 3-byte lead, 0 continuation bytes
    "\udce0\udc80",             # 3-byte lead, 1 continuation byte
    "\udcf0",                   # 4-byte lead, 0 continuation bytes
    "\udcf0\udc80",             # 4-byte lead, 1 continuation byte
    "\udcf0\udc80\udc80",       # 4-byte lead, 2 continuation bytes
    "\udcf8",                   # 5-byte lead, 0 continuation bytes
    "\udcf8\udc80",             # 5-byte lead, 1 continuation byte
    "\udcf8\udc80\udc80",       # 5-byte lead, 2 continuation bytes
    "\udcf8\udc80\udc80\udc80", # 5-byte lead, 3 continuation bytes
    "\udcfc",                   # 6-byte lead, 0 continuation bytes
    "\udcfc\udc80",             # 6-byte lead, 1 continuation byte
    "\udcfc\udc80\udc80",       # 6-byte lead, 2 continuation bytes
    "\udcfc\udc80\udc80\udc80", # 6-byte lead, 3 continuation bytes
    "\udcfc\udc80\udc80\udc80\udc80",  # 6-byte lead, 4 continuation bytes
])

# Invalid continuation bytes (trigger "0x2 != (i >> 6)" early returns).
_utf8_bad_cont = st.sampled_from([
    "\udcc3\udc00",             # 2-byte, bad continuation
    "\udcc3\udcc0",             # 2-byte, bad continuation (overlong lead)
    "\udce0\udc00\udc80",       # 3-byte, bad first continuation
    "\udce0\udc80\udc00",       # 3-byte, bad second continuation
    "\udcf0\udc00\udc80\udc80", # 4-byte, bad first continuation
    "\udcf0\udc80\udc00\udc80", # 4-byte, bad second continuation
    "\udcf0\udc80\udc80\udc00", # 4-byte, bad third continuation
    "\udcf8\udc00\udc80\udc80\udc80",
    "\udcfc\udc00\udc80\udc80\udc80\udc80",
])

# 5-byte and 6-byte leads with valid continuations (older UTF-8 decoders
# accept these; the 0x1E / 0x3E branches).
_utf8_wide = st.sampled_from([
    "\udcf8\udc88\udc80\udc80\udc80",       # 5-byte
    "\udcfc\udc84\udc80\udc80\udc80\udc80", # 6-byte
])

_utf8_lead_byte = st.sampled_from([
    "\udc80", "\udcbf", "\udcc0", "\udcc1", "\udcc2",
    "\udcdf", "\udce0", "\udcef", "\udcf0", "\udcf7",
    "\udcf8", "\udcfb", "\udcfc", "\udcfd", "\udcfE", "\udcff",
])

_utf8_payload = st.one_of(
    _utf8_valid_by_len,
    _utf8_truncated,
    _utf8_bad_cont,
    _utf8_wide,
    _utf8_lead_byte,
    _utf8_invalid,
)

# Bare keys are decoded through toml_utf8_to_ucs during key parsing.
utf8_bare_key_doc = st.tuples(
    st.lists(_utf8_payload, min_size=1, max_size=4).map("".join),
    st.one_of(st.just("1"), st.just('"v"')),
).map(lambda t: t[0] + " = " + t[1])

# Table headers also decode keys.
utf8_table_doc = st.tuples(
    st.lists(_utf8_payload, min_size=1, max_size=3).map("".join),
    st.sampled_from(["[]", "[[]]"]),
).map(lambda t: "[" + t[0] + "]" if t[1] == "[]" else "[[" + t[0] + "]]")

# Raw payload embedded directly in the document (bare text).
utf8_raw_doc = st.lists(_utf8_payload, min_size=1, max_size=6).map("".join)

# Strings with the full payload class.
utf8_rich_string = st.lists(_utf8_payload, min_size=1, max_size=6).map(
    lambda cs: '"' + "".join(cs) + '"'
)
utf8_rich_literal = st.lists(_utf8_payload, min_size=1, max_size=6).map(
    lambda cs: "'" + "".join(cs) + "'"
)
utf8_rich_doc = st.tuples(
    st.sampled_from(["k", "key", "a.b"]),
    utf8_rich_string | utf8_rich_literal,
).map(lambda t: t[0] + " = " + t[1])

# ---------------- literal-string norm path ----------------
# norm_lit_str was 0% covered; ensure literal strings with escape-like
# content (backslashes, quotes, control chars) are plentiful.
_lit_tricky_char = st.sampled_from([
    "\\", "\\n", "\\t", "\\", "\"", "\x01", "\x7f", "\u00e9",
])
literal_tricky = st.lists(_lit_tricky_char, min_size=1, max_size=8).map(
    lambda cs: "'" + "".join(cs) + "'"
)
literal_tricky_doc = st.tuples(
    st.sampled_from(["k", "key"]),
    literal_tricky,
).map(lambda t: t[0] + " = " + t[1])

# ---------------- top-level ----------------

strategy = st.one_of(
    base_doc,
    base_doc.flatmap(_mutate),
    st.tuples(st.lists(statement, min_size=1, max_size=4), line_break).map(
        lambda t: t[1].join(t[0])
    ),
    st.tuples(key, edge_value).map(lambda t: t[0] + " = " + t[1]),
    utf8_bare_key_doc,
    utf8_table_doc,
    utf8_raw_doc,
    utf8_rich_doc,
    literal_tricky_doc,
).map(_no_nul)
```