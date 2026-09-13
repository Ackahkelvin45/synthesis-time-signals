from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _chars(s):
    return st.sampled_from(list(s))

DIGITS = "0123456789"
HEXD = "0123456789abcdefABCDEF"
OCTD = "01234567"
BIND = "01"
ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BARE = ALPHA + DIGITS + "-_"

# control chars and other string content (no raw NUL)
CTRL = [chr(c) for c in range(1, 32)] + [chr(127)]
NONASCII = [chr(c) for c in list(range(0x80, 0x2000)) + [0x1F600, 0x10FFFF, 0x2028, 0x2029]]
RAWCONTENT = list(DIGITS + ALPHA + " \t-_.,;:!?@#$%^&*()+=<>/|~`") + CTRL + NONASCII

ESCAPES = ['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t', '\\/', '\\u0000',
           '\\u0041', '\\uFFFF', '\\uD83D', '\\U0001F600', '\\U0010FFFF',
           '\\q', '\\x41', '\\u12', '\\U0001F60', '\\' ]

# ---------- keys ----------

def _unquoted_key():
    return st.text(alphabet=BARE, min_size=1, max_size=12)

def _quoted_key():
    return st.one_of(
        _basic_string(),
        _literal_string(),
    )

def _simple_key():
    return st.one_of(_unquoted_key(), _quoted_key())

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(lambda ks: ".".join(ks))

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------- strings ----------

def _basic_body():
    return st.one_of(
        st.text(alphabet=RAWCONTENT, min_size=0, max_size=20),
        st.lists(st.sampled_from(ESCAPES), min_size=1, max_size=4).map(lambda xs: "".join(xs)),
        st.lists(st.one_of(st.sampled_from(RAWCONTENT), st.sampled_from(ESCAPES)),
                 min_size=0, max_size=12).map(lambda xs: "".join(xs)),
    )

def _basic_string():
    return _basic_body().map(lambda b: '"' + b + '"')

def _literal_string():
    body = st.one_of(
        st.text(alphabet=[c for c in RAWCONTENT if c not in "'"], min_size=0, max_size=20),
        st.just(""),
    )
    return body.map(lambda b: "'" + b + "'")

def _ml_basic_string():
    body = st.one_of(
        st.text(alphabet=[c for c in RAWCONTENT if c not in '"'], min_size=0, max_size=20),
        st.lists(st.one_of(st.sampled_from([c for c in RAWCONTENT if c not in '"']),
                           st.sampled_from(ESCAPES)), min_size=0, max_size=10).map(lambda xs: "".join(xs)),
    )
    return body.map(lambda b: '"""' + b + '"""')

def _ml_literal_string():
    body = st.text(alphabet=[c for c in RAWCONTENT if c not in "'"], min_size=0, max_size=20)
    return body.map(lambda b: "'''" + b + "'''")

def _string():
    return st.one_of(_basic_string(), _literal_string(), _ml_basic_string(), _ml_literal_string())

# ---------- numbers ----------

def _dec_int():
    return st.one_of(
        st.integers(min_value=-2**70, max_value=2**70).map(str),
        st.integers(min_value=-1000, max_value=1000).map(lambda n: ("%d" % n)),
        st.just("007"),
        st.just("00"),
        st.just("+0"),
        st.just("-0"),
        st.just("1_000"),
        st.just("1_2_3_4_5"),
        st.just("0"),
    )

def _hex_int():
    return st.one_of(
        st.text(alphabet=HEXD, min_size=1, max_size=8).map(lambda s: "0x" + s),
        st.just("0xDEADBEEF"),
        st.just("0x_1"),
    )

def _oct_int():
    return st.one_of(
        st.text(alphabet=OCTD, min_size=1, max_size=8).map(lambda s: "0o" + s),
        st.just("0o777"),
        st.just("0o8"),
    )

def _bin_int():
    return st.one_of(
        st.text(alphabet=BIND, min_size=1, max_size=16).map(lambda s: "0b" + s),
        st.just("0b1010_1010"),
        st.just("0b2"),
    )

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    return st.one_of(
        st.tuples(
            st.integers(min_value=-10**6, max_value=10**6).map(str),
            st.integers(min_value=-400, max_value=400).map(str),
        ).map(lambda t: t[0] + "e" + t[1]),
        st.tuples(
            st.integers(min_value=-1000, max_value=1000).map(str),
            st.integers(min_value=0, max_value=10**6).map(str),
        ).map(lambda t: t[0] + "." + t[1]),
        st.tuples(
            st.integers(min_value=-10, max_value=10).map(str),
            st.integers(min_value=0, max_value=100).map(str),
            st.integers(min_value=-300, max_value=300).map(str),
        ).map(lambda t: t[0] + "." + t[1] + "e" + t[2]),
        st.just("1."),
        st.just(".5"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1_0.0_1"),
        st.just("0.0"),
        st.just("+0.0"),
    )

def _inf_nan():
    return st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan",
                            "INF", "NaN", "infinity", "nanx"])

def _bool():
    return st.sampled_from(["true", "false", "True", "FALSE", "tru"])

# ---------- dates ----------

def _d2():
    return st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

def _year():
    return st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)

def _date():
    return st.tuples(_year(), _d2(), _d2()).map(lambda t: "%s-%s-%s" % t)

def _time():
    return st.tuples(_d2(), _d2(), _d2()).map(lambda t: "%s:%s:%s" % t)

def _time_frac():
    return st.tuples(_time(), st.integers(min_value=0, max_value=10**6).map(str)).map(
        lambda t: t[0] + "." + t[1])

def _offset():
    return st.sampled_from(["Z", "z", "+00:00", "-05:30", "+99:99", "+1:00", "Zx"])

def _date_time():
    return st.one_of(
        _date(),
        _time(),
        _time_frac(),
        st.tuples(_date(), _time()).map(lambda t: t[0] + "T" + t[1]),
        st.tuples(_date(), _time()).map(lambda t: t[0] + " " + t[1]),
        st.tuples(_date(), _time(), _offset()).map(lambda t: t[0] + "T" + t[1] + t[2]),
        st.tuples(_date(), _time_frac(), _offset()).map(lambda t: t[0] + "T" + t[1] + t[2]),
        st.just("1979-02-30"),
        st.just("1979-05-27 07:32:00Z"),
        st.just("1979-05-27t07:32:00+00:00"),
        st.just("0000-00-00"),
    )

# ---------- recursive values ----------

def _scalar_value():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _inf_nan(),
        _bool(),
        _date_time(),
    )

def _value():
    return _recursive_value()

# ---------- inline tables / arrays ----------

def _inline_table_pairs():
    return st.lists(
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1]),
        min_size=0,
        max_size=4,
    )

def _inline_table():
    return _inline_table_pairs().map(lambda ps: "{" + ", ".join(ps) + "}")

def _inline_table_trailing_comma():
    return _inline_table_pairs().map(
        lambda ps: "{" + ", ".join(ps) + ("," if ps else "") + "}")

def _inline_table_nl():
    return _inline_table_pairs().map(
        lambda ps: "{" + ",\n".join(ps) + "}")

def _array_elems():
    return st.lists(_value(), min_size=0, max_size=5)

def _array():
    return _array_elems().map(lambda vs: "[" + ", ".join(vs) + "]")

def _array_nl():
    return _array_elems().map(lambda vs: "[\n" + ",\n".join(vs) + "\n]")

def _array_trailing_comma():
    return _array_elems().map(
        lambda vs: "[" + ", ".join(vs) + ("," if vs else "") + "]")

def _array_mixed_comment():
    return _array_elems().map(
        lambda vs: "[\n# c\n" + ",\n".join(vs) + ",\n]")

def _recursive_value():
    return st.recursive(
        _scalar_value(),
        lambda children: st.one_of(
            children.map(lambda v: "[" + v + "]"),
            children.map(lambda v: "[" + v + ", " + v + "]"),
            st.lists(children, min_size=0, max_size=4).map(lambda vs: "[" + ", ".join(vs) + "]"),
            st.lists(children, min_size=0, max_size=4).map(lambda vs: "[\n" + ",\n".join(vs) + "\n]"),
            _inline_table().map(lambda s: s),
            st.tuples(_key(), children).map(lambda t: "{" + t[0] + " = " + t[1] + "}"),
            st.lists(st.tuples(_key(), children).map(lambda t: t[0] + " = " + t[1]),
                     min_size=1, max_size=3).map(lambda ps: "{" + ", ".join(ps) + "}"),
        ),
        max_leaves=12,
    )

# ---------- deep nesting (concentrate in 1500-2048 band) ----------

def _deep_array():
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(lambda n: "[" * n + "]" * n)

def _deep_array_with_value():
    return st.tuples(
        st.integers(min_value=1500, max_value=2048),
        _scalar_value(),
    ).map(lambda t: "[" * t[0] + t[1] + "]" * t[0])

def _deep_inline_table():
    depth = st.integers(min_value=200, max_value=600)
    return depth.map(lambda n: "{a = " * n + "1" + "}" * n)

# ---------- document assembly ----------

def _key_value_line():
    return st.one_of(
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _value()).map(lambda t: t[0] + "=" + t[1]),
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1] + " # c"),
        st.tuples(_key(), _deep_array()).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _deep_array_with_value()).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _deep_inline_table()).map(lambda t: t[0] + " = " + t[1]),
    )

def _malformed_line():
    return st.one_of(
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1] + '"'),
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1] + "]"),
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1] + "}"),
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1] + " = " + t[1]),
        st.tuples(_key(), _value()).map(lambda t: t[0] + " " + t[1]),
        st.tuples(_key(), _value()).map(lambda t: t[0] + " == " + t[1]),
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1] + ","),
        st.tuples(_key(), _value()).map(lambda t: "=" + t[0] + " = " + t[1]),
        st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[1]),
        st.just('a = "unterminated'),
        st.just("a = 'unterminated"),
        st.just('a = """unterminated'),
        st.just("a = '''unterminated"),
        st.just("[["),
        st.just("]]"),
        st.just("{"),
        st.just("}"),
        st.just("["),
        st.just("]"),
        st.just("a = "),
        st.just("= 1"),
        st.just("a = {b = 1\n}"),
        st.just("a = \x01"),
        st.just("a = 1\x02"),
    )

def _table_line():
    return st.one_of(
        _key().map(lambda k: "[" + k + "]"),
        _key().map(lambda k: "[[" + k + "]]"),
        st.just("[]"),
        st.just("[[]]"),
        st.just("[.a]"),
        st.just("[[a]"),
        st.just("[a]]"),
        st.just("[a"),
        st.just("[]]"),
    )

def _comment_line():
    return st.one_of(
        st.just("#"),
        st.just("# comment"),
        st.text(alphabet=RAWCONTENT, min_size=0, max_size=30).map(lambda s: "# " + s),
    )

def _blank_line():
    return st.sampled_from(["", " ", "\t", "\r"])

def _line():
    return st.one_of(
        _key_value_line(),
        _table_line(),
        _comment_line(),
        _blank_line(),
        _malformed_line(),
    )

def _document():
    return st.one_of(
        st.lists(_line(), min_size=0, max_size=12).map(lambda ls: "\n".join(ls)),
        st.lists(_line(), min_size=1, max_size=12).map(lambda ls: "\n".join(ls) + "\r\n"),
        st.lists(_line(), min_size=1, max_size=12).map(lambda ls: "\n".join(ls)),
        st.lists(_line(), min_size=1, max_size=12).map(lambda ls: "\n\n".join(ls) + "\n"),
    )

# ---------- final strategy ----------

strategy = st.one_of(
    _document(),
    _key_value_line(),
    _deep_array(),
    _deep_array_with_value(),
    _deep_inline_table(),
    _malformed_line(),
    _table_line(),
    st.just(""),
    st.just("# only comment"),
    st.just('"" = 1'),
    st.just("a = {b = 1,}"),
    st.just("a = [1, 2,]"),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just('a = "x\x01y"'),
    st.just("a = 1979-02-30"),
    st.just('a = "\\u0000"'),
)