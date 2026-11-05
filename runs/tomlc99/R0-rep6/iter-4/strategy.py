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

# A small "well-formed corpus" generator: realistic multi-statement TOML documents
# that combine tables, array tables, key-values with nested values, and comments.
# This improves coverage of the grammar's structural interactions.
_well_formed_corpus = st.tuples(
    st.lists(
        st.one_of(
            key_value_line,
            standard_table,
            array_table,
            comment,
        ),
        min_size=1,
        max_size=8,
    ),
    line_break,
).map(lambda t: t[1].join(t[0]))

# IMPROVEMENT: a structured "coherent" document generator that builds a
# realistic TOML document with ordered tables/array-tables and key-values,
# plus optional interleaved comments and blank lines. This targets the parser's
# table-state machine (current table, array-of-tables, dotted keys) more
# aggressively than the flat corpus above, while still emitting valid TOML.
def _coherent_doc():
    def render(parts):
        out = []
        for kind, text in parts:
            if kind == "blank":
                out.append("")
            else:
                out.append(text)
        return "\n".join(out) + "\n"

    def section(header, body):
        lines = [(header, header)]
        if body:
            lines.extend(("line", b) for b in body)
        return lines

    return st.tuples(
        st.lists(
            st.one_of(
                # top-level key-values before any table
                st.tuples(
                    st.lists(key_value_line, min_size=0, max_size=3),
                ).map(lambda t: [("line", x) for x in t[0]]),
                # a standard table with a few key-values
                st.tuples(
                    standard_table,
                    st.lists(key_value_line, min_size=0, max_size=4),
                ).map(lambda t: section(t[0], t[1])),
                # an array table with a few key-values
                st.tuples(
                    array_table,
                    st.lists(key_value_line, min_size=0, max_size=4),
                ).map(lambda t: section(t[0], t[1])),
                # a stray comment / blank line
                st.one_of(
                    comment.map(lambda c: [("line", c)]),
                    st.just([("blank", "")]),
                ),
            ),
            min_size=1,
            max_size=6,
        ),
    ).map(lambda t: render([p for chunk in t[0] for p in chunk]))

coherent_doc = _coherent_doc()

# IMPROVEMENT: a "table-state-machine" generator that specifically exercises
# ordering constraints and conflicts the parser must detect: redefining tables,
# appending to arrays-of-tables, dotted-key/table conflicts, and interleaving
# of `[table]`, `[[array]]`, and key-values under the "current" table.
def _table_state_doc():
    def render(items):
        return "\n".join(items) + "\n"

    def build(ops):
        lines = []
        for op in ops:
            kind = op[0]
            if kind == "kv":
                lines.append(op[1])
            elif kind == "tbl":
                lines.append(op[1])
            elif kind == "atbl":
                lines.append(op[1])
            elif kind == "blank":
                lines.append("")
            elif kind == "comment":
                lines.append(op[1])
        return render(lines)

    # A small fixed pool of header names so that collisions/redefinitions happen.
    name_pool = st.sampled_from(["a", "b", "c", "a.b", "a.c", "x", "x.y"])
    header = name_pool.map(lambda n: "[" + n + "]")
    arr_header = name_pool.map(lambda n: "[[" + n + "]]")
    kv_under = st.tuples(
        st.sampled_from(["k", "v", "a", "b", "x"]),
        st.one_of(
            st.just("1"),
            st.just('"s"'),
            st.just("true"),
            st.just("[1, 2]"),
            st.just("{p = 1}"),
        ),
    ).map(lambda t: t[0] + " = " + t[1])

    op = st.one_of(
        kv_under.map(lambda s: ("kv", s)),
        header.map(lambda s: ("tbl", s)),
        arr_header.map(lambda s: ("atbl", s)),
        st.just(("blank", "")),
        comment.map(lambda c: ("comment", c)),
    )

    return st.lists(op, min_size=1, max_size=10).map(build)

table_state_doc = _table_state_doc()

strategy = st.one_of(
    base_doc,
    base_doc.flatmap(_mutate),
    st.tuples(st.lists(statement, min_size=1, max_size=4), line_break).map(
        lambda t: t[1].join(t[0])
    ),
    st.tuples(key, edge_value).map(lambda t: t[0] + " = " + t[1]),
    _well_formed_corpus,
    coherent_doc,
    table_state_doc,
).map(_no_nul)