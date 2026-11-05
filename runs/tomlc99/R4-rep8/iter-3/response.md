```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_BARE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
_CTRL = [chr(i) for i in range(0x01, 0x20) if i not in (0x0a, 0x0d)] + ["\t", "\r"]
_NONASCII = [chr(c) for c in (0x00e9, 0x4e2d, 0x1f600, 0x03b1, 0x0416, 0x2603)]


def _join(*parts):
    return "".join(parts)


# ---------- keys ----------

def _bare_key():
    return st.text(alphabet=_BARE, min_size=1, max_size=12)


_esc_short = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])


def _unicode_escape():
    return st.sampled_from(["\\u0041", "\\u00e9", "\\u0000", "\\uFFFF", "\\U0001F600",
                            "\\U00000000", "\\u4e2d"])


def _basic_string_char():
    return st.one_of(
        st.text(alphabet="abcXYZ 019!@#$%^&*()[]{}.,;:<>?|~`'", min_size=1, max_size=4),
        _esc_short,
        _unicode_escape(),
        st.sampled_from(_CTRL),
        st.sampled_from(_NONASCII),
    )


def _basic_string():
    return st.lists(_basic_string_char(), max_size=4).map(lambda xs: '"' + "".join(xs) + '"')


def _literal_string():
    return st.lists(
        st.one_of(
            st.text(alphabet="abcXYZ 019!@#$%^&*()[]{}.,;:<>?|~`\"\\", min_size=0, max_size=4),
            st.sampled_from(_CTRL),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map(lambda xs: "'" + "".join(xs) + "'")


def _ml_basic_string():
    body = st.lists(
        st.one_of(
            st.text(alphabet="abc 0123\n\t\"'", min_size=0, max_size=6),
            _esc_short,
            _unicode_escape(),
            st.sampled_from(["\\\n", "\\\r\n"]),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map("".join)
    return body.map(lambda b: '"""' + b + '"""')


def _ml_literal_string():
    body = st.lists(
        st.one_of(
            st.text(alphabet="abc 0123\n\t\"'\\", min_size=0, max_size=6),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map("".join)
    return body.map(lambda b: "'''" + b + "'''")


def _simple_key():
    return st.one_of(
        _bare_key(),
        _basic_string(),
        _literal_string(),
        st.just('""'),
    )


def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=3).map(lambda ps: ".".join(ps))


def _key():
    return st.one_of(_simple_key(), _dotted_key())


# ---------- scalars ----------

def _dec_int():
    return st.one_of(
        st.integers(min_value=-(10 ** 30), max_value=10 ** 30).map(str),
        st.sampled_from(["0", "-0", "+0", "007", "00", "1_000", "1_2_3",
                         "99999999999999999999999999999999999999",
                         "-99999999999999999999999999999999999999"]),
    )


def _hex_int():
    return st.one_of(
        st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=10).map(lambda s: "0x" + s),
        st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFFFFFF"]),
    )


def _oct_int():
    return st.one_of(
        st.text(alphabet="01234567", min_size=1, max_size=8).map(lambda s: "0o" + s),
        st.sampled_from(["0o0", "0o777", "0o1_2_3"]),
    )


def _bin_int():
    return st.one_of(
        st.text(alphabet="01", min_size=1, max_size=12).map(lambda s: "0b" + s),
        st.sampled_from(["0b0", "0b1", "0b1_0_1", "0b" + "1" * 64]),
    )


def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())


def _float():
    return st.one_of(
        st.sampled_from(["1.0", "-1.5", "+3.25", "1.", ".5", "0.0", "-0.0",
                         "1e10", "1E-10", "1.5e+300", "1e309", "-1e309",
                         "6.626e-34", "1_000.0", "1.0_0", "3.14e1_0"]),
        st.tuples(
            st.integers(min_value=-10 ** 6, max_value=10 ** 6).map(str),
            st.sampled_from([".0", ".5", "."]),
            st.one_of(st.just(""), st.sampled_from(["e1", "E-2", "e+10", "e309"])),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )


def _inf_nan():
    return st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])


def _bool():
    return st.sampled_from(["true", "false"])


def _date_time():
    return st.sampled_from([
        "1979-05-27T07:32:00Z",
        "1979-05-27 07:32:00Z",
        "1979-05-27t07:32:00z",
        "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27T07:32:00",
        "1979-05-27T07:32:00.5",
        "1979-05-27",
        "1979-02-30",
        "0000-00-00",
        "9999-99-99",
        "07:32:00",
        "07:32:00.999",
        "23:59:59.999999999",
    ])


def _string():
    return st.one_of(_basic_string(), _literal_string(), _ml_basic_string(), _ml_literal_string())


# ---------- recursive values ----------

def _scalar():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _inf_nan(),
        _bool(),
        _date_time(),
    )


def _array_body(depth):
    inner = _value(depth)
    elems = st.lists(
        st.tuples(
            inner,
            st.one_of(st.just(""), st.just(" "), st.just("\n"), st.just(" # c\n")),
        ).map(lambda t: t[0] + t[1]),
        max_size=4,
    )
    return elems


def _array(depth):
    def build(elems):
        sep = st.sampled_from([",", ", ", ",\n", " , "])
        return sep, elems

    return st.builds(
        lambda elems: _render_array(elems),
        _array_body(depth),
    )


def _render_array(elems):
    if not elems:
        return st.just("[]").example() if False else "[]"
    return "[" + ", ".join(elems) + "]"


def _inline_table(depth):
    inner = _value(depth)

    def kv():
        return st.tuples(_key(), inner).map(lambda t: t[0] + " = " + t[1])

    def render(pairs):
        if not pairs:
            return "{}"
        return "{" + ", ".join(pairs) + "}"

    return st.lists(kv(), max_size=3).map(render)


def _value(depth):
    if depth <= 0:
        return _scalar()
    return st.one_of(
        _scalar(),
        _array(depth - 1),
        _inline_table(depth - 1),
    )


def _deep_array(n):
    return st.just("[" * n + "]" * n)


def _deep_inline(n):
    # {a={a={a=...}}} nested inline tables
    return st.just("{a=" * n + "1" + "}" * n)


# ---------- documents ----------

def _comment():
    return st.lists(
        st.one_of(
            st.text(alphabet="abc 0123!@#$%^&*()[]{}.,;:<>?|~`'\"\\", min_size=0, max_size=8),
            st.sampled_from(_CTRL),
            st.sampled_from(_NONASCII),
        ),
        max_size=3,
    ).map(lambda xs: "#" + "".join(xs))


def _keyval_line(depth):
    return st.tuples(_key(), _value(depth), st.one_of(st.just(""), _comment())).map(
        lambda t: t[0] + " = " + t[1] + (" " + t[2] if t[2] else "")
    )


def _table_line():
    return st.tuples(_key(), st.one_of(st.just(""), _comment())).map(
        lambda t: "[" + t[0] + "]" + (" " + t[1] if t[1] else "")
    )


def _array_table_line():
    return st.tuples(_key(), st.one_of(st.just(""), _comment())).map(
        lambda t: "[[" + t[0] + "]]" + (" " + t[1] if t[1] else "")
    )


def _line(depth):
    return st.one_of(
        _keyval_line(depth),
        _table_line(),
        _array_table_line(),
        _comment(),
        st.just(""),
    )


def _document():
    return st.lists(_line(2), max_size=6).map(lambda ls: "\n".join(ls))


# ---------- malformed near-valid ----------

def _malformed():
    base = st.one_of(
        _keyval_line(1),
        _table_line(),
        _array_table_line(),
    )

    def drop_last(s):
        return s[:-1] if s else s

    def dup_last(s):
        return s + (s[-1] if s else "x")

    return st.one_of(
        base.map(drop_last),
        base.map(dup_last),
        st.tuples(_key(), _basic_string()).map(lambda t: t[0] + " = " + t[1][:-1]),
        st.tuples(_key(), _literal_string()).map(lambda t: t[0] + " = " + t[1][:-1]),
        st.tuples(_key(), st.just("[1, 2")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("{a = 1")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("1 2")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("true false")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _value(1)).map(lambda t: t[0] + " = " + t[1] + " stray"),
        st.tuples(_key(), st.just('"\\q"')).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("{a = 1\nb = 2}")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _value(1)).map(lambda t: t[0] + " =\n" + t[1]),
        st.tuples(_key(), st.just("1")).map(lambda t: t[0] + " = " + t[1]).map(
            lambda s: s + "\n" + s
        ),
        st.just("[]"),
        st.just("=1"),
        st.just("[["),
        st.just("]]"),
        st.just("{"),
        st.just("}"),
        st.just("."),
        st.just(","),
        st.just("[a"),
        st.just("[[a]"),
        st.just("a ="),
        st.just("a = ]"),
    )


# ---------- top-level strategy ----------

def _deep_document():
    n = st.integers(min_value=1500, max_value=2048)
    return st.one_of(
        n.map(lambda k: "a = " + "[" * k + "]" * k),
        n.map(lambda k: "a = " + "[" * k + "1" + "]" * k),
        st.integers(min_value=1, max_value=40).map(lambda k: "a = " + "{b=" * k + "1" + "}" * k),
        st.integers(min_value=1, max_value=40).map(
            lambda k: "a = " + "[" * k + "{b=1}" + "]" * k
        ),
    )


def _duplicate_doc():
    return st.tuples(_key(), _value(1)).map(
        lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[1]
    )


# ---------- UTF-8 / unicode torture ----------

# Raw bytes that are valid/invalid UTF-8 sequences, decoded with surrogateescape
# so they reach the parser as the exact byte sequence when re-encoded.
def _raw_utf8_payloads():
    payloads = []
    # valid 1-byte
    payloads.append(b"\x41")
    # valid 2-byte (é)
    payloads.append(b"\xc3\xa9")
    # valid 3-byte (中)
    payloads.append(b"\xe4\xb8\xad")
    # valid 4-byte (emoji)
    payloads.append(b"\xf0\x9f\x98\x80")
    # overlong encodings
    payloads.append(b"\xc0\xaf")
    payloads.append(b"\xe0\x80\xaf")
    payloads.append(b"\xf0\x80\x80\xaf")
    # lone continuation bytes
    payloads.append(b"\x80")
    payloads.append(b"\xbf")
    payloads.append(b"\x80\x80")
    # truncated sequences
    payloads.append(b"\xc3")
    payloads.append(b"\xe4\xb8")
    payloads.append(b"\xf0\x9f\x98")
    # invalid lead bytes
    payloads.append(b"\xfe")
    payloads.append(b"\xff")
    payloads.append(b"\xf5\x80\x80\x80")
    # 5-byte and 6-byte legacy forms
    payloads.append(b"\xf8\x88\x80\x80\x80")
    payloads.append(b"\xfc\x84\x80\x80\x80\x80")
    # surrogate halves encoded as UTF-8 (CESU-8 style)
    payloads.append(b"\xed\xa0\x80")
    payloads.append(b"\xed\xbf\xbf")
    # BOM
    payloads.append(b"\xef\xbb\xbf")
    return payloads


_RAW_UTF8 = _raw_utf8_payloads()


def _raw_utf8_str():
    return st.sampled_from(_RAW_UTF8).map(
        lambda b: b.decode("utf-8", "surrogateescape")
    )


def _unicode_heavy_value():
    # Values that exercise utf8_to_ucs: strings with raw multibyte content,
    # escapes with high codepoints, and malformed byte sequences.
    def wrap_basic(body):
        return '"' + body + '"'

    def wrap_literal(body):
        return "'" + body + "'"

    raw = _raw_utf8_str()
    return st.one_of(
        raw.map(wrap_basic),
        raw.map(wrap_literal),
        raw.map(lambda s: '"""' + s + '"""'),
        raw.map(lambda s: "'''" + s + "'''"),
        # unicode escapes with various lengths
        st.sampled_from([
            '"\\u0000"',
            '"\\u007f"',
            '"\\u0080"',
            '"\\u07ff"',
            '"\\u0800"',
            '"\\uffff"',
            '"\\U00010000"',
            '"\\U0010FFFF"',
            '"\\U001FFFFF"',
            '"\\U03FFFFFF"',
            '"\\U7FFFFFFF"',
            # invalid escapes
            '"\\u12"',
            '"\\uZZZZ"',
            '"\\U0011FFFF"',
            '"\\UFFFFFFFF"',
            # raw high codepoints
            '"\u00e9\u4e2d\U0001f600"',
            "'\u00e9\u4e2d\U0001f600'",
        ]),
        # comments with raw bytes
        raw.map(lambda s: "#" + s),
        # keys with raw bytes
        raw.map(lambda s: '"' + s + '" = 1'),
        raw.map(lambda s: "'" + s + "' = 1"),
        # bare keys with unicode escapes
        st.sampled_from([
            '"\\u00e9" = 1',
            '"\\U0001F600" = 1',
            '"\\u0000" = 1',
        ]),
    )


def _utf8_document():
    # Multi-line documents mixing raw byte payloads with structure.
    def make(parts):
        return "\n".join(parts)

    return st.lists(
        st.one_of(
            _unicode_heavy_value(),
            st.just("[t]"),
            st.just("a = 1"),
        ),
        min_size=1,
        max_size=4,
    ).map(make)


# ---------- targeted utf8_to_ucs / timestamp / literal-string fuzzers ----------

# Build strings that contain every UTF-8 lead-byte class followed by valid,
# invalid, truncated, or overlong continuation bytes. These are placed inside
# quoted strings and bare keys so the parser's utf8_to_ucs decoder is hit.
_UTF8_LEADS = [
    "\x00", "\x7f",                     # 1-byte
    "\xc2", "\xdf",                     # 2-byte leads
    "\xe0", "\xe4", "\xed", "\xef",     # 3-byte leads
    "\xf0", "\xf4", "\xf7",             # 4-byte leads
    "\xf8", "\xfc",                     # 5/6-byte legacy leads
    "\x80", "\xbf", "\xfe", "\xff",     # continuations / invalid
]
_UTF8_CONT = ["\x80", "\x8f", "\x9f", "\xaf", "\xbf"]


def _utf8_byte_seq():
    # Valid, invalid, and truncated multi-byte sequences as raw bytes.
    def enc(bs):
        return bytes(bs).decode("utf-8", "surrogateescape")

    return st.one_of(
        # 2-byte: lead + 1 continuation (valid or invalid)
        st.tuples(
            st.sampled_from([0xc2, 0xc3, 0xdf, 0xc0, 0xc1]),
            st.sampled_from([0x80, 0xbf, 0x9f, 0x41, 0x7f, 0xc0]),
        ).map(lambda t: enc(t)),
        # 3-byte: lead + 2 continuations
        st.tuples(
            st.sampled_from([0xe0, 0xe4, 0xed, 0xef, 0xe1]),
            st.sampled_from([0x80, 0x9f, 0xbf, 0x41]),
            st.sampled_from([0x80, 0x9f, 0xbf, 0x41]),
        ).map(lambda t: enc(t)),
        # 4-byte: lead + 3 continuations
        st.tuples(
            st.sampled_from([0xf0, 0xf4, 0xf7, 0xf1]),
            st.sampled_from([0x80, 0x90, 0xbf, 0x41]),
            st.sampled_from([0x80, 0x90, 0xbf, 0x41]),
            st.sampled_from([0x80, 0x90, 0xbf, 0x41]),
        ).map(lambda t: enc(t)),
        # 5-byte and 6-byte legacy forms
        st.tuples(
            st.sampled_from([0xf8, 0xfc]),
            st.sampled_from([0x80, 0x88, 0xbf]),
            st.sampled_from([0x80, 0x88, 0xbf]),
            st.sampled_from([0x80, 0x88, 0xbf]),
            st.sampled_from([0x80, 0x88, 0xbf]),
        ).map(lambda t: enc(t)),
        # truncated: lead byte alone
        st.sampled_from([0xc2, 0xe0, 0xf0, 0xf8, 0xfc]).map(lambda b: enc([b])),
        # lead + 1 continuation only (truncated 3/4-byte)
        st.tuples(
            st.sampled_from([0xe0, 0xf0, 0xf8]),
            st.sampled_from([0x80, 0xbf]),
        ).map(lambda t: enc(t)),
    )


def _utf8_in_string():
    seq = _utf8_byte_seq()
    return st.one_of(
        seq.map(lambda s: '"' + s + '"'),
        seq.map(lambda s: "'" + s + "'"),
        seq.map(lambda s: '"""' + s + '"""'),
        seq.map(lambda s: "'''" + s + "'''"),
        seq.map(lambda s: '"' + s + '" = 1'),
        seq.map(lambda s: "'" + s + "' = 1"),
        seq.map(lambda s: "#" + s),
    )


# Timestamp torture: valid and invalid date/time strings that exercise
# toml_timestamp_at's internal parse paths (date, time, offset, fractional).
def _timestamp_torture():
    def rng(lo, hi):
        return st.integers(min_value=lo, max_value=hi)

    def pad2(n):
        return "%02d" % n

    def pad4(n):
        return "%04d" % n

    date = st.tuples(rng(0, 9999), rng(0, 99), rng(0, 99)).map(
        lambda t: pad4(t[0]) + "-" + pad2(t[1]) + "-" + pad2(t[2])
    )
    time_part = st.tuples(rng(0, 99), rng(0, 99), rng(0, 99)).map(
        lambda t: pad2(t[0]) + ":" + pad2(t[1]) + ":" + pad2(t[2])
    )
    frac = st.one_of(
        st.just(""),
        st.integers(min_value=0, max_value=999999999).map(lambda n: "." + str(n)),
    )
    offset = st.sampled_from(["", "Z", "z", "+00:00", "-07:00", "+23:59", "-99:99", "+1:00"])
    sep = st.sampled_from(["T", "t", " "])

    return st.one_of(
        # full datetime
        st.tuples(date, sep, time_part, frac, offset).map(
            lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
        ),
        # date only
        date,
        # time only
        st.tuples(time_part, frac).map(lambda t: t[0] + t[1]),
        # malformed variants
        st.sampled_from([
            "9999-99-99T99:99:99.999999999+99:99",
            "0000-00-00T00:00:00",
            "1979-05-27T24:00:00Z",
            "1979-05-27T07:32:60Z",
            "1979-05-27T07:32:00+24:00",
            "1979-05-27T07:32:00.999999999999Z",
            "1979-5-7T7:3:0Z",
            "1979-05-27T07:32",
            "1979-05-27T",
            "T07:32:00",
            "1979-05-27T07:32:00.",
            "1979-05-27T07:32:00.Z",
            "-1979-05-27",
            "1979-05-27T07:32:00-",
            "1979-05-27 07:32:00.5 +07:00",
        ]),
    )


def _timestamp_value():
    return _timestamp_torture().map(lambda s: "a = " + s)


# Literal-string normalization: literal strings with CRLF, CR, tabs, and
# bare control chars exercise norm_lit_str.
def _lit_str_torture():
    body = st.lists(
        st.one_of(
            st.text(alphabet="abcXYZ 019!@#$%^&*()[]{}.,;:<>?|~`\"\\", min_size=0, max_size=6),
            st.sampled_from(["\r\n", "\r", "\n", "\t", "\x00", "\x01", "\x1f", "\x7f"]),
            st.sampled_from(_NONASCII),
        ),
        max_size=5,
    ).map("".join)
    return st.one_of(
        body.map(lambda s: "'" + s + "'"),
        body.map(lambda s: "'''" + s + "'''"),
        body.map(lambda s: "'" + s + "' = 1"),
        body.map(lambda s: "a = '" + s + "'"),
        body.map(lambda s: "a = '''" + s + "'''"),
    )


def _full_doc():
    return st.one_of(
        _document(),
        _malformed(),
        _deep_document(),
        _duplicate_doc(),
        _utf8_document(),
        _unicode_heavy_value(),
        _utf8_in_string(),
        _timestamp_value(),
        _lit_str_torture(),
        st.just(""),
        st.just("\n"),
        st.just("\r\n"),
        st.just("# only comment"),
        st.just("# only comment\n"),
        st.just("[t]"),
        st.just("[[a]]"),
        st.just("[[a]]\n[[a]]"),
        st.just('"" = 1'),
        st.just("a = {b = 1,}"),
        st.just("a = [1, 2,]"),
        st.just("a = [\n  1,\n  2, # c\n]"),
        st.just("a = 1\r\nb = 2\r\n"),
        st.just("a = 1"),
        st.just("\t[a]\n\tb = 1"),
        # BOM-prefixed documents
        st.just("\ufeffa = 1"),
        st.just("\ufeff[t]\nb = 1"),
        # CRLF and mixed line endings
        st.just("a = 1\r\nb = 2\nc = 3\r\n"),
        # leading/trailing whitespace
        st.just("  \n\n a = 1 \n\n  "),
    )


def _no_nul(s):
    return s.replace("\x00", "")


strategy = _full_doc().map(_no_nul)
```