from hypothesis import strategies as st
import json

# ---------- primitives ----------

_HEX = "0123456789abcdefABCDEF"

def _esc():
    simple = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    # \uXXXX including surrogates and weird cases
    u = st.tuples(
        st.just("\\u"),
        st.sampled_from(list(_HEX)),
        st.sampled_from(list(_HEX)),
        st.sampled_from(list(_HEX)),
        st.sampled_from(list(_HEX)),
    ).map(lambda t: "".join(t))
    # lone backslash followed by u without full hex (near-valid)
    bad_u = st.tuples(
        st.just("\\u"),
        st.text(alphabet=_HEX, min_size=0, max_size=3),
    ).map(lambda t: "".join(t))
    return st.one_of(simple, u, bad_u)

def _safe_char():
    # SAFECODEPOINT: anything except " \ and control 0x00-0x1F
    return st.characters(blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f',
                         blacklist_categories=('Cs',))

def _string_body():
    # mix of safe chars, escapes, and raw control/NUL bytes
    safe = _safe_char()
    esc = _esc()
    ctrl = st.sampled_from(["\x00", "\x01", "\x1f", "\x0b", "\x0c", "\x7f", "\x08", "\x1b"])
    # raw unicode including surrogates as literal code points is tricky in py str;
    # use escapes for those via _esc.
    return st.one_of(safe, esc, ctrl)

def _string():
    body = st.lists(_string_body(), min_size=0, max_size=12).map("".join)
    return body.map(lambda b: '"' + b + '"')

# near-valid unterminated string
def _unterminated_string():
    body = st.lists(_string_body(), min_size=0, max_size=8).map("".join)
    return body.map(lambda b: '"' + b)

# ---------- numbers ----------

def _int_part():
    zero = st.just("0")
    nonzero = st.tuples(
        st.integers(min_value=1, max_value=9).map(str),
        st.text(alphabet="0123456789", min_size=0, max_size=10),
    ).map(lambda t: "".join(t))
    return st.one_of(zero, nonzero)

def _number():
    sign = st.sampled_from(["", "-"])
    intp = _int_part()
    frac = st.tuples(
        st.just("."),
        st.text(alphabet="0123456789", min_size=1, max_size=8),
    ).map(lambda t: "".join(t))
    exp = st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(lambda t: "".join(t))
    valid = st.tuples(
        sign, intp,
        st.one_of(st.just(""), frac),
        st.one_of(st.just(""), exp),
    ).map(lambda t: "".join(t))
    # extreme magnitudes / overflow
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e308", "1e-309", "-1e-309",
        "1e9999", "-1e9999", "1e-9999",
        "9" * 400, "-" + "9" * 400,
        "0." + "9" * 400,
        "1e" + "0" * 400,
        "1e+309", "1e-400",
    ])
    # lenient accepted by parser
    lenient = st.sampled_from(["-", "-0", "0e0", "0E+0"])
    # malformed number forms
    malformed = st.sampled_from([
        "+1", ".5", "1.", "01", "007", "0x1F", "-.5", "- 1",
        "1..2", "1e", "1e+", "1e-", "--1", "1.2.3", "+", "e5",
        "1e++5", "00", "-01",
    ])
    return st.one_of(valid, extreme, lenient, malformed)

# ---------- recursive values ----------

def _value(depth):
    return st.one_of(
        _string(),
        _unterminated_string(),
        _number(),
        st.sampled_from(["true", "false", "null", "True", "FALSE", "nul", "tru", "fals"]),
        _obj(depth),
        _arr(depth),
    )

def _pair(depth):
    key = st.one_of(_string(), _unterminated_string())
    colon = st.sampled_from([":", "", ": ", "::", " : "])
    val = _value(depth)
    return st.tuples(key, colon, val).map(lambda t: "".join(t))

def _obj(depth):
    if depth <= 0:
        return st.one_of(
            st.just("{}"),
            st.tuples(
                st.just("{"),
                st.one_of(
                    st.just(""),
                    _pair(0),
                ),
                st.just("}"),
            ).map(lambda t: "".join(t)),
        )
    inner = st.one_of(
        st.just(""),
        st.tuples(
            _pair(depth),
            st.lists(
                st.tuples(st.just(","), _pair(depth - 1)).map(lambda t: "".join(t)),
                min_size=0, max_size=4,
            ).map("".join),
            st.one_of(st.just(""), st.just(",")),  # single trailing comma
        ).map(lambda t: "".join(t)),
        # malformed: leading comma, double comma
        st.sampled_from([",", ",,", ",a:1", "a:1,,b:2", '"a" "b"', '"a":,']),
    )
    return st.tuples(
        st.just("{"),
        inner,
        st.just("}"),
    ).map(lambda t: "".join(t))

def _arr(depth):
    if depth <= 0:
        return st.one_of(
            st.just("[]"),
            st.tuples(
                st.just("["),
                _value(0),
                st.just("]"),
            ).map(lambda t: "".join(t)),
        )
    inner = st.one_of(
        st.just(""),
        st.tuples(
            _value(depth),
            st.lists(
                st.tuples(st.just(","), _value(depth - 1)).map(lambda t: "".join(t)),
                min_size=0, max_size=4,
            ).map("".join),
            st.one_of(st.just(""), st.just(",")),  # single trailing comma
        ).map(lambda t: "".join(t)),
        st.sampled_from([",", ",,", ",1", "1,,2", "[", "]", "1 2", "1,2,,"]),
    )
    return st.tuples(
        st.just("["),
        inner,
        st.just("]"),
    ).map(lambda t: "".join(t))

# ---------- top-level strategy ----------

def _deep():
    # deep nesting of objects and arrays, bounded to avoid Python recursion limits
    n = st.integers(min_value=1, max_value=40)

    def build(k):
        # Build iteratively to avoid Python recursion in strategy construction.
        # Generate a list of k open chars, a leaf, and k matching close chars.
        opens = st.lists(
            st.sampled_from(["{", "["]),
            min_size=k, max_size=k,
        )
        leaf = st.sampled_from(["0", "null", '"x"', "{}", "[]"])
        closes = st.lists(
            st.sampled_from(["}", "]"]),
            min_size=k, max_size=k,
        )
        return st.tuples(opens, leaf, closes).map(
            lambda t: "".join(t[0]) + t[1] + "".join(t[2])
        )

    return n.flatmap(build)

def _malformed_toplevel():
    return st.sampled_from([
        "", " ", "\x00", "{", "}", "[", "]", "{}x", "[]x", "1abc",
        "true false", "1 garbage", "//x", "/* */1", "'x'", "{a:1}",
        '{"a":1}{"b":2}', "[1][2]", "nul", "tru", "fals",
        '"unterminated', '{"a":', '{"a"', '{"a":1', '[1,2', '[1,2,',
        '{"a":1,}', '[,]', '[,1]', '[1,,2]', '{"a":1,,}',
        '\x00\x00\x00', '{"\x00":"\x01"}', '"\x00"', '"\\u0000"',
        '"\\uD800"', '"\\uDC00"', '"\\uD800\\uDC00"', '"\\uFFFF"',
        '"\\u00"', '"\\uZZZZ"', '"\\x"', '"\\"', '"\\\\"',
        "1e309", "-", "01", ".5", "+1", "1.", "0x1F",
    ])

@st.composite
def _root(draw):
    # bias toward objects with members
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice < 5:
        return draw(_obj(draw(st.integers(min_value=1, max_value=4))))
    if choice < 7:
        return draw(_arr(draw(st.integers(min_value=1, max_value=4))))
    if choice < 8:
        return draw(_deep())
    if choice < 9:
        return draw(_value(draw(st.integers(min_value=0, max_value=2))))
    return draw(_malformed_toplevel())

strategy = _root()