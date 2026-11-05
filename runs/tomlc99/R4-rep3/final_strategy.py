import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _j(*parts):
    return "".join(parts)

_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

_UTF8_RAW = st.sampled_from([
    "\u00e9",
    "\u20ac",
    "\U0001f600",
    "\u07ff",
    "\u0800",
    "\uffff",
    "\U00010000",
    "\U0010ffff",
])

_BAD_UTF8 = st.sampled_from([
    "\udc80",
    "\udcc0",
    "\udce0",
    "\udcf0",
    "\udcf8",
    "\udcfc",
    "\udcc0\udc80",
    "\udce0\udc80",
    "\udcf0\udc80",
    "\udcf0\udc80\udc80",
])

_ESCAPE = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\uD800", "\\uDFFF", "\\U0010FFFF", "\\U0001F600",
])

def _unicode_escape():
    return st.one_of(
        st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\u%04X" % (n & 0xFFFF)),
        st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\U%08X" % n),
        st.sampled_from(["\\uD800", "\\uDC00", "\\uFFFF", "\\U0010FFFF", "\\U0001F600"]),
    )

_ESC_OR_CHAR = st.one_of(
    _ESCAPE,
    _unicode_escape(),
    _SAFE_CHARS,
    _UTF8_RAW,
    _BAD_UTF8,
)

def _basic_string():
    body = st.lists(_ESC_OR_CHAR, max_size=8).map("".join)
    return body.map(lambda b: '"' + b + '"')

def _literal_string():
    body = st.lists(
        st.one_of(
            st.characters(blacklist_categories=("Cs",), blacklist_characters="'\x00\n"),
            _UTF8_RAW,
            _BAD_UTF8,
        ),
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
        st.one_of(
            st.characters(blacklist_categories=("Cs",), blacklist_characters="'\x00"),
            _UTF8_RAW,
            _BAD_UTF8,
        ),
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
        st.just("9223372036854775807"),
        st.just("-9223372036854775808"),
        st.just("9223372036854775808"),
        st.just("18446744073709551616"),
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
        st.just("e-400"),
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
    st.just("z"),
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

def _local_time():
    return st.builds(
        lambda h, m, s: "%s:%s%s" % (h, m, s),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
        st.one_of(st.just(""), st.builds(lambda x: ":" + x, st.text(alphabet="0123456789", min_size=2, max_size=2)),
                  st.just(":60"), st.just(":61")),
    )

_datetime = st.one_of(
    _offset_datetime(),
    _local_datetime(),
    _date(),
    _partial_time(),
    _local_time(),
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
# raw byte / encoding fuzz
# ---------------------------------------------------------------------------

def _raw_bytes_string():
    body = st.lists(
        st.one_of(_UTF8_RAW, _BAD_UTF8, _SAFE_CHARS),
        min_size=0,
        max_size=10,
    ).map("".join)
    return body.map(lambda b: "'" + b + "'")

def _raw_bytes_doc():
    raw = st.one_of(_UTF8_RAW, _BAD_UTF8)
    kv = st.builds(
        lambda k, v: k + " = '" + v + "'",
        raw,
        st.lists(raw, max_size=6).map("".join),
    )
    return st.lists(kv, max_size=4).map(lambda ls: "\n".join(ls))

_encoding = st.one_of(
    _raw_bytes_string(),
    _raw_bytes_doc(),
    _string,
)

# ---------------------------------------------------------------------------
# deep nesting
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
# IMPROVED: UTF-8 / norm_lit_str / rtos / timestamp coverage
# ---------------------------------------------------------------------------

# Build valid UTF-8 multi-byte sequences from raw codepoints to force the
# parser through every branch of toml_utf8_to_ucs (1/2/3/4-byte paths).
def _utf8_seq():
    return st.one_of(
        st.integers(min_value=0x00, max_value=0x7F).map(chr),
        st.integers(min_value=0x80, max_value=0x7FF).map(chr),
        st.integers(min_value=0x800, max_value=0xFFFF)
            .filter(lambda n: not (0xD800 <= n <= 0xDFFF))
            .map(chr),
        st.integers(min_value=0x10000, max_value=0x10FFFF).map(chr),
    )

# Raw invalid byte sequences encoded as latin-1 so they reach the parser as
# raw bytes.
def _bad_utf8_bytes():
    lead2 = st.integers(min_value=0xC0, max_value=0xDF)
    lead3 = st.integers(min_value=0xE0, max_value=0xEF)
    lead4 = st.integers(min_value=0xF0, max_value=0xF7)
    lead5 = st.integers(min_value=0xF8, max_value=0xFB)
    lead6 = st.integers(min_value=0xFC, max_value=0xFD)
    cont  = st.integers(min_value=0x80, max_value=0xBF)
    bad_cont = st.integers(min_value=0x00, max_value=0x7F)
    def _b(bs):
        return "".join(chr(b) for b in bs)
    def _mk(lead, n_cont, use_bad):
        def build(l, cs, bc):
            out = [l]
            for i in range(n_cont):
                out.append(bc if (use_bad and i == 0) else cs)
            return _b(out)
        return st.builds(build, lead, cont, bad_cont)
    return st.one_of(
        lead2.map(lambda l: _b([l])),
        lead3.map(lambda l: _b([l])),
        lead4.map(lambda l: _b([l])),
        lead5.map(lambda l: _b([l])),
        lead6.map(lambda l: _b([l])),
        _mk(lead2, 1, True),
        _mk(lead3, 2, True),
        _mk(lead4, 3, True),
        _mk(lead5, 4, True),
        _mk(lead6, 5, True),
        _mk(lead2, 1, False),
        _mk(lead3, 2, False),
        _mk(lead4, 3, False),
        _mk(lead5, 4, False),
        _mk(lead6, 5, False),
        cont.map(lambda c: _b([c])),
    )

def _norm_lit_str_probe():
    body = st.lists(
        st.one_of(
            _utf8_seq(),
            _bad_utf8_bytes(),
            st.sampled_from(["\\n", "\\t", "\\u0041", "\\\\", "\\\"", "\\U0001F600"]),
            st.characters(blacklist_categories=("Cs",), blacklist_characters="'\x00\n"),
        ),
        min_size=1,
        max_size=12,
    ).map("".join)
    return st.one_of(
        body.map(lambda b: "'" + b + "'"),
        body.map(lambda b: '"""' + b + '"""'),
        body.map(lambda b: "'''" + b + "'''"),
    )

# rtos (read to end of string)
def _rtos_probe():
    body = st.lists(
        st.one_of(
            _utf8_seq(),
            _bad_utf8_bytes(),
            st.sampled_from(["\\\\", '\\"', "\\u00e9", "\\U0001F600", "\\"]),
            st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        ),
        min_size=0,
        max_size=10,
    ).map("".join)
    return st.one_of(
        body.map(lambda b: '"' + b),
        body.map(lambda b: "'" + b),
        body.map(lambda b: '"""' + b),
        body.map(lambda b: "'''" + b),
        body.map(lambda b: '"""' + b + '""'),
        body.map(lambda b: "'''" + b + "''"),
    )

def _timestamp_probe():
    year = st.one_of(
        st.just("0000"), st.just("0001"), st.just("9999"),
        st.just("10000"), st.just("-0001"),
        st.text(alphabet="0123456789", min_size=4, max_size=4),
    )
    month = st.one_of(
        st.just("00"), st.just("01"), st.just("12"), st.just("13"),
        st.just("99"),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
    )
    day = st.one_of(
        st.just("00"), st.just("01"), st.just("28"), st.just("29"),
        st.just("30"), st.just("31"), st.just("32"), st.just("99"),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
    )
    hh = st.one_of(st.just("00"), st.just("23"), st.just("24"),
                   st.just("99"),
                   st.text(alphabet="0123456789", min_size=2, max_size=2))
    mm = st.one_of(st.just("00"), st.just("59"), st.just("60"),
                   st.just("99"),
                   st.text(alphabet="0123456789", min_size=2, max_size=2))
    ss = st.one_of(st.just("00"), st.just("59"), st.just("60"),
                   st.just("61"), st.just("99"),
                   st.text(alphabet="0123456789", min_size=2, max_size=2))
    frac = st.one_of(st.just(""), st.builds(lambda d: "." + d, _digits))
    off = st.one_of(
        st.just("Z"), st.just("z"),
        st.builds(lambda s, h, m: s + h + ":" + m,
                  st.sampled_from(["+", "-"]),
                  st.one_of(st.just("00"), st.just("14"), st.just("23"),
                            st.just("99"),
                            st.text(alphabet="0123456789", min_size=2, max_size=2)),
                  st.one_of(st.just("00"), st.just("59"), st.just("60"),
                            st.just("99"),
                            st.text(alphabet="0123456789", min_size=2, max_size=2))),
    )
    date = st.builds(lambda y, m, d: y + "-" + m + "-" + d, year, month, day)
    time_ = st.builds(lambda h, m, s, f: h + ":" + m + ":" + s + f, hh, mm, ss, frac)
    delim = st.sampled_from(["T", "t", " "])
    return st.one_of(
        st.builds(lambda d, dl, t, o: d + dl + t + o, date, delim, time_, off),
        st.builds(lambda d, dl, t: d + dl + t, date, delim, time_),
        date,
        time_,
        st.builds(lambda h, m: h + ":" + m, hh, mm),
    )

def _timestamp_doc():
    return st.builds(
        lambda k, v: k + " = " + v,
        _unquoted_key,
        _timestamp_probe(),
    )

def _coverage_doc():
    parts = st.lists(
        st.one_of(
            st.builds(lambda k, v: k + " = " + v, _unquoted_key, _norm_lit_str_probe()),
            _rtos_probe().map(lambda s: "k = " + s),
            _timestamp_doc(),
            st.builds(lambda k, v: k + " = " + v, _unquoted_key, _raw_bytes_string()),
        ),
        min_size=1,
        max_size=4,
    )
    return parts.map(lambda ls: "\n".join(ls))

_coverage = st.one_of(
    _coverage_doc(),
    _norm_lit_str_probe(),
    _rtos_probe(),
    _timestamp_probe(),
    _raw_bytes_string(),
    _raw_bytes_doc(),
)

# ---------------------------------------------------------------------------
# IMPROVED: dedicated probes for toml_rtots / toml_rtod_ex / toml_rtoi /
# toml_parse_file. Build values whose *first* byte forces each entry point
# to actually parse and validate.
# ---------------------------------------------------------------------------

# toml_rtoi: signed/unsigned decimal, hex/oct/bin, underscores, overflow,
# leading zeros, empty-ish, and trailing garbage.
def _rtoi_probe():
    sign = st.sampled_from(["", "+", "-"])
    base = st.one_of(
        st.text(alphabet="0123456789", min_size=1, max_size=20),
        st.just("0"),
        st.just("00"),
        st.just("0x1F"),
        st.just("0X1F"),
        st.just("0o17"),
        st.just("0b1010"),
        st.just("1_000"),
        st.just("1__0"),
        st.just("_1"),
        st.just("1_"),
        st.just("9223372036854775807"),
        st.just("9223372036854775808"),
        st.just("-9223372036854775808"),
        st.just("18446744073709551615"),
        st.just("18446744073709551616"),
        st.just("0xFFFFFFFFFFFFFFFF"),
        st.just("0x10000000000000000"),
    )
    return st.tuples(sign, base).map(lambda t: t[0] + t[1])

# toml_rtod_ex: floats with/without fraction, exponents, leading dots,
# trailing dots, underscores, inf/nan, overflow/underflow exponents.
def _rtod_probe():
    sign = st.sampled_from(["", "+", "-"])
    mant = st.one_of(
        st.text(alphabet="0123456789", min_size=1, max_size=20),
        st.just("0"),
        st.just("1_000"),
        st.just(""),
    )
    frac = st.one_of(
        st.just(""),
        st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=20)),
        st.just("."),
        st.just(".0"),
        st.just(".0000000000000000001"),
    )
    exp = st.one_of(
        st.just(""),
        st.builds(lambda s, d: s + d,
                  st.sampled_from(["e", "E", "e+", "e-", "E+", "E-"]),
                  st.text(alphabet="0123456789", min_size=1, max_size=4)),
        st.just("e308"),
        st.just("e309"),
        st.just("e-308"),
        st.just("e-400"),
    )
    special = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
    normal = st.tuples(sign, mant, frac, exp).map(lambda t: t[0] + t[1] + t[2] + t[3])
    return st.one_of(normal, special)

# toml_rtots: full timestamps, local dates, local times, with valid and
# invalid component values to exercise every validation branch.
def _rtots_probe():
    return _timestamp_probe()

# toml_parse_file: whole documents as raw byte strings (including an empty
# file, whitespace-only, BOM, and comment-only) to reach the top-level entry.
def _parse_file_probe():
    return st.one_of(
        st.just(""),
        st.just("\n"),
        st.just("\r\n"),
        st.just("   \t  "),
        st.just("\ufeff"),
        st.just("\ufeffx = 1"),
        st.just("# only a comment"),
        st.just("# comment\n"),
        st.just("# comment\n\n"),
        st.builds(lambda k, v: k + " = " + v, _unquoted_key, _rtoi_probe()),
        st.builds(lambda k, v: k + " = " + v, _unquoted_key, _rtod_probe()),
        st.builds(lambda k, v: k + " = " + v, _unquoted_key, _rtots_probe()),
        st.builds(lambda k, v: k + " = " + v, _unquoted_key, _literal_string()),
        st.builds(lambda k, v: k + " = " + v, _unquoted_key, _basic_string()),
        _document(),
    )

# A "k = <value>" doc that forces the parser into rtoi / rtod / rtots.
def _scalar_doc():
    return st.one_of(
        st.builds(lambda k, v: k + " = " + v, _unquoted_key, _rtoi_probe()),
        st.builds(lambda k, v: k + " = " + v, _unquoted_key, _rtod_probe()),
        st.builds(lambda k, v: k + " = " + v, _unquoted_key, _rtots_probe()),
    )

# Multi-line docs to force toml_parse_file to run through the whole loop.
def _multi_scalar_doc():
    lines = st.lists(_scalar_doc(), min_size=1, max_size=5)
    return lines.map(lambda ls: "\n".join(ls))

# ---------------------------------------------------------------------------
# final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _parse_file_probe(),
    _multi_scalar_doc(),
    _scalar_doc(),
    _coverage,
    _document(),
    _malformed,
    _deep,
    _encoding,
)