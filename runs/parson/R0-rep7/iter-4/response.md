```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map("".join)

# A "safe" character for inside strings: printable ASCII excluding quote and backslash,
# plus a few unicode chars. Never a raw NUL or control char (parser is NUL-terminated).
_safe_chars = st.sampled_from(
    [chr(c) for c in range(0x20, 0x7f) if c not in (0x22, 0x5c)]
    + ["\u00e9", "\u00fc", "\u4e2d", "\u6587", "\U0001F600", "\u2028", "\u007f"]
)

_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = st.tuples(st.just("\\u"), _hex4()).map("".join)

# Surrogate escapes (lone / paired) - these are interesting edge cases.
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\uD834\\uDD1E", "\\u0000"]
)

_string_char = st.one_of(_escapes, _unicode_esc, _surrogate_esc, _safe_chars)

def _string_body(max_size=12):
    return st.lists(_string_char, max_size=max_size).map("".join)

_string = st.tuples(st.just('"'), _string_body(), st.just('"')).map("".join)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.text(alphabet="0123456789", max_size=10)).map("".join),
    st.text(alphabet="0123456789", min_size=1, max_size=18),
)

_frac = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=10)).map("".join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map("".join)

_sign = st.sampled_from(["", "-"])

_number = st.one_of(
    # normal numbers
    st.tuples(_sign, _int_part, st.one_of(st.just(""), _frac), st.one_of(st.just(""), _exp)).map("".join),
    # extreme magnitudes / overflow
    st.sampled_from([
        "1e309", "-1e309", "1e400", "-1e400", "1e-400", "1e308", "1.7976931348623157e308",
        "1.8e308", "-1.8e308", "0e0", "0e999999", "1e999999999", "123456789012345678901234567890",
        "-123456789012345678901234567890", "1.0e-999999", "-0", "-0.0", "0.0000000000000000001",
    ]),
    # lone sign (parser quirk: parses as 0)
    st.just("-"),
    # leading + / .5 / 1. / 01 style near-valid
    st.sampled_from(["+1", ".5", "1.", "01", "-01", "+.5", "--1", "1..2", "1e", "1e+", "1e-"]),
)

# ---------- recursive value ----------

_literal = st.sampled_from(["true", "false", "null"])

_json_leaves = st.one_of(_string, _number, _literal)

def _build_value(children):
    return st.one_of(
        _json_leaves,
        st.tuples(st.just("{"), st.just("}")).map("".join),
        st.tuples(st.just("["), st.just("]")).map("".join),
        # object
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_string, st.just(":"), children).map("".join),
                min_size=0, max_size=4,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map("".join),
        # array
        st.tuples(
            st.just("["),
            st.lists(children, min_size=0, max_size=4).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map("".join),
    )

# Base values (depth 0) - small, non-recursive-ish
_base = st.one_of(_json_leaves)

_value = st.recursive(_base, _build_value, max_leaves=40)

# ---------- deep nesting near the 2048 cap ----------

def _deep(depth):
    # depth nested arrays around a leaf value; depth chosen near 2048
    return st.tuples(
        st.just("[" * depth),
        _json_leaves,
        st.just("]" * depth),
    ).map("".join)

def _deep_obj(depth):
    return st.tuples(
        st.just('{"k":' * depth),
        _json_leaves,
        st.just("}" * depth),
    ).map("".join)

_depth_choice = st.sampled_from([0, 1, 2, 100, 1000, 2000, 2047, 2048, 2049, 2050, 2100, 4096])

_deep_value = st.one_of(
    _depth_choice.flatmap(_deep),
    _depth_choice.flatmap(_deep_obj),
)

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    "{,}", "[,]", "[1,,2]", '{"a":1,}', "[1,]", '{"a" 1}', '{"a":}', "{:1}",
    '{"a":1 "b":2}', '"unterminated', '"esc\\', "[1 2]", "{", "}", "[", "]",
    '{"a":1', '[1,2', '"', '\\', "tru", "fals", "nul", "True", "NULL",
    '{"a":1}}', "[[[]]", '{"a":{"b":}}', "1,2", "1 2", "[] []", "{} {}",
    '{"a":1}garbage', "1abc", "[]xyz", "1 garbage", "nullx", "truefalse",
])

# ---------- top-level composition ----------

_trailing = st.tuples(_value, st.text(alphabet=" \t\n\rabc{}[]0123", max_size=8)).map("".join)

_whitespace = st.text(alphabet=" \t\n\r", max_size=6)

def _wrap_ws(v):
    return st.tuples(_whitespace, v, _whitespace).map("".join)

# Fuzz the parser's byte-level handling: random raw bytes (including NUL and
# high bytes) mixed with structural JSON tokens. This exercises the C parser's
# tokenizer, NUL-termination assumptions, and UTF-8 validation paths that the
# pure-grammar strategies above never reach.
_byte_chars = st.sampled_from(
    [chr(c) for c in range(0x00, 0x100)]
    + ['"', "\\", "{", "}", "[", "]", ":", ",", "0", "1", "e", "E", "-", "+", ".", " ", "\t", "\n", "\r"]
)

def _byte_soup(prefix, suffix):
    return st.tuples(
        st.just(prefix),
        st.lists(_byte_chars, min_size=0, max_size=24).map("".join),
        st.just(suffix),
    ).map("".join)

_byte_fuzz = st.one_of(
    _byte_soup("", ""),
    _byte_soup('"', '"'),
    _byte_soup("[", "]"),
    _byte_soup("{", "}"),
    _byte_soup('{"a":', "}"),
    _byte_soup("[0,", "]"),
    _byte_soup('"', ""),
    _byte_soup("", '"'),
)

# ---------- targeted edge cases (hoisted so they can be sampled directly) ----------

_edge_cases = [
    '{"a":1,"a":2,"a":3}',
    '{"":1}',
    '[{"a":1},{"b":2}]',
    '[[[[[[[[[[1]]]]]]]]]]',
    '{"a":[1,2,{"b":[3,4]}]}',
    '"\\u00"',
    '"\\u12g4"',
    '"\\x41"',
    '{"a":-}',
    '[true,false,null]',
    '{"a":true,"b":false,"c":null}',
    '{"a":1e400}',
    '{"a":-1e400}',
    '{"a":1e-400}',
    '{"a":1.7976931348623157e308}',
    '{"a":1.8e308}',
    '{"a":-0}',
    '{"a":01}',
    '{"a":.5}',
    '{"a":1.}',
    '{"a":"\\ud800"}',
    '{"a":"\\ud83d\\ude00"}',
    '{"a":"\\u0000"}',
    '{"a":1} {"b":2}',
    '{"a":1}\n{"b":2}',
    'null null',
    'true false',
    '{"a":1,"b":2,"c":3,"d":4,"e":5}',
    '[[[[[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]]]]',
    '{"a":{"a":{"a":{"a":{"a":1}}}}}',
    '{"a":[[]]}',
    '{"a":[{}]}',
    '{"a":[]}',
    '{"a":{}}',
    '{"a":""}',
    '{"a":"\\n\\t\\r"}',
    '{"a":"\\/"}',
    '{"a":"\\\\"}',
    '{"a":"\\""}',
    '"\\u0000"',
    '"\\uFFFF"',
    '"\\uD834\\uDD1E"',
    '"\\ud800x"',
    '"\\ud800\\ud800"',
    '"\\udc00"',
    '{"a":1}garbage',
    '{"a":1} ',
    ' {"a":1}',
    '\t\n{"a":1}\r\n',
    '{"a":1,}',
    '{"a":1,,}',
    '[,1]',
    '[1,]',
    '[1,,]',
    '{,}',
    '{"a":1}{"b":2}',
    '[[1],[2]]',
    '{"a":[1,2,3],"b":{"c":[4,5,6]}}',
    '{"a":1e+}',
    '{"a":1e-}',
    '{"a":1e}',
    '{"a":--1}',
    '{"a":+1}',
    '{"a":-01}',
    '{"a":00}',
    '{"a":0.}',
    '{"a":.}',
    '{"a":-.}',
    '{"a":1.2.3}',
    '{"a":1e1e1}',
    '{"a":1E+10}',
    '{"a":1E-10}',
    '{"a":1e999999999999999999999}',
    '{"a":"' + 'x' * 100 + '"}',
    '[' + '1,' * 100 + '1]',
    '{"' + 'k' * 100 + '":1}',
    '{"a":1}extra',
    '{"a":1}extra{"b":2}',
    '{"a":1}\x00',
    '{"a":1}\x01',
    '{"a":1}\x1f',
    '{"a":1}\x7f',
    '{"a":1}\u2028',
    '{"a":1}\u2029',
    '{"a":1}\ufeff',
    '\ufeff{"a":1}',
    '{"a":1}\n\n\n',
    '\n\n\n{"a":1}',
    '{"a":1}\t\t\t',
    '{"a":1}\r\n',
    '{"a":1}\r',
    '{"a":1}\n',
    '{"a":1}\t',
    '{"a":1} ',
    '{"a":1}\x0b',
    '{"a":1}\x0c',
    '{"a":1}\x0e',
    '{"a":1}\x1f',
    '{"a":1}\x7f',
    '{"a":1}\x80',
    '{"a":1}\xff',
    '{"a":1}\u00e9',
    '{"a":1}\u4e2d',
    '{"a":1}\U0001F600',
    '{"a":1}\u2028',
    '{"a":1}\u2029',
    '{"a":1}\ufeff',
]

# Sample a random subset of the edge cases (varied length, varied content)
_edge_subset = st.lists(
    st.sampled_from(_edge_cases), min_size=1, max_size=1
).map(lambda xs: "".join(xs))

strategy = _wrap_ws(
    st.one_of(
        _value,
        _deep_value,
        _malformed,
        _trailing,
        _byte_fuzz,
        _edge_subset,
        st.just(""),
        st.just("{}"),
        st.just("[]"),
        st.just('{"a":0,"a":1}'),  # duplicate keys
        st.just('{"k":0,"k":1}'),
        st.just("1e309"),
        st.just("-"),
    )
)
```