```python
import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

# characters that are safe inside strings (no raw NUL)
_SAFE = st.characters(blacklist_characters="\x00")

_BARE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

def _text(min_size=0, max_size=12, alphabet=_SAFE):
    return st.text(alphabet=alphabet, min_size=min_size, max_size=max_size)


# ---------------------------------------------------------------------------
# strings (all four quoting forms)
# ---------------------------------------------------------------------------

_ESCAPES = ["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]

def _unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda v: "\\u%04x" % v if v <= 0xFFFF else "\\U%08x" % v
    )

_BASIC_BODY_CHAR = st.one_of(
    st.sampled_from(_ESCAPES),
    _unicode_escape(),
    st.characters(blacklist_characters='"\x00\n\\'),
)

def _basic_string():
    return st.lists(_BASIC_BODY_CHAR, max_size=8).map(lambda cs: '"' + "".join(cs) + '"')

def _literal_string():
    return st.lists(
        st.characters(blacklist_characters="'\x00\n"), max_size=8
    ).map(lambda cs: "'" + "".join(cs) + "'")

def _ml_basic_string():
    body = st.one_of(
        st.sampled_from(_ESCAPES),
        _unicode_escape(),
        st.characters(blacklist_characters='"\x00\\'),
    )
    return st.lists(body, max_size=8).map(lambda cs: '"""' + "".join(cs) + '"""')

def _ml_literal_string():
    return st.lists(
        st.characters(blacklist_characters="'\x00"), max_size=8
    ).map(lambda cs: "'''" + "".join(cs) + "'''")

def _any_string():
    return st.one_of(
        _basic_string(), _literal_string(), _ml_basic_string(), _ml_literal_string()
    )


# ---------------------------------------------------------------------------
# numbers
# ---------------------------------------------------------------------------

def _dec_int():
    digits = st.integers(min_value=0, max_value=9)
    return st.one_of(
        st.integers(min_value=-10**30, max_value=10**30).map(str),
        st.integers(min_value=0, max_value=10**30).map(str),
        st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
        st.integers(min_value=0, max_value=10**12).map(
            lambda n: "{:,}".format(n).replace(",", "_")
        ),
    )

def _hex_int():
    return st.integers(min_value=0, max_value=2**80).map(hex)

def _oct_int():
    return st.integers(min_value=0, max_value=2**40).map(oct)

def _bin_int():
    return st.integers(min_value=0, max_value=2**40).map(bin)

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    def mk(sign, mant, exp):
        s = str(sign) if sign else ""
        return s + mant + exp
    sign = st.sampled_from(["", "-", "+"])
    mant = st.one_of(
        st.integers(min_value=0, max_value=10**6).map(str),
        st.integers(min_value=0, max_value=10**6).map(lambda n: str(n) + "."),
        st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
        st.integers(min_value=0, max_value=10**6).map(lambda n: str(n) + ".5"),
    )
    exp = st.one_of(
        st.just(""),
        st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
        st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(e)),
    )
    return st.builds(mk, sign, mant, exp)

def _inf_nan():
    return st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan", "+nan"])

def _inf():
    return st.sampled_from(["inf", "+inf", "-inf"])

def _number():
    return st.one_of(_integer(), _float(), _inf(), _inf_nan())


# ---------------------------------------------------------------------------
# dates
# ---------------------------------------------------------------------------

def _date():
    y = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
    m = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
    d = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
    return st.tuples(y, m, d).map(lambda t: "%s-%s-%s" % t)

def _time():
    h = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
    mi = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
    s = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
    frac = st.one_of(
        st.just(""),
        st.integers(min_value=0, max_value=10**6).map(lambda n: ".%06d" % n),
    )
    return st.tuples(h, mi, s, frac).map(lambda t: "%s:%s:%s%s" % t)

def _date_time():
    date = _date()
    time = _time()
    sep = st.sampled_from(["T", "t", " "])
    offset = st.one_of(
        st.just("Z"),
        st.tuples(
            st.sampled_from(["+", "-"]),
            st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
            st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        ).map(lambda t: "%s%s:%s" % t),
    )
    return st.one_of(
        date,
        time,
        st.tuples(date, sep, time).map(lambda t: "%s%s%s" % t),
        st.tuples(date, sep, time, offset).map(lambda t: "%s%s%s%s" % t),
    )


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------

def _bare_key():
    return st.text(alphabet=_BARE_CHARS, min_size=1, max_size=10)

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_bare_key(), _quoted_key())

def _dotted_key():
    parts = st.lists(_simple_key(), min_size=2, max_size=4)
    return parts.map(lambda ps: ".".join(ps))

def _key():
    return st.one_of(_simple_key(), _dotted_key())


# ---------------------------------------------------------------------------
# recursive values (arrays, inline tables)
# ---------------------------------------------------------------------------

def _leaf_value():
    return st.one_of(
        _any_string(),
        _number(),
        st.sampled_from(["true", "false"]),
        _date_time(),
    )

def _value_strategy():
    return st.recursive(
        _leaf_value(),
        lambda children: st.one_of(
            _array_of(children),
            _inline_table_of(children),
        ),
        max_leaves=30,
    )

def _array_of(child):
    inner = st.lists(child, max_size=4)
    def render(items):
        return "[" + ", ".join(items) + "]"
    return inner.map(render)

def _inline_table_of(child):
    def mk(pairs):
        return "{" + ", ".join("%s = %s" % (k, v) for k, v in pairs) + "}"
    return st.lists(st.tuples(_key(), child), max_size=3).map(mk)


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------

def _key_value():
    return st.tuples(_key(), _value_strategy()).map(lambda t: "%s = %s" % t)

def _standard_table():
    return _key().map(lambda k: "[%s]" % k)

def _array_table():
    return _key().map(lambda k: "[[%s]]" % k)

def _line():
    return st.one_of(
        _key_value(),
        _standard_table(),
        _array_table(),
        st.just(""),
        st.text(alphabet=st.characters(blacklist_characters="\x00\n"), max_size=20).map(
            lambda s: "# " + s
        ),
    )

def _document():
    return st.lists(_line(), max_size=12).map(lambda ls: "\n".join(ls))


# ---------------------------------------------------------------------------
# deep nesting band (1500-2048)
# ---------------------------------------------------------------------------

def _deep_array():
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(lambda d: "[" * d + "1" + "]" * d)

def _deep_inline():
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(lambda d: "a = " + "{a = " * d + "1" + "}" * d)


# ---------------------------------------------------------------------------
# malformed / near-valid inputs
# ---------------------------------------------------------------------------

def _malformed():
    return st.one_of(
        st.just('a = "unterminated'),
        st.just("a = 'unterminated"),
        st.just('a = """unterminated'),
        st.just("a = [1, 2"),
        st.just("a = {b = 1"),
        st.just("a = 1 2 3"),
        st.just("[table"),
        st.just("[[table]"),
        st.just("a = "),
        st.just("= 1"),
        st.just("a = {b = 1,\nc = 2}"),
        st.just("a = 1\nb = 2\nb = 3"),
        st.just("[t]\n[t]"),
        st.just("a = 1\n[t]\na = 2"),
        st.just("a = {b = 1,}"),
        st.just("a = [1, 2,]"),
        st.just("007 = 1"),
        st.just("a = 1e309"),
        st.just("a = 1979-02-30"),
        st.just("a = .5"),
        st.just("a = 1."),
        st.just("a = 0x"),
        st.just("a = 0o"),
        st.just("a = 0b"),
        st.just("a = \\q"),
        st.just("a = \"\\q\""),
        st.just("a = 1\n\n\n"),
        st.just(""),
        st.just("# only a comment"),
        st.just("a = true\nb = false\nc = true"),
        st.just("a = \"\"\"\nmulti\nline\n\"\"\""),
        st.just("a = '''\nmulti\nline\n'''"),
        st.just("a = 1\nb = 2\nc = 3\nd = 4\ne = 5"),
        st.just("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6"),
        st.just("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\ng = 7"),
        st.just("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\ng = 7\nh = 8"),
        st.just("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\ng = 7\nh = 8\ni = 9"),
    )


# ---------------------------------------------------------------------------
# top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document(),
    _deep_array(),
    _deep_inline(),
    _malformed(),
    _inf().map(lambda s: "a = " + s),
)
```