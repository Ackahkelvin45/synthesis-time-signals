```python
from hypothesis import strategies as st
import json

# --- basic terminals -------------------------------------------------------

_safe = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

# strings with escapes, control bytes, NUL, unicode escapes
_esc_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
_hex = st.sampled_from("0123456789abcdefABCDEF")
_unicode_esc = st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map("".join)
# lone surrogates (rejected) and valid surrogate pairs (accepted)
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udfff", "\\udbff", "\\udc00", "\\ud83d\\ude00", "\\ud83d\\udca9"]
)
_esc = st.one_of(_esc_simple, _unicode_esc, _surrogate_esc)

# raw control bytes / NUL inside strings (accepted by the parser)
_raw_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_string_body = st.one_of(
    _safe,
    _esc,
    _raw_control,
    st.just("\x00"),
    st.just("\u2028"),
    st.just("\u2029"),
)

_string = st.lists(_string_body, max_size=12).map(lambda cs: '"' + "".join(cs) + '"')

# --- numbers ---------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.integers(min_value=1, max_value=9).map(str), _int_digits).map("".join),
    st.just("01"),          # leading zero (accepted)
    st.just("007"),         # ditto
)

_frac = st.one_of(
    st.tuples(st.just("."), _int_digits).map("".join),
    st.just("."),           # trailing dot (accepted)
)

_sign = st.one_of(st.just(""), st.just("-"))

_exp = st.one_of(
    st.tuples(
        st.sampled_from("eE"),
        st.one_of(st.just(""), st.just("+"), st.just("-")),
        _int_digits,
    ).map("".join),
    st.just("e309"),
    st.just("E999"),
    st.just("e-999"),
)

_number = st.one_of(
    st.tuples(_sign, _int_part).map("".join),
    st.tuples(_sign, _int_part, _frac).map("".join),
    st.tuples(_sign, _int_part, _exp).map("".join),
    st.tuples(_sign, _int_part, _frac, _exp).map("".join),
    st.sampled_from([
        "0", "-0", "1e309", "-1e309", "1e-999", "1E+308",
        "0x10", "0XFF", "0xdeadBEEF",       # hex (accepted)
        "1.", "-1.", "01", "0123",          # lenient forms
        "1e01", "1E01", "1e+01",
        "123456789012345678901234567890",
        "1.7976931348623157e309",
        "5e-324", "2.2250738585072014e-308",
    ]),
)

# --- recursive structure ---------------------------------------------------

_json_null = st.just("null")
_json_true = st.just("true")
_json_false = st.just("false")

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "\x00"])

def _join(parts):
    return "".join(parts)

def _pair(strat_value, depth):
    return st.tuples(_string, st.just(":"), strat_value).map(_join)

def _obj(strat_value, depth):
    empty = st.just("{}")
    nonempty = st.tuples(
        st.just("{"),
        st.lists(_pair(strat_value, depth), min_size=1, max_size=5).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(_join)
    return st.one_of(empty, nonempty)

def _arr(strat_value, depth):
    empty = st.just("[]")
    nonempty = st.tuples(
        st.just("["),
        st.lists(strat_value, min_size=1, max_size=5).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(_join)
    return st.one_of(empty, nonempty)

_value = st.recursive(
    st.one_of(_string, _number, _json_null, _json_true, _json_false),
    lambda children: st.one_of(
        _obj(children, 0),
        _arr(children, 0),
    ),
    max_leaves=40,
)

# --- malformed / near-valid inputs ----------------------------------------

_malformed_atoms = st.sampled_from([
    "", " ", "  ", "\x00",
    "01", "1.", "+1", ".5", "-", "+", ".", "NaN", "Infinity", "-Infinity",
    "truex", "nul", "tru", "fals",
    '"', '"abc', '"abc\\"', "'abc'", "'a'", "abc", "{a:1}", "{'a':1}",
    "[1,]", "[,1]", "[1 2]", '{"a":1,}', '{"a":1 "b":2}', '{"a" 1}',
    "{", "}", "[", "]", "{]", "[}", '{"a":}', '{:"1"}', "{,}", "[,]",
    '"\\ud800"', '"\\udfff"', '"\\ud83d"', '"\\x41"', '"\\q"',
    "0x", "0xg", "1e", "1e+", "1e-", "1..2", "--1", "1.2.3",
    "\ufeff",              # BOM alone
    "\x00\x00",
    "tru\x00e",
])

# valid prefixes / trailing content (accepted since parser stops at first value)
_valid_with_trailing = st.one_of(
    st.tuples(_value, st.just("abc")).map(_join),
    st.tuples(_value, st.just(" 1 2")).map(_join),
    st.tuples(_value, st.just("\x00")).map(_join),
    st.tuples(_value, st.just("garbage }{")).map(_join),
    st.tuples(st.just("\ufeff"), _value).map(_join),
)

# --- deep nesting near the 1000-level limit --------------------------------

_depth_choices = st.one_of(
    st.integers(min_value=0, max_value=10),
    st.integers(min_value=990, max_value=1005),
    st.sampled_from([999, 1000, 1001, 1002]),
)

def _deep(st_depth):
    return st.one_of(
        st.tuples(
            st.just("["),
            st.just("[" * st_depth),
            st.just("0"),
            st.just("]" * st_depth),
            st.just("]"),
        ).map(_join),
        st.tuples(
            st.just("{"),
            st.just('{"a":' * st_depth),
            st.just("0"),
            st.just("}" * st_depth),
            st.just("}"),
        ).map(_join),
        st.tuples(
            st.just("[" * st_depth),
            st.just("]"),
            st.just("]" * st_depth),
        ).map(_join),
        # deep nesting that hits EOF while still open (unterminated containers)
        st.tuples(
            st.just("[" * st_depth),
            st.just("0"),
        ).map(_join),
        st.tuples(
            st.just('{"a":' * st_depth),
            st.just("0"),
        ).map(_join),
        # deep nesting with trailing garbage inside the innermost position
        st.tuples(
            st.just("[" * st_depth),
            st.just(","),
            st.just("]" * st_depth),
        ).map(_join),
    )

_deep_inputs = _depth_choices.flatmap(_deep)

# --- assemble ---------------------------------------------------------------

# whitespace-padded values and whitespace-separated structures to exercise
# the parser's whitespace-skipping branches between tokens and after values.
_ws_wrapped = st.one_of(
    st.tuples(_ws, _value, _ws).map(_join),
    st.tuples(
        st.just("["),
        st.lists(
            st.tuples(_ws, _value, _ws).map(_join),
            min_size=1, max_size=4,
        ).map(lambda vs: (_ws.sample() + "," + _ws.sample()).join(vs)),
        st.just("]"),
    ).map(_join),
    st.tuples(
        st.just("{"),
        st.lists(
            st.tuples(_ws, _string, _ws, st.just(":"), _ws, _value, _ws).map(_join),
            min_size=1, max_size=4,
        ).map(lambda ps: (_ws.sample() + "," + _ws.sample()).join(ps)),
        st.just("}"),
    ).map(_join),
)

strategy = st.one_of(
    _value,
    _valid_with_trailing,
    _malformed_atoms,
    _deep_inputs,
    _ws_wrapped,
    st.sampled_from([
        "{}", "[]", "{\"\":\"\"}", "[[]]", "[{}]",
        '{"a":{"b":{"c":[1,2,3]}}}',
        '"\\u0000"', '"\\uD83D\\uDE00"', '"\x00"',
        '{"dup":1,"dup":2,"dup":3}',
        '{"a":1,"a":{"b":2}}',
        "1e309", "-1e309", "1e-999", "0x10",
        "01", "1.", "1.0", "-0.0",
        "\ufeff1", "\ufeff{}",
        "1\x00", "{}garbage", "[]extra",
        "[\"\\ud800\"]", '{"\\ud800":1}',
        "[" * 1000 + "0" + "]" * 1000,
        "[" * 1001 + "0" + "]" * 1001,
        "{" * 1000 + "}" * 1000,
        "{" * 1001 + "}" * 1001,
    ]),
).map(str)
```