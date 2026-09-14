from hypothesis import strategies as st
import json

# ---------- basic leaves ----------

_ascii_letters_digits = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_bare_chars = _ascii_letters_digits + "-_"

# A NUL-free printable-ish set plus some control bytes (except NUL).
_ctrl_ok = "".join(chr(i) for i in range(1, 0x20))
_text_chars = (
    _ascii_letters_digits
    + " \t!@#$%^&*()+-=[]{}|;:'\",.<>/?`~"
    + _ctrl_ok
    + "\u00e9\u00fc\u4e2d\u6587\U0001f600\u00a0"
)

def _no_nul(s):
    return s.replace("\x00", "")

_basic_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_unicode_escape = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda cp: "\\u%04X" % cp if cp <= 0xFFFF else "\\U%08X" % cp
)

_basic_inner_char = st.one_of(
    st.text(alphabet=_text_chars, min_size=0, max_size=8),
    _basic_escape,
    _unicode_escape,
    st.just("\\u0000"),  # six-char escape is fine
)

_basic_string = st.lists(_basic_inner_char, max_size=6).map(
    lambda parts: '"' + _no_nul("".join(parts)) + '"'
)

_literal_inner = st.text(
    alphabet=_text_chars.replace("'", "").replace("\n", "") + "\t",
    min_size=0,
    max_size=12,
)

_literal_string = _literal_inner.map(lambda s: "'" + s + "'")

_ml_basic_inner = st.lists(
    st.one_of(
        st.text(alphabet=_text_chars.replace('"', "").replace("\\", ""), min_size=0, max_size=10),
        _basic_escape,
        _unicode_escape,
        st.just("\n"),
        st.just("\r\n"),
        st.just('\\\n'),  # line continuation
    ),
    max_size=5,
).map(lambda parts: _no_nul("".join(parts)))

_ml_basic_string = _ml_basic_inner.map(lambda s: '"""' + s + '"""')

_ml_literal_inner = st.text(
    alphabet=_text_chars.replace("'", ""),
    min_size=0,
    max_size=20,
)

_ml_literal_string = _ml_literal_inner.map(lambda s: "'''" + s + "'''")

_string = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# ---------- numbers ----------

def _digits_with_underscores(digits, min_len=1, max_len=12):
    return st.lists(
        st.sampled_from(digits), min_size=min_len, max_size=max_len
    ).map(lambda ds: "".join(ds))

_dec_digits = _digits_with_underscores("0123456789", 1, 18)

_dec_int = st.one_of(
    _dec_digits,
    _dec_digits.map(lambda s: "-" + s),
    _dec_digits.map(lambda s: "+" + s),
    st.just("007"),
    st.just("0"),
    st.integers(min_value=-(2**70), max_value=2**70).map(str),
)

_hex_int = _digits_with_underscores("0123456789abcdefABCDEF", 1, 16).map(
    lambda s: "0x" + s
)
_oct_int = _digits_with_underscores("01234567", 1, 16).map(lambda s: "0o" + s)
_bin_int = _digits_with_underscores("01", 1, 16).map(lambda s: "0b" + s)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

def _float_text():
    return st.one_of(
        st.tuples(_dec_digits, _dec_digits).map(lambda t: t[0] + "." + t[1]),
        st.tuples(_dec_digits, _dec_digits, _dec_digits).map(
            lambda t: t[0] + "." + t[1] + "e" + t[2]
        ),
        st.tuples(_dec_digits, _dec_digits).map(
            lambda t: t[0] + "." + t[1] + "E+" + t[0]
        ),
        st.just("1."),
        st.just(".5"),
        st.just("1e309"),
        st.just("-1e-309"),
        st.just("6.626e-34"),
        st.just("0.0"),
        st.just("+0.0"),
    )

_floating_point = st.one_of(
    _float_text(),
    st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
)

# ---------- dates ----------

_yyyymmdd = st.tuples(
    st.integers(min_value=0, max_value=9999),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: "%04d-%02d-%02d" % t)

_hhmmss = st.tuples(
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: "%02d:%02d:%02d" % t)

_secfrac = st.integers(min_value=0, max_value=999999).map(
    lambda n: "." + str(n)
)

_partial_time = st.tuples(_hhmmss, st.one_of(st.none(), _secfrac)).map(
    lambda t: t[0] + (t[1] or "")
)

_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(
        st.sampled_from(["+", "-"]),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ).map(lambda t: "%s%02d:%02d" % t),
)

_date_time = st.one_of(
    _yyyymmdd,
    st.just("1979-02-30"),
    _partial_time,
    st.tuples(_yyyymmdd, st.sampled_from(["T", "t", " "]), _partial_time).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(
        _yyyymmdd, st.sampled_from(["T", "t", " "]), _partial_time, _offset
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
)

# ---------- keys ----------

_unquoted_key = st.text(
    alphabet=_bare_chars, min_size=1, max_size=12
)

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(
    lambda ks: ".".join(ks)
)

_key = st.one_of(_simple_key, _dotted_key)

# ---------- recursive values ----------

def _value_leaf():
    return st.one_of(
        _string,
        _integer,
        _floating_point,
        st.sampled_from(["true", "false"]),
        _date_time,
    )

def _comment_text():
    return st.text(
        alphabet=_text_chars.replace("\n", "").replace("\r", ""),
        min_size=0,
        max_size=20,
    )

def _comment():
    return _comment_text().map(lambda s: "#" + s)

def _inline_table(inner):
    def build(pairs):
        if not pairs:
            body = ""
        else:
            body = ", ".join(pairs)
        return "{" + body + "}"

    def pair(inner):
        return st.tuples(_key, inner).map(lambda t: t[0] + " = " + t[1])

    return st.lists(pair(inner), min_size=0, max_size=4).map(build)

def _array(inner):
    def build(elems):
        if not elems:
            return "[]"
        return "[" + ", ".join(elems) + "]"

    return st.lists(inner, min_size=0, max_size=5).map(build)

_value = st.recursive(
    _value_leaf(),
    lambda children: st.one_of(_array(children), _inline_table(children)),
    max_leaves=20,
)

# ---------- document structure ----------

def _key_value():
    return st.tuples(_key, _value, st.one_of(st.none(), _comment())).map(
        lambda t: t[0] + " = " + t[1] + (("  " + t[2]) if t[2] else "")
    )

def _standard_table():
    return _key.map(lambda k: "[" + k + "]")

def _array_table():
    return _key.map(lambda k: "[[" + k + "]]")

def _line():
    return st.one_of(
        _key_value(),
        _standard_table(),
        _array_table(),
        _comment(),
    )

_document = st.lists(_line(), min_size=0, max_size=12).map(
    lambda lines: "\n".join(lines)
)

# ---------- edge-case / malformed injections ----------

_deep_array = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "a = " + "[" * n + "]" * n
)

_deep_inline = st.integers(min_value=100, max_value=400).map(
    lambda n: "a = " + "{b = " * n + "1" + "}" * n
)

_malformed = st.sampled_from(
    [
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = [1, 2",
        "a = {b = 1",
        "a = [1, 2]]",
        "a = {b = 1}}",
        "[table",
        "[[table]",
        "a = ",
        "= 1",
        "a 1",
        "a = 1 b = 2",
        "a = 1\n b = 2",
        "a = {b = 1,\n c = 2}",
        "a = {b = 1,}",
        "a = 1\n a = 2",
        "[t]\n[t]",
        "a.b = 1\na.b = 2",
        'a = "x\\q"',
        "a = \x01",
        "a = 1_",
        "a = 0x",
        "a = 1979-13-45",
        "\u00e9 = 1",
    ]
)

_extreme = st.one_of(
    st.just("a = " + "x" * 10000),
    st.just("a = 1" + "_0" * 200),
    st.just('a = "' + "\\n" * 500 + '"'),
    st.just("a = " + "0" * 100 + "1"),
)

_document_full = st.one_of(
    _document,
    _deep_array,
    _deep_inline,
    _malformed,
    _extreme,
)

strategy = _document_full.map(_no_nul)