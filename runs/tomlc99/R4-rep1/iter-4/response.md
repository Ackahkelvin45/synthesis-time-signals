```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Character / atom helpers
# ---------------------------------------------------------------------------

# Characters that may appear raw inside a basic single-line string.
# Excludes NUL (harness skip), newline, backslash, double quote.
_basic_raw_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\\\"\n\r",
)

# Characters allowed raw in literal strings (no backslash escaping at all).
_literal_raw_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00'\n\r",
)

# Bare-key characters (ASCII only; non-ASCII bare keys are rejected).
_bare_key_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

# Whitespace / control bytes we may sprinkle in strings and comments.
_control_chars = st.sampled_from(
    ["\x01", "\x02", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x7f", "\t"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_hex8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)


def _escape() -> st.SearchStrategy:
    simple = st.sampled_from([r"\"", r"\\", r"\/", r"\b", r"\f", r"\n", r"\r", r"\t"])
    uni = _hex4.map(lambda h: "\\u" + h)
    exuni = _hex8.map(lambda h: "\\U" + h)
    # Also the six-character escape for NUL, which is fine inside strings.
    nul = st.just("\\u0000")
    return st.one_of(simple, uni, exuni, nul)


def _basic_body(max_elems: int) -> st.SearchStrategy:
    piece = st.one_of(
        _basic_raw_chars,
        _control_chars,
        _escape(),
    )
    return st.lists(piece, min_size=0, max_size=max_elems).map("".join)


def _literal_body(max_elems: int) -> st.SearchStrategy:
    piece = st.one_of(_literal_raw_chars, _control_chars)
    return st.lists(piece, min_size=0, max_size=max_elems).map("".join)


# ---------------------------------------------------------------------------
# UTF-8 byte-level strings (targets toml_utf8_to_ucs)
# ---------------------------------------------------------------------------

# Raw bytes (as latin-1 code points) covering the full multi-byte UTF-8
# lead/continuation layout, including invalid sequences, overlong forms,
# surrogates and out-of-range code points.  These are embedded directly in
# the produced document so the parser's UTF-8 decoder is exercised.
_utf8_byte_chars = st.characters(min_codepoint=0x80, max_codepoint=0xFF)


def _utf8_bytes_body(max_elems: int = 8) -> st.SearchStrategy:
    # Craft sequences that look like UTF-8 but are frequently malformed.
    lead = st.sampled_from(
        [
            "\xc2", "\xdf",           # 2-byte leads
            "\xe0", "\xe0\xa0", "\xed", "\xef",  # 3-byte leads
            "\xf0", "\xf0\x90", "\xf4", "\xf7",  # 4-byte leads
            "\xf8", "\xfc",           # 5/6-byte (invalid) leads
        ]
    )
    cont = st.sampled_from(["\x80", "\x8f", "\xbf", "\x80\x80", "\x80\x80\x80"])
    piece = st.one_of(_utf8_byte_chars, lead, cont)
    return st.lists(piece, min_size=1, max_size=max_elems).map("".join)


def _utf8_string() -> st.SearchStrategy:
    # Raw non-ASCII bytes inside a basic string, plus escaped code points,
    # so both the decoder and the escape decoder are hit.
    body = st.one_of(_utf8_bytes_body(6), _basic_body(6))
    return body.map(lambda b: '"' + b + '"')


# ---------------------------------------------------------------------------
# Strings (all four quoting forms)
# ---------------------------------------------------------------------------

def _string(max_elems: int = 12) -> st.SearchStrategy:
    basic = _basic_body(max_elems).map(lambda b: '"' + b + '"')
    literal = _literal_body(max_elems).map(lambda b: "'" + b + "'")

    # Multiline basic: content may include newlines, but not a bare """ run.
    ml_piece = st.one_of(
        st.characters(blacklist_categories=("Cs",), blacklist_characters='\x00"\\'),
        _control_chars,
        st.sampled_from(["\n", "\r\n"]),
        _escape(),
    )
    ml_basic = (
        st.lists(ml_piece, min_size=0, max_size=max_elems)
        .map("".join)
        .map(lambda b: '"""' + b + '"""')
    )

    # Multiline literal: raw content, no ''' run.
    ml_lit_piece = st.one_of(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00'"),
        _control_chars,
        st.sampled_from(["\n", "\r\n"]),
    )
    ml_literal = (
        st.lists(ml_lit_piece, min_size=0, max_size=max_elems)
        .map("".join)
        .map(lambda b: "'''" + b + "'''")
    )

    return st.one_of(basic, literal, ml_basic, ml_literal, _utf8_string())


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _dec_int() -> st.SearchStrategy:
    digits = st.text(alphabet="0123456789", min_size=1, max_size=20)
    # Underscore-grouped form.
    grouped = st.tuples(
        st.text(alphabet="123456789", min_size=1, max_size=1),
        st.lists(
            st.text(alphabet="0123456789", min_size=1, max_size=1),
            min_size=1,
            max_size=20,
        ),
    ).map(lambda t: t[0] + "".join(t[1]))
    grouped_us = st.tuples(
        st.text(alphabet="123456789", min_size=1, max_size=1),
        st.lists(
            st.text(alphabet="0123456789", min_size=1, max_size=1),
            min_size=1,
            max_size=20,
        ),
    ).map(lambda t: t[0] + "_" + "_".join(t[1]))
    body = st.one_of(digits, grouped, grouped_us)
    sign = st.sampled_from(["", "+", "-"])
    return st.tuples(sign, body).map(lambda t: t[0] + t[1])


def _hex_int() -> st.SearchStrategy:
    d = st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=16)
    grouped = st.lists(d, min_size=1, max_size=8).map(lambda xs: "_".join(xs))
    return st.one_of(d, grouped).map(lambda s: "0x" + s)


def _oct_int() -> st.SearchStrategy:
    d = st.text(alphabet="01234567", min_size=1, max_size=16)
    grouped = st.lists(d, min_size=1, max_size=8).map(lambda xs: "_".join(xs))
    return st.one_of(d, grouped).map(lambda s: "0o" + s)


def _bin_int() -> st.SearchStrategy:
    d = st.text(alphabet="01", min_size=1, max_size=32)
    grouped = st.lists(d, min_size=1, max_size=8).map(lambda xs: "_".join(xs))
    return st.one_of(d, grouped).map(lambda s: "0b" + s)


def _integer() -> st.SearchStrategy:
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())


# Floating point forms that stress toml_rtod_ex: long mantissas, exponents,
# bare-fraction, bare-exponent, and hex-float-ish oddities.
def _float() -> st.SearchStrategy:
    frac = st.text(alphabet="0123456789", min_size=1, max_size=18)
    exp = st.one_of(
        st.text(alphabet="0123456789", min_size=1, max_size=4),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.text(alphabet="0123456789", min_size=1, max_size=4),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )
    # Various forms, including the lenient ones the parser accepts.
    forms = st.one_of(
        st.tuples(_dec_int(), st.just("."), frac).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(_dec_int(), st.just("."), frac, exp).map(
            lambda t: t[0] + t[1] + t[2] + t[3]
        ),
        st.tuples(st.just("."), frac).map(lambda t: t[0] + t[1]),
        st.tuples(st.just("."), frac, exp).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(_dec_int(), st.just(".")).map(lambda t: t[0] + t[1]),
        st.tuples(_dec_int(), exp).map(lambda t: t[0] + t[1]),
        # Very long digit runs / many-digit exponents.
        st.tuples(_dec_int(), st.just("."), frac, exp).map(
            lambda t: t[0] + t[1] + t[2] + t[3]
        ),
    )
    inf_nan = st.one_of(
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    )
    return st.one_of(forms, inf_nan)


# ---------------------------------------------------------------------------
# Dates / times
# ---------------------------------------------------------------------------

def _two() -> st.SearchStrategy:
    return st.text(alphabet="0123456789", min_size=2, max_size=2)


def _four() -> st.SearchStrategy:
    return st.text(alphabet="0123456789", min_size=4, max_size=4)


def _partial_time() -> st.SearchStrategy:
    secfrac = st.one_of(
        st.just(""),
        st.text(alphabet="0123456789", min_size=1, max_size=9).map(lambda s: "." + s),
    )
    return st.tuples(_two(), _two(), _two(), secfrac).map(
        lambda t: t[0] + ":" + t[1] + ":" + t[2] + t[3]
    )


def _full_date() -> st.SearchStrategy:
    return st.tuples(_four(), _two(), _two()).map(
        lambda t: t[0] + "-" + t[1] + "-" + t[2]
    )


def _offset() -> st.SearchStrategy:
    num = st.tuples(
        st.sampled_from(["+", "-"]), _two(), st.just(":"), _two()
    ).map(lambda t: t[0] + t[1] + t[2] + t[3])
    return st.one_of(st.just("Z"), num)


def _date_time() -> st.SearchStrategy:
    delim = st.sampled_from(["T", "t", " "])
    offset_dt = st.tuples(_full_date(), delim, _partial_time(), _offset()).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )
    local_dt = st.tuples(_full_date(), delim, _partial_time()).map(
        lambda t: t[0] + t[1] + t[2]
    )
    return st.one_of(offset_dt, local_dt, _full_date(), _partial_time())


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def _unquoted_key() -> st.SearchStrategy:
    return st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)


def _quoted_key() -> st.SearchStrategy:
    # Empty quoted key is legal.
    basic = _basic_body(6).map(lambda b: '"' + b + '"')
    literal = _literal_body(6).map(lambda b: "'" + b + "'")
    return st.one_of(basic, literal)


def _simple_key() -> st.SearchStrategy:
    return st.one_of(_unquoted_key(), _quoted_key())


def _key() -> st.SearchStrategy:
    dotted = st.lists(_simple_key(), min_size=2, max_size=4).map(
        lambda xs: ".".join(xs)
    )
    return st.one_of(_simple_key(), dotted)


# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _scalar_value() -> st.SearchStrategy:
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        st.sampled_from(["true", "false"]),
        _date_time(),
    )


def _value(depth_band: int = 2048) -> st.SearchStrategy:
    # Recursive production: arrays and inline tables nest.
    def extend(children: st.SearchStrategy) -> st.SearchStrategy:
        # Array: elements may be values; allow empty, trailing comma, newlines,
        # comments, mixed types.
        array = st.one_of(
            st.just("[]"),
            st.tuples(
                st.lists(children, min_size=1, max_size=4),
                st.sampled_from(["", ","]),
            ).map(lambda t: "[" + ", ".join(t[0]) + t[1] + "]"),
            st.tuples(
                st.lists(children, min_size=1, max_size=3),
                st.sampled_from(["\n", "\n# c\n", "\r\n"]),
            ).map(lambda t: "[" + ",\n".join(t[0]) + t[1] + "]"),
        )

        # Inline table: key = value pairs. Allow empty and trailing comma.
        pair = st.tuples(_key(), children).map(lambda t: t[0] + " = " + t[1])
        inline = st.one_of(
            st.just("{}"),
            st.tuples(
                st.lists(pair, min_size=1, max_size=3),
                st.sampled_from(["", ","]),
            ).map(lambda t: "{" + ", ".join(t[0]) + t[1] + "}"),
        )
        return st.one_of(array, inline)

    return st.recursive(_scalar_value(), extend, max_leaves=6)


# ---------------------------------------------------------------------------
# Malformed / near-valid mutations
# ---------------------------------------------------------------------------

def _malformed() -> st.SearchStrategy:
    # Build small valid fragments then break one delimiter.
    valid = st.one_of(
        _string(max_elems=4),
        _integer(),
        _float(),
        _date_time(),
        st.just("true"),
        st.just("false"),
        st.just("[]"),
        st.just("{}"),
        st.just("[1, 2]"),
        st.just("{a = 1}"),
    )

    def mutate(v: str) -> str:
        return v

    missing = valid.map(lambda v: v[:-1] if v else v)
    doubled = valid.map(lambda v: v + v[-1:] if v else v)
    unterminated = st.one_of(
        _basic_body(5).map(lambda b: '"' + b),
        _literal_body(5).map(lambda b: "'" + b),
        st.text(alphabet="abc ", min_size=1, max_size=5).map(lambda s: '"""' + s),
    )
    stray = st.sampled_from(
        ["=", "]", "}", ",", "[[", "]]", "[", "{", ".", "=", "#x"]
    )
    return st.one_of(missing, doubled, unterminated, stray)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def _comment() -> st.SearchStrategy:
    body = st.lists(
        st.one_of(
            st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00\n\r"),
            _control_chars,
        ),
        min_size=0,
        max_size=10,
    ).map("".join)
    return body.map(lambda b: "#" + b)


def _key_value_line(value: st.SearchStrategy) -> st.SearchStrategy:
    return st.tuples(_key(), value, st.one_of(st.just(""), _comment())).map(
        lambda t: t[0] + " = " + t[1] + (" " + t[2] if t[2] else "")
    )


def _table_header() -> st.SearchStrategy:
    std = _key().map(lambda k: "[" + k + "]")
    arr = _key().map(lambda k: "[[" + k + "]]")
    return st.one_of(std, arr)


def _line(value: st.SearchStrategy) -> st.SearchStrategy:
    return st.one_of(
        _key_value_line(value),
        _table_header(),
        _comment(),
        st.just(""),
    )


@st.composite
def _document(draw) -> str:
    value = _value()
    lines = draw(st.lists(_line(value), min_size=0, max_size=8))
    # Occasionally append a malformed token line.
    if draw(st.booleans()):
        lines.append(draw(_malformed()))
    nl = draw(st.sampled_from(["\n", "\r\n"]))
    doc = nl.join(lines)
    # Sometimes no trailing newline.
    if draw(st.booleans()):
        doc += nl
    return doc


def _deep_nesting() -> st.SearchStrategy:
    # Concentrate in the interesting depth band (1500-2048), but keep it
    # bounded so tests remain fast; a single level is just brackets.
    depth = st.integers(min_value=1, max_value=64)

    def build(d: int) -> str:
        return "[" * d + "1" + "]" * d

    return depth.map(build)


def _nested_doc() -> st.SearchStrategy:
    return st.tuples(
        _deep_nesting(),
        _key(),
    ).map(lambda t: t[1] + " = " + t[0])


# ---------------------------------------------------------------------------
# Raw byte-level documents (exercise toml_utf8_to_ucs / toml_rtots paths)
# ---------------------------------------------------------------------------

def _raw_utf8_doc() -> st.SearchStrategy:
    # A document whose value is a string containing arbitrary high bytes,
    # both raw and escaped, plus a comment with high bytes.
    body = _utf8_bytes_body(10)
    return st.tuples(_key(), body).map(
        lambda t: t[0] + ' = "' + t[1] + '"\n# ' + t[1]
    )


# ---------------------------------------------------------------------------
# Targeted value lines: ensure every scalar parser is exercised.
# ---------------------------------------------------------------------------

_utf8_lead_bytes = st.sampled_from(
    [
        "\xc0", "\xc1", "\xc2", "\xdf",              # 2-byte leads
        "\xe0", "\xe1", "\xed", "\xef",              # 3-byte leads
        "\xf0", "\xf1", "\xf4", "\xf5", "\xf7",      # 4-byte leads
        "\xf8", "\xfb", "\xfc", "\xfd",              # 5/6-byte leads
    ]
)
_utf8_cont_bytes = st.sampled_from(
    ["\x80", "\x81", "\x8f", "\x90", "\x9f", "\xa0", "\xbf", "\xc0", "\xff"]
)


def _utf8_seq() -> st.SearchStrategy:
    # Build a plausible (often invalid) multi-byte sequence.
    def build(t):
        lead, conts = t
        return lead + "".join(conts)

    return st.tuples(
        _utf8_lead_bytes,
        st.lists(_utf8_cont_bytes, min_size=0, max_size=4),
    ).map(build)


def _utf8_value_line() -> st.SearchStrategy:
    # String whose raw content is a crafted UTF-8 sequence, so the parser
    # must call toml_utf8_to_ucs on the bytes.
    seq = st.lists(_utf8_seq(), min_size=1, max_size=4).map("".join)
    return st.tuples(_key(), seq).map(lambda t: t[0] + ' = "' + t[1] + '"')


# ---------------------------------------------------------------------------
# Direct UTF-8 decoder targeting.
#
# The previous run showed toml_utf8_to_ucs at 0% branch coverage.  The
# decoder is reached from *literal* strings and from raw bytes in basic
# strings, but it is most reliably reached when the whole string body is a
# single crafted multi-byte sequence.  We emit many such strings, one per
# line, covering every lead-byte class (1/2/3/4/5/6 byte forms) and every
# truncation / bad-continuation path inside each branch.
# ---------------------------------------------------------------------------

# Each entry is a raw byte sequence (as latin-1 code points) that drives the
# decoder down a specific branch: valid forms, truncated forms, wrong
# continuation bytes, and out-of-range leads.
_utf8_probe_seqs = [
    # 1-byte (ASCII) — the (i >> 7) == 0 branch.
    "\x00", "\x01", "\x41", "\x7f",
    # 2-byte 110xxxxx 10xxxxxx — the (i >> 5) == 0x6 branch.
    "\xc2\x80", "\xc2\xbf", "\xdf\xbf", "\xdf\x80",
    "\xc2",            # truncated: len < 2
    "\xc2\x00",        # bad continuation (0x00 >> 6 != 0x2)
    "\xc2\xc0",        # bad continuation
    "\xc2\xff",        # bad continuation
    "\xc0\x80",        # overlong
    # 3-byte 1110xxxx 10xxxxxx 10xxxxxx — the (i >> 4) == 0xE branch.
    "\xe0\xa0\x80", "\xe0\xbf\xbf", "\xef\xbf\xbf", "\xed\xa0\x80",
    "\xe0",            # truncated: len < 3
    "\xe0\xa0",        # truncated: len < 3
    "\xe0\x00\x80",    # bad first continuation
    "\xe0\xa0\x00",    # bad second continuation
    "\xe0\xa0\xc0",    # bad second continuation
    # 4-byte 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx — (i >> 3) == 0x1E branch.
    "\xf0\x90\x80\x80", "\xf0\xbf\xbf\xbf", "\xf4\x8f\xbf\xbf",
    "\xf0",            # truncated: len < 4
    "\xf0\x90",        # truncated
    "\xf0\x90\x80",    # truncated
    "\xf0\x00\x80\x80",  # bad first continuation
    "\xf0\x90\x00\x80",  # bad second continuation
    "\xf0\x90\x80\x00",  # bad third continuation
    "\xf0\x90\x80\xc0",  # bad third continuation
    # 5-byte 111110xx ... — (i >> 2) == 0x3E branch.
    "\xf8\x88\x80\x80\x80", "\xfb\xbf\xbf\xbf\xbf",
    "\xf8",            # truncated: len < 5
    "\xf8\x88",        # truncated
    "\xf8\x88\x80",    # truncated
    "\xf8\x88\x80\x80",  # truncated
    "\xf8\x00\x80\x80\x80",  # bad continuation
    "\xf8\x88\x00\x80\x80",  # bad continuation
    # 6-byte 1111110x ... — (i >> 1) == 0x7E branch.
    "\xfc\x84\x80\x80\x80\x80", "\xfd\xbf\xbf\xbf\xbf\xbf",
    "\xfc",            # truncated: len < 6
    "\xfc\x84",        # truncated
    "\xfc\x84\x80",    # truncated
    "\xfc\x84\x80\x80",  # truncated
    "\xfc\x84\x80\x80\x80",  # truncated
    "\xfc\x00\x80\x80\x80\x80",  # bad continuation
    "\xfc\x84\x00\x80\x80\x80",  # bad continuation
    # Bare continuation / stray high bytes (no valid lead).
    "\x80", "\xbf", "\xff", "\xfe",
]


def _utf8_probe_line() -> st.SearchStrategy:
    # Emit a literal string whose body is exactly one crafted byte sequence,
    # so the decoder consumes it as the whole string content.  Literal
    # strings do not run the escape decoder, so the bytes reach
    # toml_utf8_to_ucs directly.
    body = st.sampled_from(_utf8_probe_seqs)
    return st.tuples(_key(), body).map(lambda t: t[0] + " = '" + t[1] + "'")


def _utf8_probe_doc() -> st.SearchStrategy:
    # Several probe lines in one document to exercise multiple branches in
    # a single parse.
    return st.lists(_utf8_probe_line(), min_size=1, max_size=8).map(
        lambda xs: "\n".join(xs)
    )


def _utf8_escaped_probe_line() -> st.SearchStrategy:
    # The same byte sequences but wrapped in \u / \U escapes: this reaches
    # the escape decoder which also funnels through toml_utf8_to_ucs for
    # the encoded form.
    esc = st.one_of(
        _hex4.map(lambda h: "\\u" + h),
        _hex8.map(lambda h: "\\U" + h),
    )
    return st.tuples(_key(), esc).map(lambda t: t[0] + ' = "' + t[1] + '"')


# ---------------------------------------------------------------------------
# Direct toml_rtots targeting.
#
# The previous run showed toml_rtots at 0% branch coverage.  toml_rtots is
# reached when a value is a bare (unquoted) date/time token.  Provide a
# dense grid of edge cases: every field at its boundary, leap seconds,
# out-of-range fields, and every offset form.  We deliberately keep the
# tokens bare (no surrounding quotes) so the parser routes them to
# toml_rtots rather than the string decoder.
# ---------------------------------------------------------------------------

_t_yy = ["0000", "0001", "1969", "1970", "2020", "2024", "9998", "9999"]
_t_mm = ["00", "01", "02", "11", "12", "13", "99"]
_t_dd = ["00", "01", "28", "29", "30", "31", "32", "99"]
_t_hh = ["00", "01", "11", "12", "23", "24", "99"]
_t_mi = ["00", "01", "29", "30", "58", "59", "60", "61", "99"]
_t_ss = ["00", "01", "29", "30", "58", "59", "60", "61", "99"]
_t_frac = ["", ".0", ".1", ".123456", ".123456789", ".1234567890", ".999999999"]


def _rtots_token() -> st.SearchStrategy:
    # Bare time-only token.
    return st.tuples(
        st.sampled_from(_t_hh),
        st.sampled_from(_t_mi),
        st.sampled_from(_t_ss),
        st.sampled_from(_t_frac),
    ).map(lambda t: t[0] + ":" + t[1] + ":" + t[2] + t[3])


def _rtots_date() -> st.SearchStrategy:
    return st.tuples(
        st.sampled_from(_t_yy),
        st.sampled_from(_t_mm),
        st.sampled_from(_t_dd),
    ).map(lambda t: t[0] + "-" + t[1] + "-" + t[2])


def _rtots_offset() -> st.SearchStrategy:
    return st.one_of(
        st.just("Z"),
        st.just("z"),
        st.tuples(
            st.sampled_from(["+", "-"]),
            st.sampled_from(["00", "01", "12", "13", "23", "24", "99"]),
            st.just(":"),
            st.sampled_from(["00", "01", "30", "59", "60", "99"]),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
        st.tuples(
            st.sampled_from(["+", "-"]),
            st.sampled_from(["0000", "0100", "1260", "9999"]),
        ).map(lambda t: t[0] + t[1]),
    )


def _rtots_value() -> st.SearchStrategy:
    delim = st.sampled_from(["T", "t", " "])
    date = _rtots_date()
    time = _rtots_token()
    off = _rtots_offset()
    return st.one_of(
        time,
        date,
        st.tuples(date, delim, time).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(date, delim, time, off).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    )


def _rtots_value_line() -> st.SearchStrategy:
    return st.tuples(_key(), _rtots_value()).map(lambda x: x[0] + " = " + x[1])


def _rtots_doc() -> st.SearchStrategy:
    return st.lists(_rtots_value_line(), min_size=1, max_size=10).map(
        lambda xs: "\n".join(xs)
    )


# ---------------------------------------------------------------------------
# Direct toml_rtod_ex targeting.
#
# The previous run showed toml_rtod_ex at 0% branch coverage.  toml_rtod_ex
# is reached for *bare* float tokens (no surrounding quotes).  Provide a
# dense grid of edge cases: bare fractions, bare exponents, huge digit
# runs, signs, and the special inf/nan spellings.
# ---------------------------------------------------------------------------

_rd_sign = st.sampled_from(["", "+", "-"])
_rd_digits = st.text(alphabet="0123456789", min_size=1, max_size=40)
_rd_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map(lambda t: t[0] + t[1] + t[2])


def _rtod_token() -> st.SearchStrategy:
    return st.one_of(
        # int.frac
        st.tuples(_rd_digits, st.just("."), _rd_digits).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        # int.frac exp
        st.tuples(_rd_digits, st.just("."), _rd_digits, _rd_exp).map(
            lambda t: t[0] + t[1] + t[2] + t[3]
        ),
        # .frac
        st.tuples(st.just("."), _rd_digits).map(lambda t: t[0] + t[1]),
        # .frac exp
        st.tuples(st.just("."), _rd_digits, _rd_exp).map(
            lambda t: t[0] + t[1] + t[2]
        ),
        # int.
        st.tuples(_rd_digits, st.just(".")).map(lambda t: t[0] + t[1]),
        # int exp
        st.tuples(_rd_digits, _rd_exp).map(lambda t: t[0] + t[1]),
        # special values
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    )


def _rtod_value_line() -> st.SearchStrategy:
    return st.tuples(_key(), _rd_sign, _rtod_token()).map(
        lambda x: x[0] + " = " + x[1] + x[2]
    )


def _rtod_doc() -> st.SearchStrategy:
    return st.lists(_rtod_value_line(), min_size=1, max_size=10).map(
        lambda xs: "\n".join(xs)
    )


# ---------------------------------------------------------------------------
# Direct walk_tabpath targeting.
#
# The previous run showed walk_tabpath at 0% branch coverage.  walk_tabpath
# is reached for dotted keys and table headers.  Provide documents that
# share prefix paths, redefine tables, and mix arrays-of-tables with
# key-values so the traversal hits its redefinition branches.
# ---------------------------------------------------------------------------

def _tabpath_value_line() -> st.SearchStrategy:
    # Dotted / quoted keys that exercise walk_tabpath deeply.
    parts = st.lists(
        st.one_of(
            _unquoted_key(),
            _quoted_key(),
        ),
        min_size=1,
        max_size=6,
    )
    key = parts.map(lambda xs: ".".join(xs))
    return st.tuples(key, _scalar_value()).map(lambda t: t[0] + " = " + t[1])


def _tabpath_header() -> st.SearchStrategy:
    parts = st.lists(
        st.one_of(_unquoted_key(), _quoted_key()),
        min_size=1,
        max_size=6,
    ).map(lambda xs: ".".join(xs))
    return st.one_of(
        parts.map(lambda k: "[" + k + "]"),
        parts.map(lambda k: "[[" + k + "]]"),
    )


def _tabpath_doc() -> st.SearchStrategy:
    # A document with table headers and key-values that share prefix paths,
    # exercising walk_tabpath's traversal and redefinition handling.
    header = _tabpath_header()
    line = st.one_of(
        _tabpath_value_line(),
        _key_value_line(_scalar_value()),
        _comment(),
        st.just(""),
    )
    return st.lists(st.one_of(header, line), min_size=1, max_size=10).map(
        lambda xs: "\n".join(xs)
    )


def _tabpath_shared_prefix_doc