EDIT: generate_nesting_toward_cap
```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

hexdigits = "0123456789abcdefABCDEF"

def _hex4():
    return st.lists(st.sampled_from(hexdigits), min_size=4, max_size=4).map("".join)

# Valid escapes
valid_escapes = st.one_of(
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    st.tuples(st.just("\\u"), _hex4()).map(lambda t: t[0] + t[1]),
    # surrogate pair escapes (valid pair)
    st.tuples(
        st.sampled_from(["\\ud8", "\\ud9", "\\uda", "\\udb"]),
        st.lists(st.sampled_from(hexdigits), min_size=2, max_size=2).map("".join),
        st.sampled_from(["\\udc", "\\udd", "\\ude", "\\udf"]),
        st.lists(st.sampled_from(hexdigits), min_size=2, max_size=2).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    # lone surrogate escapes (parser rejects, but interesting)
    st.tuples(
        st.sampled_from(["\\ud800", "\\udbff", "\\udc00", "\\udfff"]),
    ).map(lambda t: t[0]),
)

# Safe code points: anything except quote, backslash, and control chars.
safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in Python str
    blacklist_characters='"\\',
).filter(lambda c: not (0x00 <= ord(c) <= 0x1F))

# Raw control / NUL bytes inside strings (parser accepts these)
raw_control = st.sampled_from(["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x7f"])

string_body_piece = st.one_of(valid_escapes, safe_chars, raw_control)

json_string = st.lists(string_body_piece, max_size=8).map(lambda xs: '"' + "".join(xs) + '"')

# Malformed strings (near-valid)
malformed_string = st.one_of(
    st.just('"'),                     # unterminated empty
    st.tuples(st.just('"'), st.lists(string_body_piece, max_size=5).map("".join)).map(lambda t: t[0] + t[1]),  # unterminated
    st.just('"\\'),                   # trailing backslash, unterminated
    st.just('"\\x"'),                 # invalid escape
    st.just('"\\u12"'),               # short unicode escape
    st.just("'abc'"),                 # single quotes
)

# ---------- numbers ----------

int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.lists(st.sampled_from("0123456789"), max_size=6).map("".join)).map(lambda t: t[0] + t[1]),
    # leading zeros (accepted by parser, malformed per grammar)
    st.lists(st.sampled_from("0123456789"), min_size=2, max_size=6).map("".join),
)

frac_part = st.one_of(
    st.tuples(st.just("."), st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join)).map(lambda t: t[0] + t[1]),
    st.just("."),  # trailing dot (accepted by parser)
)

exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.lists(st.sampled_from("0123456789"), min_size=1, max_size=4).map("".join),
).map(lambda t: t[0] + t[1] + t[2])

# extreme exponents
extreme_exp = st.sampled_from(["e309", "e-309", "e9999", "E+308", "e-400", "e308", "e400"])

number = st.one_of(
    st.tuples(st.just("-"), int_part).map(lambda t: t[0] + t[1]),
    int_part,
    st.tuples(int_part, frac_part).map(lambda t: t[0] + t[1]),
    st.tuples(int_part, exp_part).map(lambda t: t[0] + t[1]),
    st.tuples(int_part, frac_part, exp_part).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(int_part, extreme_exp).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("-"), int_part, extreme_exp).map(lambda t: t[0] + t[1] + t[2]),
    # hex numbers (accepted by parser)
    st.tuples(st.sampled_from(["0x", "0X"]), st.lists(st.sampled_from(hexdigits), min_size=1, max_size=6).map("".join)).map(lambda t: t[0] + t[1]),
)

# malformed numbers
malformed_number = st.one_of(
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("-.5"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.just("1e"),
    st.just("1e+"),
    st.just("-"),
    st.just("--1"),
)

# ---------- recursive values ----------

ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  "])

def _join(parts):
    return "".join(parts)

def _ws_wrap(x):
    return st.tuples(ws, st.just(x), ws).map(_join)

# leaf values
leaf_value = st.one_of(
    json_string,
    malformed_string,
    number,
    malformed_number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

# key: valid string mostly, occasionally malformed
key_string = st.one_of(json_string, malformed_string)

def build_value():
    return st.recursive(
        leaf_value,
        lambda children: st.one_of(
            # arrays
            st.tuples(
                st.just("["),
                st.lists(children, max_size=4).map(lambda xs: ",".join(xs)),
                st.just("]"),
            ).map(_join),
            # objects
            st.tuples(
                st.just("{"),
                st.lists(
                    st.tuples(key_string, st.just(":"), children).map(_join),
                    max_size=4,
                ).map(lambda xs: ",".join(xs)),
                st.just("}"),
            ).map(_join),
            # arrays with surrounding whitespace inside brackets
            st.tuples(
                st.just("["),
                ws,
                st.lists(children, max_size=4).map(lambda xs: ",".join(xs)),
                ws,
                st.just("]"),
            ).map(_join),
            # objects with surrounding whitespace inside braces
            st.tuples(
                st.just("{"),
                ws,
                st.lists(
                    st.tuples(key_string, ws, st.just(":"), ws, children).map(_join),
                    max_size=4,
                ).map(lambda xs: ",".join(xs)),
                ws,
                st.just("}"),
            ).map(_join),
        ),
        max_leaves=12,
    )

value = build_value()

# ---------- edge-case / malformed top-level inputs ----------

edge_cases = st.one_of(
    # empty containers
    st.just("{}"),
    st.just("[]"),
    st.just(" { } "),
    st.just("[ ]"),
    # trailing commas (rejected)
    st.just("[1,]"),
    st.just('{"a":1,}'),
    st.just("[,]"),
    st.just("{,}"),
    # double commas
    st.just("[1,,2]"),
    st.just('{"a":1,,"b":2}'),
    # missing colon
    st.just('{"a" 1}'),
    st.just('{"a"}'),
    st.just('{a:1}'),
    # unquoted keys
    st.just('{a:1}'),
    st.just('{abc: "x"}'),
    # empty input
    st.just(""),
    st.just("   "),
    # BOM
    st.just("\ufeff{}"),
    st.just("\ufeff1"),
    st.just("\ufeff[1,2]"),
    # NUL bytes
    st.just("\x00"),
    st.just('"a\x00b"'),
    st.just('{"a\x00":1}'),
    st.just("1\x00"),
    # duplicate keys
    st.just('{"a":1,"a":2}'),
    st.just('{"a":1,"a":2,"a":3}'),
    # lone minus / plus / dot
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("-.5"),
    # special words
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    # lone surrogate escape
    st.just('"\\ud800"'),
    st.just('"\\udfff"'),
    # invalid escapes
    st.just('"\\x"'),
    st.just('"\\u12"'),
    st.just('"\\q"'),
    # unterminated
    st.just('"abc'),
    st.just('{"a":'),
    st.just('[1,2'),
    st.just('{"a":1'),
    # trailing content after valid value (accepted)
    st.just("1abc"),
    st.just("1 2"),
    st.just('{}[]'),
    st.just('nullnull'),
    # hex number
    st.just("0x10"),
    st.just("0XFF"),
    # leading zeros
    st.just("01"),
    st.just("007"),
    st.just("-01"),
    # trailing dot
    st.just("1."),
    st.just("-1."),
    st.just("1.e5"),
    # extreme magnitudes
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-400"),
    st.just("1e9999"),
    # raw control inside string
    st.just('"a\tb"'),
    st.just('"a\nb"'),
    st.just('"a\rb"'),
)

# ---------- deep nesting near the 1000 limit ----------

def _nest(depth, open_c, close_c):
    return open_c * depth + close_c * depth

deep_nesting = st.one_of(
    st.integers(min_value=990, max_value=1000).map(lambda d: _nest(d, "[", "]")),
    st.integers(min_value=990, max_value=1000).map(lambda d: _nest(d, '{"a":', "}")),
    st.integers(min_value=999, max_value=1005).map(lambda d: _nest(d, "[", "]")),
    st.integers(min_value=999, max_value=1005).map(lambda d: _nest(d, '{"a":', "}")),
    # mixed nesting
    st.integers(min_value=490, max_value=500).map(
        lambda d: "[{\"a\":" * d + "1" + "}]" * d
    ),
    # nesting right at and just over the 1000 depth cap, with a leaf in the middle
    st.integers(min_value=995, max_value=1005).map(
        lambda d: "[" * d + "1" + "]" * d
    ),
    st.integers(min_value=995, max_value=1005).map(
        lambda d: '{"a":' * d + "1" + "}" * d
    ),
    # alternating array/object nesting near the cap
    st.integers(min_value=495, max_value=505).map(
        lambda d: "[{\"a\":" * d + "1" + "}]" * d
    ),
)

# ---------- combined strategy ----------

strategy = st.one_of(
    value,
    edge_cases,
    deep_nesting,
    # top-level value with surrounding whitespace
    st.tuples(ws, value, ws).map(_join),
    # valid value followed by trailing junk (accepted)
    st.tuples(value, st.sampled_from(["abc", " ", " 1", "\x00", "garbage"])).map(_join),
)
```