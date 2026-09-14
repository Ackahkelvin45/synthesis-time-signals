```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------- helpers

_BARE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
_BARE_START = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"


def _unquoted_key():
    return st.text(alphabet=_BARE_CHARS, min_size=1, max_size=12)


def _basic_string_body():
    # characters allowed raw inside basic strings (no NUL, no newline, no quote/backslash)
    safe = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\n\r\\\x00',
        ),
        min_size=0,
        max_size=40,
    )
    return safe


_ESCAPES = [
    '\\b', '\\t', '\\n', '\\f', '\\r', '\\"', '\\\\', '\\/',
    '\\u0000', '\\u001f', '\\u007f', '\\u00e9', '\\u4e2d', '\\uD83D',
    '\\U0001F600', '\\U0010FFFF', '\\uFFFF', '\\u0007',
]


def _basic_string_inner():
    return st.one_of(
        _basic_string_body(),
        st.sampled_from(_ESCAPES),
    )


def _basic_string():
    return st.lists(_basic_string_inner(), max_size=6).map(lambda parts: '"' + "".join(parts) + '"')


def _literal_string():
    body = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'\n\r\x00",
        ),
        min_size=0,
        max_size=40,
    )
    return body.map(lambda s: "'" + s + "'")


def _ml_basic_string():
    body = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\x00",
        ),
        min_size=0,
        max_size=60,
    )
    return body.map(lambda s: '"""' + s + '"""')


def _ml_literal_string():
    body = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\x00",
        ),
        min_size=0,
        max_size=60,
    )
    return body.map(lambda s: "'''" + s + "'''")


def _string():
    return st.one_of(
        _basic_string(),
        _literal_string(),
        _ml_basic_string(),
        _ml_literal_string(),
    )


# ---------------------------------------------------------------- numbers

def _dec_int():
    digits = st.text(alphabet="0123456789", min_size=1, max_size=25)
    sign = st.sampled_from(["", "+", "-"])
    return st.tuples(sign, digits).map(lambda t: t[0] + t[1])


def _hex_int():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=20).map(
        lambda s: "0x" + s
    )


def _oct_int():
    return st.text(alphabet="01234567", min_size=1, max_size=20).map(lambda s: "0o" + s)


def _bin_int():
    return st.text(alphabet="01", min_size=1, max_size=20).map(lambda s: "0b" + s)


def _int_with_underscores():
    body = st.text(alphabet="0123456789", min_size=1, max_size=6)
    return body.map(lambda s: "_".join(list(s)))


def _integer():
    return st.one_of(
        _dec_int(),
        _hex_int(),
        _oct_int(),
        _bin_int(),
        st.sampled_from(["0", "007", "1_000", "9223372036854775808",
                         "99999999999999999999999999999999",
                         "-9223372036854775809", "+0", "-0"]),
        _int_with_underscores(),
    )


def _float():
    return st.one_of(
        st.sampled_from([
            "1.", ".5", "1.0", "-1.", "+.5", "0.0", "-0.0",
            "1e309", "-1e309", "1e-309", "6.626e-34", "1_000.5",
            "3.14159", "1e0", "1E10", "1.5e+3", "1.5E-3",
        ]),
        st.builds(
            lambda a, b, c: a + "." + b + c,
            st.sampled_from(["", "+", "-"]),
            st.text(alphabet="0123456789", min_size=1, max_size=8),
            st.sampled_from(["", "e0", "e10", "E-5", "e+42"]),
        ),
    )


def _inf_nan():
    return st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])


# ---------------------------------------------------------------- dates

def _date():
    return st.builds(
        lambda y, mo, d: "%04d-%02d-%02d" % (y, mo, d),
        st.integers(min_value=0, max_value=9999),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    )


def _time():
    return st.builds(
        lambda h, mi, s, frac: "%02d:%02d:%02d%s" % (h, mi, s, frac),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.sampled_from(["", ".0", ".123456", ".999"]),
    )


def _offset():
    return st.one_of(
        st.just("Z"),
        st.builds(
            lambda sign, h, m: "%s%02d:%02d" % (sign, h, m),
            st.sampled_from(["+", "-"]),
            st.integers(min_value=0, max_value=23),
            st.integers(min_value=0, max_value=59),
        ),
    )


def _date_time():
    return st.one_of(
        _date(),
        _time(),
        st.tuples(_date(), st.sampled_from(["T", "t", " "]), _time()).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        st.tuples(
            _date(), st.sampled_from(["T", "t", " "]), _time(), _offset()
        ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
        st.sampled_from([
            "1979-02-30", "1979-05-27T07:32:00Z", "1979-05-27 07:32:00Z",
            "1979-05-27T00:32:00-07:00", "1979-05-27T00:32:00.999999-07:00",
            "07:32:00", "00:32:00.999999", "0000-00-00",
        ]),
    )


# ---------------------------------------------------------------- keys

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())


def _simple_key():
    return st.one_of(_quoted_key(), _unquoted_key())


def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(lambda ks: ".".join(ks))


def _key():
    return st.one_of(_simple_key(), _dotted_key())


# ---------------------------------------------------------------- values (recursive)

def _scalar_value():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _inf_nan(),
        st.sampled_from(["true", "false"]),
        _date_time(),
    )


def _value(draw, depth):
    if depth <= 0:
        return draw(_scalar_value())
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        return draw(_scalar_value())
    if choice == 1:
        return _gen_array(draw, depth - 1)
    if choice == 2:
        return _gen_inline_table(draw, depth - 1)
    return draw(_scalar_value())


def _gen_array(draw, depth):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "[" + draw(st.sampled_from(["", "\n", " ", "# c\n"])) + "]"
    items = [_value(draw, depth) for _ in range(n)]
    trailing = draw(st.sampled_from(["", ",", ", # trailing\n"]))
    sep = draw(st.sampled_from([", ", ",\n", ", ", ", "]))
    return "[" + sep.join(items) + trailing + "]"


def _gen_inline_table(draw, depth):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "{}"
    parts = []
    for _ in range(n):
        k = draw(_key())
        v = _value(draw, depth)
        parts.append("%s = %s" % (k, v))
    trailing = draw(st.sampled_from(["", ","]))
    return "{" + ", ".join(parts) + trailing + "}"


def _value_toplevel():
    return st.recursive(
        _scalar_value(),
        lambda children: st.one_of(
            st.lists(children, max_size=4).map(
                lambda xs: "[" + ", ".join(xs) + "]"
            ),
            st.lists(children, max_size=3).map(
                lambda xs: "{" + ", ".join(
                    "k%d = %s" % (i, v) for i, v in enumerate(xs)
                ) + "}"
            ),
        ),
        max_leaves=12,
    )


# ---------------------------------------------------------------- documents

def _key_value_line():
    return st.tuples(_key(), _value_toplevel()).map(
        lambda t: "%s = %s" % (t[0], t[1])
    )


def _comment_line():
    body = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\n\r\x00",
        ),
        min_size=0,
        max_size=30,
    )
    return body.map(lambda s: "# " + s)


def _table_header():
    return _key().map(lambda k: "[%s]" % k)


def _array_table_header():
    return _key().map(lambda k: "[[%s]]" % k)


def _line():
    return st.one_of(
        _key_value_line(),
        _table_header(),
        _array_table_header(),
        _comment_line(),
        st.just(""),
    )


def _document():
    n = st.integers(min_value=0, max_value=12)
    return st.lists(_line(), min_size=0, max_size=12).map(lambda ls: "\n".join(ls))


# ---------------------------------------------------------------- malformed / edge

def _malformed():
    return st.sampled_from([
        "a = ",                      # missing value
        "a = [1, 2",                 # unterminated array
        "a = {b = 1",                # unterminated inline table
        "a = \"unterminated",        # unterminated string
        "a = 'unterminated",         # unterminated literal
        "a = 1 2",                   # stray token
        "= 1",                       # missing key
        "[t",                        # unterminated table header
        "[[t]",                      # mismatched array table
        "a = [1,, 2]",               # doubled comma
        "a = {,}",                   # stray comma
        "a = 1\na = 2",              # duplicate key
        "[t]\n[t]",                  # duplicate table
        "a = \"\\q\"",               # invalid escape
        "a =\n1",                    # value on next line
        "a = {b = 1\n}",             # newline in inline table
        "missing =",                 # bare key with unicode rejected case
        "a = 1]]",                   # doubled delimiter
        "[]",                        # empty table header
        "a = [}",                    # mismatched delimiters
    ])


def _deep_array():
    def build(depth):
        return "[" * depth + "]" * depth
    return st.integers(min_value=1500, max_value=2048).map(build)


def _deep_inline():
    def build(depth):
        return "{" * depth + "}" * depth
    return st.integers(min_value=200, max_value=600).map(build)


def _utf8_escape():
    # Exercise toml_utf8_to_ucs: raw multi-byte UTF-8 chars and \u/\U escapes
    # including surrogate pairs, boundary codepoints, and invalid sequences.
    raw = st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\n\r\\\x00',
        ),
        min_size=0,
        max_size=8,
    )
    escapes = st.sampled_from([
        "\\u0000", "\\u007F", "\\u0080", "\\u07FF", "\\u0800", "\\uFFFF",
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
        "\\uD83D\\uDE00", "\\uD800\\uDC00", "\\uDBFF\\uDFFF",
        "\\U00000000", "\\U0000007F", "\\U00000080", "\\U000007FF",
        "\\U00000800", "\\U0000FFFF", "\\U00010000", "\\U0010FFFF",
        "\\U00110000", "\\UFFFFFFFF",
        "\\uD83D", "\\uDE00", "\\uD800\\uD800", "\\uDC00\\uDC00",
    ])
    inner = st.lists(st.one_of(raw, escapes), max_size=6).map("".join)
    return inner.map(lambda s: 'a = "' + s + '"')


def _utf8_raw():
    # Raw multibyte sequences (2/3/4-byte) placed directly in strings and keys.
    chars = st.sampled_from([
        "\u00e9", "\u00ff", "\u07ff", "\u0800", "\u4e2d", "\uffff",
        "\U0001F600", "\U0010FFFF",
    ])
    body = st.lists(chars, min_size=1, max_size=6).map("".join)
    return st.one_of(
        body.map(lambda s: 'a = "' + s + '"'),
        body.map(lambda s: 'a = \'' + s + '\''),
        body.map(lambda s: '"""' + s + '"""'),
        body.map(lambda s: "'''" + s + "'''"),
        body.map(lambda s: "[" + s + "]"),
        body.map(lambda s: s + " = 1"),
    )


def _edge_document():
    return st.one_of(
        _malformed(),
        _deep_array().map(lambda s: "a = " + s),
        _deep_inline().map(lambda s: "a = " + s),
        _utf8_escape(),
        _utf8_raw(),
        st.just(""),
        st.just("\n"),
        st.just("\r\n"),
        st.just("# only a comment"),
        st.just('"" = 1'),
        st.just("a = \"\\u0000\""),
        st.just("a = \"x\x01y\""),
        st.just("a = 1979-02-30"),
        st.just("a = 007"),
        st.just("a = 1."),
        st.just("a = .5"),
        st.just("a = {b = 1,}"),
        st.just("a = 1_000"),
        st.just("a = 0xDEAD_BEEF"),
        st.just("a = 0o755"),
        st.just("a = 0b1010_1010"),
        st.just("a = 1e309"),
        st.just("a = -inf"),
        st.just("a = nan"),
        st.just("[t]\n[[t]]"),
        st.just("a.b.c = 1"),
        st.just("a = [\n  1,\n  2, # c\n]"),
        st.just("\t" + "a = 1"),
        st.just("a = 1"),  # no trailing newline
    )


# ---------------------------------------------------------------- root strategy

def _root():
    return st.one_of(
        _document(),
        _edge_document(),
    )


strategy = _root()
```