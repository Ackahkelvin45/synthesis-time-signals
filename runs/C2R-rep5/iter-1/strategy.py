from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"',
)
_SAFE_NOCTRL = _SAFE.filter(lambda c: ord(c) >= 0x20)

_ESCAPES = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_HEX = st.sampled_from("0123456789abcdefABCDEF")
_UNICODE_ESC = st.tuples(_HEX, _HEX, _HEX, _HEX).map(lambda t: "\\u" + "".join(t))

_SURROGATE_ESC = st.tuples(
    st.sampled_from("dD"), st.sampled_from("89abAB"),
    _HEX, _HEX,
).map(lambda t: "\\u" + t[0] + t[1] + t[2] + t[3])

_STR_BODY = st.one_of(
    _SAFE_NOCTRL,
    _ESCAPES,
    _UNICODE_ESC,
    _SURROGATE_ESC,
    st.just("\x00"),
    st.just("\x01"),
    st.just("\x1f"),
    st.just("\x7f"),
)

_STR_CONTENT = st.lists(_STR_BODY, max_size=12).map("".join)

_STRING = _STR_CONTENT.map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
    st.integers(min_value=1, max_value=10**40).map(str),
    st.integers(min_value=10**300, max_value=10**320).map(str),
)

_FRAC = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
    st.integers(min_value=10**300, max_value=10**320).map(lambda n: "." + str(n)),
)

_EXP = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.one_of(st.just(""), st.just("+"), st.just("-")),
        st.integers(min_value=0, max_value=400).map(str),
    ).map(lambda t: t[0] + t[1] + t[2]),
    st.just("e309"),
    st.just("E309"),
    st.just("e-309"),
    st.just("e999999999"),
)

_SIGN = st.one_of(st.just(""), st.just("-"))

_NUMBER = st.tuples(_SIGN, _INT, _FRAC, _EXP).map(lambda t: "".join(t))

# ---------- malformed number forms (still useful) ----------

_BAD_NUMBER = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "-", "-.5", "+.5",
    "1e", "1e+", "1e-", "1.2.3", "1e309", "-1e309", "1E309",
    "--1", "1e+309", "0.", "00", "-01", "1..2",
])

# ---------- malformed strings ----------

_BAD_STRING = st.one_of(
    st.just('"unterminated'),
    st.just('"'),
    st.just('"\\'),
    st.just('"\\u"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('"\\x41"'),
    st.just("'single'"),
    st.just("bare"),
)

# ---------- malformed structural fragments ----------

_BAD_FRAGMENT = st.sampled_from([
    "[1,,2]", "[,]", "[,1]", "{,}", "{,1}", '{"a":1,,"b":2}',
    '{"a" 1}', '{"a":}', '{:1}', '{"a":1 "b":2}', '{a:1}',
    '[1 2]', '[1,2', '{"a":1', '}', ']', '[', '{',
    '{"a":1}}', '[1,2]]', '1abc', '[]xyz', '1 garbage', 'true false',
    '//x', '/* */1',
    '[}', '{]', '{"a":[}', '[{"a":1]',
])

_WS = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\t"),
    st.just("\n"),
    st.just("\r"),
    st.just("\x00"),
    st.just("\x0b"),
    st.just("\x0c"),
)

# ---------- recursive value ----------

_value = st.deferred(lambda: _value_strategy)

_key = _STRING

_pair = st.tuples(_key, _WS, st.just(":"), _WS, _value).map(lambda t: "".join(t))

_obj_members = st.tuples(
    _pair,
    st.lists(st.tuples(st.just(","), _pair).map(lambda t: t[0] + t[1]), max_size=6),
).map(lambda t: t[0] + "".join(t[1]))

_obj = st.one_of(
    st.just("{}"),
    _obj_members.map(lambda s: "{" + s + "}"),
    _obj_members.map(lambda s: "{" + s + ",}"),
    st.just("{" + "\x00" + "}"),
    st.just('{"a":1,"a":2}'),
    st.just('{"a":1,"a":2,"a":3}'),
)

_arr = st.one_of(
    st.just("[]"),
    st.lists(_value, min_size=1, max_size=8).map(lambda xs: "[" + ",".join(xs) + "]"),
    st.lists(_value, min_size=1, max_size=8).map(lambda xs: "[" + ",".join(xs) + ",]"),
)

_leaf_value = st.one_of(
    _STRING,
    _NUMBER,
    _BAD_NUMBER,
    _BAD_STRING,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("TRUE"),
    st.just("None"),
)

_value_strategy = st.one_of(
    _leaf_value,
    _obj,
    _arr,
    _BAD_FRAGMENT,
)

_deep = st.integers(min_value=0, max_value=200).flatmap(
    lambda n: st.just("[" * n + "1" + "]" * n)
)

_deep_obj = st.integers(min_value=0, max_value=60).flatmap(
    lambda n: st.just('{"a":' * n + "1" + "}" * n)
)

# ---------- top-level ----------

_top = st.one_of(
    _value,
    _deep,
    _deep_obj,
    st.tuples(_WS, _value, _WS).map(lambda t: t[0] + t[1] + t[2]),
    st.just(""),
    st.just("\x00"),
    st.just(" "),
    st.just("null\x00"),
    st.just("\x00null"),
)

strategy = _top