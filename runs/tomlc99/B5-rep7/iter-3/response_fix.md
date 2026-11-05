```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _no_nul(s):
    return s.replace("\x00", "")

_bare_chars = st.sampled_from(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
)

_bare_key = st.one_of(
    st.just(""),
    st.text(_bare_chars, min_size=1, max_size=20),
    st.text(_bare_chars, min_size=10000, max_size=10000),
)

_hex = st.sampled_from("0123456789abcdefABCDEF")

_unicode_esc = st.builds(
    lambda h: "\\u" + h,
    st.text(_hex, min_size=4, max_size=4),
)
_ex_unicode_esc = st.builds(
    lambda h: "\\U" + h,
    st.text(_hex, min_size=8, max_size=8),
)
_simple_esc = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_esc = st.one_of(_simple_esc, _unicode_esc, _ex_unicode_esc)

_basic_body_char = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\\n\x00'),
    st.just("\x01"),
    st.just("\x7f"),
    st.just("\t"),
)

_basic_string = st.builds(
    lambda parts: '"' + _no_nul("".join(parts)) + '"',
    st.lists(st.one_of(_esc, _basic_body_char), max_size=12),
)

_literal_body_char = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters="'\n\x00"),
    st.just("\x01"),
    st.just("\t"),
)

_literal_string = st.builds(
    lambda parts: "'" + _no_nul("".join(parts)) + "'",
    st.lists(_literal_body_char, max_size=12),
)

_ml_basic_string = st.builds(
    lambda parts: '"""' + _no_nul("".join(parts)) + '"""',
    st.lists(
        st.one_of(
            _esc,
            st.just("\\\n"),
            st.just("\\\r\n"),
            st.characters(blacklist_categories=("Cs",), blacklist_characters='\\\x00'),
        ),
        max_size=10,
    ),
)

_ml_literal_string = st.builds(
    lambda parts: "'''" + _no_nul("".join(parts)) + "'''",
    st.lists(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        max_size=10,
    ),
)

_any_string = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# ---------- numbers ----------

_digit = st.sampled_from("0123456789")
_digit_1_9 = st.sampled_from("123456789")
_hexd = st.sampled_from("0123456789abcdefABCDEF")
_octd = st.sampled_from("01234567")
_bind = st.sampled_from("01")

def _digits_str(d, min_size=1, max_size=25):
    return st.text(d, min_size=min_size, max_size=max_size)

_dec_int = st.one_of(
    st.builds(lambda s, d: s + d, st.sampled_from(["", "+", "-"]), _digits_str(_digit, 1, 25)),
    st.builds(
        lambda s, a, rest: s + a + rest,
        st.sampled_from(["", "+", "-"]),
        _digit_1_9,
        st.text(st.one_of(_digit, st.just("_")), max_size=30),
    ),
    st.just("007"),
    st.just("-0"),
    st.just("+" + "9" * 40),
    st.just("-" + "9" * 40),
)

_hex_int = st.builds(
    lambda body: "0x" + body,
    st.text(st.one_of(_hexd, st.just("_")), min_size=1, max_size=30),
)
_oct_int = st.builds(
    lambda body: "0o" + body,
    st.text(st.one_of(_octd, st.just("_")), min_size=1, max_size=30),
)
_bin_int = st.builds(
    lambda body: "0b" + body,
    st.text(st.one_of(_bind, st.just("_")), min_size=1, max_size=30),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_frac = st.builds(
    lambda d: "." + d,
    st.text(st.one_of(_digit, st.just("_")), min_size=1, max_size=20),
)
_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(st.one_of(_digit, st.just("_")), min_size=1, max_size=10),
)

_float = st.one_of(
    st.builds(lambda i, f: i + f, _dec_int, _frac),
    st.builds(lambda i, e: i + e, _dec_int, _exp),
    st.builds(lambda i, f, e: i + f + e, _dec_int, _frac, _exp),
    st.just("1."),
    st.just(".5"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("0.0"),
)

_inf_nan = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
)

_floating = st.one_of(_float, _inf_nan)

# ---------- dates ----------

_yy = st.text(_digit, min_size=4, max_size=4)
_mm = st.text(_digit, min_size=2, max_size=2)
_dd = st.text(_digit, min_size=2, max_size=2)
_hh = st.text(_digit, min_size=2, max_size=2)
_mi = st.text(_digit, min_size=2, max_size=2)
_ss = st.text(_digit, min_size=2, max_size=2)
_secfrac = st.builds(lambda d: "." + d, st.text(_digit, min_size=1, max_size=9))

_full_date = st.builds(lambda a, b, c: a + "-" + b + "-" + c, _yy, _mm, _dd)
_partial_time = st.builds(
    lambda h, m, s, f: h + ":" + m + ":" + s + f,
    _hh, _mi, _ss, st.one_of(st.just(""), _secfrac),
)
_offset = st.one_of(
    st.just("Z"),
    st.builds(lambda s, h, m: s + h + ":" + m,
              st.sampled_from(["+", "-"]), _hh, _mi),
)
_delim = st.sampled_from(["T", "t", " "])

_offset_dt = st.builds(
    lambda d, dl, t, o: d + dl + t + o, _full_date, _delim, _partial_time, _offset
)
_local_dt = st.builds(
    lambda d, dl, t: d + dl + t, _full_date, _delim, _partial_time
)
_local_date = _full_date
_local_time = _partial_time

_datetime = st.one_of(
    _offset_dt, _local_dt, _local_date, _local_time,
    st.just("1979-02-30"),
    st.just("1979-05-27 07:32:00Z"),
)

# ---------- keys ----------

_quoted_key = st.one_of(_basic_string, _literal_string)

def _simple_key():
    return st.one_of(_quoted_key, _bare_key)

def _dotted_key():
    return st.builds(
        lambda parts: ".".join(parts),
        st.lists(_simple_key(), min_size=2, max_size=4),
    )

_key = st.one_of(_simple_key(), _dotted_key())

# ---------- recursive values ----------

def _leaf_value():
    return st.one_of(
        _any_string,
        _integer,
        _floating,
        st.sampled_from(["true", "false"]),
        _datetime,
    )

def _value(depth):
    if depth <= 0:
        return _leaf_value()
    return st.one_of(
        _leaf_value(),
        _array(depth - 1),
        _inline_table(depth - 1),
    )

def _array(depth):
    inner = _value(depth)
    return st.one_of(
        st.just("[]"),
        st.builds(lambda v: "[" + v + "]", inner),
        st.builds(
            lambda vs: "[" + ", ".join(vs) + "]",
            st.lists(inner, min_size=1, max_size=5),
        ),
        st.builds(
            lambda vs: "[" + ", ".join(vs) + ",]",
            st.lists(inner, min_size=1, max_size=5),
        ),
        st.builds(
            lambda vs: "[\n" + ",\n".join(vs) + "\n]",
            st.lists(inner, min_size=0, max_size=4),
        ),
        st.builds(
            lambda vs: "[\n# c\n" + ",\n".join(vs) + ",\n# d\n]",
            st.lists(inner, min_size=0, max_size=4),
        ),
    )

def _inline_table(depth):
    inner = _value(depth)
    kv = st.builds(lambda k, v: k + " = " + v, _key, inner)
    return st.one_of(
        st.just("{}"),
        st.builds(lambda p: "{" + p + "}", kv),
        st.builds(
            lambda ps: "{" + ", ".join(ps) + "}",
            st.lists(kv, min_size=1, max_size=4),
        ),
        st.builds(
            lambda ps: "{" + ", ".join(ps) + ",}",
            st.lists(kv, min_size=1, max_size=4),
        ),
    )

_value_rec = st.recursive(
    _leaf_value(),
    lambda children: st.one_of(
        st.builds(lambda v: "[" + v + "]", children),
        st.builds(lambda vs: "[" + ", ".join(vs) + "]", st.lists(children, max_size=4)),
        st.builds(lambda p: "{" + p + "}",
                  st.builds(lambda k, v: k + " = " + v, _key, children)),
        st.builds(lambda ps: "{" + ", ".join(ps) + "}",
                  st.lists(st.builds(lambda k, v: k + " = " + v, _key, children),
                           max_size=4)),
    ),
    max_leaves=20,
)

# ---------- deep nesting band ----------

def _deep_array(depth):
    return st.builds(
        lambda d, v: "[" * d + v + "]" * d,
        st.integers(min_value=1, max_value=depth),
        _leaf_value(),
    )

_deep = st.one_of(
    _deep_array(2048),
    st.builds(
        lambda d: "[" * d + "]" * d,
        st.integers(min_value=1500, max_value=2048),
    ),
)

# ---------- document structure ----------

_comment = st.builds(
    lambda body: "#" + body,
    st.text(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\x00"),
        max_size=30,
    ),
)

_kv_line = st.builds(
    lambda k, v, c: k + " = " + v + c,
    _key,
    st.one_of(_value_rec, _deep),
    st.one_of(st.just(""), st.builds(lambda c: " " + c, _comment)),
)

_std_table = st.builds(
    lambda k, c: "[" + k + "]" + c,
    _key,
    st.one_of(st.just(""), st.builds(lambda c: " " + c, _comment)),
)

_array_table = st.builds(
    lambda k, c: "[[" + k + "]]" + c,
    _key,
    st.one_of(st.just(""), st.builds(lambda c: " " + c, _comment)),
)

_expression = st.one_of(
    _kv_line,
    _std_table,
    _array_table,
    _comment,
)

_nl = st.sampled_from(["\n", "\r\n", "\n\n"])

_document = st.builds(
    lambda exprs, trailing: _no_nul("\n").join(exprs) + trailing,
    st.lists(_expression, min_size=0, max_size=8),
    st.sampled_from(["", "\n", "\r\n"]),
)

# ---------- malformed near-valid ----------

def _mangle(s):
    return s

_malformed = st.one_of(
    # unterminated string
    st.builds(lambda body: 'a = "' + body, st.text(
        st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\\n\x00'),
        max_size=10)),
    st.builds(lambda body: "a = '" + body, st.text(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="'\n\x00"),
        max_size=10)),
    # missing / doubled delimiters
    st.just("a = [1, 2"),
    st.just("a = [1, 2]]"),
    st.just("a = {b = 1"),
    st.just("a = {b = 1}}"),
    st.just("[t"),
    st.just("[[t]"),
    st.just("[[t]]]"),
    st.just("a = 1 = 2"),
    # stray token
    st.just("a = @"),
    st.just("a = 1 @ 2"),
    st.just("a b = 1"),
    st.just("= 1"),
    st.just("a ="),
    st.just("a =\n1"),
    # invalid escape
    st.just('a = "\\q"'),
    # bare unicode key
    st.just("café = 1"),
    # duplicate keys
    st.just("a = 1\na = 2"),
    st.just("[t]\n[t]"),
    st.just("[[a]]\n[a]"),
    # newline in inline table
    st.just("a = {b = 1,\nc = 2}"),
    # invalid date-ish
    st.just("a = 1979-13-45T99:99:99Z"),
)

# ---------- combine ----------

_document_full = st.one_of(
    _document,
    st.just(""),
    st.just("# only a comment"),
    st.just("# c\n"),
    st.builds(lambda k, v: k + " = " + v, _key, _deep),
    st.builds(lambda k: "[" + k + "]", _bare_key),
    st.builds(lambda k: "[[" + k + "]]", _bare_key),
    st.just('"" = 1'),
    st.just("a = []"),
    st.just("a = {}"),
    st.just("a = 1_000"),
    st.just("a = 0xDEAD_BEEF"),
    st.just("a = 0o777"),
    st.just("a = 0b1010_1010"),
    st.just("a = 1979-05-27 07:32:00Z"),
    st.just("a = 07:32:00"),
    st.just("a = 1979-05-27T07:32:00"),
    st.just("a = 1979-05-27"),
    st.just('a = "x\\u0000y"'),
    st.just('a = "x\x01y"'),
    st.just("# comment with \x01 control"),
    st.just("a = {b = 1,}"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just("a = 007"),
    st.just("[t]\n"),
    st.just("[[a]]\n[[a]]\n"),
    st.just('a.b.c = 1'),
    st.just('"a.b" = 1'),
    st.just("a = [1, 'x', true, 1979-05-27, [2], {c = 3}]"),
    _malformed,
)

strategy = st.one_of(_document_full, _document, _malformed).map(_no_nul)
```