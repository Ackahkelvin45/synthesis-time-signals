from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

def _esc():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    hex4 = st.tuples(*[st.sampled_from(_hex)] * 4).map(lambda t: "\\u" + "".join(t))
    surrogate = st.sampled_from(["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\udc00"])
    return st.one_of(simple, hex4, surrogate)

def _safe_char():
    # printable-ish safe points incl. high unicode, plus raw control/NUL encouraged
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                      blacklist_categories=("Cs",),
                      blacklist_characters='"\\'),
        st.sampled_from(["\x00", "\x01", "\x1f", "\t", "\n", "\r"]),
    )

def _string_body_char():
    return st.one_of(_safe_char(), _esc())

def _string():
    return st.lists(_string_body_char(), max_size=8).map(lambda cs: '"' + "".join(cs) + '"')

# ---------- numbers ----------

_int = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),  # leading zeros
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x")),
)

_frac = st.one_of(
    st.just("."),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
    st.tuples(st.integers(0, 9).map(str), st.integers(0, 10**6).map(str)).map(
        lambda t: "." + t[0] + t[1]),
)

def _exp():
    sign = st.sampled_from(["", "+", "-"])
    digits = st.one_of(
        st.integers(min_value=0, max_value=9).map(str),
        st.integers(min_value=0, max_value=10**4).map(lambda n: "0" + str(n)),
        st.sampled_from(["309", "310", "308", "9999", "1000"]),
    )
    return st.tuples(sign, digits).map(lambda t: "e" + t[0] + t[1])

_number = st.one_of(
    _int,
    st.tuples(st.sampled_from(["", "-"]), _int, _frac).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.sampled_from(["", "-"]), _int, _exp()).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.sampled_from(["", "-"]), _int, _frac, _exp()).map(
        lambda t: t[0] + t[1] + t[2] + t[3]),
    st.sampled_from(["1e309", "-1e309", "1e1000", "0x10", "01", "1."]),
)

# ---------- malformed near-misses ----------

_malformed_scalar = st.sampled_from([
    "NaN", "Infinity", "-Infinity", "+1", ".5", "-", "+", "01.", "0x", "0xG",
    "1e", "1e+", "1.", ".", "--1", "1.2.3", "truefalse", "nul", "tru",
    "TRUE", "'x'", "\"abc", "\"\\q\"", "\"\\u12\"", "\"\\ud800\"",
    "[1,]", "{\"a\":1,}", "{,}", "[,]", "{\"a\" 1}", "{a:1}",
    "{'a':1}", "[1 2]", "}", "]", "{", "[", "", "  ",
])

# ---------- recursive values ----------

def _value():
    return st.recursive(
        st.one_of(_string(), _number(), st.sampled_from(["true", "false", "null"])),
        lambda children: st.one_of(_arr(children), _obj(children)),
        max_leaves=12,
    )

def _arr(children):
    inner = st.lists(children, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]")
    return inner

def _obj(children):
    pairs = st.lists(st.tuples(_string(), children), max_size=4).map(
        lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}")
    return pairs

# ---------- deep nesting near the 1000 limit ----------

_deep = st.integers(min_value=900, max_value=1005).flatmap(
    lambda d: st.one_of(
        st.just("[" * d + "]" * d),
        st.just("[" * d),                      # unterminated deep
        st.just("[" * d + "1" + "]" * d),
        st.just("{" + "\"a\":{" * d + "1" + "}" * d),
        st.just("[" * d + "]" * (d - 1)),      # one short
    )
)

# ---------- top-level ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "\ufeff", "\x00"])

def _with_trailing(v):
    junk = st.one_of(
        st.just(""),
        st.sampled_from(["abc", " 1 2", "\x00", " garbage", "}", "]", ","]),
    )
    return st.tuples(v, junk).map(lambda t: t[0] + t[1])

value = st.one_of(_value(), _malformed_scalar, _deep)

strategy = st.one_of(
    _with_trailing(value),
    st.tuples(_ws, value).map(lambda t: t[0] + t[1]),
    st.tuples(value, _ws).map(lambda t: t[0] + t[1]),
    st.tuples(_ws, value, _ws).map(lambda t: t[0] + t[1] + t[2]),
)