from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Character / atom helpers
# ---------------------------------------------------------------------------

_basic_raw_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\\\"\n\r",
)

_literal_raw_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00'\n\r",
)

_bare_key_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

_control_chars = st.sampled_from(
    ["\x01", "\x02", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x7f", "\t"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_hex8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)


def _escape() -> st.SearchStrategy:
    simple = st.sampled_from([r"\"", r"\\", r"\/", r"\b", r"\f", r"\n", r"\r", r"\t"])
    uni = _hex4.map(lambda h: "\\u" + h)
    exuni = _hex8.map(lambda h: "\\U" + h)
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
# UTF-8 byte-level strings
# ---------------------------------------------------------------------------

_utf8_byte_chars = st.characters(min_codepoint=0x80, max_codepoint=0xFF)


def _utf8_bytes_body(max_elems: int = 8) -> st.SearchStrategy:
    lead = st.sampled_from(
        [
            "\xc2", "\xdf",
            "\xe0", "\xe0\xa0", "\xed", "\xef",
            "\xf0", "\xf0\x90", "\xf4", "\xf7",
            "\xf8", "\xfc",
        ]
    )
    cont = st.sampled_from(["\x80", "\x8f", "\xbf", "\x80\x80", "\x80\x80\x80"])
    piece = st.one_of(_utf8_byte_chars, lead, cont)
    return st.lists(piece, min_size=1, max_size=max_elems).map("".join)


def _utf8_string() -> st.SearchStrategy:
    body = st.one_of(_utf8_bytes_body(6), _basic_body(6))
    return body.map(lambda b: '"' + b + '"')


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

def _string(max_elems: int = 12) -> st.SearchStrategy:
    basic = _basic_body(max_elems).map(lambda b: '"' + b + '"')
    literal = _literal_body(max_elems).map(lambda b: "'" + b + "'")

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
    forms = st.one_of(
        st.tuples(_dec_int(), st.just("."), frac).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(_dec_int(), st.just("."), frac, exp).map(
            lambda t: t[0] + t[1] + t[2] + t[3]
        ),
        st.tuples(st.just("."), frac).map(lambda t: t[0] + t[1]),
        st.tuples(st.just("."), frac, exp).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(_dec_int(), st.just(".")).map(lambda t: t[0] + t[1]),
        st.tuples(_dec_int(), exp).map(lambda t: t[0] + t[1]),
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
    def extend(children: st.SearchStrategy) -> st.SearchStrategy:
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
    if draw(st.booleans()):
        lines.append(draw(_malformed()))
    nl = draw(st.sampled_from(["\n", "\r\n"]))
    doc = nl.join(lines)
    if draw(st.booleans()):
        doc += nl
    return doc


def _deep_nesting() -> st.SearchStrategy:
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
# Raw byte-level documents
# ---------------------------------------------------------------------------

def _raw_utf8_doc() -> st.SearchStrategy:
    body = _utf8_bytes_body(10)
    return st.tuples(_key(), body).map(
        lambda t: t[0] + ' = "' + t[1] + '"\n# ' + t[1]
    )


# ---------------------------------------------------------------------------
# Targeted value lines
# ---------------------------------------------------------------------------

_utf8_lead_bytes = st.sampled_from(
    [
        "\xc0", "\xc1", "\xc2", "\xdf",
        "\xe0", "\xe1", "\xed", "\xef",
        "\xf0", "\xf1", "\xf4", "\xf5", "\xf7",
        "\xf8", "\xfb", "\xfc", "\xfd",
    ]
)
_utf8_cont_bytes = st.sampled_from(
    ["\x80", "\x81", "\x8f", "\x90", "\x9f", "\xa0", "\xbf", "\xc0", "\xff"]
)


def _utf8_seq() -> st.SearchStrategy:
    def build(t):
        lead, conts = t
        return lead + "".join(conts)

    return st.tuples(
        _utf8_lead_bytes,
        st.lists(_utf8_cont_bytes, min_size=0, max_size=4),
    ).map(build)


def _utf8_value_line() -> st.SearchStrategy:
    seq = st.lists(_utf8_seq(), min_size=1, max_size=4).map("".join)
    return st.tuples(_key(), seq).map(lambda t: t[0] + ' = "' + t[1] + '"')


def _rtots_value_line() -> st.SearchStrategy:
    yy = st.sampled_from(["0000", "0001", "9999", "2020", "2024"])
    mm = st.sampled_from(["00", "01", "02", "12", "13", "99"])
    dd = st.sampled_from(["00", "01", "28", "29", "30", "31", "32", "99"])
    hh = st.sampled_from(["00", "01", "12", "23", "24", "99"])
    mi = st.sampled_from(["00", "01", "30", "59", "60", "99"])
    ss = st.sampled_from(["00", "01", "30", "58", "59", "60", "61", "99"])
    frac = st.one_of(
        st.just(""),
        st.text(alphabet="0123456789", min_size=1, max_size=9).map(lambda s: "." + s),
    )
    t = st.tuples(hh, mi, ss, frac).map(lambda x: x[0] + ":" + x[1] + ":" + x[2] + x[3])
    d = st.tuples(yy, mm, dd).map(lambda x: x[0] + "-" + x[1] + "-" + x[2])
    off = st.one_of(
        st.just("Z"),
        st.just("z"),
        st.tuples(st.sampled_from(["+", "-"]), _two(), st.just(":"), _two()).map(
            lambda x: x[0] + x[1] + x[2] + x[3]
        ),
    )
    delim = st.sampled_from(["T", "t", " "])
    val = st.one_of(
        t,
        d,
        st.tuples(d, delim, t).map(lambda x: x[0] + x[1] + x[2]),
        st.tuples(d, delim, t, off).map(lambda x: x[0] + x[1] + x[2] + x[3]),
    )
    return st.tuples(_key(), val).map(lambda x: x[0] + " = " + x[1])


def _rtod_value_line() -> st.SearchStrategy:
    sign = st.sampled_from(["", "+", "-"])
    intpart = st.one_of(
        st.just("0"),
        st.just("1"),
        st.text(alphabet="0123456789", min_size=1, max_size=30),
    )
    frac = st.text(alphabet="0123456789", min_size=1, max_size=30)
    exp = st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=5),
    ).map(lambda x: x[0] + x[1] + x[2])
    val = st.one_of(
        st.tuples(intpart, st.just("."), frac).map(lambda x: x[0] + x[1] + x[2]),
        st.tuples(intpart, st.just("."), frac, exp).map(
            lambda x: x[0] + x[1] + x[2] + x[3]
        ),
        st.tuples(intpart, exp).map(lambda x: x[0] + x[1]),
        st.tuples(st.just("."), frac).map(lambda x: x[0] + x[1]),
        st.tuples(intpart, st.just(".")).map(lambda x: x[0] + x[1]),
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    )
    return st.tuples(_key(), sign, val).map(lambda x: x[0] + " = " + x[1] + x[2])


def _tabpath_value_line() -> st.SearchStrategy:
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


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document(),
    _nested_doc(),
    _key_value_line(_value()),
    _malformed(),
    _raw_utf8_doc(),
    _utf8_value_line(),
    _rtots_value_line(),
    _rtod_value_line(),
    _tabpath_doc(),
)