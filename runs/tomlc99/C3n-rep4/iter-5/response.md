```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

# Characters allowed for bare (unquoted) keys per grammar: [A-Za-z0-9_-]
_BARE_KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

# A pool of interesting non-ASCII / escape / control characters for strings.
# NOTE: never emit a raw NUL byte in the document (harness skips NUL-terminated
# buffers). \u0000 as an escape inside a string is allowed.
_ESCAPES = [
    "\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u001F", "\\u007F", "\\u00E9", "\\u20AC", "\\uD83D", "\\uDE00",
    "\\U0001F600", "\\U00000000", "\\U0010FFFF",
]

# Raw control bytes that are NOT NUL (parser accepts raw control chars in strings).
_RAW_CONTROL = [chr(c) for c in range(1, 32) if c != 0] + [chr(127)]

_NON_ASCII = ["é", "ü", "ß", "π", "Ω", "中", "文", "🙂", "🚀", "\u00a0", "\u2028", "\u2029"]


def _bare_key():
    return st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=10)


def _basic_string_body():
    # Build a body char-by-char, mixing plain, escapes, raw controls, non-ASCII.
    plain = st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='"\n\\\x00',
    )
    esc = st.sampled_from(_ESCAPES)
    ctrl = st.sampled_from(_RAW_CONTROL)
    nonascii = st.sampled_from(_NON_ASCII)
    piece = st.one_of(plain, esc, ctrl, nonascii)
    return st.lists(piece, min_size=0, max_size=12).map("".join)


def _literal_string_body():
    plain = st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="'\n\x00",
    )
    return st.lists(plain, min_size=0, max_size=12).map("".join)


def _ml_basic_string_body():
    # multiline basic string: may contain newlines, escapes, controls.
    plain = st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='\\\x00',
    )
    esc = st.sampled_from(_ESCAPES)
    ctrl = st.sampled_from(_RAW_CONTROL)
    nonascii = st.sampled_from(_NON_ASCII)
    nl = st.just("\n")
    piece = st.one_of(plain, esc, ctrl, nonascii, nl)
    return st.lists(piece, min_size=0, max_size=12).map("".join)


def _ml_literal_string_body():
    plain = st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    )
    return st.lists(plain, min_size=0, max_size=12).map("".join)


# ---------- scalars ----------

def _string():
    basic = _basic_string_body().map(lambda b: '"' + b + '"')
    literal = _literal_string_body().map(lambda b: "'" + b + "'")
    ml_basic = _ml_basic_string_body().map(lambda b: '"""' + b + '"""')
    ml_literal = _ml_literal_string_body().map(lambda b: "'''" + b + "'''")
    return st.one_of(basic, literal, ml_basic, ml_literal)


def _integer():
    dec = st.one_of(
        st.integers(min_value=-(2**80), max_value=2**80).map(str),
        st.sampled_from([
            "0", "00", "007", "-0", "+0", "1_000", "-1_000",
            "9223372036854775807", "9223372036854775808",
            "-9223372036854775808", "-9223372036854775809",
            "18446744073709551615", "18446744073709551616",
            "1234567890123456789012345678901234567890",
        ]),
    )
    hex_ = st.sampled_from([
        "0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF",
        "0x1_2_3", "0xABCDEF0123456789",
    ])
    oct_ = st.sampled_from([
        "0o0", "0o777", "0o7_7_7", "0o01234567",
    ])
    bin_ = st.sampled_from([
        "0b0", "0b1", "0b1010_1010", "0b11111111111111111111111111111111",
    ])
    return st.one_of(dec, hex_, oct_, bin_)


def _float():
    sampled = st.sampled_from([
        "0.0", "-0.0", "+0.0", "1.", "1.0", ".5", "-.5", "+.5",
        "1e10", "1E10", "1e+10", "1e-10", "1.5e10", "1.5E-10",
        "1_000.000_1", "6.626e-34", "1e309", "-1e309", "1e-309",
        "3.141592653589793", "2.2250738585072014e-308",
        "1.7976931348623157e308", "inf", "+inf", "-inf", "nan", "+nan", "-nan",
        "0e0", "9_224_617.445_991_228_313",
    ])
    gen = st.tuples(
        st.integers(min_value=0, max_value=10**6),
        st.integers(min_value=0, max_value=10**6),
        st.integers(min_value=-320, max_value=320),
    ).map(lambda t: "%d.%de%d" % t)
    return st.one_of(sampled, gen)


def _bool():
    return st.sampled_from(["true", "false"])


def _date_time():
    return st.sampled_from([
        "1979-05-27T07:32:00Z",
        "1979-05-27T00:32:00-07:00",
        "1979-05-27T00:32:00.999999+07:00",
        "1979-05-27 07:32:00Z",
        "1979-05-27t07:32:00z",
        "1979-05-27T07:32:00",
        "1979-05-27T00:32:00.999999",
        "1979-05-27",
        "07:32:00",
        "00:32:00.999999",
        "1979-02-30",
        "0000-00-00",
        "9999-99-99T99:99:99Z",
        "2024-02-29T23:59:60+00:00",
        "1979-05-27T07:32:00+24:00",
    ])


# ---------- recursive values ----------

def _leaf_value():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _bool(),
        _date_time(),
    )


def _comment():
    # comment text: no newline; may include raw control chars and non-ASCII.
    plain = st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\n\r\x00",
    )
    ctrl = st.sampled_from(_RAW_CONTROL)
    nonascii = st.sampled_from(_NON_ASCII)
    piece = st.one_of(plain, ctrl, nonascii)
    return st.lists(piece, min_size=0, max_size=20).map(lambda cs: "#" + "".join(cs))


def _key():
    bare = _bare_key()
    quoted = _string()
    simple = st.one_of(bare, quoted)
    dotted = st.lists(simple, min_size=2, max_size=4).map(".".join)
    return st.one_of(simple, dotted)


def _inline_table(depth):
    # inline tables cannot contain newlines
    kv = st.tuples(_key(), _value(depth)).map(lambda t: t[0] + " = " + t[1])
    kvs = st.lists(kv, min_size=0, max_size=5)
    trailing = st.booleans()
    def build(t):
        items, tr = t
        if not items:
            return "{}"
        if tr:
            return "{" + ", ".join(items) + ",}"
        return "{" + ", ".join(items) + "}"
    return st.tuples(kvs, trailing).map(build)


def _array(depth):
    # arrays may contain newlines and comments
    sep = st.sampled_from([", ", ",\n", " , ", ",\n# c\n", ", # c\n"])
    trailing = st.booleans()
    def build(t):
        items, tr = t
        if not items:
            return "[]"
        body = sep.example() if False else ", "
        joined = body.join(items)
        if tr:
            joined += ","
        return "[" + joined + "]"
    return st.tuples(st.lists(_value(depth), min_size=0, max_size=5), trailing).map(build)


def _value(depth):
    if depth <= 0:
        return _leaf_value()
    return st.one_of(
        _leaf_value(),
        _array(depth - 1),
        _inline_table(depth - 1),
    )


# ---------- document structure ----------

def _key_value(depth):
    def build(t):
        k, v = t
        return k + " = " + v
    return st.tuples(_key(), _value(depth)).map(build)


def _standard_table():
    return _key().map(lambda k: "[" + k + "]")


def _array_table():
    return _key().map(lambda k: "[[" + k + "]]")


def _expression(depth):
    return st.one_of(
        _key_value(depth),
        _standard_table(),
        _array_table(),
        _comment(),
    )


def _document():
    # depth band concentrated in the parser's interesting recursion range.
    depth = st.integers(min_value=0, max_value=6)
    lines = depth.flatmap(lambda d: st.lists(_expression(d), min_size=0, max_size=8))
    trailing_nl = st.booleans()
    def build(t):
        exprs, tnl = t
        out = "\n".join(exprs)
        if tnl:
            out += "\n"
        return out
    return st.tuples(lines, trailing_nl).map(build)


# ---------- malformed / near-valid inputs ----------

_MALFORMED = [
    # missing or doubled delimiters
    "a = [1, 2",
    "a = [1, 2]]",
    "a = {b = 1",
    "a = {b = 1}}",
    "a = {b = 1,, c = 2}",
    "[t",
    "[[t]",
    "[[t]]]",
    "a = 1 = 2",
    "a =",
    "= 1",
    "a = ,",
    # unterminated strings
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    # stray tokens
    "a = @",
    "a = 1 2",
    "a b = 1",
    "a = 1\nb = 2\nc =",
    "@@@",
    "a = [",
    "a = {",
    # invalid escapes
    'a = "\\q"',
    'a = "\\x41"',
    # newline inside inline table
    "a = {b = 1,\nc = 2}",
    # value on next line
    "a =\n1",
    # duplicate keys
    "a = 1\na = 2",
    # duplicate tables
    "[t]\n[t]",
    # non-ascii bare key
    "é = 1",
    # empty key edge
    '"" = 1',
    # trailing junk
    "a = 1\n]",
    # control char in weird place
    "a = 1\x01",
]


def _malformed():
    return st.sampled_from(_MALFORMED)


# ---------- deep nesting (concentrated in the 1500-2048 band) ----------

def _deep_array():
    depth = st.integers(min_value=1500, max_value=2048)
    def build(d):
        return "a = " + "[" * d + "]" * d
    return depth.map(build)


def _deep_inline_table():
    depth = st.integers(min_value=1500, max_value=2048)
    def build(d):
        inner = "1"
        for _ in range(d):
            inner = "{x = " + inner + "}"
        return "a = " + inner
    return depth.map(build)


# ---------- utf8 decoding (toml_utf8_to_ucs) ----------

def _utf8_sequence():
    # Produce raw multi-byte UTF-8 sequences (valid + invalid) inside strings,
    # comments, keys, and bare positions so toml_utf8_to_ucs is exercised.
    # 2-byte (0xC0-0xDF), 3-byte (0xE0-0xEF), 4-byte (0xF0-0xF7) lead bytes,
    # continuation bytes (0x80-0xBF), plus overlong/invalid forms.
    lead = st.sampled_from([
        0xC2, 0xC3, 0xDF, 0xE0, 0xE1, 0xED, 0xEF, 0xF0, 0xF1, 0xF4, 0xF7,
        0xC0, 0xC1, 0xF5, 0xF8, 0xFC, 0xFE, 0xFF, 0x80, 0xBF,
    ])
    cont = st.sampled_from([0x80, 0x8F, 0x9F, 0xA0, 0xBF])
    # valid 2-byte, 3-byte, 4-byte encodings
    valid = st.sampled_from([
        "é".encode("utf-8").decode("latin-1"),
        "€".encode("utf-8").decode("latin-1"),
        "中".encode("utf-8").decode("latin-1"),
        "🙂".encode("utf-8").decode("latin-1"),
        "\U0010FFFF".encode("utf-8").decode("latin-1"),
    ])
    # truncated / invalid sequences
    bad = st.tuples(lead, cont).map(lambda t: bytes([t[0], t[1]]).decode("latin-1"))
    bad2 = st.tuples(lead, cont, cont).map(
        lambda t: bytes([t[0], t[1], t[2]]).decode("latin-1")
    )
    bad3 = st.tuples(lead, cont, cont, cont).map(
        lambda t: bytes([t[0], t[1], t[2], t[3]]).decode("latin-1")
    )
    lone = lead.map(lambda b: bytes([b]).decode("latin-1"))
    return st.one_of(valid, bad, bad2, bad3, lone)


def _utf8_document():
    # Embed raw UTF-8 byte sequences into various syntactic positions.
    seq = _utf8_sequence()
    def as_string(s):
        return 'a = "' + s + '"'
    def as_literal(s):
        return "a = '" + s + "'"
    def as_ml_string(s):
        return 'a = """' + s + '"""'
    def as_comment(s):
        return "# " + s
    def as_key(s):
        return '"' + s + '" = 1'
    def as_bare(s):
        return s + " = 1"
    def as_quoted_key(s):
        return '"pre' + s + 'post" = 1'
    builder = st.sampled_from([as_string, as_literal, as_ml_string, as_comment, as_key, as_bare, as_quoted_key])
    return st.tuples(builder, seq).map(lambda t: t[0](t[1]))


# ---------- assembled strategy ----------

def _valid_document():
    return _document()


def _edge_document():
    return st.one_of(
        st.just(""),
        st.just("\n"),
        st.just("# comment only"),
        st.just("# comment only\n"),
        st.just("a = 1"),
        st.just("a = 1\n"),
        st.just("a = 007"),
        st.just("a = 1."),
        st.just("a = .5"),
        st.just('a = "x\x01y"'),
        st.just("# comment \x01\n"),
        st.just("a = {b = 1,}"),
        st.just("a = 1979-02-30"),
        st.just("a = 1_000"),
        st.just("a = 1e309"),
        st.just("a = inf"),
        st.just("a = -inf"),
        st.just("a = nan"),
        st.just("a = 0xDEAD_BEEF"),
        st.just("a = 0o777"),
        st.just("a = 0b1010_1010"),
        st.just("a = 1979-05-27 07:32:00Z"),
        st.just("a = 07:32:00"),
        st.just('a = """\nhello\n"""'),
        st.just("a = '''\nhello\n'''"),
        st.just('a = "\\u0000"'),
        st.just('a = "\\U0001F600"'),
        st.just("a = []"),
        st.just("a = {}"),
        st.just("[t]"),
        st.just("[[a]]"),
        st.just('"" = 1'),
        st.just("a.b.c = 1"),
        st.just("a = [1, 2, 3,]"),
        st.just("a = [\n1,\n2,\n]"),
        st.just("a = [1, # c\n2]"),
        st.just("a = 1\r\nb = 2"),
        st.just("\ta = 1"),
        st.just("a" * 10000 + " = 1"),
        st.just("a = 1"),  # no trailing newline
    )


strategy = st.one_of(
    _valid_document(),
    _edge_document(),
    _malformed(),
    _deep_array(),
    _deep_inline_table(),
    _utf8_document(),
)
```