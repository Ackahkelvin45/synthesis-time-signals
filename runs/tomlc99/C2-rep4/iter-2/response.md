```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"
_oct = "01234567"
_bin = "01"
_dec = "0123456789"

# bare keys must be A-Za-z0-9_- only
_bare_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

def _bare_key():
    return st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)

# ---------- strings ----------

_escapes = ["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]

def _unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\u%04X" % n if n <= 0xFFFF else "\\U%08X" % n
    )

def _basic_string_body_char():
    # non-ASCII text, control bytes (except we avoid raw NUL), quotes escaped
    return st.one_of(
        st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                                       blacklist_characters='"\\'),
                min_size=0, max_size=8),
        st.text(alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
                min_size=0, max_size=6),
        st.just("\x01"),
        st.just("\x02"),
        st.just("\x7f"),
        st.just("\t"),
        st.just("\r"),
        st.just("\x1f"),
        st.just("\x0b"),
        st.just("\x0c"),
        st.just("\x00".replace("\x00", "")),  # never emit raw NUL
    )

def _basic_string():
    body = st.lists(
        st.one_of(_basic_string_body_char(),
                  st.sampled_from(_escapes),
                  _unicode_escape()),
        max_size=10,
    ).map("".join)
    return st.builds(lambda b: '"' + b + '"', body)

def _literal_string():
    body = st.lists(
        st.one_of(
            st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                                           blacklist_characters="'\n"),
                    min_size=0, max_size=8),
            st.text(alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
                    min_size=0, max_size=6),
            st.just("\x01"),
            st.just("\t"),
            st.just("\r"),
        ),
        max_size=10,
    ).map("".join)
    return st.builds(lambda b: "'" + b + "'", body)

def _ml_basic_string():
    body = st.lists(
        st.one_of(_basic_string_body_char(),
                  st.sampled_from(_escapes),
                  _unicode_escape(),
                  st.just("\n"),
                  st.just("\r\n"),
                  st.just("\\\n")),  # line-ending backslash
        max_size=12,
    ).map("".join)
    # avoid accidental triple-quote termination issues by keeping it simple
    return st.builds(lambda b: '"""' + b.replace('"""', '""\\"') + '"""', body)

def _ml_literal_string():
    body = st.lists(
        st.one_of(
            st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                                           blacklist_characters="'"),
                    min_size=0, max_size=8),
            st.text(alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
                    min_size=0, max_size=6),
            st.just("\n"),
            st.just("\t"),
            st.just("\x01"),
        ),
        max_size=12,
    ).map("".join)
    return st.builds(lambda b: "'''" + b.replace("'''", "''") + "'''", body)

def _any_string():
    return st.one_of(_basic_string(), _literal_string(),
                     _ml_basic_string(), _ml_literal_string())

# ---------- numbers ----------

def _dec_int():
    digits = st.text(alphabet=_dec, min_size=1, max_size=20)
    return st.one_of(
        digits,
        st.builds(lambda s: "0" + s, digits),  # leading zeros accepted
        st.builds(lambda s: "+" + s, digits),
        st.builds(lambda s: "-" + s, digits),
        st.just("0"),
        st.just("007"),
        st.text(alphabet=_dec + "_", min_size=1, max_size=25),
        st.just("9223372036854775808"),   # beyond 64-bit
        st.just("-9223372036854775809"),
        st.just("99999999999999999999999999999999999999"),
    )

def _hex_int():
    body = st.text(alphabet=_hex, min_size=1, max_size=16)
    return st.one_of(
        st.builds(lambda s: "0x" + s, body),
        st.just("0x0"),
        st.just("0xDEAD_BEEF"),
        st.just("0xFFFFFFFFFFFFFFFFFFFF"),
    )

def _oct_int():
    body = st.text(alphabet=_oct, min_size=1, max_size=16)
    return st.one_of(
        st.builds(lambda s: "0o" + s, body),
        st.just("0o0"),
        st.just("0o7_5_5"),
    )

def _bin_int():
    body = st.text(alphabet=_bin, min_size=1, max_size=16)
    return st.one_of(
        st.builds(lambda s: "0b" + s, body),
        st.just("0b0"),
        st.just("0b1_0_1"),
    )

def _int():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    digits = st.text(alphabet=_dec, min_size=1, max_size=18)
    frac = st.text(alphabet=_dec, min_size=1, max_size=18)
    exp = st.text(alphabet=_dec, min_size=1, max_size=4)
    return st.one_of(
        st.builds(lambda a, b: a + "." + b, digits, frac),
        st.builds(lambda a, b, c: a + "." + b + "e" + c, digits, frac, exp),
        st.builds(lambda a, b: a + "." + b + "E+" + b, digits, frac),
        st.builds(lambda a, b: a + "." + b + "e-" + b, digits, frac),
        st.builds(lambda a: a + "e" + "309", digits),   # huge exponent
        st.builds(lambda a: a + "E-309", digits),
        st.just("1."),        # no digit after dot (accepted)
        st.just(".5"),        # no leading digit (accepted)
        st.just("1e309"),
        st.just("-1e309"),
        st.just("inf"),
        st.just("+inf"),
        st.just("-inf"),
        st.just("nan"),
        st.just("+nan"),
        st.just("-nan"),
        st.just("0.0"),
        st.just("1_000.000_1"),
        st.builds(lambda a, b: a + "." + b, digits.map(lambda s: s + "_" + s), frac),
    )

# ---------- booleans ----------

def _bool():
    return st.sampled_from(["true", "false"])

# ---------- dates ----------

def _d2():
    return st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

def _year():
    return st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)

def _date():
    return st.builds(lambda y, m, d: y + "-" + m + "-" + d, _year(), _d2(), _d2())

def _time_part():
    return st.builds(lambda h, m, s: h + ":" + m + ":" + s, _d2(), _d2(), _d2())

def _local_time():
    return st.one_of(
        _time_part(),
        st.builds(lambda t, f: t + "." + f, _time_part(),
                  st.text(alphabet=_dec, min_size=1, max_size=6)),
    )

def _offset():
    return st.one_of(
        st.just("Z"),
        st.just("z"),
        st.builds(lambda s, h, m: s + h + ":" + m,
                  st.sampled_from(["+", "-"]), _d2(), _d2()),
    )

def _date_time():
    delim = st.sampled_from(["T", "t", " "])
    return st.one_of(
        _date(),
        _local_time(),
        st.builds(lambda d, dl, t: d + dl + t, _date(), delim, _local_time()),
        st.builds(lambda d, dl, t, o: d + dl + t + o, _date(), delim, _local_time(), _offset()),
        st.just("1979-02-30"),   # calendar-invalid, accepted
        st.just("1979-05-27 07:32:00Z"),
        st.just("1979-05-27T07:32:00.999999-07:00"),
    )

# ---------- keys ----------

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_bare_key(), _quoted_key(), st.just('""'))

def _key():
    return st.one_of(
        _simple_key(),
        st.lists(_simple_key(), min_size=2, max_size=4).map(".".join),
    )

# ---------- recursive values ----------

def _value(depth):
    if depth <= 0:
        return st.one_of(_any_string(), _int(), _float(), _bool(), _date_time())
    return st.one_of(
        _any_string(), _int(), _float(), _bool(), _date_time(),
        _array(depth - 1),
        _inline_table(depth - 1),
    )

def _array(depth):
    inner = _value(depth)
    return st.builds(
        lambda elems, trailing: "[" + ", ".join(elems) + ("," if trailing and elems else "") + "]",
        st.lists(inner, max_size=5),
        st.booleans(),
    )

def _inline_table_keyvals_non_empty(depth):
    inner = _value(depth)
    pair = st.builds(lambda k, v: k + " = " + v, _key(), inner)
    return st.builds(
        lambda pairs: "{" + ", ".join(pairs) + "}",
        st.lists(pair, min_size=1, max_size=4),
    )

def _inline_table(depth):
    inner = _value(depth)
    pair = st.builds(lambda k, v: k + " = " + v, _key(), inner)
    return st.one_of(
        st.builds(
            lambda pairs, trailing: "{" + ", ".join(pairs) + ("," if trailing and elems(pairs) else "") + "}",
            st.lists(pair, max_size=4),
            st.booleans(),
        ),
        _inline_table_keyvals_non_empty(depth),
    )

def _value_top():
    # deep nesting concentrated in the 1500-2048 band
    deep = st.integers(min_value=1500, max_value=2048)
    return st.one_of(
        _value(3),
        deep.flatmap(lambda d: st.just("[" * d + "]" * d)),
        deep.flatmap(lambda d: st.just("[" * d + "1" + "]" * d)),
        deep.flatmap(lambda d: st.just("[" * d + "{" + "}" + "]" * d)),
    )

# ---------- documents ----------

def _comment():
    return st.one_of(
        st.just(""),
        st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E,
                                       blacklist_characters="\n"),
                min_size=0, max_size=20).map(lambda s: "#" + s),
        st.just("#\x01\x02"),  # raw control char in comment (accepted)
    )

def _key_value():
    return st.builds(lambda k, v, c: k + " = " + v + c, _key(), _value_top(), _comment())

def _standard_table():
    return st.builds(lambda k, c: "[" + k + "]" + c, _key(), _comment())

def _array_table():
    return st.builds(lambda k, c: "[[" + k + "]]" + c, _key(), _comment())

def _line():
    return st.one_of(_key_value(), _standard_table(), _array_table(), _comment())

def _document():
    lines = st.lists(_line(), max_size=8)
    sep = st.sampled_from(["\n", "\r\n"])
    return st.builds(lambda ls, s: s.join(ls), lines, sep)

# ---------- malformed / near-valid ----------

def _malformed():
    return st.one_of(
        st.just("a = \"unterminated"),
        st.just("a = 'unterminated"),
        st.just('a = """unterminated'),
        st.just("a = [[1, 2]"),
        st.just("a = [1, 2]]"),
        st.just("a = {b = 1"),
        st.just("a = {b = 1}}"),
        st.just("[table"),
        st.just("[[table]"),
        st.just("a = "),
        st.just("= 1"),
        st.just("a 1"),
        st.just("a = 1 2"),
        st.just("a = {b = 1\n}"),       # newline inside inline table -> reject
        st.just("a = \"\\q\""),          # invalid escape -> reject
        st.just("a = 1\nb = 2\nc = 3\n"),
        st.just("\x01\x02\x03"),
        st.just("]]]"),
        st.just("{"),
        st.just("}"),
        st.just("["),
        st.just("]"),
        st.just("a.b.c = 1\na.b.c = 2"),  # duplicate via dotted key -> reject
        st.just("[t]\n[t]"),              # duplicate table -> reject
        st.just("a = 1\na = 2"),          # duplicate key -> reject
        st.just("caf\u00e9 = 1"),         # non-ASCII bare key -> reject
        st.just("a = 1\nb =\n2"),         # value on next line -> reject
    )

# ---------- top-level strategy ----------

def _complete_or_malformed():
    return st.one_of(
        _document(),
        _malformed(),
        st.just(""),
        st.just("\n"),
        st.just("# only a comment"),
        st.just("[t]\n"),
        st.just("[[a]]\n"),
        st.just("a = {}\n"),
        st.just("a = []\n"),
        st.just('"" = 1\n'),
        st.just("a = 007\n"),
        st.just("a = 1.\n"),
        st.just("a = .5\n"),
        st.just("a = {b = 1,}\n"),
        st.just("a = 1979-02-30\n"),
        st.just("a = \"x\x01y\"\n"),
        st.just("a = 1_000\n"),
        st.just("a = 0xDEAD_BEEF\n"),
        st.just("a = 0o755\n"),
        st.just("a = 0b1010\n"),
        st.just("a = inf\nb = nan\nc = -inf\n"),
        st.just("a = 1e309\n"),
    )

strategy = _complete_or_malformed()
```