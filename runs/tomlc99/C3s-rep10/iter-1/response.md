```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------- primitives

def _no_nul(s):
    return s.replace("\x00", "")

_ascii_print = st.characters(min_codepoint=0x20, max_codepoint=0x7E, exclude_characters='"\\\n\r')
_ascii_print_lit = st.characters(min_codepoint=0x20, max_codepoint=0x7E, exclude_characters="'\n\r")
_ascii_any = st.characters(min_codepoint=0x20, max_codepoint=0x7E)
_unicode_text = st.text(
    alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
    min_size=0, max_size=8,
)
_control_bytes = st.sampled_from(["\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x7f", "\t"])

# ---------------------------------------------------------------- escapes

_short_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _u4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4).map(lambda h: "\\u" + h)

def _u8():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8).map(lambda h: "\\U" + h)

_bad_escapes = st.sampled_from(["\\q", "\\x41", "\\u12", "\\U0011FFFF", "\\ ", "\\\x00"])

_escape = st.one_of(_short_escapes, _u4(), _u8())

# ---------------------------------------------------------------- strings

def _basic_body():
    return st.one_of(
        _ascii_print.map(_no_nul),
        _escape,
        _unicode_text.map(_no_nul),
        _control_bytes,
    )

_basic_string = st.lists(_basic_body(), max_size=8).map(lambda parts: '"' + "".join(parts) + '"')

def _literal_body():
    return st.one_of(
        _ascii_print_lit.map(_no_nul),
        _unicode_text.map(_no_nul),
        _control_bytes,
    )

_literal_string = st.lists(_literal_body(), max_size=8).map(lambda parts: "'" + "".join(parts) + "'")

def _ml_basic_body():
    return st.one_of(
        _ascii_print.map(_no_nul),
        _escape,
        _unicode_text.map(_no_nul),
        _control_bytes,
        st.just("\n"),
        st.just("\r\n"),
        st.just("\\\n"),
    )

_ml_basic_string = st.lists(_ml_basic_body(), max_size=6).map(
    lambda parts: '"""' + "".join(parts) + '"""'
)

def _ml_literal_body():
    return st.one_of(
        _ascii_print_lit.map(_no_nul),
        _unicode_text.map(_no_nul),
        _control_bytes,
        st.just("\n"),
        st.just("\r\n"),
    )

_ml_literal_string = st.lists(_ml_literal_body(), max_size=6).map(
    lambda parts: "'''" + "".join(parts) + "'''"
)

# near-valid malformed strings
_unterminated_basic = st.lists(_basic_body(), min_size=0, max_size=5).map(
    lambda parts: '"' + "".join(parts)
)
_unterminated_literal = st.lists(_literal_body(), min_size=0, max_size=5).map(
    lambda parts: "'" + "".join(parts)
)
_unterminated_ml_basic = st.lists(_ml_basic_body(), min_size=0, max_size=4).map(
    lambda parts: '"""' + "".join(parts)
)
_unterminated_ml_literal = st.lists(_ml_literal_body(), min_size=0, max_size=4).map(
    lambda parts: "'''" + "".join(parts)
)
_bad_escape_string = st.lists(
    st.one_of(_basic_body(), _bad_escapes), max_size=6
).map(lambda parts: '"' + "".join(parts) + '"')

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------------------------------------------------------------- numbers

_digit = st.integers(min_value=0, max_value=9).map(str)
_digit19 = st.integers(min_value=1, max_value=9).map(str)
_hexd = st.sampled_from("0123456789abcdefABCDEF")
_octd = st.sampled_from("01234567")
_bind = st.sampled_from("01")

def _join(chars):
    return "".join(chars)

def _underscored(gen, min_len=1):
    def build(n):
        if n <= 0:
            return ""
        parts = []
        for i in range(n):
            if i > 0 and (i % 3 == 0):
                parts.append("_")
            parts.append(gen())
        return "".join(parts)
    return st.integers(min_value=min_len, max_value=12).map(build)

_dec_int = st.one_of(
    st.integers(min_value=0, max_value=9).map(str),
    st.integers(min_value=-2**70, max_value=2**70).map(str),
    st.integers(min_value=0, max_value=2**80).map(str),
    st.sampled_from(["0", "-0", "+0", "007", "000", "0_0", "1_000_000"]),
    _underscored(_digit19, min_len=1),
    st.integers(min_value=0, max_value=2**64).map(lambda n: "+" + str(n)),
    st.integers(min_value=-2**64, max_value=-1).map(str),
    st.sampled_from(["9223372036854775807", "9223372036854775808", "-9223372036854775808",
                     "-9223372036854775809", "99999999999999999999999999999999"]),
)

_hex_int = _underscored(_hexd, min_len=1).map(lambda s: "0x" + s)
_oct_int = _underscored(_octd, min_len=1).map(lambda s: "0o" + s)
_bin_int = _underscored(_bind, min_len=1).map(lambda s: "0b" + s)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_frac = _underscored(_digit, min_len=1).map(lambda s: "." + s)
_exp = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.integers(min_value=-400, max_value=400).map(lambda n: "E+" + str(abs(n))),
    st.sampled_from(["e0", "E0", "e+0", "e-0", "e309", "e-309", "e9999", "E-9999"]),
)

def _float_build():
    return st.one_of(
        st.tuples(_frac, _exp).map(lambda t: "0" + t[0] + t[1]),
        st.tuples(_frac, _exp).map(lambda t: "1" + t[0] + t[1]),
        _frac.map(lambda s: "0" + s),
        _frac.map(lambda s: "1" + s),
        st.tuples(_integer, _exp).map(lambda t: t[0] + t[1]),
        st.just("1."),
        st.just(".5"),
        st.just("-1."),
        st.just("+0."),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-400"),
    )

_float = _float_build()

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan",
                            "Inf", "NaN", "INF", "NAN"])

_floating = st.one_of(_float, _inf_nan)

_bool = st.sampled_from(["true", "false", "True", "FALSE", "tru", "truee"])

# ---------------------------------------------------------------- datetimes

def _year():
    return st.one_of(
        st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n),
        st.sampled_from(["1979", "0000", "9999"]),
    )

def _month():
    return st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

def _day():
    return st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

_full_date = st.tuples(_year(), _month(), _day()).map(lambda t: "%s-%s-%s" % t)

def _time_part():
    return st.tuples(
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
    ).map(lambda t: "%s:%s:%s" % t)

def _secfrac():
    return st.integers(min_value=1, max_value=9).map(
        lambda n: "." + "".join(str((i * 7 + 3) % 10) for i in range(n))
    )

_partial_time = st.tuples(_time_part(), st.one_of(st.none(), _secfrac())).map(
    lambda t: t[0] + (t[1] or "")
)

_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(
        st.sampled_from(["+", "-"]),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
    ).map(lambda t: "%s%s:%s" % t),
)

_delim = st.sampled_from(["T", "t", " "])

_offset_datetime = st.tuples(_full_date, _delim, _partial_time, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)

_local_datetime = st.tuples(_full_date, _delim, _partial_time).map(
    lambda t: t[0] + t[1] + t[2]
)

_local_date = _full_date
_local_time = _partial_time

_datetime = st.one_of(_offset_datetime, _local_datetime, _local_date, _local_time)

# ---------------------------------------------------------------- keys

_unquoted_key = st.text(
    alphabet=st.characters(min_codepoint=ord("A"), max_codepoint=ord("Z")).map(chr).__class__ and
    st.sampled_from(list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")),
    min_size=1, max_size=8,
)

_simple_key = st.one_of(
    _unquoted_key,
    _basic_string,
    _literal_string,
    st.just('""'),
    st.just("''"),
)

def _dotted_key():
    return st.lists(_simple_key, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------- recursive values

def _value(draw, depth):
    if depth <= 0:
        return draw(st.one_of(
            _string, _integer, _floating, _bool, _datetime,
        ))
    choice = draw(st.integers(min_value=0, max_value=6))
    if choice == 0:
        return draw(_array(depth - 1))
    if choice == 1:
        return draw(_inline_table(depth - 1))
    return draw(st.one_of(_string, _integer, _floating, _bool, _datetime))


def _array(depth):
    @st.composite
    def build(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        items = [draw(_value(depth - 1)) for _ in range(n)]
        inner = ", ".join(items)
        style = draw(st.integers(min_value=0, max_value=3))
        if style == 0:
            return "[]"
        if style == 1:
            return "[" + inner + "]"
        if style == 2:
            return "[" + inner + ",]"
        return "[\n" + ",\n".join(items) + "\n]"
    return build()


def _inline_table(depth):
    @st.composite
    def build(draw):
        n = draw(st.integers(min_value=0, max_value=3))
        pairs = []
        for _ in range(n):
            k = draw(_key)
            v = draw(_value(depth - 1))
            pairs.append(k + " = " + v)
        style = draw(st.integers(min_value=0, max_value=3))
        if style == 0:
            return "{}"
        if style == 1:
            return "{" + ", ".join(pairs) + "}"
        if style == 2:
            return "{" + ", ".join(pairs) + ",}"
        return "{ " + ", ".join(pairs) + " }"
    return build()


_value_strategy = st.recursive(
    st.one_of(_string, _integer, _floating, _bool, _datetime),
    lambda children: st.one_of(
        st.lists(children, max_size=4).map(lambda xs: "[" + ", ".join(xs) + "]"),
        st.lists(children, max_size=4).map(lambda xs: "[" + ", ".join(xs) + ",]"),
        st.lists(
            st.tuples(_key, children), max_size=3
        ).map(lambda ps: "{" + ", ".join("%s = %s" % (k, v) for (k, v) in ps) + "}"),
    ),
    max_leaves=12,
)

# ---------------------------------------------------------------- documents

_comment = st.one_of(
    st.just("#"),
    st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
            max_size=20).map(lambda s: "# " + s),
    st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
            max_size=12).map(lambda s: "#" + s + "\x01"),
)

def _keyval():
    return st.tuples(_key, _value_strategy).map(lambda t: "%s = %s" % (t[0], t[1]))

def _table_header():
    return _key.map(lambda k: "[" + k + "]")

def _array_table_header():
    return _key.map(lambda k: "[[" + k + "]]")

def _line():
    return st.one_of(
        _keyval(),
        _table_header(),
        _array_table_header(),
        _comment,
    )

def _document():
    @st.composite
    def build(draw):
        n = draw(st.integers(min_value=0, max_value=8))
        lines = [draw(_line()) for _ in range(n)]
        sep = draw(st.sampled_from(["\n", "\r\n"]))
        trailing = draw(st.booleans())
        doc = sep.join(lines)
        if trailing and doc:
            doc = doc + sep
        return doc
    return build()

# ---------------------------------------------------------------- malformed extras

def _malformed():
    return st.one_of(
        _unterminated_basic,
        _unterminated_literal,
        _unterminated_ml_basic,
        _unterminated_ml_literal,
        _bad_escape_string,
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + "]"),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + "}"),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + '"'),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + "'"),
        st.tuples(_key, _value_strategy).map(lambda t: "[" + t[0] + " = " + t[1]),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + " , ,"),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + " extra"),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[1]),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[1]),
        st.tuples(_key, _value_strategy).map(lambda t: "[" + t[0] + "]\n" + t[0] + " = " + t[1]),
        st.tuples(_key, _value_strategy).map(lambda t: "[[%s]]\n[%s]\n%s = %s" % (t[0], t[0], t[0], t[1])),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = { " + t[1] + "\n}"),
        st.tuples(_key, _value_strategy).map(lambda t: t[0] + " = " + t[1] + "\n[" + t[0] + "]"),
        st.just("= 1"),
        st.just("[]"),
        st.just("[["),
        st.just("]]"),
        st.just("{"),
        st.just("}"),
        st.just("["),
        st.just("]"),
        st.just("a ="),
        st.just("a = = 1"),
        st.just("a b = 1"),
        st.just("a = 1 b = 2"),
        st.just("\n\n\n"),
        st.just("# only comment"),
        st.just(""),
        st.just("a = 1\n\n\nb = 2"),
        st.just("a = 1\r\nb = 2\r\n"),
        st.just("\ta = 1"),
        st.just("a = 1\t"),
        st.just("a = \"\\u0000\""),
        st.just("a = \"\\uD800\""),
        st.just("a = \"\\U00110000\""),
    )

# ---------------------------------------------------------------- deep nesting

def _deep_array(depth):
    return "[" * depth + "1" + "]" * depth

def _deep_inline(depth):
    return "{a = " * depth + "1" + "}" * depth

def _deep_dotted(depth):
    return ".".join("k%d" % i for i in range(depth)) + " = 1"

_depth_strategy = st.one_of(
    st.integers(min_value=1, max_value=8).map(_deep_array),
    st.integers(min_value=1, max_value=8).map(_deep_inline),
    st.integers(min_value=1, max_value=16).map(_deep_dotted),
    st.just(_deep_array(1500)),
    st.just(_deep_array(2048)),
    st.just(_deep_inline(1500)),
    st.just(_deep_inline(2048)),
    st.just(_deep_array(2049)),
    st.just(_deep_inline(2049)),
)

# ---------------------------------------------------------------- top-level

def _big_key():
    return st.integers(min_value=1, max_value=2000).map(lambda n: "k" * n + " = 1")

strategy = st.one_of(
    _document(),
    _malformed(),
    _depth_strategy,
    _big_key(),
    _value_strategy,
    _string,
    _integer,
    _floating,
    _datetime,
).map(_no_nul)
```