from hypothesis import strategies as st
import json

# ---------- primitives ----------

_bare_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

def _bare_key():
    return st.text(alphabet=_bare_chars, min_size=1, max_size=12)

def _quoted_key():
    return st.one_of(
        st.text(alphabet="abcXYZ0123 _-", min_size=0, max_size=8).map(lambda s: '"' + s + '"'),
        st.text(alphabet="abcXYZ0123 _-", min_size=0, max_size=8).map(lambda s: "'" + s + "'"),
    )

def _simple_key():
    return st.one_of(_bare_key(), _quoted_key())

def _key():
    return st.one_of(
        _simple_key(),
        st.lists(_simple_key(), min_size=2, max_size=4).map(lambda ks: ".".join(ks)),
    )

# ---------- strings ----------

_escapes = ["\\b", "\\t", "\\n", "\\f", "\\r", "\\\"", "\\\\", "\\/",
            "\\u0041", "\\u00e9", "\\u0000", "\\U0001F600", "\\U00000041"]

def _basic_string_body():
    return st.one_of(
        st.text(alphabet="abcXYZ 0123!@#$%^&*()", min_size=0, max_size=10),
        st.sampled_from(_escapes),
        st.lists(st.one_of(
            st.text(alphabet="abcXYZ 0123", min_size=0, max_size=4),
            st.sampled_from(_escapes),
            st.sampled_from(["\x01", "\x02", "\x7f", "\t"]),
        ), min_size=0, max_size=4).map(lambda xs: "".join(xs)),
        st.sampled_from(["é", "日本語", "ñ", "\u00e9\u00e8"]),
    )

def _basic_string():
    return _basic_string_body().map(lambda s: '"' + s + '"')

def _literal_string():
    return st.text(alphabet="abcXYZ 0123!@#é", min_size=0, max_size=10).map(lambda s: "'" + s + "'")

def _ml_basic_string():
    bodies = st.one_of(
        st.text(alphabet="abcXYZ 0123\n\t", min_size=0, max_size=12),
        st.lists(st.one_of(
            st.text(alphabet="abcXYZ \n0123", min_size=0, max_size=4),
            st.sampled_from(["\\\n", "\\n", "\\t", "\\u0041", "\\U0001F600"]),
        ), min_size=0, max_size=4).map(lambda xs: "".join(xs)),
    )
    return bodies.map(lambda s: '"""' + s + '"""')

def _ml_literal_string():
    return st.text(alphabet="abcXYZ 0123\n\t", min_size=0, max_size=12).map(lambda s: "'''" + s + "'''")

def _string():
    return st.one_of(_basic_string(), _literal_string(), _ml_basic_string(), _ml_literal_string())

# ---------- numbers ----------

def _dec_int():
    return st.one_of(
        st.integers(min_value=-10**18, max_value=10**18).map(str),
        st.sampled_from(["0", "007", "00", "-0", "+0", "1_000", "9_9_9",
                         "9223372036854775807", "-9223372036854775808",
                         "99999999999999999999999999999999"]),
    )

def _hex_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x")),
        st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xabcdefABCDEF"]),
    )

def _oct_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2**32).map(lambda n: "0o" + format(n, "o")),
        st.sampled_from(["0o0", "0o777", "0o7_7_7"]),
    )

def _bin_int():
    return st.one_of(
        st.integers(min_value=0, max_value=2**32).map(lambda n: "0b" + format(n, "b")),
        st.sampled_from(["0b0", "0b1010", "0b1_0_1"]),
    )

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    return st.one_of(
        st.floats(allow_nan=False, allow_infinity=False).map(repr),
        st.sampled_from(["1.0", "-1.5", "+3.14", "1e10", "1E-10", "1e+309",
                         "1.", ".5", "0.0", "1.0e309", "6.626e-34",
                         "1_0.5_0", "3.14159_26535"]),
        st.just("inf"), st.just("-inf"), st.just("+inf"),
        st.just("nan"), st.just("-nan"), st.just("+nan"),
    )

def _bool():
    return st.sampled_from(["true", "false"])

def _date_time():
    return st.sampled_from([
        "1979-05-27T07:32:00Z", "1979-05-27t07:32:00z",
        "1979-05-27 07:32:00Z", "1979-05-27T00:32:00-07:00",
        "1979-05-27T00:32:00+07:00", "1979-05-27T07:32:00.999999Z",
        "1979-05-27T07:32:00", "1979-05-27 07:32:00",
        "1979-05-27", "1979-02-30", "0000-00-00",
        "07:32:00", "07:32:00.999", "23:59:60",
    ])

# ---------- composite values ----------

def _scalar_value():
    return st.one_of(_string(), _integer(), _float(), _bool(), _date_time())

def _inline_table(depth):
    if depth <= 0:
        return st.just("{}")
    keyval = st.tuples(_key(), _value(depth - 1)).map(lambda kv: kv[0] + " = " + kv[1])
    return st.one_of(
        st.just("{}"),
        st.lists(keyval, min_size=1, max_size=3).map(lambda xs: "{" + ", ".join(xs) + "}"),
        st.lists(keyval, min_size=1, max_size=3).map(lambda xs: "{" + ", ".join(xs) + ",}"),
    )

def _array(depth):
    if depth <= 0:
        return st.just("[]")
    inner = _value(depth - 1)
    return st.one_of(
        st.just("[]"),
        st.lists(inner, min_size=1, max_size=4).map(lambda xs: "[" + ", ".join(xs) + "]"),
        st.lists(inner, min_size=1, max_size=4).map(lambda xs: "[" + ", ".join(xs) + ",]"),
        st.lists(inner, min_size=1, max_size=3).map(lambda xs: "[\n  " + ",\n  ".join(xs) + ",\n]"),
    )

def _value(depth):
    if depth <= 0:
        return _scalar_value()
    return st.one_of(
        _scalar_value(),
        _array(depth),
        _inline_table(depth),
    )

# ---------- document structure ----------

def _key_value(depth):
    return st.tuples(_key(), _value(depth)).map(lambda kv: kv[0] + " = " + kv[1])

def _standard_table():
    return _key().map(lambda k: "[" + k + "]")

def _array_table():
    return _key().map(lambda k: "[[" + k + "]]")

def _comment():
    return st.one_of(
        st.just(""),
        st.text(alphabet="abcXYZ 0123!@#$", min_size=0, max_size=20).map(lambda s: "# " + s),
        st.just("#\x01\x02 control"),
    )

def _line(depth):
    return st.one_of(
        _key_value(depth),
        _standard_table(),
        _array_table(),
        _comment(),
    )

# ---------- malformed / near-valid ----------

def _malformed(depth):
    base = _value(depth)
    return st.one_of(
        # unterminated string
        st.just('a = "unterminated'),
        st.just("a = 'unterminated"),
        st.just('a = """unterminated'),
        # missing delimiter
        st.just("a = [1, 2"),
        st.just("a = {b = 1"),
        st.just("[table"),
        st.just("[[array_table"),
        # doubled delimiter
        st.just("a = [[1, 2]]"),
        st.just("a = {{b = 1}}"),
        st.just("a == 1"),
        # stray token
        st.just("a = 1 2 3"),
        st.just("= 1"),
        st.just("a ="),
        st.just("a = "),
        st.just("a 1"),
        st.just("]"),
        st.just("}"),
        st.just("[["),
        # invalid escape
        st.just('a = "\\q"'),
        # value on next line
        st.just("a =\n1"),
        # newline inside inline table
        st.just("a = {b = 1,\nc = 2}"),
        # duplicate keys (rejected)
        st.just("a = 1\na = 2"),
        st.just("[t]\nx = 1\n[t]\ny = 2"),
        # non-ascii bare key
        st.just("é = 1"),
        st.just("ключ = 1"),
        # bare key with invalid char
        st.just("a b = 1"),
        # stray control in key position
        st.just("\x01 = 1"),
        # empty
        st.just(""),
    )

# ---------- deep nesting ----------

def _deep_array(n):
    return st.just("[" * n + "]" * n)

def _deep_inline_table(n):
    # {a = {a = ... {}} ...}
    inner = "{}"
    parts = ["{}"]
    for i in range(n):
        parts.append("{a = " + parts[-1] + "}")
    return st.just(parts[-1])

def _deep_document():
    return st.one_of(
        st.integers(min_value=1500, max_value=2048).map(_deep_array_value),
        st.integers(min_value=1, max_value=64).map(_deep_inline_value),
        st.integers(min_value=1, max_value=64).map(_deep_array_value),
    )

def _deep_array_value(n):
    return "a = " + "[" * n + "]" * n

def _deep_inline_value(n):
    inner = "{}"
    for _ in range(n):
        inner = "{a = " + inner + "}"
    return "a = " + inner

# ---------- utf8 -> ucs decoding coverage ----------

_utf8_ucs_samples = [
    # 1-byte ASCII
    "a = \"plain ascii\"\n",
    # 2-byte sequences (U+0080..U+07FF)
    "a = \"\u0080\"\n",
    "a = \"\u00e9\"\n",
    "a = \"\u00ff\"\n",
    "a = \"\u07ff\"\n",
    "a = \"\u0500\u06ff\"\n",
    # 3-byte sequences (U+0800..U+FFFF)
    "a = \"\u0800\"\n",
    "a = \"\u0fff\"\n",
    "a = \"\u4e2d\u6587\"\n",
    "a = \"\u3042\u3044\u3046\"\n",
    "a = \"\uffff\"\n",
    "a = \"\ud7ff\"\n",
    # 4-byte sequences (U+10000..U+10FFFF)
    "a = \"\U00010000\"\n",
    "a = \"\U0001F600\"\n",
    "a = \"\U0010FFFF\"\n",
    "a = \"\U00020000\U0002FFFF\"\n",
    # mixed widths in one string
    "a = \"a\u00e9\u4e2d\U0001F600z\"\n",
    # in keys, comments, tables
    "\u00e9 = 1\n",
    "\u4e2d\u6587 = 2\n",
    "[\u00e9]\nx = 1\n",
    "[\u4e2d\u6587]\ny = 1\n",
    "[[\u00e9.\u4e2d]]\nz = 1\n",
    "# comment \u00e9 \u4e2d \U0001F600\n",
    # multi-line strings with multibyte
    "a = \"\"\"\u00e9\u4e2d\U0001F600\"\"\"\n",
    "a = '''\u00e9\u4e2d\U0001F600'''\n",
    # truncated / invalid utf8 byte sequences embedded
    "a = \"\xc3\"\n",
    "a = \"\xc3\x28\"\n",
    "a = \"\xe2\x28\xa1\"\n",
    "a = \"\xf0\x28\x8c\x28\"\n",
    "a = \"\x80\"\n",
    "a = \"\xbf\"\n",
    "a = \"\xed\xa0\x80\"\n",
    "a = \"\xf4\x90\x80\x80\"\n",
    "a = \"\xff\xfe\"\n",
    "a = \"\xfe\xff\"\n",
    "a = \"\xc0\x80\"\n",
    "a = \"\xe0\x80\x80\"\n",
    "a = \"\xf0\x80\x80\x80\"\n",
    # BOM
    "\ufeffa = 1\n",
    "\ufeff# bom comment\n",
    # lone surrogates encoded as escapes / raw
    "a = \"\\ud800\"\n",
    "a = \"\\udfff\"\n",
    "a = \"\\uD83D\\uDE00\"\n",
    "a = \"\\uFFFD\"\n",
    # long multibyte string to stress decoder loop
    "a = \"" + "\u00e9" * 64 + "\"\n",
    "a = \"" + "\u4e2d" * 64 + "\"\n",
    "a = \"" + "\U0001F600" * 64 + "\"\n",
    # boundary codepoints
    "a = \"\u007f\u0080\"\n",
    "a = \"\u07ff\u0800\"\n",
    "a = \"\uffff\U00010000\"\n",
    # across key/value/table mixed
    "\u00e9 = \"\u4e2d\"\n[\u00e9]\n\u4e2d = \"\U0001F600\"\n",
]

def _utf8_ucs_document():
    return st.sampled_from(_utf8_ucs_samples)

# ---------- utf8 -> ucs branch coverage (raw byte sequences) ----------

def _utf8_ucs_raw_document():
    # Build raw byte sequences that exercise each branch of a UTF-8 decoder:
    # lead-byte classes (0x00-0x7F, 0xC0-0xDF, 0xE0-0xEF, 0xF0-0xF7, 0xF8-0xFF),
    # continuation-byte checks, overlong encodings, surrogate range, > U+10FFFF,
    # truncated sequences, and 5/6-byte legacy forms.
    lead = st.sampled_from([
        0x00, 0x41, 0x7F,               # 1-byte
        0xC2, 0xDF,                     # valid 2-byte lead
        0xC0, 0xC1,                     # overlong 2-byte lead
        0xE0, 0xE1, 0xED, 0xEF,         # valid 3-byte lead (ED = surrogate range)
        0xF0, 0xF1, 0xF4, 0xF5, 0xF7,   # valid/edge 4-byte lead
        0xF8, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF,  # 5/6-byte legacy / invalid
        0x80, 0x8F, 0x9F, 0xBF,         # stray continuation
    ])
    cont = st.sampled_from([0x80, 0x8F, 0x9F, 0xAF, 0xBF, 0x00, 0x41, 0xC0, 0xFF])

    def seq():
        n = st.integers(min_value=0, max_value=6)
        return st.tuples(lead, st.lists(cont, min_size=0, max_size=6)).map(
            lambda lc: bytes([lc[0]] + lc[1])
        )

    def make_doc(b: bytes):
        # wrap in a TOML string context; decode latin-1 so bytes survive as str
        # (Hypothesis strings are unicode; latin-1 round-trips to raw bytes on
        #  a UTF-8 encoder only for 0x00-0x7F, so we emit the bytes directly via
        #  a surrogateescape-free latin-1 representation).
        return 'a = "' + b.decode("latin-1") + '"\n'

    def make_bare(b: bytes):
        return b.decode("latin-1")

    return st.one_of(
        st.lists(seq(), min_size=1, max_size=4).map(
            lambda bs: "".join(make_doc(b) for b in bs)
        ),
        st.lists(seq(), min_size=1, max_size=4).map(
            lambda bs: "".join(make_bare(b) for b in bs)
        ),
        st.lists(seq(), min_size=1, max_size=4).map(
            lambda bs: "# " + "".join(make_bare(b) for b in bs) + "\n"
        ),
        seq().map(make_doc),
        seq().map(make_bare),
    )

# ---------- toml_utf8_to_ucs targeted coverage ----------

def _utf8_to_ucs_document():
    # Explicitly enumerate the branch structure of a toml_utf8_to_ucs decoder:
    # it typically dispatches on the lead byte, then loops over continuation
    # bytes, validating ranges and reconstructing the codepoint. Each sample
    # below targets a distinct branch path.
    samples = [
        # ---- 1-byte lead (0x00..0x7F): no continuation loop ----
        "a = \"\\x00\"\n",
        "a = \"A\"\n",
        "a = \"\\x7f\"\n",
        # ---- 2-byte lead 0xC0..0xDF ----
        # valid 2-byte: C2 80 (U+0080) .. DF BF (U+07FF)
        "a = \"\u0080\"\n",           # C2 80
        "a = \"\u07ff\"\n",           # DF BF
        "a = \"\u00c3\u00a9\"\n",     # C3 A9 (é)
        # overlong 2-byte: C0 80, C1 BF
        "a = \"\u00c0\u0080\"\n",
        "a = \"\u00c1\u00bf\"\n",
        # truncated 2-byte: lead only
        "a = \"\u00c2\"\n",
        "a = \"\u00df\"\n",
        # bad continuation after 2-byte lead
        "a = \"\u00c2\u0041\"\n",
        "a = \"\u00c2\u00c0\"\n",
        "a = \"\u00c2\u00ff\"\n",
        # ---- 3-byte lead 0xE0..0xEF ----
        # valid 3-byte: E0 A0 80 (U+0800) .. EF BF BF (U+FFFF)
        "a = \"\u0800\"\n",           # E0 A0 80 (lowest valid 3-byte)
        "a = \"\uffff\"\n",           # EF BF BF (highest valid 3-byte)
        "a = \"\u4e2d\"\n",           # E4 B8 AD
        # overlong 3-byte: E0 80 80 .. E0 9F BF
        "a = \"\u00e0\u0080\u0080\"\n",
        "a = \"\u00e0\u009f\u00bf\"\n",
        # surrogate range: ED A0 80 .. ED BF BF
        "a = \"\u00ed\u00a0\u0080\"\n",
        "a = \"\u00ed\u00bf\u00bf\"\n",
        # truncated 3-byte: 1 or 2 bytes
        "a = \"\u00e0\"\n",
        "a = \"\u00e0\u00a0\"\n",
        "a = \"\u00e4\u00b8\"\n",
        # bad continuation after 3-byte lead
        "a = \"\u00e0\u0041\u0080\"\n",
        "a = \"\u00e0\u00a0\u0041\"\n",
        "a = \"\u00e0\u00ff\u00bf\"\n",
        "a = \"\u00ef\u00bf\u0041\"\n",
        # ---- 4-byte lead 0xF0..0xF7 ----
        # valid 4-byte: F0 90 80 80 (U+10000) .. F4 8F BF BF (U+10FFFF)
        "a = \"\U00010000\"\n",       # F0 90 80 80 (lowest valid 4-byte)
        "a = \"\U0010FFFF\"\n",       # F4 8F BF BF (highest valid 4-byte)
        "a = \"\U0001F600\"\n",       # F0 9F 98 80
        # overlong 4-byte: F0 80 80 80 .. F0 8F BF BF
        "a = \"\u00f0\u0080\u0080\u0080\"\n",
        "a = \"\u00f0\u008f\u00bf\u00bf\"\n",
        # beyond U+10FFFF: F4 90 80 80 .. F7 BF BF BF
        "a = \"\u00f4\u0090\u0080\u0080\"\n",
        "a = \"\u00f5\u0080\u0080\u0080\"\n",
        "a = \"\u00f7\u00bf\u00bf\u00bf\"\n",
        # truncated 4-byte: 1, 2, or 3 bytes
        "a = \"\u00f0\"\n",
        "a = \"\u00f0\u0090\"\n",
        "a = \"\u00f0\u0090\u0080\"\n",
        "a = \"\u00f4\u008f\u00bf\"\n",
        # bad continuation after 4-byte lead
        "a = \"\u00f0\u0041\u0080\u0080\"\n",
        "a = \"\u00f0\u0090\u0041\u0080\"\n",
        "a = \"\u00f0\u0090\u0080\u0041\"\n",
        "a = \"\u00f0\u00c0\u0080\u0080\"\n",
        "a = \"\u00f0\u0090\u00ff\u00bf\"\n",
        # ---- 5-byte legacy lead 0xF8..0xFB ----
        "a = \"\u00f8\u0080\u0080\u0080\u0080\"\n",
        "a = \"\u00f8\u00bf\u00bf\u00bf\u00bf\"\n",
        "a = \"\u00f8\u0041\u0080\u0080\u0080\"\n",
        "a = \"\u00f8\u0080\u0080\u0080\"\n",   # truncated 5-byte
        "a = \"\u00fb\u00bf\u00bf\u00bf\u00bf\"\n",
        # ---- 6-byte legacy lead 0xFC..0xFD ----
        "a = \"\u00fc\u0080\u0080\u0080\u0080\u0080\"\n",
        "a = \"\u00fc\u00bf\u00bf\u00bf\u00bf\u00bf\"\n",
        "a = \"\u00fc\u0080\u0080\u0080\u0080\"\n",  # truncated 6-byte
        "a = \"\u00fd\u00bf\u00bf\u00bf\u00bf\u00bf\"\n",
        # ---- invalid lead bytes 0xFE, 0xFF ----
        "a = \"\u00fe\"\n",
        "a = \"\u00ff\"\n",
        "a = \"\u00fe\u00fe\u00fe\u00fe\"\n",
        "a = \"\u00ff\u00ff\u00ff\u00ff\"\n",
        # ---- stray continuation bytes (0x80..0xBF) as lead ----
        "a = \"\u0080\"\n",
        "a = \"\u008f\"\n",
        "a = \"\u009f\"\n",
        "a = \"\u00bf\"\n",
        "a = \"\u0080\u0080\u0080\"\n",
        # ---- mixed valid/invalid sequences in one string ----
        "a = \"A\u00c3\u00a9\u00e4\u00b8\u00ad\U0001F600Z\"\n",
        "a = \"\u00c2\u0080\u00e0\u00a0\u0080\u00f0\u0090\u0080\u0080\"\n",
        "a = \"\u00c0\u0080\u00e0\u0080\u0080\u00f0\u0080\u0080\u0080\"\n",
        # ---- boundary codepoint transitions ----
        "a = \"\u007f\u00c2\u0080\"\n",              # 1 -> 2 byte
        "a = \"\u00df\u00bf\u00e0\u00a0\u0080\"\n",  # 2 -> 3 byte
        "a = \"\u00ef\u00bf\u00bf\u00f0\u0090\u0080\u0080\"\n",  # 3 -> 4 byte
        # ---- multibyte outside strings (keys, comments, tables) ----
        "\u00c3\u00a9 = 1\n",
        "[\u00c3\u00a9]\nx = 1\n",
        "# \u00c3\u00a9 \u00e4\u00b8\u00ad \U0001F600\n",
        "a = 1 # \u00c3\u00a9 trailing\n",
        # ---- long sequences to exercise decoder loop bound ----
        "a = \"" + "\u00c3\u00a9" * 32 + "\"\n",
        "a = \"" + "\u00e4\u00b8\u00ad" * 32 + "\"\n",
        "a = \"" + "\u00f0\u009f\u0098\u0080" * 32 + "\"\n",
    ]
    return st.sampled_from(samples)

# ---------- top-level strategy ----------

def _document(depth):
    lines = st.lists(_line(depth), min_size=0, max_size=8)
    return lines.map(lambda ls: "\n".join(ls))

def _document_with_trailing():
    lines = st.lists(_line(2), min_size=0, max_size=8)
    return st.one_of(
        lines.map(lambda ls: "\n".join(ls)),
        lines.map(lambda ls: "\n".join(ls) + "\n"),
        lines.map(lambda ls: "\n".join(ls) + "\r\n"),
        lines.map(lambda ls: "\n".join(ls) + "\n\n"),
    )

strategy = st.one_of(
    _document_with_trailing(),
    _malformed(2),
    _deep_document(),
    _utf8_ucs_document(),
    _utf8_ucs_raw_document(),
    _utf8_to_ucs_document(),
    st.just("[t]\nkey = \"value\"\n"),
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("# comment\n# another\n"),
    st.just('"" = 1'),
    st.just("a.b.c = 1"),
    st.just("a = {b = {c = {d = 1}}}"),
    st.just("a = [[1, 2], [3, 4]]"),
    st.just("a = [1, 'two', 3.0, true, 1979-05-27]"),
    st.just("a = 1e309"),
    st.just("a = 9223372036854775808"),
    st.just("a = 0xFFFFFFFFFFFFFFFF"),
    st.just("a = 1979-05-27 07:32:00Z"),
    st.just("a = \"\\u0000\""),
    st.just("a = \"\\U0001F600\""),
    st.just("a = \"line1\\nline2\""),
    st.just("a = '''\nline1\nline2\n'''"),
    st.just('a = """\nline1\nline2\n"""'),
    st.just("a = \"x\x01y\""),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just("a = {b = 1,}"),
    st.just("a = 1979-02-30"),
    st.just("a = +inf"),
    st.just("a = -nan"),
    st.just("a = 1_000"),
    st.just("a = 0o777"),
    st.just("a = 0b1010"),
    st.just("a = 07:32:00"),
    st.just("a = 1979-05-27T07:32:00"),
)