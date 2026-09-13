```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _hex(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)

# safe code points: exclude " \ and control chars 0x00-0x1F
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

# escapes inside strings
_esc_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_esc_unicode = st.one_of(
    _hex(4).map(lambda h: "\\u" + h),
    # lone surrogates
    st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda c: "\\u%04x" % c),
    st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda c: "\\u%04x" % c),
    # NUL escape (six chars, safe)
    st.just("\\u0000"),
    # other control escapes
    st.integers(min_value=0, max_value=0x1F).map(lambda c: "\\u%04x" % c),
)

_esc = st.one_of(_esc_simple, _esc_unicode)

_string_body_piece = st.one_of(_safe_char, _esc)

# a valid JSON string token
json_string = st.lists(_string_body_piece, max_size=12).map(lambda parts: '"' + "".join(parts) + '"')

# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=10)

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), st.text(alphabet="0123456789", max_size=10))
          .map(lambda t: t[0] + t[1]),
    )

_frac = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=10)).map(
    lambda t: t[0] + t[1]
)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

def _number():
    sign = st.one_of(st.just(""), st.just("-"))
    return st.tuples(sign, _int_part(), st.one_of(st.just(""), _frac), st.one_of(st.just(""), _exp)).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "1e-323", "0e0", "-0",
    "1e999999999", "-1e-999999999",
    "9" * 30, "-" + "9" * 30,
    "1" + "0" * 300,
    "0." + "0" * 300 + "1",
    "1." + "9" * 300,
    "1e" + "9" * 10,
    "-0.0", "0.0",
])

number = st.one_of(_number(), _extreme_number)

# ---------- malformed fragments ----------

_malformed_scalar = st.sampled_from([
    "+1", ".5", "-.5", "01", "007", "-01", "1.", "1.e5", ".e5",
    "1e", "1e+", "1E-", "0x10", "1_000", "Infinity", "-Infinity", "NaN",
    "TRUE", "True", "FALSE", "NULL", "nul", "tru", "fals",
    "'single'", "unquoted",
])

# unterminated string
_unterminated_string = _string_body_piece.map(lambda s: '"' + s if not s.startswith("\\u") else '"' + s)
_unterminated_string = st.lists(_string_body_piece, max_size=6).map(lambda parts: '"' + "".join(parts))

# ---------- recursive grammar ----------

# depth budget: concentrate near 2048
_depth = st.one_of(
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=1, max_value=2048),
    st.sampled_from([2046, 2047, 2048, 2049, 2050, 2100, 4096]),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  "])

def _obj_strategy(value_st):
    # pair: STRING ':' value
    pair = st.tuples(json_string, _ws, st.just(":"), _ws, value_st).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )
    pairs = st.lists(pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps))
    empty = st.just("{}")
    nonempty = st.tuples(st.just("{"), pairs, st.just("}")).map(lambda t: t[0] + t[1] + t[2])
    return st.one_of(empty, nonempty)

def _arr_strategy(value_st):
    items = st.lists(value_st, min_size=1, max_size=4).map(lambda xs: ",".join(xs))
    empty = st.just("[]")
    nonempty = st.tuples(st.just("["), items, st.just("]")).map(lambda t: t[0] + t[1] + t[2])
    return st.one_of(empty, nonempty)

_value = st.deferred(lambda: _value_strategy)

def _value_strategy():
    return st.one_of(
        json_string,
        number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _obj_strategy(_value),
        _arr_strategy(_value),
        _malformed_scalar,
    )

# ---------- malformed top-level variants ----------

def _malformed():
    return st.one_of(
        # double commas / trailing commas
        st.just("[1,,2]"),
        st.just("[1,2,]"),
        st.just("[,]"),
        st.just("{\"a\":1,,\"b\":2}"),
        st.just("{\"a\":1,}"),
        st.just("{,}"),
        # missing colons
        st.just("{\"a\" 1}"),
        st.just("{\"a\"}"),
        st.just("{\"a\":}"),
        # unterminated
        _unterminated_string,
        # trailing content after complete value (accepted by parser)
        st.tuples(st.one_of(json_string, number, st.just("{}"), st.just("[]")),
                  st.sampled_from(["abc", " garbage", "xyz", " 1", "null"])).map(lambda t: t[0] + t[1]),
        # leading + / .5 / 01
        st.just("+1"),
        st.just(".5"),
        st.just("01"),
        # lone sign
        st.just("-"),
        st.just("-."),
        # empty
        st.just("{}"),
        st.just("[]"),
        st.just(""),
    )

# ---------- deep nesting near cap ----------

def _deep_nesting():
    depth = st.one_of(
        st.integers(min_value=1, max_value=2048),
        st.sampled_from([2046, 2047, 2048, 2049, 2050, 2100, 4096]),
    )
    kind = st.sampled_from(["arr", "obj"])

    def build(t):
        d, k = t
        if k == "arr":
            return "[" * d + "]" * d
        else:
            # {"a":{"a":{ ... }}} with d levels
            inner = "null"
            for _ in range(d):
                inner = '{"a":' + inner + "}"
            return inner

    return st.tuples(depth, kind).map(build)

# ---------- duplicate keys ----------

def _duplicate_keys():
    key = st.sampled_from(['"k"', '"a"', '"x"'])
    val = st.one_of(number, json_string, st.just("null"), st.just("true"))
    return st.tuples(key, val).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":0}")

# ---------- top-level strategy ----------

_value_top = st.one_of(
    _value_strategy(),
    _malformed(),
    _deep_nesting(),
    _duplicate_keys(),
)

# wrap with optional whitespace
strategy = st.tuples(_ws, _value_top, _ws).map(lambda t: t[0] + t[1] + t[2])
```