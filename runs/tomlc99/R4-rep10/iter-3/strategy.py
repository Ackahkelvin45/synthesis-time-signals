from hypothesis import strategies as st
import json

# ---------- basic character / text pieces ----------

def _no_nul(chars):
    return chars.filter(lambda c: c != "\x00")

# ASCII safe for basic strings (no quote, backslash, newline); plus raw controls allowed by parser
_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(lambda c: c not in '"\\'),
    st.sampled_from(["\t", "\x01", "\x02", "\x07", "\x0b", "\x0c", "\x1f"]),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF).filter(lambda c: c != "\x00" and not (0xD800 <= ord(c) <= 0xDFFF)),
)

_literal_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(lambda c: c != "'"),
    st.sampled_from(["\t", "\x01", "\x02", "\x07", "\x0b", "\x0c", "\x1f"]),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF).filter(lambda c: c != "\x00" and not (0xD800 <= ord(c) <= 0xDFFF)),
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_hex8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)

_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.tuples(st.just("\\u"), _hex4).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("\\U"), _hex8).map(lambda t: t[0] + t[1]),
)

_basic_body = st.one_of(_basic_char, _escape)

def _basic_string():
    return st.tuples(
        st.just('"'),
        st.lists(_basic_body, max_size=12).map("".join),
        st.just('"'),
    ).map(lambda t: t[0] + t[1] + t[2])

def _literal_string():
    return st.tuples(
        st.just("'"),
        st.lists(_literal_char, max_size=12).map("".join),
        st.just("'"),
    ).map(lambda t: t[0] + t[1] + t[2])

_ml_basic_body = st.one_of(
    _basic_char,
    _escape,
    st.just("\n"),
    st.just("\r\n"),
    st.just("\\\n"),
    st.just("\\\r\n"),
)

def _ml_basic_string():
    return st.tuples(
        st.just('"""'),
        st.lists(_ml_basic_body, max_size=20).map("".join),
        st.just('"""'),
    ).map(lambda t: t[0] + t[1] + t[2])

_ml_literal_body = st.one_of(
    _literal_char,
    st.just("\n"),
    st.just("\r\n"),
)

def _ml_literal_string():
    return st.tuples(
        st.just("'''"),
        st.lists(_ml_literal_body, max_size=20).map("".join),
        st.just("'''"),
    ).map(lambda t: t[0] + t[1] + t[2])

# ---------- numbers ----------

_digit = st.sampled_from("0123456789")

def _dec_int():
    sign = st.one_of(st.just(""), st.just("+"), st.just("-"))
    body = st.one_of(
        st.lists(_digit, min_size=1, max_size=1).map("".join),
        st.tuples(
            st.sampled_from("123456789"),
            st.lists(st.one_of(_digit, st.just("_")), max_size=20).map("".join),
        ).map(lambda t: t[0] + t[1]),
        st.tuples(
            st.sampled_from("123456789"),
            st.lists(_digit, min_size=1, max_size=20).map("".join),
        ).map(lambda t: t[0] + t[1]),
        st.lists(_digit, min_size=2, max_size=30).map("".join),  # leading zeros accepted
        st.just("0"),
    )
    return st.tuples(sign, body).map(lambda t: t[0] + t[1])

def _hex_int():
    hd = st.sampled_from("0123456789abcdefABCDEF")
    return st.tuples(
        st.just("0x"),
        st.lists(st.one_of(hd, st.just("_")), min_size=1, max_size=30).map("".join),
    ).map(lambda t: t[0] + t[1])

def _oct_int():
    od = st.sampled_from("01234567")
    return st.tuples(
        st.just("0o"),
        st.lists(st.one_of(od, st.just("_")), min_size=1, max_size=30).map("".join),
    ).map(lambda t: t[0] + t[1])

def _bin_int():
    bd = st.sampled_from("01")
    return st.tuples(
        st.just("0b"),
        st.lists(st.one_of(bd, st.just("_")), min_size=1, max_size=40).map("".join),
    ).map(lambda t: t[0] + t[1])

def _float():
    sign = st.one_of(st.just(""), st.just("+"), st.just("-"))
    zero_prefixable = st.tuples(
        _digit,
        st.lists(st.one_of(_digit, st.just("_")), max_size=20).map("".join),
    ).map(lambda t: t[0] + t[1])
    exp = st.tuples(
        st.sampled_from("eE"),
        st.one_of(st.just(""), st.just("+"), st.just("-")),
        zero_prefixable,
    ).map(lambda t: t[0] + t[1] + t[2])
    frac = st.tuples(st.just("."), zero_prefixable).map(lambda t: t[0] + t[1])
    dec = st.one_of(
        _dec_int(),
        st.just("0"),
    )
    forms = st.one_of(
        st.tuples(dec, exp).map(lambda t: t[0] + t[1]),
        st.tuples(dec, frac, st.one_of(st.just(""), exp)).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(dec, st.just(".")).map(lambda t: t[0] + t[1]),  # 1.
        st.tuples(st.just("."), zero_prefixable).map(lambda t: t[0] + t[1]),  # .5
        st.tuples(st.just("."), zero_prefixable, exp).map(lambda t: t[0] + t[1] + t[2]),
        st.just("0.0"),
        st.just("1e309"),
        st.just("-1e-999"),
    )
    return st.tuples(sign, forms).map(lambda t: t[0] + t[1])

def _special_float():
    return st.one_of(
        st.just("inf"), st.just("+inf"), st.just("-inf"),
        st.just("nan"), st.just("+nan"), st.just("-nan"),
    )

# ---------- dates ----------

def _two():
    return st.text(alphabet="0123456789", min_size=2, max_size=2)

def _four():
    return st.text(alphabet="0123456789", min_size=4, max_size=4)

def _partial_time():
    secfrac = st.tuples(st.just("."), st.lists(_digit, min_size=1, max_size=9).map("".join)).map(lambda t: t[0] + t[1])
    return st.tuples(
        _two(), st.just(":"), _two(), st.just(":"), _two(),
        st.one_of(st.just(""), secfrac),
    ).map(lambda t: "".join(t))

def _offset():
    return st.one_of(
        st.just("Z"),
        st.just("z"),
        st.tuples(
            st.sampled_from("+-"), _two(), st.just(":"), _two()
        ).map(lambda t: "".join(t)),
    )

def _full_date():
    return st.tuples(_four(), st.just("-"), _two(), st.just("-"), _two()).map(lambda t: "".join(t))

def _offset_date_time():
    delim = st.sampled_from(["T", "t", " "])
    return st.tuples(_full_date(), delim, _partial_time(), _offset()).map(lambda t: "".join(t))

def _local_date_time():
    delim = st.sampled_from(["T", "t", " "])
    return st.tuples(_full_date(), delim, _partial_time()).map(lambda t: "".join(t))

def _local_date():
    return _full_date()

def _local_time():
    return _partial_time()

# ---------- keys ----------

_unquoted_key_char = st.sampled_from(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)

def _unquoted_key():
    return st.lists(_unquoted_key_char, min_size=1, max_size=10).map("".join)

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_quoted_key(), _unquoted_key())

def _dotted_key(simple_key_strategy):
    return st.tuples(
        simple_key_strategy,
        st.lists(st.tuples(st.just("."), simple_key_strategy).map(lambda t: t[0] + t[1]), min_size=1, max_size=4),
    ).map(lambda t: t[0] + "".join(t[1]))

# ---------- values (recursive) ----------

def _scalar_value():
    return st.one_of(
        _basic_string(),
        _ml_basic_string(),
        _literal_string(),
        _ml_literal_string(),
        _dec_int(),
        _hex_int(),
        _oct_int(),
        _bin_int(),
        _float(),
        _special_float(),
        st.sampled_from(["true", "false"]),
        _offset_date_time(),
        _local_date_time(),
        _local_date(),
        _local_time(),
    )

def _ws():
    return st.text(alphabet=" \t", max_size=3)

def _nl():
    return st.one_of(st.just("\n"), st.just("\r\n"))

def _comment():
    body = st.text(
        alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(lambda c: c != "\x00"),
        max_size=20,
    )
    return st.tuples(st.just("#"), body).map(lambda t: t[0] + t[1])

def _value_strategy():
    return st.recursive(
        _scalar_value(),
        lambda children: st.one_of(
            _array(children),
            _inline_table(children),
        ),
        max_leaves=30,
    )

def _array(children):
    inner = st.one_of(
        children,
        st.tuples(st.just(","), _ws(), children).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(st.just(","), _ws(), _nl(), _ws(), children).map(lambda t: "".join(t)),
    )
    items = st.one_of(
        st.just(""),
        st.lists(inner, min_size=1, max_size=6).map("".join),
    )
    trailing = st.one_of(st.just(""), st.just(","))
    tail_ws = st.one_of(st.just(""), st.tuples(_ws(), _nl(), _ws()).map("".join))
    return st.tuples(
        st.just("["), _ws(), items, trailing, tail_ws, st.just("]")
    ).map(lambda t: "".join(t))

def _inline_table(children):
    def pair():
        key = _simple_key()
        val = children
        return st.tuples(
            key, _ws(), st.just("="), _ws(), val
        ).map(lambda t: "".join(t))
    body = st.one_of(
        st.just(""),
        st.lists(pair(), min_size=1, max_size=5).map(lambda ps: ", ".join(ps)),
    )
    trailing = st.one_of(st.just(""), st.just(","))
    return st.tuples(
        st.just("{"), _ws(), body, trailing, _ws(), st.just("}")
    ).map(lambda t: "".join(t))

# ---------- document structure ----------

def _key_value_line():
    key = st.one_of(_simple_key(), _dotted_key(_simple_key()))
    val = _value_strategy()
    return st.tuples(
        key, _ws(), st.just("="), _ws(), val, st.one_of(st.just(""), _comment())
    ).map(lambda t: "".join(t))

def _standard_table_line():
    key = st.one_of(_simple_key(), _dotted_key(_simple_key()))
    return st.tuples(
        st.just("["), _ws(), key, _ws(), st.just("]"), st.one_of(st.just(""), _comment())
    ).map(lambda t: "".join(t))

def _array_table_line():
    key = st.one_of(_simple_key(), _dotted_key(_simple_key()))
    return st.tuples(
        st.just("[["), _ws(), key, _ws(), st.just("]]"), st.one_of(st.just(""), _comment())
    ).map(lambda t: "".join(t))

def _line():
    return st.one_of(
        _key_value_line(),
        _standard_table_line(),
        _array_table_line(),
        _comment(),
    )

def _document():
    lines = st.lists(
        st.tuples(_line(), st.one_of(st.just("\n"), st.just("\r\n"))).map(lambda t: t[0] + t[1]),
        max_size=8,
    )
    final = st.one_of(st.just(""), _line())
    return st.tuples(lines, final).map(lambda t: "".join(t[0]) + t[1])

# ---------- malformed / near-valid variants ----------

def _malformed():
    base = _document()
    return st.one_of(
        # unterminated string
        st.tuples(st.just('k = "abc'), st.one_of(st.just(""), st.just("\n"))).map("".join),
        st.tuples(st.just("k = 'abc"), st.one_of(st.just(""), st.just("\n"))).map("".join),
        # missing delimiter
        st.just("a = [1, 2\n"),
        st.just("a = {b = 1\n"),
        st.just("[table\n"),
        st.just("[[arr]\n"),
        # doubled delimiters
        st.just("a = [[1, 2]]\n"),
        st.just("a = {{b = 1}}\n"),
        st.just("[t]]\n"),
        st.just("[[t]]]\n"),
        # stray token
        st.just("a = 1 2\n"),
        st.just("a b = 1\n"),
        st.just("= 1\n"),
        st.just("a =\n"),
        st.just("a = \n"),
        # newline inside inline table (rejected)
        st.just("a = {b = 1,\nc = 2}\n"),
        # bare unicode key (rejected)
        st.just("\u00e9 = 1\n"),
        # invalid escape (rejected)
        st.just('a = "\\q"\n'),
        # duplicate keys (rejected)
        st.just("a = 1\na = 2\n"),
        st.just("[t]\n[t]\n"),
        st.just("[[a]]\n[[a]]\n[a]\n"),
        # value on next line
        st.just("a =\n1\n"),
        # deep nesting near band (arrays)
        st.tuples(
            st.just("a = "),
            st.just("[" * 1600),
            st.just("1"),
            st.just("]" * 1600),
            st.just("\n"),
        ).map("".join),
        # deep nesting inline tables
        st.tuples(
            st.just("a = "),
            st.just("{b = " * 800),
            st.just("1"),
            st.just("}" * 800),
            st.just("\n"),
        ).map("".join),
        # empty document / comment-only
        st.just(""),
        st.just("# just a comment"),
        st.just("# c\n# d\n"),
        base,
    )

# ---------- UTF-8 / unicode exercising (targets toml_utf8_to_ucs, norm_lit_str, toml_ucs_to_utf8) ----------

def _raw_byte_seq():
    # Raw bytes smuggled through a str via surrogateescape-free codepoints is not possible in
    # a pure-str strategy; instead we exercise multi-byte UTF-8 through literal content and
    # through invalid/overlong-style byte sequences represented as latin-1 codepoints.
    return st.one_of(
        # valid multi-byte UTF-8 (1..4 byte ranges)
        st.sampled_from([
            "\u007f",           # 1-byte edge
            "\u0080",           # 2-byte low
            "\u07ff",           # 2-byte high
            "\u0800",           # 3-byte low
            "\uffff",           # 3-byte high (BMP)
            "\U00010000",       # 4-byte low
            "\U0010FFFF",       # 4-byte high
            "\u00e9", "\u4e2d", "\U0001F600",
        ]),
        # lone continuation / lead bytes as latin-1 codepoints (invalid UTF-8 in file)
        st.sampled_from([
            "\u0080", "\u00bf",          # bare continuation 10xxxxxx
            "\u00c0", "\u00c1", "\u00df",  # 2-byte leads
            "\u00e0", "\u00ef",          # 3-byte leads
            "\u00f0", "\u00f7",          # 4-byte leads
            "\u00f8", "\u00fb",          # 5-byte leads
            "\u00fc", "\u00fd",          # 6-byte leads
            "\u00fe", "\u00ff",
        ]),
    )

def _utf8_document():
    # Put raw unicode / latin-1 bytes into both literal strings and comments so the
    # decoder paths (toml_utf8_to_ucs, toml_ucs_to_utf8, norm_lit_str) get exercised.
    payload = st.lists(_raw_byte_seq(), min_size=1, max_size=6).map("".join)
    def build(p):
        forms = st.one_of(
            st.tuples(st.just("a = '"), st.just(p), st.just("'\n")).map("".join),
            st.tuples(st.just('a = "'), st.just(p), st.just('"\n')).map("".join),
            st.tuples(st.just("# "), st.just(p), st.just("\n")).map("".join),
            st.tuples(st.just("a = '''"), st.just(p), st.just("'''\n")).map("".join),
            st.tuples(st.just('a = """'), st.just(p), st.just('"""\n')).map("".join),
        )
        return forms
    return payload.flatmap(build)

# ---------- final strategy ----------

_complete = _document()
_edge = st.one_of(
    st.just("a = 007\n"),
    st.just("a = 1.\n"),
    st.just("a = .5\n"),
    st.just('a = "x\x01y"\n'),
    st.just("# comment \x01\n"),
    st.just("a = {b = 1,}\n"),
    st.just("a = 1979-02-30\n"),
    st.just("a = []\n"),
    st.just("a = {}\n"),
    st.just("[t]\n"),
    st.just("[[a]]\n"),
    st.just('"" = 1\n'),
    st.just("a = 1_000\n"),
    st.just("a = 0x_1\n"),
    st.just("a = 1e309\n"),
    st.just("a = -inf\n"),
    st.just("a = nan\n"),
    st.just("a = 1979-05-27 07:32:00Z\n"),
    st.just("a = 10:00:00\n"),
    st.just("a = 1979-05-27\n"),
    st.just("a = 1979-05-27T07:32:00.999-07:00\n"),
    st.just("a = [1, 'two', 3.0, true, 1979-05-27]\n"),
    st.just("a = [\n  1,\n  # c\n  2,\n]\n"),
    st.just("a = \"\\u0000\"\n"),
    st.just("a = \"\\U0001F600\"\n"),
    st.just("a\t=\t1\n"),
    st.just("a = 1"),
    st.just("a = 1\r\nb = 2\r\n"),
)

strategy = st.one_of(_complete, _edge, _malformed(), _utf8_document())