import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _j(*parts):
    return "".join(parts)

# characters usable inside strings (no raw NUL; controls allowed by parser)
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

_ESCAPE = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
])

def _unicode_escape():
    return st.one_of(
        st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\u%04X" % (n & 0xFFFF)),
        st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\U%08X" % n),
    )

_ESC_OR_CHAR = st.one_of(
    _ESCAPE,
    _unicode_escape(),
    _SAFE_CHARS,
)

def _basic_string():
    body = st.lists(_ESC_OR_CHAR, max_size=8).map("".join)
    return body.map(lambda b: '"' + b + '"')

def _literal_string():
    body = st.lists(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="'\x00\n"),
        max_size=8,
    ).map("".join)
    return body.map(lambda b: "'" + b + "'")

def _ml_basic_string():
    body = st.lists(
        st.one_of(_ESC_OR_CHAR, st.just("\n"), st.just("\r\n")),
        max_size=8,
    ).map("".join)
    return body.map(lambda b: '"""' + b + '"""')

def _ml_literal_string():
    body = st.lists(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="'\x00"),
        max_size=8,
    ).map("".join)
    return body.map(lambda b: "'''" + b + "'''")

_string = st.one_of(
    _basic_string(),
    _literal_string(),
    _ml_basic_string(),
    _ml_literal_string(),
)

# ---------------------------------------------------------------------------
# numbers
# ---------------------------------------------------------------------------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _dec_int():
    sign = st.sampled_from(["", "+", "-"])
    body = st.one_of(
        _digits,
        st.just("0"),
        st.builds(lambda a, b: a + "_" + b, _digits, _digits),
        st.just("007"),
        st.just("999999999999999999999999999999999999"),
    )
    return st.tuples(sign, body).map(lambda t: t[0] + t[1])

def _hex_int():
    body = st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=6)
    return body.map(lambda b: "0x" + b)

def _oct_int():
    body = st.text(alphabet="01234567", min_size=1, max_size=6)
    return body.map(lambda b: "0o" + b)

def _bin_int():
    body = st.text(alphabet="01", min_size=1, max_size=6)
    return body.map(lambda b: "0b" + b)

_integer = st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    sign = st.sampled_from(["", "+", "-"])
    frac = st.one_of(
        st.just(""),
        st.builds(lambda a: "." + a, _digits),
        st.just("."),
    )
    exp = st.one_of(
        st.just(""),
        st.builds(
            lambda s, d: s + d,
            st.sampled_from(["e", "E", "e+", "e-", "E+", "E-"]),
            _digits,
        ),
        st.just("e309"),
    )
    mant = st.one_of(_digits, st.just(""), st.just("0"))
    return st.tuples(sign, mant, frac, exp).map(lambda t: t[0] + t[1] + t[2] + t[3])

_special_float = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_floating = st.one_of(_float(), _special_float)

_boolean = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# dates / times
# ---------------------------------------------------------------------------

def _date():
    return st.builds(
        lambda y, m, d: "%s-%s-%s" % (y, m, d),
        st.text(alphabet="0123456789", min_size=4, max_size=4),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
    )

def _partial_time():
    return st.builds(
        lambda h, m, s, f: "%s:%s:%s%s" % (h, m, s, f),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
        st.one_of(st.just(""), st.builds(lambda d: "." + d, _digits)),
    )

_offset = st.one_of(
    st.just("Z"),
    st.builds(
        lambda s, h, m: s + h + ":" + m,
        st.sampled_from(["+", "-"]),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
    ),
)

def _offset_datetime():
    delim = st.sampled_from(["T", "t", " "])
    return st.builds(
        lambda d, dl, t, o: d + dl + t + o,
        _date(), delim, _partial_time(), _offset,
    )

def _local_datetime():
    delim = st.sampled_from(["T", "t", " "])
    return st.builds(lambda d, dl, t: d + dl + t, _date(), delim, _partial_time())

_datetime = st.one_of(
    _offset_datetime(),
    _local_datetime(),
    _date(),
    _partial_time(),
)

# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------

_unquoted_key = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=8,
)

_quoted_key = st.one_of(_basic_string(), _literal_string())

_simple_key = st.one_of(_unquoted_key, _quoted_key)

def _dotted_key():
    return st.lists(_simple_key, min_size=1, max_size=3).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key())

# ---------------------------------------------------------------------------
# values (recursive)
# ---------------------------------------------------------------------------

_scalar = st.one_of(
    _string,
    _integer,
    _floating,
    _boolean,
    _datetime,
)

def _value_strategy(children):
    arr = _array(children)
    inline = _inline_table(children)
    return st.one_of(_scalar, arr, inline)

def _array(children):
    # element value uses children
    elem = children
    def build(elems, trailing, ml):
        sep = ",\n" if ml else ","
        if not elems:
            return "[]"
        body = sep.join(elems)
        if trailing:
            body += ","
        if ml:
            return "[\n" + body + "\n]"
        return "[" + body + "]"
    return st.builds(
        build,
        st.lists(elem, max_size=4),
        st.booleans(),
        st.booleans(),
    )

def _inline_table_keyval(children):
    return st.builds(
        lambda k, v: k + " = " + v,
        _key,
        children,
    )

def _inline_table(children):
    def build(pairs, trailing):
        if not pairs:
            return "{}"
        body = ", ".join(pairs)
        if trailing:
            body += ","
        return "{" + body + "}"
    return st.builds(
        build,
        st.lists(_inline_table_keyval(children), max_size=3),
        st.booleans(),
    )

_value = st.recursive(_scalar, _value_strategy, max_leaves=20)

# ---------------------------------------------------------------------------
# statements
# ---------------------------------------------------------------------------

def _comment():
    body = st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00\n\r"),
        max_size=10,
    )
    return body.map(lambda b: "#" + b)

def _key_value():
    return st.builds(
        lambda k, v: k + " = " + v,
        _key,
        _value,
    )

def _standard_table():
    return st.builds(lambda k: "[" + k + "]", _key)

def _array_table():
    return st.builds(lambda k: "[[" + k + "]]", _key)

_statement = st.one_of(
    _key_value(),
    _standard_table(),
    _array_table(),
    _comment(),
    st.just(""),
)

def _document():
    lines = st.lists(_statement, max_size=6)
    def build(ls, trailing_nl):
        body = "\n".join(ls)
        if trailing_nl and ls:
            body += "\n"
        return body
    return st.builds(build, lines, st.booleans())

# ---------------------------------------------------------------------------
# malformed mutations (near-valid-but-broken)
# ---------------------------------------------------------------------------

def _drop_char(s):
    if len(s) < 2:
        return s + "]"
    i = len(s) // 2
    return s[:i] + s[i + 1:]

def _double_char(s):
    if not s:
        return "[["
    i = len(s) // 2
    return s[:i] + s[i] + s[i:]

def _stray_token(s):
    return s + " stray"

def _unterminated(s):
    if s.startswith('"') and not s.startswith('"""'):
        return s[:-1] if s.endswith('"') else s
    return '"' + s

def _truncate(s):
    if len(s) < 2:
        return s
    return s[: max(1, len(s) - 1)]

_malformed = st.one_of(
    _key_value().map(_drop_char),
    _key_value().map(_double_char),
    _key_value().map(_stray_token),
    _key_value().map(_unterminated),
    _array(_value).map(_drop_char),
    _inline_table(_value).map(_drop_char),
    _document().map(_truncate),
)

# ---------------------------------------------------------------------------
# deep nesting (arrays / inline tables) in the 1500-2048 band
# ---------------------------------------------------------------------------

def _deep_array():
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(lambda d: "[" * d + "]" * d)

def _deep_inline():
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(lambda d: "{a = " * d + "1" + "}" * d)

_deep = st.one_of(
    _deep_array().map(lambda s: "x = " + s),
    _deep_inline().map(lambda s: "x = " + s),
)

# ---------------------------------------------------------------------------
# final strategy
# ---------------------------------------------------------------------------

# Near-valid-but-broken mutations across the full statement/value grammar,
# including deep-nesting boundary cases, to exercise error-recovery paths.
_deep_malformed = st.one_of(
    _deep_array().map(lambda s: "x = " + s[:-1]),
    _deep_inline().map(lambda s: "x = " + s[:-1]),
    _deep_array().map(lambda s: "x = " + s + "]"),
    _deep_inline().map(lambda s: "x = " + s + "}"),
)

strategy = st.one_of(
    _document(),
    _malformed,
    _deep,
    _deep_malformed,
)