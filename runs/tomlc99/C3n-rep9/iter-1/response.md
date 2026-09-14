```python
from hypothesis import strategies as st
import json

# ---------- basic character classes ----------

# Printable ASCII minus the chars that would break the token we're inside.
_basic_escape_chars = '\\"/bfnrt'

def _unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda cp: "\\u%04X" % cp if cp <= 0xFFFF else "\\U%08X" % cp
    )

def _escape():
    return st.one_of(
        st.sampled_from(list(_basic_escape_chars)).map(lambda c: "\\" + c),
        _unicode_escape(),
    )

# A char safe inside a basic string: anything except `"`, `\`, and newline.
def _basic_string_char():
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                      blacklist_characters='\\"\n\r'),
        # raw control bytes (parser accepts them in strings)
        st.integers(min_value=0, max_value=0x1F).map(chr).filter(
            lambda c: c != '\x00'  # never emit NUL
        ),
        st.just('\t'),
    )

def basic_string():
    return st.one_of(
        st.just('""'),
        st.lists(
            st.one_of(_basic_string_char(), _escape()),
            min_size=1, max_size=12,
        ).map(lambda parts: '"' + "".join(parts) + '"'),
    )

def literal_string():
    return st.one_of(
        st.just("''"),
        st.lists(
            st.one_of(
                st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                              blacklist_characters="'\n\r"),
                st.integers(min_value=0, max_value=0x1F).map(chr).filter(
                    lambda c: c != '\x00'
                ),
                st.just('\t'),
            ),
            min_size=1, max_size=12,
        ).map(lambda parts: "'" + "".join(parts) + "'"),
    )

def ml_basic_string():
    body = st.lists(
        st.one_of(
            _basic_string_char(),
            _escape(),
            st.just('\n'),
            st.just('\\\n'),   # line-ending backslash
        ),
        min_size=0, max_size=16,
    ).map(lambda parts: "".join(parts))
    return body.map(lambda s: '"""' + s + '"""')

def ml_literal_string():
    body = st.lists(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                          blacklist_characters="'"),
            st.integers(min_value=0, max_value=0x1F).map(chr).filter(
                lambda c: c != '\x00'
            ),
            st.just('\t'),
            st.just('\n'),
        ),
        min_size=0, max_size=16,
    ).map(lambda parts: "".join(parts))
    # avoid accidental triple-quote termination issues by not emitting '''
    return body.filter(lambda s: "'''" not in s).map(lambda s: "'''" + s + "'''")

def string_value():
    return st.one_of(basic_string(), literal_string(),
                     ml_basic_string(), ml_literal_string())

# ---------- numbers ----------

def dec_int():
    digits = st.integers(min_value=0, max_value=9).map(str)
    body = st.one_of(
        digits,
        st.lists(digits, min_size=1, max_size=20).map(lambda ds: "".join(ds)),
        # underscores
        st.lists(digits, min_size=2, max_size=10).map(
            lambda ds: "_".join(ds)
        ),
        # extreme magnitude
        st.just("9" * 30),
        st.just("1" + "0" * 18),
        # leading zeros (accepted by parser)
        st.just("007"),
        st.just("0000"),
    )
    sign = st.sampled_from(["", "+", "-"])
    return st.tuples(sign, body).map(lambda t: t[0] + t[1])

def hex_int():
    hd = st.sampled_from("0123456789abcdefABCDEF")
    body = st.lists(hd, min_size=1, max_size=16).map(lambda ds: "".join(ds))
    return body.map(lambda s: "0x" + s)

def oct_int():
    od = st.sampled_from("01234567")
    body = st.lists(od, min_size=1, max_size=16).map(lambda ds: "".join(ds))
    return body.map(lambda s: "0o" + s)

def bin_int():
    bd = st.sampled_from("01")
    body = st.lists(bd, min_size=1, max_size=32).map(lambda ds: "".join(ds))
    return body.map(lambda s: "0b" + s)

def integer_value():
    return st.one_of(dec_int(), hex_int(), oct_int(), bin_int())

def float_value():
    digits = st.integers(min_value=0, max_value=9).map(str)
    intpart = st.one_of(
        st.just(""),
        digits,
        st.lists(digits, min_size=1, max_size=10).map(lambda ds: "".join(ds)),
        st.just("0"),
    )
    fracpart = st.one_of(
        st.just(""),
        st.lists(digits, min_size=1, max_size=10).map(lambda ds: "".join(ds)),
        st.just("5"),
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.lists(digits, min_size=1, max_size=3).map(lambda ds: "".join(ds)),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.just("e309"),
        st.just("E-400"),
    )
    sign = st.sampled_from(["", "+", "-"])

    def build(t):
        s, i, f, e = t
        if f == "" and e == "":
            f = "0"  # ensure it's a float
        return s + (i if i != "" else "0") + "." + f + e

    mainstream = st.tuples(sign, intpart, fracpart, exp).map(build)
    specials = st.sampled_from([
        "inf", "+inf", "-inf", "nan", "+nan", "-nan",
        "1.", ".5", "1.e10", ".5e-3",  # parser-accepted oddities
    ])
    return st.one_of(mainstream, specials)

def bool_value():
    return st.sampled_from(["true", "false"])

def date_time_value():
    d2 = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
    year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
    date = st.tuples(year, d2, d2).map(lambda t: "-".join(t))
    time_part = st.tuples(d2, d2, d2).map(lambda t: ":".join(t))
    secfrac = st.one_of(
        st.just(""),
        st.lists(st.integers(0, 9).map(str), min_size=1, max_size=6).map(
            lambda ds: "." + "".join(ds)
        ),
    )
    partial_time = st.tuples(time_part, secfrac).map(lambda t: t[0] + t[1])
    delim = st.sampled_from(["T", "t", " "])
    offset = st.one_of(
        st.just("Z"),
        st.tuples(st.sampled_from(["+", "-"]), d2, d2).map(
            lambda t: t[0] + t[1] + ":" + t[2]
        ),
    )
    return st.one_of(
        date,
        partial_time,
        st.tuples(date, delim, partial_time).map(lambda t: "".join(t)),
        st.tuples(date, delim, partial_time, offset).map(lambda t: "".join(t)),
        # calendar-invalid dates (accepted by parser)
        st.just("1979-02-30"),
        st.just("2000-13-45"),
    )

# ---------- keys ----------

def unquoted_key():
    chars = st.sampled_from(
        list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    )
    return st.lists(chars, min_size=1, max_size=12).map(lambda cs: "".join(cs))

def simple_key():
    return st.one_of(
        unquoted_key(),
        basic_string(),
        literal_string(),
        st.just('""'),  # empty quoted key
    )

def dotted_key():
    return st.lists(simple_key(), min_size=2, max_size=4).map(
        lambda ks: ".".join(ks)
    )

def key():
    return st.one_of(simple_key(), dotted_key())

# ---------- values (recursive) ----------

def _leaf_value():
    return st.one_of(
        string_value(),
        integer_value(),
        float_value(),
        bool_value(),
        date_time_value(),
    )

def _array():
    # arrays allow newlines/comments between elements and trailing comma
    inner = st.recursive(
        _leaf_value(),
        lambda children: st.one_of(
            st.lists(children, min_size=0, max_size=4).map(
                lambda vs: "[" + ", ".join(vs) + "]"
            ),
            st.lists(children, min_size=0, max_size=4).map(
                lambda vs: "[ " + ", ".join(vs) + " , ]"  # trailing comma
            ),
            st.lists(children, min_size=0, max_size=3).map(
                lambda vs: "[\n  " + ",\n  ".join(vs) + ",\n]"  # multiline
            ),
        ),
        max_leaves=20,
    )
    return inner

def _inline_table():
    def kv():
        return st.tuples(key(), st.one_of(_leaf_value(), _array())).map(
            lambda t: t[0] + " = " + t[1]
        )
    return st.lists(kv(), min_size=0, max_size=4).map(
        lambda kvs: "{" + ", ".join(kvs) + "}"
    )

def value():
    return st.recursive(
        _leaf_value(),
        lambda children: st.one_of(
            _array(),
            _inline_table(),
            st.lists(children, min_size=0, max_size=4).map(
                lambda vs: "[" + ", ".join(vs) + "]"
            ),
        ),
        max_leaves=25,
    )

# ---------- statements / document ----------

_comment_text = st.one_of(
    st.just(""),
    st.lists(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                          blacklist_characters="\n\r"),
            st.integers(min_value=1, max_value=0x1F).map(chr),
            st.just('\t'),
        ),
        min_size=0, max_size=20,
    ).map(lambda cs: "".join(cs)),
)

def comment():
    return _comment_text.map(lambda s: "#" + s)

def key_value_line():
    return st.tuples(key(), value()).map(lambda t: t[0] + " = " + t[1])

def standard_table():
    return key().map(lambda k: "[" + k + "]")

def array_table():
    return key().map(lambda k: "[[" + k + "]]")

def statement():
    return st.one_of(
        key_value_line(),
        standard_table(),
        array_table(),
        comment(),
    )

def _join_lines(lines):
    return "\n".join(lines)

def document():
    body = st.lists(statement(), min_size=0, max_size=12).map(_join_lines)
    # optionally add trailing newline or not
    return st.one_of(
        body,
        body.map(lambda s: s + "\n"),
        body.map(lambda s: s.replace("\n", "\r\n")),
    )

# ---------- malformed / near-valid variants ----------

def malformed():
    good = document()
    return st.one_of(
        good,
        # unterminated string
        st.tuples(unquoted_key(), basic_string()).map(
            lambda t: t[0] + " = " + t[1][:-1]
        ),
        # missing closing bracket
        st.tuples(unquoted_key(), value()).map(
            lambda t: t[0] + " = [" + t[1]
        ),
        # doubled delimiter
        st.tuples(unquoted_key(), value()).map(
            lambda t: t[0] + " = [[" + t[1] + "]]"
        ),
        # stray token
        st.just("= 1\n"),
        st.just("key =\n"),
        st.just("[table\n"),
        st.just("key = value\n"),
        # newline inside inline table (rejected by parser)
        st.tuples(key(), value()).map(
            lambda t: "k = {" + t[0] + " = " + t[1] + ",\n}"
        ),
        # duplicate key
        st.tuples(unquoted_key(), value()).map(
            lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[1]
        ),
        # invalid escape
        st.just('a = "bad \\q escape"'),
        # non-ASCII bare key
        st.just("k\u00e9y = 1"),
    )

# ---------- deep nesting in the steer band ----------

def deep_array(depth):
    return st.just("[" * depth + "]" * depth)

def deep_nesting():
    # depth in the interesting band 1500-2048
    return st.integers(min_value=1500, max_value=2048).map(deep_array)

def deep_inline_table():
    # inline tables nest too; keep depth smaller since each level is heavier
    return st.integers(min_value=200, max_value=800).map(
        lambda d: "{" * 0 + "{a = " * d + "1" + "}" * d
    )

# ---------- final strategy ----------

def _assemble():
    return st.one_of(
        document(),
        malformed(),
        deep_nesting(),
        deep_inline_table(),
        # empty document variants
        st.just(""),
        st.just("\n"),
        st.just("# only a comment"),
        st.just("# only a comment\n"),
        # empty containers
        st.just("a = []"),
        st.just("a = {}"),
        st.just("[t]"),
        st.just("[t]\n"),
        st.just("[[a]]"),
        st.just("[[a]]\n"),
        # extreme numeric magnitudes
        st.just("a = 1e309"),
        st.just("a = -1e309"),
        st.just("a = 99999999999999999999999999999999"),
        st.just("a = 0xFFFFFFFFFFFFFFFFFFFFFFFF"),
        # escapes and non-ASCII
        st.just('a = "\\u0000"'),
        st.just('a = "\\uFFFF"'),
        st.just('a = "\\U0001F600"'),
        st.just('a = "\u00e9\u4e2d\u6587"'),
        # embedded control bytes (no raw NUL)
        st.just('a = "x\x01y"'),
        st.just('a = "x\x1fy"'),
        st.just('# comment with \x01 control'),
        # CRLF
        st.just("a = 1\r\nb = 2\r\n"),
        # no trailing newline
        st.just("a = 1"),
        # 10 000-char key
        st.just("k" * 10000 + " = 1"),
        # super-table after sub-table
        st.just("[a.b]\nx = 1\n[a]\ny = 2"),
        # dotted keys
        st.just("a.b.c = 1"),
        st.just('"a".b."c" = 1'),
        # empty quoted key
        st.just('"" = 1'),
    )

strategy = _assemble()
```