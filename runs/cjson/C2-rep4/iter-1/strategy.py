from hypothesis import strategies as st
import json

# ---------- leaf / token strategies ----------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"',
    min_codepoint=0x20,
)

# raw control / NUL bytes allowed inside strings by the parser
_raw_ctrl = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

_hex = "0123456789abcdefABCDEF"
_hex4 = st.text(alphabet=_hex, min_size=4, max_size=4)

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4.map(lambda h: "\\u" + h),
    # lone surrogates -> parser rejects
    st.sampled_from(["\\ud800", "\\udfff", "\\uD83D", "\\uDC00"]),
    # valid surrogate pair
    st.tuples(
        st.sampled_from(["\\ud800", "\\ud83d", "\\udbff"]),
        st.sampled_from(["\\udc00", "\\udfff", "\\udc37"]),
    ).map(lambda t: t[0] + t[1]),
)

_string_body = st.one_of(
    _safe_chars.map(str),
    _raw_ctrl,
    _escapes,
)

_json_string = st.lists(_string_body, max_size=12).map(lambda xs: '"' + "".join(xs) + '"')

# unterminated / malformed strings
_malformed_string = st.one_of(
    st.lists(_string_body, max_size=6).map(lambda xs: '"' + "".join(xs)),
    st.just('"'),
    st.just('"abc'),
    st.just("'single'"),
    st.just('"bad\\x"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
)

# ---------- numbers ----------

_int = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
    st.integers(min_value=-(10**6), max_value=-1).map(str),
    st.integers(min_value=10**15, max_value=10**19).map(str),
    # leading zeros (accepted by parser)
    st.tuples(st.just("0"), st.integers(min_value=0, max_value=999).map(str)).map(
        lambda t: t[0] + t[1]
    ),
)

_frac = st.one_of(
    st.tuples(st.just("."), st.integers(min_value=0, max_value=10**6).map(str)).map(
        lambda t: t[0] + t[1]
    ),
    st.just("."),  # trailing dot accepted
)

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=999).map(str),
).map(lambda t: t[0] + t[1] + t[2])

_extreme_exp = st.sampled_from(
    ["e309", "e-309", "e308", "e400", "E+999", "e-999", "e01", "e+00"]
)

_number = st.one_of(
    _int,
    st.tuples(st.just("-"), _int).map(lambda t: t[0] + t[1]),
    st.tuples(_int, _frac).map(lambda t: t[0] + t[1]),
    st.tuples(_int, _frac, _exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_int, _exp).map(lambda t: t[0] + t[1]),
    st.tuples(_int, _extreme_exp).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("-"), _int, _extreme_exp).map(lambda t: t[0] + t[1] + t[2]),
    # hex (accepted by parser)
    st.tuples(st.just("0x"), st.integers(min_value=0, max_value=0xFFFF).map(lambda n: format(n, "x"))).map(
        lambda t: t[0] + t[1]
    ),
    # malformed numbers
    st.sampled_from(["-", "+1", ".5", "-.5", "1..2", "1e", "1e+", "0x", "NaN", "Infinity", "-Infinity", "01.5", "1.2.3"]),
)

# ---------- recursive structure ----------

_json_value = st.recursive(
    st.one_of(
        _json_string,
        _number,
        st.sampled_from(["true", "false", "null"]),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]"),
        st.lists(
            st.tuples(_json_string, children).map(lambda t: t[0] + ":" + t[1]),
            max_size=5,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ),
    max_leaves=30,
)

# ---------- deep nesting near the 1000-level limit ----------

def _deep(depth, open_c, close_c):
    return open_c * depth + "0" + close_c * depth

_deep_nesting = st.one_of(
    st.integers(min_value=990, max_value=1000).map(lambda d: _deep(d, "[", "]")),
    st.integers(min_value=990, max_value=1000).map(lambda d: _deep(d, '{"a":', "}")),
    st.integers(min_value=1001, max_value=1005).map(lambda d: _deep(d, "[", "]")),
    st.integers(min_value=1001, max_value=1005).map(lambda d: _deep(d, '{"a":', "}")),
    st.integers(min_value=0, max_value=50).map(lambda d: _deep(d, "[", "]")),
    st.just("[" * 1000 + "]" * 999),  # unbalanced deep
)

# ---------- malformed / near-valid ----------

_malformed = st.one_of(
    st.sampled_from([
        "",
        " ",
        "{",
        "}",
        "[",
        "]",
        "{,}",
        "[,]",
        "[1,,2]",
        "[1,2,]",
        '{"a":1,}',
        '{"a" 1}',
        '{"a":}',
        '{:1}',
        "{a:1}",
        "{'a':1}",
        "[1 2]",
        '{"a":1 "b":2}',
        "[,]",
        "[1,]",
        "{\"a\":1,}",
        "\x00",
        "1\x00",
        "\x00{}",
        "\xef\xbb\xbf1",
        "\ufeff{}",
        "\ufeff[1,2]",
        "\ufeff",
    ]),
    _malformed_string,
    st.tuples(_json_value, st.sampled_from(["", " ", "abc", "\x00", " 1 2", "trailing"])).map(
        lambda t: t[0] + t[1]
    ),
    st.tuples(
        st.sampled_from(["[", "{", '{"a":', "[1,", '{"a":1,"b":']),
        _json_value,
    ).map(lambda t: t[0] + t[1]),
)

# ---------- top-level combination ----------

strategy = st.one_of(
    _json_value,
    _deep_nesting,
    _malformed,
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("0"),
    st.just("-0"),
    st.just("1e309"),
    st.just('{"a":1,"a":2,"a":3}'),
    st.just('{"":0}'),
    st.just('["\\ud800"]'),
    st.just('["\\ud800\\udc00"]'),
    st.just('"\\u0000"'),
    st.just('"\x00"'),
    st.just("1."),
    st.just("01"),
    st.just("0x10"),
    st.just("1abc"),
    st.just("1 2"),
)