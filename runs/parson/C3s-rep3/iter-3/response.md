```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- string atoms ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(_join)

_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.tuples(st.just("\\u"), _hex4()).map(_join),
)

# surrogate escapes: lone high, lone low, valid pair, invalid pair
_high = st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda n: "\\u%04x" % n)
_low = st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda n: "\\u%04x" % n)
_surrogate = st.one_of(_high, _low, st.tuples(_high, _low).map(_join))

# safe code points: exclude ", \, and raw control chars (0x00-0x1F)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
                         '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_string_body = st.one_of(
    st.text(_safe_char, max_size=12),
    st.lists(st.one_of(_escape, _surrogate, st.text(_safe_char, max_size=4)),
             max_size=8).map(_join),
    st.just("\\u0000"),  # six-char escape, fine
    st.just("\\u0000\\u0000"),
)

def _quoted(body):
    return '"' + body + '"'

_string = _string_body.map(_quoted)

# unterminated / malformed strings
_bad_string = st.one_of(
    st.tuples(st.just('"'), _string_body).map(_join),           # unterminated
    st.just('"'),                                                # lone quote
    st.just('"\\'),                                              # trailing backslash
    st.just('"\\u12"'),                                          # short unicode
    st.just('"\\x41"'),                                          # invalid escape
    st.just('"\\uD800"'),                                        # lone surrogate
)

# ---------- numbers ----------

_int_digits = st.text(st.sampled_from("0123456789"), min_size=1, max_size=6)

_number = st.one_of(
    st.just("0"),
    st.just("-0"),
    st.tuples(st.just("-"), _int_digits).map(_join),
    _int_digits,
    st.integers(min_value=-(10**18), max_value=10**18).map(str),
    # fractional
    st.tuples(st.one_of(st.just(""), st.just("-")),
              _int_digits,
              st.just("."),
              _int_digits).map(_join),
    # exponents, incl. overflow-triggering
    st.tuples(st.one_of(st.just(""), st.just("-")),
              _int_digits,
              st.sampled_from(["e", "E"]),
              st.one_of(st.just(""), st.just("+"), st.just("-")),
              _int_digits).map(_join),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("1e999999"),
    st.just("1e-999999"),
    st.just("1.7976931348623157e308"),
    st.just("1.7976931348623159e308"),
    st.just("0e0"),
    st.just("0e999"),
    # malformed / lenient
    st.just("-"),
    st.just("-."),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("00"),
    st.just("-01"),
    st.just("1e"),
    st.just("1e+"),
    st.just("0x10"),
    st.just("Infinity"),
    st.just("NaN"),
)

# ---------- recursive values ----------

_MAX_DEPTH = 64

def _value(depth):
    # depth-limited recursive construction, concentrating near the cap
    if depth >= _MAX_DEPTH:
        return st.one_of(_string, _number, st.sampled_from(["true", "false", "null"]))
    leaf = st.one_of(
        _string,
        _number,
        st.sampled_from(["true", "false", "null"]),
    )
    child = st.deferred(lambda: _value(depth + 1))

    pair = st.tuples(_string, st.just(":"), child).map(_join)
    obj = st.one_of(
        st.just("{}"),
        st.tuples(st.just("{"),
                  st.lists(pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps)),
                  st.just("}")).map(_join),
    )
    arr = st.one_of(
        st.just("[]"),
        st.tuples(st.just("["),
                  st.lists(child, min_size=1, max_size=4).map(lambda vs: ",".join(vs)),
                  st.just("]")).map(_join),
    )
    return st.one_of(leaf, obj, arr)

_value_st = st.deferred(lambda: _value(0))

# ---------- deep nesting near the cap ----------

def _deep(depth):
    # balanced-ish nesting with a scalar at the bottom
    openers = st.sampled_from(["[", "{"])
    def build(n):
        return st.tuples(openers, _deep_inner(n - 1)).map(lambda t: t[0] + t[1])
    return build(depth)

def _deep_inner(n):
    if n <= 0:
        return st.one_of(_string, _number, st.sampled_from(["true", "false", "null"]))
    return st.tuples(st.sampled_from(["[", "{"]), _deep_inner(n - 1)).map(lambda t: t[0] + t[1])

_deep_array = st.integers(min_value=_MAX_DEPTH - 8, max_value=_MAX_DEPTH + 4).flatmap(
    lambda n: st.tuples(st.just("[" * n), _value_st, st.just("]" * n)).map(_join)
)
_deep_obj = st.integers(min_value=_MAX_DEPTH - 8, max_value=_MAX_DEPTH + 4).flatmap(
    lambda n: st.tuples(st.just('{"k":' * n), _value_st, st.just("}" * n)).map(_join)
)
_deep_mixed = st.integers(min_value=2, max_value=64).flatmap(
    lambda n: _deep_inner(n)
)

# ---------- malformed / near-valid ----------

_malformed = st.one_of(
    st.just('{"a":1,}'),
    st.just('{"a":1,,"b":2}'),
    st.just('{"a" 1}'),
    st.just('{"a":}'),
    st.just('{:1}'),
    st.just('{a:1}'),
    st.just('[1,]'),
    st.just('[,1]'),
    st.just('[1,,2]'),
    st.just('[,]'),
    st.just('{'),
    st.just('}'),
    st.just('['),
    st.just(']'),
    st.just('{"a":1'),
    st.just('[1,2'),
    st.just('"unterminated'),
    st.just("'single'"),
    st.just('{"a":1}"trailing"'),
    st.just('[]trailing'),
    st.just('1 garbage'),
    st.just('1abc'),
    st.just('null null'),
    st.just('{"a":1,"a":2}'),
    st.just('{"a":1,"a":2,"a":3}'),
    st.just('{"dup":1,"dup":2}'),
    st.just('{"a":{"b":1},"a":2}'),
    st.just('\x00'),  # will be filtered by harness, but keep out: remove
)
# remove raw NUL from malformed set
_malformed = _malformed.filter(lambda s: "\x00" not in s)

# ---------- duplicate keys ----------

def _dup_obj():
    key = st.sampled_from(["k", "a", "x"])
    val = st.one_of(_string, _number, st.sampled_from(["true", "false", "null"]))
    return st.tuples(
        st.just("{"),
        st.lists(st.tuples(key, st.just(":"), val).map(_join),
                 min_size=2, max_size=5).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(_join)

_dup = _dup_obj()

# ---------- whitespace / structural variants ----------

_ws = st.sampled_from([" ", "\t", "\n", "\r", "  ", "\t\n", "\r\n", "\n\n", " \t "])

def _ws_pair():
    return st.tuples(_ws, _ws).map(_join)

_ws_value = st.tuples(_ws, _value_st, _ws).map(_join)

_ws_obj = st.tuples(
    st.just("{"),
    st.lists(
        st.tuples(_string, st.just(":"), _value_st).map(_join),
        min_size=1, max_size=4,
    ).map(lambda ps: ("," + _ws_example()).join(ps) if False else ",".join(ps)),
    st.just("}"),
).map(_join)

def _ws_example():
    return " "

_ws_obj = st.tuples(
    st.just("{"),
    st.lists(
        st.tuples(_string, _ws, st.just(":"), _ws, _value_st).map(_join),
        min_size=1, max_size=4,
    ).map(lambda ps: ("," + " ").join(ps) if False else ",".join(ps)),
    st.just("}"),
).map(_join)

_ws_arr = st.tuples(
    st.just("["),
    st.lists(_value_st, min_size=1, max_size=4).map(lambda vs: ",".join(vs)),
    st.just("]"),
).map(_join)

_ws_heavy = st.tuples(
    _ws,
    st.one_of(
        st.tuples(st.just("["), _ws, _value_st, _ws, st.just("]")).map(_join),
        st.tuples(st.just("{"), _ws, _string, _ws, st.just(":"), _ws, _value_st, _ws, st.just("}")).map(_join),
    ),
    _ws,
).map(_join)

# ---------- top-level combination ----------

def _no_nul(s):
    return "\x00" not in s

strategy = st.one_of(
    _value_st,
    _deep_array,
    _deep_obj,
    _deep_mixed,
    _malformed,
    _dup,
    _bad_string,
    _ws_value,
    _ws_obj,
    _ws_arr,
    _ws_heavy,
    st.tuples(_value_st, st.sampled_from(["", " ", "garbage", "abc", "[]", "{}"])).map(_join),
).filter(_no_nul)
```