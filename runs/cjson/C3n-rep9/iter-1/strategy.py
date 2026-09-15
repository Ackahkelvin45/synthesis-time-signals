from hypothesis import strategies as st
import json

# ---------- primitives ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \t\n"])

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

def _esc():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    hexd = st.sampled_from("0123456789abcdefABCDEF")
    uni = st.tuples(hexd, hexd, hexd, hexd).map(lambda t: "\\u" + "".join(t))
    # lone surrogates: rejected by parser, but interesting
    lone_hi = st.sampled_from("d8d9dadb").flatmap(
        lambda hi: st.tuples(st.just(hi), st.sampled_from("0123456789abcdefABCDEF"),
                             st.sampled_from("0123456789abcdefABCDEF"),
                             st.sampled_from("0123456789abcdefABCDEF"))
    ).map(lambda t: "\\u" + "".join(t))
    lone_lo = st.sampled_from("dcdddedf").flatmap(
        lambda lo: st.tuples(st.just(lo), st.sampled_from("0123456789abcdefABCDEF"),
                             st.sampled_from("0123456789abcdefABCDEF"),
                             st.sampled_from("0123456789abcdefABCDEF"))
    ).map(lambda t: "\\u" + "".join(t))
    surrogate_pair = st.tuples(
        st.sampled_from("d8d9dadb"),
    ).flatmap(
        lambda _: st.tuples(
            st.sampled_from("0123456789abcdefABCDEF"), st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("dcdddedf"),
            st.sampled_from("0123456789abcdefABCDEF"), st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("0123456789abcdefABCDEF"),
        )
    ).map(lambda t: "\\u" + "".join(t[:3]) + "\\u" + "".join(t[3:]))
    return st.one_of(simple, uni, lone_hi, lone_lo, surrogate_pair)

# raw control / NUL bytes allowed inside strings per adaptation notes
_raw_ctrl = st.sampled_from(["\x00", "\x01", "\x1f", "\t", "\n", "\r", "\x0b", "\x0c"])

_str_body = st.one_of(
    st.text(_safe_chars, min_size=0, max_size=8),
    _esc(),
    _raw_ctrl,
)

_string = st.one_of(
    st.tuples(st.just('"'), _str_body, st.just('"')).map("".join),
    # unterminated string (near-valid)
    st.tuples(st.just('"'), _str_body).map("".join),
)

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)
_nz_digits = st.text("123456789", min_size=1, max_size=1).flatmap(
    lambda d: st.text("0123456789", min_size=0, max_size=5).map(lambda rest: d + rest)
)

_int_part = st.one_of(
    st.just("0"),
    _nz_digits,
    _digits,          # leading zeros: accepted by parser
    st.just(""),
)

_frac = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map("".join),
    st.just("."),     # trailing dot: accepted
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits,
    ).map("".join),
)

# extreme exponents
_big_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text("0123456789", min_size=3, max_size=4),
).map("".join)

_number = st.one_of(
    st.tuples(st.sampled_from(["", "-"]), _int_part, _frac, _exp).map("".join),
    st.tuples(st.sampled_from(["", "-"]), st.just("1"), st.just("."), st.just("0"), _big_exp).map("".join),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1E999999999"),
    st.just("0x10"),      # hex: accepted by parser
    st.just("0XFF"),
    # near-valid malformed
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("00"),
    st.just("1."),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.just("1e"),
    st.just("1e+"),
)

# ---------- recursive values ----------

_json = st.deferred(lambda: _value)

def _value_strat():
    return st.one_of(
        _string,
        _number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _json,
    )

_value = _value_strat()

def _pair_strat():
    return st.tuples(_string, _ws, st.just(":"), _ws, _value).map("".join)

def _obj_strat():
    pairs = st.lists(_pair_strat(), min_size=0, max_size=4)
    return st.tuples(
        st.just("{"),
        _ws,
        pairs.map(lambda ps: ("," + "").join(ps)),
        _ws,
        st.just("}"),
    ).map("".join)

def _arr_strat():
    elems = st.lists(_value, min_size=0, max_size=4)
    return st.tuples(
        st.just("["),
        _ws,
        elems.map(lambda es: ",".join(es)),
        _ws,
        st.just("]"),
    ).map("".join)

_obj = _obj_strat()
_arr = _arr_strat()

_value = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _obj,
    _arr,
)

# ---------- deep nesting near the 1000 limit ----------

def _deep(depth):
    # build nested arrays or objects to a given depth
    open_c = st.sampled_from(["[", "{"])
    close_c = st.sampled_from(["]", "}"])
    return st.tuples(open_c, close_c).flatmap(
        lambda oc: st.tuples(
            st.just(oc[0] * depth),
            st.just(oc[1] * depth),
        )
    ).map(lambda t: t[0] + "0" + t[1])

_deep_nesting = st.one_of(
    st.integers(min_value=0, max_value=1000).flatmap(_deep),
    st.integers(min_value=995, max_value=1005).flatmap(_deep),
    st.just("[" * 1000 + "0" + "]" * 1000),
    st.just("[" * 1001 + "0" + "]" * 1001),
    st.just("{" + '"k":' * 1000 + "0" + "}" * 1000),
    st.just("{" + '"k":' * 1001 + "0" + "}" * 1001),
)

# ---------- near-valid / malformed ----------

_malformed = st.sampled_from([
    "{,}",
    "[,]",
    "[1,,2]",
    "[1,2,]",
    '{"a":1,}',
    '{"a":}',
    '{"a" 1}',
    "{a:1}",
    "'a'",
    '{"a":1 "b":2}',
    "[1 2]",
    '"unterminated',
    '"\\x"',
    '"\\u12"',
    '"\\ud800"',
    '"\\udc00"',
    "",
    " ",
    "\x00",
    "1\x00",
    "\ufeff1",
    "\ufeff{\"a\":1}",
    "1 2",
    "1abc",
    "{}extra",
    "[]trailing",
    '{"a":1}{"b":2}',
    "[[[[[",
    "{{{{",
    "]]]]",
    "}",
    "]",
    ":",
    ",",
])

# ---------- assemble ----------

_value = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _obj,
    _arr,
    _deep_nesting,
    _malformed,
)

# top-level json = value optionally with leading BOM and trailing junk
_top = st.one_of(
    _value,
    st.tuples(st.just("\ufeff"), _value).map("".join),
    st.tuples(_value, st.sampled_from(["", "\x00", "1abc", " ", "junk", "\n"])).map("".join),
)

strategy = _top