```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

def _ascii_printable():
    return st.characters(min_codepoint=0x20, max_codepoint=0x7e)

def _nonascii():
    return st.characters(min_codepoint=0x80, max_codepoint=0x10ffff).filter(
        lambda c: not (0xD800 <= ord(c) <= 0xDFFF)
    )

def _control():
    # raw control chars allowed in strings/comments by the parser, but no NUL
    return st.sampled_from(
        [chr(i) for i in range(1, 0x20) if i != 0x0a] + ["\t", "\x7f"]
    )

# ---------- strings ----------

_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

def _unicode_escape():
    kind = st.sampled_from(["u", "U"])
    n = st.integers(min_value=4, max_value=8)

    def build(k, width):
        digits = "".join("%04x" % (i % 0x10000) for i in range(width // 4))
        return "\\" + k + digits

    return st.tuples(kind, n).map(lambda t: build(t[0], t[1]))

def _basic_char():
    plain = st.characters(min_codepoint=0x20, max_codepoint=0x10ffff).filter(
        lambda c: c not in ('"', "\\", "\n") and not (0xD800 <= ord(c) <= 0xDFFF)
    )
    return st.one_of(
        plain,
        st.sampled_from(["\\u0000", "\\u001f", "\\u007f"]),
        _control(),
        _escapes,
        _unicode_escape(),
    )

def _literal_char():
    plain = st.characters(min_codepoint=0x20, max_codepoint=0x10ffff).filter(
        lambda c: c not in ("'", "\n") and not (0xD800 <= ord(c) <= 0xDFFF)
    )
    return st.one_of(plain, _control())

def _basic_string():
    body = st.lists(_basic_char(), max_size=12).map(_join)
    return body.map(lambda b: '"' + b + '"')

def _literal_string():
    body = st.lists(_literal_char(), max_size=12).map(_join)
    return body.map(lambda b: "'" + b + "'")

def _ml_basic_string():
    inner = st.lists(
        st.one_of(_basic_char(), st.just("\n"), st.just("\r\n")), max_size=10
    ).map(_join)
    return inner.map(lambda b: '"""' + b + '"""')

def _ml_literal_string():
    inner = st.lists(
        st.one_of(_literal_char(), st.just("\n"), st.just("\r\n")), max_size=10
    ).map(_join)
    return inner.map(lambda b: "'''" + b + "'''")

def _any_string():
    return st.one_of(
        _basic_string(), _literal_string(), _ml_basic_string(), _ml_literal_string()
    )

# ---------- numbers ----------

def _digits(n_min=1, n_max=6):
    return st.integers(min_value=n_min, max_value=n_max).flatmap(
        lambda n: st.lists(st.integers(min_value=0, max_value=9), min_size=n, max_size=n)
        .map(lambda ds: "".join(str(d) for d in ds))
    )

def _dec_int():
    sign = st.sampled_from(["", "", "+", "-"])
    body = st.one_of(
        _digits(1, 1),
        st.lists(st.integers(0, 9), min_size=1, max_size=8)
        .map(lambda ds: "".join(str(d) for d in ds)),
        st.tuples(
            st.integers(1, 9),
            st.lists(st.integers(0, 9), min_size=1, max_size=6),
        ).map(lambda t: str(t[0]) + "".join(str(d) for d in t[1])),
        st.just("007"),
        st.just("9223372036854775807"),
        st.just("18446744073709551616"),
        st.just("999999999999999999999999999999999999"),
    )
    return st.tuples(sign, body).map(lambda t: t[0] + t[1])

def _hex_int():
    return st.tuples(
        st.sampled_from(["0x", "0X"]),
        st.lists(st.sampled_from("0123456789abcdefABCDEF"), min_size=1, max_size=8),
    ).map(lambda t: t[0] + "".join(t[1]))

def _oct_int():
    return st.tuples(
        st.just("0o"),
        st.lists(st.sampled_from("01234567"), min_size=1, max_size=8),
    ).map(lambda t: t[0] + "".join(t[1]))

def _bin_int():
    return st.tuples(
        st.just("0b"),
        st.lists(st.sampled_from("01"), min_size=1, max_size=8),
    ).map(lambda t: t[0] + "".join(t[1]))

def _underscored_int():
    base = st.sampled_from(["", "0x", "0o", "0b"])
    digit_sets = {
        "": "0123456789",
        "0x": "0123456789abcdefABCDEF",
        "0o": "01234567",
        "0b": "01",
    }

    def build(b):
        ds = digit_sets[b]
        parts = ["%s" % (d,) for d in ds]
        return st.lists(st.sampled_from(ds), min_size=2, max_size=6).map(
            lambda xs: b + "_".join(xs)
        )

    return base.flatmap(build)

def _integer():
    return st.one_of(
        _dec_int(), _hex_int(), _oct_int(), _bin_int(), _underscored_int()
    )

def _float():
    return st.one_of(
        st.tuples(
            st.sampled_from(["", "+", "-"]),
            st.sampled_from(["inf", "nan"]),
        ).map(lambda t: t[0] + t[1]),
        st.tuples(
            _dec_int(),
            st.sampled_from([".", ".0", ".5", "."]),
            st.one_of(st.just(""), _digits(1, 4)),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(
            _dec_int(),
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            _digits(1, 3),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
        st.just("1."),
        st.just(".5"),
        st.just("1e309"),
        st.just("-1e400"),
        st.just("3.141592653589793"),
    )

# ---------- dates ----------

def _two(n_min=0, n_max=99):
    return st.integers(min_value=n_min, max_value=n_max).map(lambda n: "%02d" % n)

def _year():
    return st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)

def _full_date():
    return st.tuples(_year(), _two(0, 99), _two(0, 99)).map(
        lambda t: t[0] + "-" + t[1] + "-" + t[2]
    )

def _partial_time():
    return st.tuples(
        _two(0, 99), _two(0, 99), _two(0, 99),
        st.one_of(st.just(""), st.tuples(st.just("."), _digits(1, 6)).map(_join)),
    ).map(lambda t: t[0] + ":" + t[1] + ":" + t[2] + t[3])

def _offset():
    return st.one_of(
        st.just("Z"),
        st.tuples(st.sampled_from(["+", "-"]), _two(0, 99), st.just(":"), _two(0, 99))
        .map(_join),
    )

def _date_time():
    delim = st.sampled_from(["T", "t", " "])
    return st.one_of(
        st.tuples(_full_date(), delim, _partial_time(), _offset()).map(_join),
        st.tuples(_full_date(), delim, _partial_time()).map(_join),
        _full_date(),
        _partial_time(),
        st.just("1979-02-30"),
        st.just("1979-05-27 07:32:00Z"),
        st.just("1979-13-45T99:99:99+99:99"),
    )

# ---------- keys ----------

def _unquoted_key():
    return st.lists(
        st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"),
        min_size=1, max_size=8,
    ).map(_join)

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_unquoted_key(), _quoted_key(), st.just('""'))

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(lambda ks: ".".join(ks))

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------- recursive values ----------

def _scalar_value():
    return st.one_of(
        _any_string(),
        _integer(),
        _float(),
        st.sampled_from(["true", "false"]),
        _date_time(),
    )

def _array_value(children):
    return st.tuples(
        st.lists(children, min_size=0, max_size=4),
        st.sampled_from(["", ","]),
    ).map(lambda t: "[" + ", ".join(t[0]) + t[1] + "]")

def _inline_table_value(children):
    def build(pairs):
        if not pairs:
            return "{}"
        body = ", ".join(pairs)
        return "{" + body + "}"

    return st.lists(
        st.tuples(_key(), children).map(lambda t: t[0] + " = " + t[1]),
        min_size=0, max_size=4,
    ).map(build)

def _value():
    return st.recursive(
        _scalar_value(),
        lambda children: st.one_of(
            _array_value(children),
            _inline_table_value(children),
        ),
        max_leaves=12,
    )

# ---------- deep nesting generators ----------

def _deep_array(depth):
    return st.just("[" * depth + "]" * depth)

def _deep_inline(depth):
    # nested inline tables: {a={a={...={}}}}
    return st.just("{a=" * depth + "}" * depth)

def _deep_mixed(depth):
    def build(n):
        parts = []
        for i in range(n):
            parts.append("[{a=" if i % 2 == 0 else "[")
        inner = ""
        for i in range(n):
            parts.append("}]" if (n - 1 - i) % 2 == 0 else "]")
        return "".join(parts) + inner

    return st.just(build(depth))

def _deep_value():
    depth = st.integers(min_value=1500, max_value=2048)
    return st.one_of(
        depth.flatmap(_deep_array),
        depth.flatmap(_deep_inline),
        depth.flatmap(_deep_mixed),
    )

# ---------- utf8 / raw-token / rtod / lit-str targeted generators ----------

def _utf8_payload():
    # Exercise toml_utf8_to_ucs / toml_rtots / toml_rtod_ex / norm_lit_str paths
    # with multibyte UTF-8 inside strings, keys, comments, and bare contexts.
    multibyte = st.sampled_from([
        "\u00e9", "\u00ff", "\u0100", "\u07ff", "\u0800", "\uffff",
        "\U00010000", "\U0010ffff", "\u4e2d", "\u6587", "\u00a0",
        "\u2028", "\u2029", "\u3000",
    ])
    raw_utf8 = st.sampled_from([
        "\xc3\xa9", "\xe4\xb8\xad", "\xf0\x9f\x98\x80",
        "\xc2\x80", "\xdf\xbf", "\xef\xbf\xbf",
    ])
    bad_utf8 = st.sampled_from([
        "\xff", "\xfe", "\xc0\x80", "\xe0\x80\x80", "\xf0\x80\x80\x80",
        "\xed\xa0\x80", "\xf5\x80\x80\x80",
    ])
    return st.one_of(multibyte, raw_utf8, bad_utf8)

def _utf8_document():
    def basic(b):
        return '"' + b + '"'
    def literal(b):
        return "'" + b + "'"
    def ml_basic(b):
        return '"""' + b + '"""'
    def ml_literal(b):
        return "'''" + b + "'''"
    def key(b):
        return '"' + b + '"'
    def comment(b):
        return "#" + b
    def bare(b):
        return b

    payload = _utf8_payload()
    return st.one_of(
        payload.map(lambda b: "a = " + basic(b)),
        payload.map(lambda b: "a = " + literal(b)),
        payload.map(lambda b: "a = " + ml_basic(b)),
        payload.map(lambda b: "a = " + ml_literal(b)),
        payload.map(lambda b: key(b) + " = 1"),
        payload.map(comment),
        payload.map(bare),
        st.tuples(payload, payload).map(lambda t: "a = \"" + t[0] + t[1] + "\""),
    )

def _rtod_ex_document():
    # Exercise toml_rtod_ex: floats with exponents, inf/nan, underscores, signs.
    mant = st.one_of(
        st.just("0"), st.just("1"), st.just("123"), st.just("1_000"),
        st.just("0.0"), st.just("1.5"), st.just(".5"), st.just("1."),
    )
    exp = st.one_of(
        st.just(""), st.just("e0"), st.just("e+10"), st.just("E-5"),
        st.just("e_1"), st.just("e1_0"), st.just("e999"),
    )
    sign = st.sampled_from(["", "+", "-"])
    special = st.sampled_from([
        "inf", "+inf", "-inf", "nan", "+nan", "-nan",
        "1e309", "-1e400", "1e-400",
    ])
    return st.one_of(
        st.tuples(sign, mant, exp).map(lambda t: "a = " + t[0] + t[1] + t[2]),
        special.map(lambda s: "a = " + s),
    )

def _rtots_document():
    # Exercise toml_rtots: date/time parsing edge cases.
    return st.one_of(
        st.just("a = 1979-05-27T07:32:00Z"),
        st.just("a = 1979-05-27T00:32:00-07:00"),
        st.just("a = 1979-05-27T00:32:00.999999-07:00"),
        st.just("a = 1979-05-27 07:32:00Z"),
        st.just("a = 1979-05-27T07:32:00"),
        st.just("a = 07:32:00"),
        st.just("a = 00:32:00.999999"),
        st.just("a = 1979-05-27"),
        st.just("a = 0000-00-00"),
        st.just("a = 9999-99-99T99:99:99.999999+99:99"),
        st.just("a = 1979-05-27T07:32:00.Z"),
        st.just("a = 1979-05-27T07:32:00+00:00"),
        st.just("a = 1979-05-27T07:32:00.1Z"),
        st.just("a = 1979-05-27t07:32:00z"),
    )

def _norm_lit_str_document():
    # Exercise norm_lit_str: literal strings, multiline literal strings.
    return st.one_of(
        st.just("a = 'C:\\Users\\nodejs\\templates'"),
        st.just("a = '\\\\ServerX\\admin$\\system32\\'"),
        st.just("a = 'Tom \"Dubs\" Preston-Werner'"),
        st.just("a = '<\\i\\c*\\s*>'"),
        st.just("a = '''I [dw]on't need \\d{2} apples'''"),
        st.just("a = '''\nThe first newline is\ntrimmed in raw strings.\n'''"),
        st.just("a = ''''That,' she said, 'is still pointless.''''"),
        st.just("a = ''''''"),
        st.just("a = ''"),
        st.tuples(_literal_string(), _literal_string()).map(
            lambda t: "a = " + t[0] + "\nb = " + t[1]
        ),
    )

# ---------- malformed / near-valid ----------

def _unterminated_string():
    return st.one_of(
        st.just('a = "unterminated'),
        st.just("a = 'unterminated"),
        st.just('a = """unterminated'),
        st.just("a = '''unterminated"),
        st.tuples(_basic_string(), st.just('"')).map(lambda t: "a = " + t[0] + t[1]),
    )

def _bad_escape():
    return st.sampled_from(['a = "\\q"', 'a = "\\x41"', 'a = "\\"'])

def _missing_delimiter():
    return st.one_of(
        st.just("a = [1, 2"),
        st.just("a = {b = 1"),
        st.just("[table"),
        st.just("[[array"),
        st.just("a = 1"),
        st.just("a ="),
        st.just("= 1"),
        st.just("[t]"),
    )

def _doubled_delimiter():
    return st.one_of(
        st.just("a = [[1, 2]]"),
        st.just("a = {{b = 1}}"),
        st.just("[[t]]"),
        st.just("a = [1,,2]"),
        st.just("a = {b = 1,, c = 2}"),
        st.just("a == 1"),
        st.just("a = 1 = 2"),
    )

def _stray_token():
    return st.one_of(
        st.just("a = 1 b = 2"),
        st.just("a = 1 @"),
        st.just("@ = 1"),
        st.just("a = 1\n@"),
        st.just("a = 1\nb"),
        st.just("a = true false"),
        st.just("a = 1 # comment \x01"),
    )

def _duplicate():
    return st.one_of(
        st.just("a = 1\na = 2"),
        st.just("[t]\na = 1\n[t]\nb = 2"),
        st.just("[[a]]\n[[a]]\n[a]"),
        st.just("a.b = 1\na.b = 2"),
    )

def _malformed():
    return st.one_of(
        _unterminated_string(),
        _bad_escape(),
        _missing_delimiter(),
        _doubled_delimiter(),
        _stray_token(),
        _duplicate(),
    )

# ---------- document assembly ----------

def _comment():
    body = st.lists(
        st.one_of(
            st.characters(min_codepoint=0x20, max_codepoint=0x10ffff).filter(
                lambda c: c != "\n" and not (0xD800 <= ord(c) <= 0xDFFF)
            ),
            _control(),
        ),
        max_size=10,
    ).map(_join)
    return body.map(lambda b: "#" + b)

def _line_end():
    return st.sampled_from(["\n", "\r\n", "\n", "\n"])

def _key_value():
    return st.tuples(_key(), _value()).map(lambda t: t[0] + " = " + t[1])

def _standard_table():
    return _key().map(lambda k: "[" + k + "]")

def _array_table():
    return _key().map(lambda k: "[[" + k + "]]")

def _expression():
    return st.one_of(
        _key_value(),
        _standard_table(),
        _array_table(),
        _comment(),
    )

def _document():
    return st.tuples(
        st.lists(_expression(), min_size=0, max_size=6),
        st.sampled_from(["", "\n", "\r\n"]),
    ).map(lambda t: "\n".join(t[0]) + t[1])

# ---------- top-level strategy ----------

strategy = st.one_of(
    _document(),
    _deep_value().map(lambda v: "a = " + v),
    _malformed(),
    _utf8_document(),
    _rtod_ex_document(),
    _rtots_document(),
    _norm_lit_str_document(),
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("a = 1"),
    st.just("a = 1\n"),
    st.just("[]"),
    st.just("a = []"),
    st.just("a = {}"),
    st.just("[t]"),
    st.just("[[a]]"),
    st.just('"" = 1'),
)
```