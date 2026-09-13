```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------
BARE_KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

def _bare_key(min_size=1, max_size=12):
    return st.text(alphabet=BARE_KEY_CHARS, min_size=min_size, max_size=max_size)

def _simple_key():
    quoted = st.one_of(
        st.text(min_size=0, max_size=8).filter(lambda s: '"' not in s and "\\" not in s and "\n" not in s).map(lambda s: '"' + s + '"'),
        st.text(min_size=0, max_size=8).filter(lambda s: "'" not in s and "\n" not in s).map(lambda s: "'" + s + "'"),
    )
    return st.one_of(_bare_key(), quoted)

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(lambda ks: ".".join(ks))

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------- strings ----------
_ESCAPES = ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
            "\\u0000", "\\u00e9", "\\uFFFF", "\\U0001F600", "\\U0010FFFF"]

def _basic_string_content():
    pieces = st.one_of(
        st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\\n'), min_size=0, max_size=10),
        st.sampled_from(_ESCAPES),
        st.integers(min_value=0, max_value=0x1F).map(lambda c: chr(c)),  # raw control chars (accepted)
        st.sampled_from(["\x00", "\x01", "\x7f", "\t"]),
    )
    return st.lists(pieces, min_size=0, max_size=6).map(lambda ps: "".join(ps))

def _basic_string():
    return _basic_string_content().map(lambda s: '"' + s + '"')

def _literal_string():
    return st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="'\n"), min_size=0, max_size=10).map(lambda s: "'" + s + "'")

def _ml_basic_string():
    inner = st.lists(
        st.one_of(
            st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\'), min_size=0, max_size=8),
            st.sampled_from(_ESCAPES),
            st.sampled_from(["\n", "\r\n", "\t", "\x01"]),
        ),
        min_size=0, max_size=5,
    ).map(lambda ps: "".join(ps))
    return inner.map(lambda s: '"""' + s.replace('"""', '""\\"') + '"""')

def _ml_literal_string():
    inner = st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="'"), min_size=0, max_size=12)
    return inner.map(lambda s: "'''" + s + "'''")

def _string():
    return st.one_of(_basic_string(), _literal_string(), _ml_basic_string(), _ml_literal_string())

# ---------- numbers ----------
def _dec_int():
    digits = st.text(alphabet="0123456789", min_size=1, max_size=20)
    signed = st.booleans().map(lambda b: "-" if b else "")
    leading_zero = st.sampled_from(["007", "000", "01", "00"])
    with_underscores = st.lists(st.text(alphabet="0123456789", min_size=1, max_size=3), min_size=2, max_size=4).map(lambda xs: "_".join(xs))
    huge = st.sampled_from(["9223372036854775808", "-9223372036854775809", "18446744073709551616", "99999999999999999999999999"])
    return st.one_of(
        st.tuples(signed, digits).map(lambda t: t[0] + t[1]),
        st.tuples(signed, leading_zero).map(lambda t: t[0] + t[1]),
        st.tuples(signed, with_underscores).map(lambda t: t[0] + t[1]),
        st.just(huge),
    )

def _hex_int():
    body = st.lists(st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=4), min_size=1, max_size=4).map(lambda xs: "_".join(xs))
    return st.booleans().map(lambda b: "-" if b else "").flatmap(lambda s: body.map(lambda b: s + "0x" + b))

def _oct_int():
    body = st.lists(st.text(alphabet="01234567", min_size=1, max_size=4), min_size=1, max_size=4).map(lambda xs: "_".join(xs))
    return st.booleans().map(lambda b: "-" if b else "").flatmap(lambda s: body.map(lambda b: s + "0o" + b))

def _bin_int():
    body = st.lists(st.text(alphabet="01", min_size=1, max_size=8), min_size=1, max_size=3).map(lambda xs: "_".join(xs))
    return st.booleans().map(lambda b: "-" if b else "").flatmap(lambda s: body.map(lambda b: s + "0b" + b))

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    sign = st.booleans().map(lambda b: "-" if b else "")
    frac = st.text(alphabet="0123456789", min_size=1, max_size=8)
    exp = st.tuples(
        st.sampled_from(["e", "E"]),
        st.booleans().map(lambda b: "-" if b else "+"),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2])
    forms = st.one_of(
        st.tuples(st.text(alphabet="0123456789", min_size=1, max_size=6), frac, exp).map(lambda t: t[0] + "." + t[1] + t[2]),
        st.tuples(st.text(alphabet="0123456789", min_size=1, max_size=6), exp).map(lambda t: t[0] + t[1]),
        st.tuples(st.text(alphabet="0123456789", min_size=1, max_size=6), frac).map(lambda t: t[0] + "." + t[1]),
        st.just("1."),
        st.just(".5"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1_000.5"),
        st.just("inf"), st.just("-inf"), st.just("+inf"),
        st.just("nan"), st.just("-nan"), st.just("+nan"),
    )
    return st.tuples(sign, forms).map(lambda t: t[0] + t[1])

# ---------- dates ----------
def _date():
    return st.tuples(
        st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
    ).map(lambda t: "%s-%s-%s" % t)

def _time():
    return st.tuples(
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.one_of(st.just(""), st.integers(min_value=0, max_value=999999).map(lambda n: ".%06d" % n)),
    ).map(lambda t: "%s:%s:%s%s" % t)

def _date_time():
    delim = st.sampled_from(["T", "t", " "])
    offset = st.one_of(
        st.just("Z"),
        st.tuples(st.sampled_from(["+", "-"]),
                  st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
                  st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)).map(lambda t: t[0] + t[1] + ":" + t[2]),
    )
    return st.one_of(
        _date(),
        _time(),
        st.tuples(_date(), delim, _time()).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(_date(), delim, _time(), offset).map(lambda t: t[0] + t[1] + t[2] + t[3]),
        st.just("1979-02-30"),
        st.just("1979-05-27 07:32:00Z"),
        st.just("0000-00-00T00:00:00.000Z"),
    )

# ---------- recursive values ----------
def _scalar_value():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        st.sampled_from(["true", "false"]),
        _date_time(),
    )

def _array_value(depth):
    inner = st.one_of(
        _scalar_value(),
        st.deferred(lambda: _array_value(depth - 1)) if depth > 0 else st.nothing(),
        st.deferred(lambda: _inline_table_value(depth - 1)) if depth > 0 else st.nothing(),
    )
    elems = st.lists(inner, min_size=0, max_size=5)
    def build(xs):
        if not xs:
            return "[]"
        body = ", ".join(xs)
        if st.booleans:  # placeholder to keep structure simple
            pass
        return "[" + body + "]"
    return elems.map(build)

def _inline_table_value(depth):
    if depth <= 0:
        pairs = st.just([])
    else:
        def pair():
            return st.tuples(_key(), _value(depth - 1)).map(lambda t: t[0] + " = " + t[1])
        pairs = st.lists(pair(), min_size=0, max_size=4)
    def build(ps):
        if not ps:
            return "{}"
        return "{" + ", ".join(ps) + "}"
    return pairs.map(build)

def _value(depth):
    return st.one_of(
        _scalar_value(),
        _array_value(depth),
        _inline_table_value(depth),
    )

# ---------- document structure ----------
def _comment():
    return st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n"),
        min_size=0, max_size=20,
    ).map(lambda s: "#" + s)

def _key_value_line(depth):
    return st.tuples(_key(), _value(depth)).map(lambda t: t[0] + " = " + t[1])

def _table_lines(depth):
    header = _key().map(lambda k: "[" + k + "]")
    aot = _key().map(lambda k: "[[" + k + "]]")
    return st.one_of(header, aot)

# ---------- malformed / near-valid ----------
def _malformed():
    return st.sampled_from([
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = '''unterminated",
        "a = [1, 2",
        "a = {b = 1",
        "a = {b = 1,\n c = 2}",
        "a = 1 2",
        "a = \n1",
        "a = ",
        "= 1",
        "[t",
        "[[t]",
        "a = 1\nb = 2\nb = 3",
        "[t]\n[t]",
        "a = 1\n[a]",
        "a = \\q",
        "a b = 1",
        "a = 1,\n",
        "\x00",
        "a = 1\n\x00",
        "[]",
        "[[]]",
        "a = {,}",
        "a = {b = 1,,}",
        "a = [1,,2]",
        "a = [1 2]",
        "a = 1_",
        "a = 0x",
        "a = 0o8",
        "a = 0b2",
        "a = 1e",
        "a = .",
        "a = t",
        "a = tr",
        "[[a]]\n[a]",
    ])

def _document():
    depth = st.integers(min_value=0, max_value=6)
    lines = st.lists(
        st.one_of(
            _comment(),
            st.integers(min_value=0, max_value=6).flatmap(_key_value_line),
            st.integers(min_value=0, max_value=6).flatmap(_table_lines),
            st.just(""),
        ),
        min_size=0, max_size=12,
    )
    def build(ls):
        return "\n".join(ls)
    return lines.map(build)

# ---------- deep nesting band ----------
def _deep_array():
    depth = st.integers(min_value=1500, max_value=2048)
    def build(n):
        return "a = " + "[" * n + "]" * n
    return depth.map(build)

def _deep_inline():
    depth = st.integers(min_value=1500, max_value=2048)
    def build(n):
        return "a = " + "{b = " * n + "1" + "}" * n
    return depth.map(build)

# ---------- top-level strategy ----------
def _complete_document():
    return st.one_of(
        _document(),
        _deep_array(),
        _deep_inline(),
        st.just(""),
        st.just("\n"),
        st.just("# just a comment"),
        st.just("# no newline at end"),
        st.just("k = 1"),
        st.just("k = 1\n"),
        st.just("[t]\n"),
        st.just("[[a]]\n"),
        st.just('"" = 1'),
        st.just("a = {b = 1,}"),
        st.just("a = [1, 2,]"),
        st.just("a = 1979-02-30"),
        st.just("a = 007"),
        st.just("a = 1."),
        st.just("a = .5"),
        st.just('a = "x\x01y"'),
        st.just("# comment \x01"),
        st.just("a = 1\r\nb = 2\r\n"),
        st.just("\t k = 1"),
        st.just("a = 1\nb = 2\nc = 3"),
    )

def _mixed():
    return st.one_of(
        _complete_document(),
        _malformed(),
        _key_value_line(3),
        _table_lines(3),
        _value(3),
        _string(),
        _integer(),
        _float(),
        _date_time(),
    )

strategy = _mixed()
```