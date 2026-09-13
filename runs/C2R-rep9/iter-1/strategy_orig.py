from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _unicode_escape():
    return st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_simple_escapes = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_esc = st.one_of(_simple_escapes, _unicode_escape())

# safe code points: anything except " \ and control chars 0x00-0x1F
_safe_char = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in Python str
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
                         '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

# Characters we deliberately inject raw (including NUL and control bytes)
_raw_control = st.sampled_from(["\x00", "\x01", "\x07", "\x0b", "\x1f", "\x7f", "\t", "\n", "\r"])

# A "string body" piece: either a safe char, an escape, or a raw control byte
_string_piece = st.one_of(
    _safe_char,
    _esc,
    _raw_control,
)

def _string_body():
    return st.lists(_string_piece, min_size=0, max_size=12).map("".join)

# Also produce deliberately unterminated strings (missing closing quote)
def _unterminated_string():
    return st.tuples(st.just('"'), _string_body()).map(lambda t: t[0] + t[1])

_string = st.one_of(
    _string_body().map(lambda b: '"' + b + '"'),
    _unterminated_string(),
)

# ---------- numbers ----------

_digit = st.sampled_from("0123456789")
_nonzero = st.sampled_from("123456789")

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(_nonzero, st.lists(_digit, max_size=18).map("".join)).map(lambda t: t[0] + t[1]),
        # malformed leading-zero ints
        st.tuples(st.just("0"), st.lists(_digit, min_size=1, max_size=6).map("".join)).map(lambda t: t[0] + t[1]),
    )

def _frac_part():
    return st.tuples(st.just("."), st.lists(_digit, min_size=1, max_size=17).map("".join)).map(lambda t: t[0] + t[1])

def _exp_part():
    return st.tuples(
        st.sampled_from("eE"),
        st.one_of(st.just(""), st.sampled_from("+-")),
        st.lists(_digit, min_size=1, max_size=4).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2])

def _number():
    sign = st.sampled_from(["", "-"])
    intp = _int_part()
    frac = st.one_of(st.just(""), _frac_part())
    exp = st.one_of(st.just(""), _exp_part())
    base = st.tuples(sign, intp, frac, exp).map(lambda t: t[0] + t[1] + t[2] + t[3])
    extras = st.sampled_from([
        "-",            # lone minus (accepted)
        "+1",           # leading plus (rejected)
        ".5",           # leading dot (rejected)
        "1.",           # trailing dot (rejected)
        "01",           # leading zero (rejected)
        "0x1F",         # hex (rejected)
        "1e309",        # overflow
        "1e-309",       # underflow
        "1e999999",     # huge exponent
        "-0",           # negative zero
        "1E+308",
        "1e+000",
        "123456789012345678901234567890",
        "0.0",
        "-0.0e-0",
    ])
    return st.one_of(base, extras)

# ---------- recursive values ----------

_json_value = st.deferred(lambda: _value)

def _member():
    return st.tuples(_string, st.just(":"), _json_value).map(lambda t: t[0] + t[1] + t[2])

def _obj():
    # empty, single, many, duplicate keys, trailing comma
    empty = st.just("{}")
    members = st.lists(_member(), min_size=1, max_size=6)
    trailing = st.booleans()

    def build(t):
        ms, tr = t
        body = ",".join(ms)
        if tr:
            body = body + ","
        return "{" + body + "}"

    non_empty = st.tuples(members, trailing).map(build)

    # malformed object variants
    malformed = st.sampled_from([
        "{", "}", "{,}", "{,", "{a:1}", "{'a':1}", "{\"a\" 1}",
        "{\"a\":}", "{\"a\":1,,\"b\":2}", "{\"a\":1 \"b\":2}",
    ])
    return st.one_of(empty, non_empty, malformed)

def _arr():
    empty = st.just("[]")
    items = st.lists(_json_value, min_size=1, max_size=6)
    trailing = st.booleans()

    def build(t):
        its, tr = t
        body = ",".join(its)
        if tr:
            body = body + ","
        return "[" + body + "]"

    non_empty = st.tuples(items, trailing).map(build)

    malformed = st.sampled_from([
        "[", "]", "[,]", "[,1]", "[1,,2]", "[1 2]",
    ])
    return st.one_of(empty, non_empty, malformed)

def _value():
    return st.one_of(
        _string,
        _number(),
        _obj(),
        _arr(),
        st.sampled_from(["true", "false", "null", "True", "FALSE", "NULL", "nul", "tru"]),
    )

# ---------- top-level ----------

_deep_nesting = st.integers(min_value=1, max_value=64).flatmap(
    lambda n: st.just("[" * n + "]" * n)
)

_deep_obj_nesting = st.integers(min_value=1, max_value=40).flatmap(
    lambda n: st.just('{"a":' * n + "1" + "}" * n)
)

_trailing_garbage = st.sampled_from([
    "1abc", "[]xyz", "1 garbage", "true false", "{} extra",
    "null\nnull", '"a" "b"',
])

_top = st.one_of(
    _value(),
    _deep_nesting,
    _deep_obj_nesting,
    _trailing_garbage,
    st.just(""),
    st.just(" "),
    st.just("\x00"),
    st.just('"\x00"'),
    st.just('{"\x00":1}'),
    st.just("[1,2,]\x00"),
)

# Bias toward objects with members (stressed first-pass path)
def _bias_objects():
    return st.one_of(
        st.lists(_top, min_size=1, max_size=1).map(lambda xs: xs[0]),
        _obj(),
        _obj(),
        _obj(),
    )

strategy = _bias_objects()