from hypothesis import strategies as st
import json

# ---------- leaf token strategies ----------

# Valid numbers, including extreme magnitudes/exponents and overflow (1e309).
_valid_number = st.one_of(
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    st.integers(min_value=0, max_value=10**6).map(str),
    st.sampled_from([
        "0", "-0", "1", "-1", "10", "100", "1e0", "1e308", "1e309",
        "-1e309", "1e-309", "1e-999", "1e999", "123456789012345678901234567890",
        "1E10", "1e+10", "1e-10", "0.0", "-0.0", "3.141592653589793",
        "2.2250738585072014e-308", "1.7976931348623157e308",
        "1.7976931348623159e308", "0.1", "1e01", "1e000000001", "-1e-0",
    ]),
)

# Malformed / non-RFC number forms the parser may accept or reject.
_malformed_number = st.sampled_from([
    "-", "+1", ".5", "1.", "01", "007", "0x1F", "1e", "1e+", "1e-",
    "-.5", "+.5", "1.2.3", "--1", "1e309e1", "Infinity", "NaN", "-Infinity",
    "1_000", "1,000", "0b101", "1f", "1d", "1.0e", ".", "+", "e5",
])

# Plain (unescaped) string content characters.
_plain_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF, blacklist_categories=("Cs",)),
    st.sampled_from(["\x00", "\x01", "\x1f", "\x7f", "\t", "\n", "\r", "\b", "\f"]),
)

# Escape sequences, including \uXXXX and surrogate escapes.
_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04x" % n),
    st.sampled_from([
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uD83D\\uDE00",
        "\\u0000", "\\uffff", "\\uFFFF", "\\uD800\\uD800",
    ]),
)

_escaped_string = st.lists(st.one_of(_plain_char, _escape), max_size=12).map(
    lambda cs: '"' + "".join(cs) + '"'
)

# Unterminated / malformed string variants.
_malformed_string = st.one_of(
    st.lists(_plain_char, max_size=8).map(lambda cs: '"' + "".join(cs)),
    st.sampled_from([
        '"', '""', '"\\', '"\\u', '"\\u12', '"\\uZZZZ', '"abc',
        '"\\x41"', '"\\uD800"', '"unterminated', "'single'", "'x'",
    ]),
)

_string = st.one_of(_escaped_string, _malformed_string)

# ---------- recursive structure ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

_value = st.deferred(lambda: _value_strategy)

# Bias toward objects with members (the stressed first-pass path).
_obj_member = st.tuples(_string, st.just(":"), _value, st.just(",")).map("".join)

_obj = st.one_of(
    st.just("{}"),
    st.tuples(
        st.just("{"),
        st.lists(_obj_member, min_size=1, max_size=5),
        _string,
        st.just(":"),
        _value,
        st.just("}"),
    ).map(lambda t: t[0] + "".join(t[1]) + t[2] + t[3] + t[4] + t[5]),
    # single trailing comma
    st.tuples(
        st.just("{"),
        _string, st.just(":"), _value, st.just(","),
        st.just("}"),
    ).map("".join),
)

_arr = st.one_of(
    st.just("[]"),
    st.tuples(
        st.just("["),
        st.lists(_value, min_size=1, max_size=5),
        st.just("]"),
    ).map(lambda t: t[0] + ",".join(t[1]) + t[2]),
    # single trailing comma
    st.tuples(st.just("["), _value, st.just(","), st.just("]")).map("".join),
)

# Malformed / near-valid structures.
_malformed_struct = st.sampled_from([
    "{,}", "[,]", "[,1]", "[1,,2]", "{,}", '{"a":}', '{"a"}', '{"a":1',
    '{"a" 1}', '{"a"::1}', "{:1}", "[1 2]", "[]]", "}", "]", "{", "[",
    "[1,2,]", '{"a":1,}', '{"a":1,,}', "[]xyz", "1abc", "true false",
    "1 garbage", "nullnull", "{{}}", "[[]]", '{"a":1}}{', "[1][2]",
    '{"a":1,"a":2,"a":3}', '{"":1}', '{"\\uD800":1}',
])

_scalar = st.one_of(
    _string,
    _valid_number,
    _malformed_number,
    st.sampled_from(["true", "false", "null", "True", "FALSE", "None", "nul", "tru"]),
)

_value_strategy = st.one_of(_scalar, _obj, _arr, _malformed_struct)

# Deep nesting: no depth cap, so build deep chains explicitly.
_deep = st.integers(min_value=1, max_value=64).flatmap(
    lambda d: st.just("[" * d + "1" + "]" * d)
)
_deep_obj = st.integers(min_value=1, max_value=32).flatmap(
    lambda d: st.just('{"k":' * d + "1" + "}" * d)
)

# Top-level: a value, optionally with surrounding whitespace.
_json_value = st.one_of(
    _value,
    _deep,
    _deep_obj,
    st.tuples(_ws, _value, _ws).map("".join),
)

strategy = _json_value