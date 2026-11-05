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

# Structural / grammar-boundary edge cases that exercise parser state transitions:
# headers followed by key-values, array-of-tables sequences, dotted keys with
# quoted segments, mixed line endings, BOM, comments in tricky positions.
_structural_edge = st.sampled_from([
    "[a]\n[b]\nx = 1",
    "[[a]]\n[[a]]\nx = 1",
    "[a.b.c]\nx = 1",
    "[a]\n[a.b]\nx = 1",
    "a.b.c = 1",
    '"a.b" = 1',
    "'a.b' = 1",
    'a."b.c" = 1',
    "[ a . b ]\nx = 1",
    "[a]\r\nx = 1\r\n[b]\r\ny = 2",
    "\ufeffx = 1",
    "# c\n[a] # t\nx = 1 # v\n",
    "x = [ # c\n 1, # d\n 2 ]",
    "x = { a = 1, b = { c = 2 } }",
    "x = [ [ [ 1 ] ] ]",
    "x = \"\"\"\nline1\nline2\n\"\"\"",
    "x = '''\nline1\nline2\n'''",
    "x = \"\"\"a\"b\"\"c\"\"\"",
    "x = \"a\\\n   b\"",
    "x = 0xDEAD_BEEF",
    "x = 0o7_7_7",
    "x = 0b1_0_1",
    "x = +1_000",
    "x = -0.0",
    "x = 1e-0",
    "x = 1979-05-27T00:32:00.999999-07:00",
    "x = 1979-05-27t07:32:00z",
    "x = 1979-05-27T07:32:00.5+00:00",
    "x = 00:00:00",
    "x = 1979-05-27",
    "x = 1 # trailing\r\n",
    "= 1",
    "[]",
    "[[]]",
    "x = ",
    "x = [,]",
    "x = {,}",
    "x = {a = 1,}",
    "x = [1,]",
    "x = [1,,2]",
    "x = \"\\uD800\"",
    "x = \"\\U00110000\"",
    "x = \"\\u12\"",
    "x=\t1",
    "x\t=\t1",
    "\tx = 1",
    "x = 1\x01",
    "x = true\nx = false",
    "x = 1979-13-45",
    "x = 25:99:99",
    "x = nan\nx = inf",
    "x = -inf",
    "x = 0x",
    "x = 0o",
    "x = 0b",
    "x = +",
    "x = .",
    "x = e5",
])

base_doc = st.one_of(
    empty_doc,
    document,
    st.tuples(key, st.one_of(value, edge_value)).map(lambda t: t[0] + " = " + t[1]),
    deep_nesting.map(lambda d: "k = " + d),
    st.tuples(unquoted_key, deep_nesting).map(lambda t: t[0] + " = " + t[1]),
    _structural_edge,
)

# A realistic multi-line document combining headers, key-values, and
# array-of-tables blocks, so the fuzzer exercises parser state across
# table transitions rather than only isolated statements.
def _table_block():
    header = st.tuples(
        st.sampled_from(["[", "[["]),
        key,
        st.sampled_from(["]", "]]"]),
    ).map(lambda t: t[0] + t[1] + t[2])
    body = st.lists(key_value_line, min_size=0, max_size=3)
    return st.tuples(header, body).map(lambda t: t[0] + "\n" + "\n".join(t[1]))

structured_doc = st.lists(
    st.one_of(_table_block(), key_value_line, comment),
    min_size=1, max_size=5,
).map(lambda parts: "\n".join(parts) + "\n")

# IMPROVED: a token-level mutator that operates on the generated TOML text to
# produce near-valid inputs. Byte-level mutations of a valid document exercise
# the parser's error recovery and boundary handling much more effectively than
# purely random structural generation, because a single corrupted character
# often lands right at a token boundary the parser cares about.
def _token_mutate(s):
    ops = [
        lambda t: t,
        lambda t: t[: len(t) // 2] + t[len(t) // 2 + 1:] if len(t) > 1 else t,  # drop a char
        lambda t: t + t[-1:] if t else t,                                        # duplicate last char
        lambda t: t[::-1],                                                       # reverse
        lambda t: t.replace("=", "", 1),                                         # drop a '='
        lambda t: t.replace("=", "==", 1),                                       # double '='
        lambda t: t.replace(".", "", 1),                                         # drop a '.'
        lambda t: t.replace("\n", "", 1),                                        # join lines
        lambda t: t.replace("[", "]", 1),                                        # swap bracket
        lambda t: t.replace("]", "[", 1),                                        # swap bracket
        lambda t: t.replace('"', "", 1),                                         # drop a quote
        lambda t: t.replace("'", "", 1),                                         # drop a quote
        lambda t: t.replace(",", "", 1),                                         # drop a comma
        lambda t: t.replace(" ", "\t", 1),                                       # space->tab
        lambda t: t.replace("\n", "\r\n", 1),                                    # CRLF
        lambda t: t.replace("0x", "0X", 1),                                      # case flip
        lambda t: t.replace("true", "True", 1),                                  # case flip
        lambda t: t + "\n",                                                      # trailing newline
        lambda t: "\n" + t,                                                      # leading newline
        lambda t: t + "\n[",                                                     # unterminated header
        lambda t: t + "\n[[",                                                    # unterminated array header
        lambda t: t + "\nx =",                                                   # missing value
        lambda t: t + "\nx = \"",                                                # unterminated string
        lambda t: t + "\nx = [",                                                 # unterminated array
        lambda t: t + "\nx = {",                                                 # unterminated inline
        lambda t: t + "\nx = 1.",                                                # trailing dot
        lambda t: t + "\nx = .1",                                                # leading dot
        lambda t: t + "\nx = 0x",                                                # empty hex
        lambda t: t + "\nx = 0b",                                                # empty bin
        lambda t: t + "\nx = 0o",                                                # empty oct
        lambda t: t + "\nx = 1_",                                                # trailing underscore
        lambda t: t + "\nx = _1",                                                # leading underscore
        lambda t: t + "\nx = 1__2",                                              # double underscore
        lambda t: t + "\nx = 1979-05-27T",                                       # truncated datetime
        lambda t: t + "\nx = 1979-05-27T07:32:00.",                              # truncated secfrac
        lambda t: t + "\nx = 1979-05-27T07:32:00+",                              # truncated offset
        lambda t: t + "\nx = \"\\",                                              # truncated escape
        lambda t: t + "\nx = \"\\u",                                             # truncated unicode esc
        lambda t: t + "\nx = \"\\uD",                                            # truncated surrogate
    ]
    return st.sampled_from(ops).map(lambda f: _no_nul(f(s)))

# IMPROVED: line-level mutation that targets the boundaries between statements,
# which is where most parser state bugs live (table context switching, key
# path resolution, duplicate detection).
def _line_mutate(s):
    lines = s.split("\n")
    ops = [
        lambda ls: ls,
        lambda ls: ls[:-1] if ls else ls,                       # drop last line
        lambda ls: ls[1:] if ls else ls,                        # drop first line
        lambda ls: ls + ls[-1:] if ls else ls,                  # duplicate last line
        lambda ls: ls[:1] + ls + ls[:1] if ls else ls,          # wrap with first line
        lambda ls: [ln for ln in ls if ln] if ls else ls,       # drop blank lines
        lambda ls: ls + [""] if ls else ls,                     # trailing blank
        lambda ls: [""] + ls if ls else ls,                     # leading blank
        lambda ls: [ln.replace("[", "[[", 1) for ln in ls],     # convert std->array tables
        lambda ls: [ln.replace("[[", "[", 1) for ln in ls],     # convert array->std tables
        lambda ls: [ln + " # c" for ln in ls],                  # append comments
        lambda ls: [ln + "," for ln in ls],                     # append stray commas
        lambda ls: [ln + "]" for ln in ls],                     # append stray brackets
        lambda ls: [ln.replace("=", "=", 1) for ln in ls],      # no-op (keeps valid)
        lambda ls: [ln.replace(" ", "", 1) for ln in ls],       # strip a space
        lambda ls: [ln.replace("\r", "", 1) for ln in ls],      # strip CR
        lambda ls: [ln + "\r" for ln in ls],                    # add CR
        lambda ls: [ln.replace("=", " = ", 1) for ln in ls],    # normalize spaces
    ]
    return st.sampled_from(ops).map(lambda f: _no_nul("\n".join(f(lines))))

def _mutator(s):
    return st.one_of(_token_mutate(s), _line_mutate(s))

strategy = st.one_of(
    base_doc,
    base_doc.flatmap(_mutate),
    base_doc.flatmap(_mutator),
    st.tuples(st.lists(statement, min_size=1, max_size=4), line_break).map(
        lambda t: t[1].join(t[0])
    ),
    st.tuples(key, edge_value).map(lambda t: t[0] + " = " + t[1]),
    structured_doc,
    structured_doc.flatmap(_mutator),
).map(_no_nul)