Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(*parts):
    return "".join(parts)

_ws = st.sampled_from(["", " ", "  ", "\t", " \t "])

def _comment():
    # control chars allowed in comments by the parser (no NUL, no newline)
    body = st.text(
        alphabet=st.characters(
            blacklist_categories=(), blacklist_characters="\x00\n\r"
        ),
        max_size=12,
    )
    return body.map(lambda b: "#" + b)

# ---------- keys ----------

_unquoted_key_char = st.sampled_from(
    list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
)

def _unquoted_key():
    return st.lists(_unquoted_key_char, min_size=1, max_size=8).map("".join)

_basic_key_esc = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
     "\\u0041", "\\u0000", "\\U0001F600", "\\u00e9",
     "\\uD800", "\\uDFFF", "\\uDBFF", "\\uDC00", "\\U0010FFFF",
     "\\u0008", "\\u000C", "\\u000B", "\\u0007", "\\u001F",
     "\\u007F", "\\u0080", "\\uFFFF", "\\U00000000"]
)

def _basic_string_inner():
    return st.lists(
        st.one_of(
            st.characters(
                blacklist_categories=(),
                blacklist_characters='"\x00\n',
            ).map(str),
            _basic_key_esc,
        ),
        max_size=6,
    ).map("".join)

def _basic_string():
    return _basic_string_inner().map(lambda s: '"' + s + '"')

def _literal_string():
    return st.lists(
        st.characters(
            blacklist_categories=(),
            blacklist_characters="'\x00\n",
        ),
        max_size=6,
    ).map(lambda cs: "'" + "".join(cs) + "'")

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_unquoted_key(), _quoted_key())

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(".".join)

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------- strings / values ----------

_ml_basic_esc = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
     "\\u0041", "\\u0000", "\\U0001F600", "\\\n", "\\\r\n",
     "\\ ", "\\\t", "\\uD800", "\\uDFFF", "\\U0010FFFF",
     "\\u0008", "\\u000C", "\\u000B", "\\u007F", "\\u0080"]
)

def _ml_basic_string():
    inner = st.lists(
        st.one_of(
            st.characters(
                blacklist_categories=(),
                blacklist_characters='"\x00',
            ).map(str),
            _ml_basic_esc,
        ),
        max_size=8,
    ).map("".join)
    return inner.map(lambda s: '"""' + s + '"""')

def _ml_literal_string():
    inner = st.lists(
        st.characters(
            blacklist_categories=(),
            blacklist_characters="'\x00",
        ),
        max_size=8,
    ).map("".join)
    return inner.map(lambda s: "'''" + s + "'''")

def _string():
    return st.one_of(
        _basic_string(),
        _literal_string(),
        _ml_basic_string(),
        _ml_literal_string(),
    )

def _digits():
    return st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join)

def _underscored_digits(min_d=1, max_d=6):
    return st.lists(st.sampled_from("0123456789"), min_size=min_d, max_size=max_d).map(
        lambda ds: ds[0] + "".join("_" + d for d in ds[1:]) if len(ds) > 1 else ds[0]
    )

def _dec_int():
    return st.one_of(
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=8).map("".join),
        _underscored_digits(),
        st.just("0"),
        st.just("007"),
        st.just("0" * 30),
        st.integers(min_value=-2**70, max_value=2**70).map(str),
        st.integers(min_value=-2**63, max_value=2**64).map(str),
        st.just("-0"),
        st.just("+1"),
        st.just("+0"),
        st.just("-9223372036854775808"),
        st.just("18446744073709551615"),
        st.just("9223372036854775808"),
        st.just("-9223372036854775809"),
    )

def _hex_int():
    body = st.lists(st.sampled_from("0123456789abcdefABCDEF"), min_size=1, max_size=6).map("".join)
    return body.map(lambda b: "0x" + b)

def _oct_int():
    body = st.lists(st.sampled_from("01234567"), min_size=1, max_size=6).map("".join)
    return body.map(lambda b: "0o" + b)

def _bin_int():
    body = st.lists(st.sampled_from("01"), min_size=1, max_size=8).map("".join)
    return body.map(lambda b: "0b" + b)

def _integer():
    return st.one_of(
        _dec_int(), _hex_int(), _oct_int(), _bin_int(),
        st.just("0x"),
        st.just("0o"),
        st.just("0b"),
        st.just("0x_1"),
        st.just("0o8"),
        st.just("0b2"),
        st.just("1__2"),
        st.just("_1"),
        st.just("1_"),
        st.just("0xFFFFFFFFFFFFFFFF"),
        st.just("0xFFFFFFFFFFFFFFFFF"),
    )

def _float():
    frac = st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join)
    exp = st.builds(
        lambda sign, ds: "e" + sign + ds,
        st.sampled_from(["", "+", "-"]),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=3).map("".join),
    )
    plain = st.builds(
        lambda a, b: a + "." + b,
        _digits(),
        frac,
    )
    with_exp = st.builds(
        lambda a, b, e: a + "." + b + e,
        _digits(),
        frac,
        exp,
    )
    bare_exp = st.builds(lambda a, e: a + e, _digits(), exp)
    return st.one_of(
        plain,
        with_exp,
        bare_exp,
        st.just("1."),
        st.just(".5"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("0.0"),
        st.just("1_000.5"),
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
        st.just("1e"),
        st.just("1.e5"),
        st.just(".e5"),
        st.just("1.2.3"),
        st.just("1e+"),
        st.just("-0.0"),
        st.just("1_0.0_1"),
        st.just("1.0e1_0"),
        st.just("1.7976931348623157e308"),
        st.just("1.7976931348623159e308"),
        st.just("5e-324"),
        st.just("1e-400"),
        st.just("+1.5"),
        st.just("+.5"),
    )

def _bool():
    return st.sampled_from(["true", "false", "True", "FALSE", "tru", "fals"])

def _date_time():
    year = st.lists(st.sampled_from("0123456789"), min_size=4, max_size=4).map("".join)
    month = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    day = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    hh = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    mm = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    ss = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    secfrac = st.builds(
        lambda ds: "." + ds,
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join),
    )
    partial_time = st.builds(
        lambda h, m, s, f: h + ":" + m + ":" + s + f,
        hh, mm, ss, st.one_of(st.just(""), secfrac),
    )
    full_date = st.builds(lambda y, mo, d: y + "-" + mo + "-" + d, year, month, day)
    offset = st.one_of(
        st.just("Z"),
        st.just("z"),
        st.builds(lambda s, h, m: s + h + ":" + m, st.sampled_from(["+", "-"]), hh, mm),
        st.builds(lambda s, h, m: s + h + m, st.sampled_from(["+", "-"]), hh, mm),
    )
    full_time = st.builds(lambda pt, off: pt + off, partial_time, offset)
    delim = st.sampled_from(["T", "t", " "])
    return st.one_of(
        st.builds(lambda d, dl, t: d + dl + t, full_date, delim, full_time),
        st.builds(lambda d, dl, t: d + dl + t, full_date, delim, partial_time),
        full_date,
        partial_time,
        st.just("1979-02-30"),
        st.just("1979-05-27 07:32:00Z"),
        st.just("0000-00-00"),
        st.just("23:59:59.999999"),
        st.just("1979-05-27T07:32:00"),
        st.just("1979-05-27T00:32:00.999999-07:00"),
        st.just("1979-05-27T00:32:00.999999+07:00"),
        st.just("1979-05-27"),
        st.just("07:32:00"),
        st.just("1979-5-27"),
        st.just("1979-05-27T7:32:00Z"),
        st.just("1979-05-27T07:32:00.Z"),
        st.just("1979-05-27T07:32:00+0700"),
        st.just("1979-13-40T25:61:61Z"),
        st.just("1979-05-27T07:32:00Z07:00"),
    )

# ---------- recursive arrays / inline tables ----------

def _value(depth):
    if depth <= 0:
        return st.one_of(
            _string(), _integer(), _float(), _bool(), _date_time(),
        )
    child = st.deferred(lambda: _value(depth - 1))
    return st.one_of(
        _string(), _integer(), _float(), _bool(), _date_time(),
        _array(child, depth),
        _inline_table(child, depth),
    )

def _array(child, depth):
    nl = st.sampled_from(["", " ", "\n", "\r\n", " \n ", "\n# c\n", "\t"])
    sep = st.builds(lambda a, b: a + "," + b, nl, nl)
    elems = st.lists(
        st.builds(lambda c, s: c + s, child, nl),
        min_size=0,
        max_size=4,
    ).map(lambda xs: "".join(xs))
    trailing = st.sampled_from(["", ",", " ,", ",\n", ",,", " ,,"])
    return st.builds(
        lambda lead, body, tr, tail: "[" + lead + body + tr + tail + "]",
        nl, elems, trailing, nl,
    )

def _inline_table(child, depth):
    def pair(c):
        return st.builds(
            lambda k, eq, v: k + eq + v,
            _key(),
            st.sampled_from(["=", " = ", "\t=\t"]),
            c,
        )
    pairs = st.lists(
        st.builds(lambda p, ws: p + ws, pair(child), st.sampled_from(["", " ", "  ", ",\n", ","])),
        min_size=0,
        max_size=3,
    ).map(lambda xs: "".join(xs))
    trailing = st.sampled_from(["", ",", " ,", ",,", " ,,"])
    return st.builds(
        lambda body, tr: "{" + body + tr + "}",
        pairs, trailing,
    )

# ---------- document lines ----------

def _key_value(depth):
    return st.builds(
        lambda k, eq, v, c: k + eq + v + c,
        _key(),
        st.sampled_from(["=", " = ", "\t=\t", "= ", " ="]),
        _value(depth),
        st.one_of(st.just(""), _comment().map(lambda c: " " + c)),
    )

def _table():
    return st.builds(
        lambda k, c: "[" + k + "]" + c,
        _key(),
        st.one_of(st.just(""), _comment().map(lambda c: " " + c)),
    )

def _array_table():
    return st.builds(
        lambda k, c: "[[" + k + "]]" + c,
        _key(),
        st.one_of(st.just(""), _comment().map(lambda c: " " + c)),
    )

def _line(depth):
    return st.one_of(
        _key_value(depth),
        _table(),
        _array_table(),
        _comment(),
        st.just(""),
    )

def _malformed(depth):
    # near-valid-but-malformed inputs
    return st.one_of(
        # unterminated basic string
        _basic_string_inner().map(lambda s: 'a = "' + s),
        # unterminated literal string
        st.lists(
            st.characters(blacklist_categories=(), blacklist_characters="'\x00\n"),
            max_size=5,
        ).map(lambda cs: "a = '" + "".join(cs)),
        # missing closing bracket in array
        _value(depth).map(lambda v: "a = [" + v),
        # missing closing brace in inline table
        _value(depth).map(lambda v: "a = {b = " + v),
        # doubled delimiter
        _value(depth).map(lambda v: "a = [[" + v + "]]"),
        _value(depth).map(lambda v: "a = {{b = " + v + "}}"),
        # stray token
        st.just("a = 1 2"),
        st.just("a = "),
        st.just("= 1"),
        st.just("a b = 1"),
        st.just("[t"),
        st.just("[[t]"),
        st.just("a = {b = 1\n}"),
        st.just('a = "\\q"'),
        st.just("a = 1\nb = 2\nb = 3"),
        st.just("[t]\n[t]"),
        st.just("a = 1\nb"),
        # non-ascii bare key
        st.just("\u00e9 = 1"),
        st.just("k\u00e9y = 1"),
        # new malformed cases
        st.just('a = """'),
        st.just("a = '''"),
        st.just("a = [1, 2"),
        st.just("a = {b = 1"),
        st.just("a = {b = 1,}"),
        st.just("a = {,}"),
        st.just("a = [,]"),
        st.just("a = [1,,2]"),
        st.just("[]"),
        st.just("[[]]"),
        st.just("[ ]"),
        st.just("a = 0x"),
        st.just("a = 0o8"),
        st.just("a = 0b2"),
        st.just("a = 1__0"),
        st.just("a = _1"),
        st.just("a = 1_"),
        st.just("a = ."),
        st.just("a = e5"),
        st.just("a = 1e"),
        st.just('a = "\\u12"'),
        st.just('a = "\\uD800"'),
        st.just('a = "\\uDFFF"'),
        st.just('a = "\\U00110000"'),
        st.just('a = "\\uZZZZ"'),
        st.just("a = 1979-05-27T07:32:00+"),
        st.just("a = 1979-05-27T07:32:00Z07:00"),
        st.just("a = true false"),
        st.just("a = True"),
        st.just("[t]]"),
        st.just("[[t]]]"),
        st.just("[[t]"),
        st.just("[t]x"),
        st.just("a.b.c = 1\na.b = 2"),
        st.just("a = 1\na = 2"),
        st.just("a = {b = 1}\na.b = 2"),
        st.just("a = [1]\na.b = 2"),
        st.just("a = 1\r\nb = 2\r\n"),
        st.just("\ufeffa = 1"),
        st.just("a = 1\x00"),
        st.just("a = \"\x01\""),
        st.just("# comment\r\n"),
        st.just("a = 1 # c\r\nb = 2"),
    )

# ---------- document ----------

def _document():
    def lines(depth):
        return st.lists(
            _line(depth),
            min_size=0,
            max_size=6,
        ).map(lambda ls: "\n".join(ls))

    def with_malformed(depth):
        return st.one_of(lines(depth), _malformed(depth))

    base = with_malformed(2)
    return st.one_of(
        base,
        # deep-nesting band 1500-2048
        st.integers(min_value=1500, max_value=2048).flatmap(
            lambda d: st.builds(
                lambda v: "a = " + v,
                _value(d),
            )
        ),
        # empty / comment-only documents
        st.just(""),
        st.just("\n"),
        st.just("# only a comment"),
        st.just("# c1\n# c2\n"),
        # no trailing newline
        st.builds(lambda s: s, base),
        # CRLF document
        lines(2).map(lambda s: s.replace("\n", "\r\n")),
        # mixed line endings
        lines(2).map(lambda s: "\r\n".join(s.split("\n"))),
        # leading/trailing whitespace
        st.builds(lambda s: "  " + s + "  \n", base),
        # BOM prefix
        st.builds(lambda s: "\ufeff" + s, base),
        # table + key-value combination
        st.builds(
            lambda t, kv: t + "\n" + kv,
            _table(),
            _key_value(1),
        ),
        # array-of-tables sequence
        st.builds(
            lambda t, kv1, kv2: t + "\n" + kv1 + "\n" + kv2,
            _array_table(),
            _key_value(1),
            _key_value(1),
        ),
    )

strategy = _document()
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.