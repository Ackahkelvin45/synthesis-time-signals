```python
import json
from hypothesis import strategies as st

# ---------- scalar building blocks ----------

def _safe_char():
    # printable-ish chars plus some interesting ones; avoid quote/backslash here
    return st.sampled_from(
        list("abcXYZ019 _-.,:;{}[]()<>!@#$%^&*~`|?/")
        + ["\t", "\n", "\r", "\x00", "\x01", "\x1f", "\x7f", "\u00e9", "\u20ac"]
    )

def _escaped_char():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
    unicode_esc = hex4.map(lambda h: "\\u" + h)
    return st.one_of([simple, unicode_esc])

def _string_body_char():
    return st.one_of([_safe_char(), _escaped_char()])

def _string_content():
    return st.lists(_string_body_char(), max_size=6).map("".join)

def _string():
    return _string_content().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _int_part():
    zero = st.just("0")
    nonzero = st.tuples(
        st.sampled_from("123456789"),
        st.text(alphabet="0123456789", max_size=6),
    ).map(lambda t: t[0] + t[1])
    return st.one_of([zero, nonzero])

def _frac_part():
    return st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=6)).map(
        lambda t: t[0] + t[1]
    )

def _exp_part():
    sign = st.sampled_from(["", "+", "-"])
    digits = st.text(alphabet="0123456789", min_size=1, max_size=4)
    return st.tuples(st.sampled_from("eE"), sign, digits).map(lambda t: t[0] + t[1] + t[2])

def _number():
    neg = st.sampled_from(["", "-"])
    core = st.tuples(neg, _int_part()).map(lambda t: t[0] + t[1])
    with_frac = st.tuples(core, st.one_of([st.none(), _frac_part()])).map(
        lambda t: t[0] + (t[1] or "")
    )
    with_exp = st.tuples(with_frac, st.one_of([st.none(), _exp_part()])).map(
        lambda t: t[0] + (t[1] or "")
    )
    return with_exp

def _extreme_number():
    return st.sampled_from([
        "1e309", "-1e309", "1e999999", "0e0", "-0", "0.0",
        "1e-999999", "123456789012345678901234567890",
        "0x10", "0xDEADBEEF", "1.", "01", "-01", "007",
        "1E+308", "1e-308", "9007199254740993",
    ])

# ---------- malformed fragments ----------

def _malformed_value():
    return st.sampled_from([
        "", "-", "+1", ".5", "01", "1.", "0x10", "NaN", "Infinity",
        "-Infinity", "truex", "nul", "tru", "fals", "False", "NULL",
        '"unterminated', '"\\ud800"', '"\\uD800"', '"\\u"', '"\\u12"',
        '"\\q"', "'single'", "{,}", "[,]", "[1,,2]", '{"a" 1}',
        '{"a":}', "{:1}", '{"a":1,}', "[1,2,]", "{", "}", "[", "]",
        "1e", "1e+", "1e-", "--1", "1..2", "1.2.3", "0b101",
        "\x00", "\ufeff", " ", "\t\n",
    ])

# ---------- recursive structure ----------

def _ws():
    return st.text(alphabet=" \t\n\r", max_size=2)

def _key():
    return _string()

def _scalar_value():
    return st.one_of([
        _string(),
        _number(),
        _extreme_number(),
        st.sampled_from(["true", "false", "null"]),
    ])

def _value(draw, depth):
    # depth-limited recursion done via st.recursive below
    pass

def _leaf():
    return st.one_of([_scalar_value(), _malformed_value()])

def _make_obj(depth):
    if depth <= 0:
        return st.just("{}")
    pair = st.tuples(
        _key(),
        _ws(),
        st.just(":"),
        _ws(),
        _value_strategy(depth - 1),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])
    pairs = st.lists(pair, min_size=0, max_size=4)
    return st.tuples(
        st.just("{"),
        _ws(),
        pairs,
        _ws(),
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + ",".join(t[2]) + t[3] + t[4])

def _make_arr(depth):
    if depth <= 0:
        return st.just("[]")
    elems = st.lists(_value_strategy(depth - 1), min_size=0, max_size=4)
    return st.tuples(
        st.just("["),
        _ws(),
        elems,
        _ws(),
        st.just("]"),
    ).map(lambda t: t[0] + t[1] + ",".join(t[2]) + t[3] + t[4])

def _value_strategy(depth):
    if depth <= 0:
        return _leaf()
    return st.one_of([
        _leaf(),
        _make_obj(depth),
        _make_arr(depth),
    ])

# ---------- deep nesting near the 1000 limit ----------

def _deep_nesting():
    open_chars = st.sampled_from(["", "[", "{", '{"a":', "[["])
    depth = st.integers(min_value=995, max_value=1002)

    def build(t):
        oc, d = t
        if oc == "":
            # plain nested arrays
            return "[" * d + "]" * d
        if oc == "[":
            return "[" * d + "0" + "]" * d
        if oc == "{":
            return "{" * d + "}" * d
        if oc == '{"a":':
            return '{"a":' * d + "0" + "}" * d
        # "[[" mix
        return "[" * d + "[" * d + "]" * d + "]" * d

    return st.tuples(open_chars, depth).map(build)

# ---------- top-level composition ----------

def _bom():
    return st.sampled_from(["", "\ufeff"])

def _trailing_junk():
    return st.one_of([
        st.just(""),
        st.sampled_from(["abc", " 1 2", "\x00", "x", "{}", "]", "garbage"]),
    ])

def _top_level():
    value = _value_strategy(4)
    parts = st.tuples(_bom(), _ws(), value, _trailing_junk())
    return parts.map(lambda t: t[0] + t[1] + t[2] + t[3])

strategy = st.one_of([
    _top_level(),
    _deep_nesting(),
    _malformed_value(),
    _extreme_number(),
    _string(),
    _number(),
    st.just("{}"),
    st.just("[]"),
    st.just(""),
    st.just("null"),
    st.just("true"),
    st.just("false"),
])
```