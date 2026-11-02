```python
from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

_bare_key_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)

def _bare_key():
    return st.lists(_bare_key_char, min_size=1, max_size=12).map("".join)

_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

def _unicode_escape():
    return st.integers(min_value=0, max_value=0xFFFF).map(
        lambda n: "\\u%04X" % n
    )

def _ex_unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\U%08X" % n
    )

def _basic_char():
    return st.one_of(
        _escape,
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters='"\x00\\\n',
                min_codepoint=0x20,
            ),
            min_size=0,
            max_size=8,
        ),
        _unicode_escape(),
        _ex_unicode_escape(),
        st.integers(min_value=1, max_value=0x1F).map(chr),
    )

def _basic_string():
    return st.lists(_basic_char(), max_size=6).map(lambda cs: '"' + "".join(cs) + '"')

def _literal_char():
    return st.one_of(
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters="'\x00\n",
            ),
            min_size=0,
            max_size=8,
        ),
        st.integers(min_value=1, max_value=0x1F).map(chr),
    )

def _literal_string():
    return st.lists(_literal_char(), max_size=6).map(lambda cs: "'" + "".join(cs) + "'")

def _ml_basic_string():
    inner = st.lists(
        st.one_of(
            _escape,
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters='"\x00\\',
                ),
                min_size=0,
                max_size=10,
            ),
            _unicode_escape(),
            st.just("\n"),
            st.integers(min_value=1, max_value=0x1F).map(chr),
        ),
        max_size=6,
    ).map("".join)
    return inner.map(lambda s: '"""' + s + '"""')

def _ml_literal_string():
    inner = st.lists(
        st.one_of(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="'\x00",
                ),
                min_size=0,
                max_size=10,
            ),
            st.just("\n"),
            st.integers(min_value=1, max_value=0x1F).map(chr),
        ),
        max_size=6,
    ).map("".join)
    return inner.map(lambda s: "'''" + s + "'''")

def _string():
    return st.one_of(
        _basic_string(),
        _literal_string(),
        _ml_basic_string(),
        _ml_literal_string(),
    )

# ---------- numbers ----------

def _dec_int():
    return st.one_of(
        st.integers(min_value=0, max_value=10**6).map(str),
        st.integers(min_value=0, max_value=999).map(lambda n: "0" + str(n)),
        st.integers(min_value=1000, max_value=10**12).map(
            lambda n: "{:,}".format(n).replace(",", "_")
        ),
        st.integers(min_value=0, max_value=10**40).map(str),
        st.integers(min_value=-(10**20), max_value=10**20).map(str),
        st.sampled_from(["+0", "-0", "0"]),
    )

def _hex_int():
    return st.one_of(
        st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "0x%X" % n),
        st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "0x%x" % n),
        st.integers(min_value=0, max_value=0xFFFF).map(
            lambda n: "0x" + "{:x}".format(n).replace("", "_").strip("_")
        ),
        st.just("0x0"),
        st.just("0xFFFFFFFFFFFFFFFFFFFFFFFF"),
    )

def _oct_int():
    return st.one_of(
        st.integers(min_value=0, max_value=0o7777).map(lambda n: "0o%o" % n),
        st.just("0o0"),
        st.just("0o7777777777777777777777"),
    )

def _bin_int():
    return st.one_of(
        st.integers(min_value=0, max_value=0xFF).map(lambda n: "0b" + bin(n)[2:]),
        st.just("0b0"),
        st.just("0b" + "1" * 64),
    )

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    return st.one_of(
        st.floats(allow_nan=False, allow_infinity=False, width=64).map(repr),
        st.integers(min_value=0, max_value=1000).map(lambda n: "%d." % n),
        st.integers(min_value=0, max_value=1000).map(lambda n: ".%d" % n),
        st.integers(min_value=-400, max_value=400).map(lambda e: "1e%d" % e),
        st.integers(min_value=-400, max_value=400).map(lambda e: "1E+%d" % e),
        st.just("1e309"),
        st.just("1e-400"),
        st.just("1.7976931348623157e+308"),
        st.just("1_000.000_1"),
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    )

# ---------- date-time ----------

def _year():
    return st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)

def _month():
    return st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

def _day():
    return st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

def _full_date():
    return st.tuples(_year(), _month(), _day()).map(lambda t: "%s-%s-%s" % t)

def _partial_time():
    return st.tuples(
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.one_of(st.none(), st.integers(min_value=0, max_value=999999).map(lambda n: ".%d" % n)),
    ).map(lambda t: "%s:%s:%s%s" % (t[0], t[1], t[2], t[3] or ""))

def _offset():
    return st.one_of(
        st.just("Z"),
        st.just("z"),
        st.tuples(
            st.sampled_from(["+", "-"]),
            st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
            st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        ).map(lambda t: "%s%s:%s" % t),
    )

def _delim():
    return st.sampled_from(["T", "t", " "])

def _offset_date_time():
    return st.tuples(_full_date(), _delim(), _partial_time(), _offset()).map(
        lambda t: "%s%s%s%s" % t
    )

def _local_date_time():
    return st.tuples(_full_date(), _delim(), _partial_time()).map(
        lambda t: "%s%s%s" % t
    )

def _local_date():
    return _full_date()

def _local_time():
    return _partial_time()

def _date_time():
    return st.one_of(
        _offset_date_time(),
        _local_date_time(),
        _local_date(),
        _local_time(),
    )

def _bool():
    return st.sampled_from(["true", "false"])

# ---------- keys ----------

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_quoted_key(), _bare_key())

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=3).map(lambda ks: ".".join(ks))

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------- recursive values ----------

def _scalar_value():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _bool(),
        _date_time(),
    )

def _value(depth):
    if depth <= 0:
        return _scalar_value()
    return st.one_of(
        _scalar_value(),
        _array(depth - 1),
        _inline_table(depth - 1),
    )

def _array(depth):
    inner = st.lists(
        st.one_of(
            _value(depth),
            st.just(""),
        ),
        max_size=4,
    )
    def render(items):
        body = ", ".join(items)
        return "[" + body + "]"
    return inner.map(render)

def _inline_table(depth):
    pair = st.tuples(_key(), _value(depth)).map(lambda t: "%s = %s" % t)
    pairs = st.lists(pair, max_size=3)
    def render(ps):
        return "{" + ", ".join(ps) + "}"
    return pairs.map(render)

def _any_value():
    return _value(3)

# ---------- documents ----------

def _comment():
    return st.lists(
        st.one_of(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="\x00\n",
                ),
                min_size=0,
                max_size=20,
            ),
            st.integers(min_value=1, max_value=0x1F).map(chr),
        ),
        max_size=6,
    ).map(lambda cs: "#" + "".join(cs))

def _key_value_line():
    return st.tuples(_key(), _any_value()).map(lambda t: "%s = %s" % t)

def _standard_table():
    return _key().map(lambda k: "[" + k + "]")

def _array_table():
    return _key().map(lambda k: "[[" + k + "]]")

def _expression():
    return st.one_of(
        _key_value_line(),
        _standard_table(),
        _array_table(),
        _comment(),
    )

def _document():
    lines = st.lists(_expression(), max_size=6)
    def render(ls):
        return "\n".join(ls)
    return lines.map(render)

# ---------- malformed / near-valid ----------

def _malformed():
    return st.one_of(
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters='"\x00\n',
            ),
            min_size=1,
            max_size=6,
        ).map(lambda s: 'a = "' + s),
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters="'\x00\n",
            ),
            min_size=1,
            max_size=6,
        ).map(lambda s: "a = '" + s),
        st.just("a = [1, 2, 3"),
        st.just("a = [[1, 2]]]"),
        st.just("a = = 1"),
        st.just("a 1"),
        st.just("a = {b = 1,\n c = 2}"),
        st.just('a = "\\q"'),
        st.just("a =\n1"),
        st.just("é = 1"),
        st.just("a = 1\na = 2"),
        st.just("[t]\n[t]"),
        st.just("[t]\n[[t]]"),
        st.just(" = 1"),
        st.just("[ ]"),
        st.just("[]"),
        st.just("[[ ]]"),
        st.just("a. = 1"),
        st.just(".a = 1"),
    )

# ---------- strategy ----------

def _depth_band():
    return st.integers(min_value=1500, max_value=2048)

def _deep_array(depth):
    def build(n):
        if n <= 0:
            return st.just("[]")
        return build(n - 1).map(lambda s: "[" + s + "]")
    return build(depth)

def _deep_inline_table(depth):
    def build(n):
        if n <= 0:
            return st.just("{}")
        return build(n - 1).map(lambda s: "{a = " + s + "}")
    return build(depth)

def _deep_nesting():
    return st.one_of(
        _depth_band().flatmap(_deep_array),
        _depth_band().flatmap(_deep_inline_table),
    )

# ----- UTF-8 decoding paths (toml_utf8_to_ucs) -----
# Target the actual decoder by feeding raw byte sequences. The harness
# encodes str -> bytes as UTF-8, so to reach the decoder we must emit
# characters whose UTF-8 encoding is valid; malformed sequences must be
# produced via lone surrogate escapes... but those can't be encoded.
# Instead, we exercise every valid multi-byte length plus boundary
# code points, and use latin-1 chars that become 2-byte UTF-8 on encode,
# which still routes through the multi-byte decoder.

_utf8_byte_seq = st.one_of(
    # 2-byte boundary
    st.sampled_from(["\u0080", "\u00bf", "\u00c0", "\u00c1", "\u00ff"]),
    # 2-byte general
    st.integers(min_value=0x80, max_value=0x7FF).map(chr),
    # 3-byte boundary (excluding surrogates)
    st.sampled_from(["\u0800", "\ud7ff", "\ue000", "\uffff"]),
    st.integers(min_value=0x800, max_value=0xFFFF).filter(
        lambda n: not (0xD800 <= n <= 0xDFFF)
    ).map(chr),
    # 4-byte boundary
    st.sampled_from(["\U00010000", "\U0010ffff", "\U0001f600"]),
    st.integers(min_value=0x10000, max_value=0x10FFFF).map(chr),
)

def _utf8_fragment():
    return st.lists(_utf8_byte_seq, min_size=1, max_size=6).map("".join)

def _utf8_documents():
    frag = _utf8_fragment()
    return st.one_of(
        frag.map(lambda s: 'a = "' + s + '"'),
        frag.map(lambda s: "a = '" + s + "'"),
        frag.map(lambda s: 'a = """' + s + '"""'),
        frag.map(lambda s: "a = '''" + s + "'''"),
        frag.map(lambda s: "# " + s),
        frag.map(lambda s: s + " = 1"),
        frag.map(lambda s: '"' + s + '" = 1'),
        frag.map(lambda s: "[" + s + "]"),
        frag.map(lambda s: "[[" + s + "]]"),
        frag,
        frag.map(lambda s: "a = 1 # " + s),
    )

# ----- literal-string normalisation (norm_lit_str) -----

def _lit_str_edge():
    return st.one_of(
        st.just("a = 'line1\nline2'"),
        st.just("a = 'line1\r\nline2'"),
        st.just("a = '''\nline1\nline2\n'''"),
        st.just("a = '''\r\nline1\r\nline2\r\n'''"),
        st.just("a = '''''"),
        st.just("a = ''''''"),
        st.just("a = ''''x''''"),
        st.just("a = '''\n'''"),
        st.just("a = '\\'"),
        st.just("a = '\\n'"),
        st.just("a = '''\\'''"),
        st.just("a = '''a''b'''"),
        st.just("a = '''a'''b'''"),
        st.just("a = 'x" + "\x01" + "y'"),
        st.just("a = '''x" + "\x01" + "y'''"),
        st.just("a = '" + "z" * 200 + "'"),
        st.just("a = '''" + "z" * 200 + "'''"),
        st.just("a = 'x\ty'"),
        st.just("a = '''x\ty'''"),
    )

# ----- float conversion (toml_rtod_ex) -----

def _float_edge():
    return st.one_of(
        st.just("a = 0.0"),
        st.just("a = -0.0"),
        st.just("a = +0.0"),
        st.just("a = 0e0"),
        st.just("a = 0e-0"),
        st.just("a = 0e+0"),
        st.just("a = 1e0"),
        st.just("a = 1E0"),
        st.just("a = 1e-0"),
        st.just("a = 1e+0"),
        st.just("a = 1.0e0"),
        st.just("a = 1.0E0"),
        st.just("a = 1_0.0_1e1_0"),
        st.just("a = 1e308"),
        st.just("a = 1e-308"),
        st.just("a = 4.9406564584124654e-324"),
        st.just("a = 2.2250738585072014e-308"),
        st.just("a = 1.7976931348623157e308"),
        st.just("a = 1.7976931348623159e308"),
        st.just("a = 1e999"),
        st.just("a = -1e999"),
        st.just("a = 1e-999"),
        st.just("a = 0.0000000000000000000000000000001"),
        st.just("a = 123456789012345678901234567890.0"),
        st.just("a = 1." + "0" * 400 + "e1"),
        st.just("a = ." + "0" * 400 + "1"),
        st.just("a = 1e0000000000000000000001"),
        st.just("a = 1e-0000000000000000000001"),
        st.just("a = 1_2_3.4_5_6e7_8"),
        st.just("a = 1_2_3e4_5"),
        st.just("a = +1.5e+10"),
        st.just("a = -1.5e-10"),
    )

# ----- file parsing (toml_parse_file) -----

def _file_like_documents():
    return st.one_of(
        st.just("\ufeffa = 1"),
        st.just("\ufeff# comment\n"),
        st.just("\ufeff"),
        st.just("\ufeff\ufeff"),
        st.just("a = 1\r\nb = 2\r\n"),
        st.just("a = 1\rb = 2"),
        st.just("[a]\r\n[b]\r\n"),
        st.just("a = 1\0"),
        st.just("a = 1\x00b = 2"),
        st.just("a = 1\x00"),
        st.just("# comment\x00\na = 1"),
        st.just("a = 1\n\x00"),
        st.just("a = 1\ntrailing garbage"),
        st.just("\n\n\n\na = 1\n\n\n"),
        st.just("a = 1\n# trailing comment"),
        st.just("a = 1\n# trailing comment\n"),
        st.just("[t]\na = 1\n[t.b]\nc = 2\n"),
        st.just("[[t]]\na = 1\n[[t]]\na = 2\n"),
        st.just("x = 1\ny = 2\nz = 3\n"),
        st.just("a = {b = 1}\n[t]\nc = 2\n"),
    )

def _edge_documents():
    return st.one_of(
        st.just(""),
        st.just("\n"),
        st.just("# only a comment"),
        st.just("# comment\n"),
        st.just("[t]"),
        st.just("[[a]]"),
        st.just("[[a]]\n[[a]]"),
        st.just('"" = 1'),
        st.just("'' = 1"),
        st.just("a = []"),
        st.just("a = {}"),
        st.just("a = [[]]"),
        st.just("a = [{b = 1}]"),
        st.just("a = {b = 1,}"),
        st.just("a = 007"),
        st.just("a = 1."),
        st.just("a = .5"),
        st.just('a = "x\x01y"'),
        st.just("# comment with \x01 control"),
        st.just("a = 1979-02-30"),
        st.just("a = 1e309"),
        st.just("a = 0xFFFFFFFFFFFFFFFFFFFFFFFF"),
        st.just("a = 1_000"),
        st.just("a = inf"),
        st.just("a = -inf"),
        st.just("a = nan"),
        st.just("a = true"),
        st.just("a = false"),
        st.just("a = 1979-05-27T07:32:00Z"),
        st.just("a = 1979-05-27 07:32:00Z"),
        st.just("a = 1979-05-27T07:32:00"),
        st.just("a = 1979-05-27"),
        st.just("a = 07:32:00"),
        st.just("a = 07:32:00.999999"),
        st.just("a = {b = 1, c = 2}"),
        st.just("a = [1, 2, 3,]"),
        st.just("a = [\n1,\n2,\n]"),
        st.just("a.b.c = 1"),
        st.just('"a b" = 1'),
        st.just("'a b' = 1"),
        st.just("a = \"\"\"multi\nline\"\"\""),
        st.just("a = '''multi\nline'''"),
        st.just("a = \"\\u0041\""),
        st.just("a = \"\\U0001F600\""),
        st.just("a = \"\\u0000\""),
        st.just("a = 1\r\nb = 2"),
        st.just("\ta = 1"),
        st.just("a = 1"),
        st.just("a = 1\n"),
        st.just("a" * 10000 + " = 1"),
        st.just("[a.b.c]"),
        st.just("[a]\n[a.b]"),
        st.just("[a.b]\n[a]"),
        st.just("[[a.b]]"),
        st.just("a = {b = {c = {d = 1}}}"),
    )

def _documents():
    return st.one_of(
        _document(),
        _malformed(),
        _edge_documents(),
        _deep_nesting(),
        _utf8_documents(),
        _lit_str_edge(),
        _float_edge(),
        _file_like_documents(),
    )

strategy = _documents()
```