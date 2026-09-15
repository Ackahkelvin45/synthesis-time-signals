from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"
_safe = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

def _esc():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    uni = st.tuples(*([st.sampled_from(_hex)] * 4)).map(lambda t: "\\u" + "".join(t))
    # lone surrogates are rejected by the parser, so include them sparingly
    lone = st.sampled_from(["\\ud800", "\\udfff", "\\udc00"])
    pair = st.tuples(
        st.integers(min_value=0xD800, max_value=0xDBFF),
        st.integers(min_value=0xDC00, max_value=0xDFFF),
    ).map(lambda t: "\\u%04x\\u%04x" % t)
    return st.one_of(simple, uni, lone, pair)

def _raw_control():
    return st.sampled_from(["\x00", "\x01", "\x1f", "\t", "\n", "\r", "\x7f"])

_string_body = st.one_of(_safe, _esc(), _raw_control())
_string = st.lists(_string_body, max_size=8).map(lambda cs: '"' + "".join(cs) + '"')

# ---------- numbers ----------

_int = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=1, max_value=10**6).map(lambda n: "0" * 1 + str(n)),  # leading zeros
)
_frac = st.one_of(
    st.tuples(st.sampled_from([".", "."]), st.integers(min_value=0, max_value=10**9)).map(
        lambda t: t[0] + str(t[1])
    ),
    st.just("."),  # trailing dot
)
_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=10**3),
).map(lambda t: t[0] + t[1] + str(t[2]))

_number = st.one_of(
    _int,
    st.tuples(st.just("-"), _int).map(lambda t: t[0] + t[1]),
    st.tuples(_int, _frac).map(lambda t: t[0] + t[1]),
    st.tuples(_int, _exp).map(lambda t: t[0] + t[1]),
    st.tuples(_int, _frac, _exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.just("-"), _int, _frac, _exp).map(lambda t: "".join(t)),
    # extreme magnitudes / overflow
    st.sampled_from(["1e309", "-1e309", "1e-400", "1e999999", "0e0", "1E+308"]),
    # hex numbers (accepted by parser)
    st.tuples(st.sampled_from(["0x", "0X"]), st.integers(min_value=0, max_value=2**32)).map(
        lambda t: t[0] + format(t[1], "x")
    ),
    # near-valid but malformed
    st.sampled_from(["+1", ".5", "-", "01", "00", "-.5", "1.", "1e", "1e+", "--1"]),
)

# ---------- values ----------

_leaf = st.one_of(
    _string,
    _number,
    st.sampled_from(["true", "false", "null"]),
    st.sampled_from(["NaN", "Infinity", "-Infinity"]),  # rejected by parser
)

def _depth_bias():
    # concentrate near the ~1000 nesting limit
    return st.one_of(
        st.integers(min_value=0, max_value=6),
        st.integers(min_value=995, max_value=1002),
    )

def _pad(depth):
    return st.just(depth)

def _deep_arr():
    return st.integers(min_value=995, max_value=1002).flatmap(
        lambda d: st.just("[" * d + "0" + "]" * d)
    )

def _deep_obj():
    return st.integers(min_value=995, max_value=1002).flatmap(
        lambda d: st.just('{"a":' * d + "0" + "}" * d)
    )

def _duplicate_keys():
    return st.integers(min_value=2, max_value=6).flatmap(
        lambda n: st.just("{" + ",".join('"k":%d' % i for i in range(n)) + "}")
    )

def _malformed():
    return st.sampled_from([
        "[1,,2]", "[1,]", '{"a":1,}', '{"a" 1}', '{"a":}', "{,}",
        '["unterminated', '"unterminated', '{"a":1', "[1,2",
        "{'a':1}", "{a:1}", "'single'", "[,]", "{:}", "[1 2]",
        '{"a":1 "b":2}', "tru", "nul", "fals", "tru e",
        "\ufeff",  # BOM alone -> rejected
        "\ufeff1",  # BOM then value -> accepted
        "1abc", "1 2", "\x00", "1\x00", '"a\x00b"',
    ])

# ---------- whitespace / structural edge cases ----------

_whitespace = st.one_of(
    st.sampled_from([" ", "\t", "\n", "\r", "\f", "\v"]),
    st.tuples(
        st.sampled_from([" ", "\t", "\n", "\r"]),
        st.sampled_from([" ", "\t", "\n", "\r"]),
    ).map(lambda t: t[0] + t[1]),
)

_ws_wrapped = st.one_of(
    # leading/trailing whitespace around values
    st.tuples(_whitespace, st.sampled_from(["1", "true", "null", '"a"', "[]", "{}"]), _whitespace).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    # whitespace inside arrays/objects
    st.just("[\n  1,\n  2\n]"),
    st.just("{\n  \"a\" : 1\n}"),
    st.just("[ 1 , 2 ]"),
    st.just("{ \"a\" : 1 , \"b\" : 2 }"),
    st.just("[1,2,3]"),
    st.just("[\r\n\t1\r\n]"),
    # only whitespace
    st.just("   "),
    st.just("\n\t\r"),
)

# ---------- recursive ----------

def _make_value(children):
    return st.one_of(
        _leaf,
        st.lists(children, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]"),
        st.lists(
            st.tuples(_string, children).map(lambda t: t[0] + ":" + t[1]),
            max_size=5,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
        st.just("{}"),
        st.just("[]"),
    )

_value = st.recursive(_leaf, _make_value, max_leaves=40)

# ---------- trailing garbage / multi-value inputs ----------
# These exercise parser paths that handle extra content after a complete value,
# non-whitespace trailing bytes, and multiple concatenated documents.
_trailing = st.one_of(
    st.tuples(
        st.sampled_from(["1", "true", "null", '"a"', "[]", "{}", "[1,2]", '{"a":1}']),
        st.sampled_from([
            "x", "1", "true", "null", '"b"', "[]", "{}", " 1", "\n1",
            "]", "}", ",", ":", "1 2", "nullnull", "truefalse",
        ]),
    ).map(lambda t: t[0] + t[1]),
    st.sampled_from([
        "1 2 3", "null null", "true false", "{}[]", "[]{}",
        '{"a":1}{"b":2}', "[1][2]", '"a""b"',
        "1\n2", "null\t1", "[] \n {}", "true\r\nfalse",
        "1//comment", "1/*c*/", "1#c", "1;",
        "[1,2] extra", '{"a":1} extra',
        "0x1 0x2", "1e5 2e5",
        '"a" "b" "c"',
    ]),
)

# ---------- invalid UTF-8 / raw byte sequences ----------
# The parser's byte-level scanning paths (UTF-8 decoding, invalid continuation
# bytes, overlong encodings, truncated multibyte sequences) are not reached by
# the string-level generators above. Feed raw byte sequences as latin-1-decoded
# strings so they survive Hypothesis's text model but reach the parser as
# arbitrary byte payloads.
_invalid_utf8 = st.sampled_from([
    "\x80", "\xbf", "\xc0", "\xc1", "\xc2", "\xdf", "\xe0", "\xed",
    "\xf0", "\xf4", "\xf5", "\xfe", "\xff",
    "\xc0\x80", "\xc1\xbf",            # overlong encodings
    "\xe0\x80\x80", "\xed\xa0\x80",    # overlong / surrogate
    "\xf0\x80\x80\x80", "\xf4\x90\x80\x80",  # out-of-range
    "\xe2\x82", "\xf0\x9f\x92",        # truncated multibyte
    "\xc3", "\xe2", "\xf0",            # lone lead bytes
    "\x80\x80\x80", "\xff\xfe",        # stray continuation / BOM bytes
    "\xed\xbf\xbf", "\xef\xbf\xbe",
])

_byte_garbage = st.one_of(
    _invalid_utf8,
    st.tuples(
        st.sampled_from(['"', "[", "{", "1", "t", "n", " ", "\n"]),
        _invalid_utf8,
    ).map(lambda t: t[0] + t[1]),
    st.tuples(
        _invalid_utf8,
        st.sampled_from(['"', "]", "}", "1", "e", " ", "\n"]),
    ).map(lambda t: t[0] + t[1]),
    st.tuples(st.just('"'), _invalid_utf8, st.just('"')).map(lambda t: "".join(t)),
)

strategy = st.one_of(
    _value,
    _deep_arr(),
    _deep_obj(),
    _duplicate_keys(),
    _malformed(),
    _ws_wrapped,
    _trailing,
    _byte_garbage,
    st.just("{}"),
    st.just("[]"),
    st.just(""),
)