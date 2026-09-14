from hypothesis import strategies as st

# ---------- leaf pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map("".join)

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4().map(lambda h: "\\u" + h),
    # lone / paired surrogates
    st.sampled_from([
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
        "\\uD800\\uDC00", "\\uDBFF\\uDFFF", "\\uD834\\uDD1E",
        "\\u0000", "\\u001F", "\\u007F", "\\uFFFF", "\\uFFFE",
    ]),
)

# safe code points: not quote, not backslash, not raw control 0x00-0x1F
_safe = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

# raw control bytes / NUL embedded directly in strings (parser uses length)
_raw_ctrl = st.sampled_from(
    ["\x00", "\x01", "\x1f", "\x7f", "\x0b", "\x0c", "\x1b", "\x08"]
)

_str_body = st.one_of(
    _safe.map(str),
    _escapes,
    _raw_ctrl,
    _hex4().map(lambda h: "\\u" + h),
)

def _string():
    return st.lists(_str_body, max_size=8).map(lambda parts: '"' + "".join(parts) + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nz_digits = st.text(alphabet="0123456789", min_size=1, max_size=6).filter(
    lambda s: s[0] != "0"
)

_int_part = st.one_of(st.just("0"), _nz_digits)

_frac = st.tuples(st.just("."), _digits).map("".join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    _digits,
).map("".join)

_extreme = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "1e-324", "1e400",
    "0e0", "0e999", "-0", "-0.0", "1e+308", "1E-999",
    "179769313486231570000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0.0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001",
])

_number = st.one_of(
    _extreme,
    st.tuples(
        st.one_of(st.just(""), st.just("-")),
        _int_part,
        st.one_of(st.just(""), _frac),
        st.one_of(st.just(""), _exp),
    ).map("".join),
    # parser-accepted oddities: lone `-`
    st.just("-"),
)

# ---------- malformed near-valid tokens ----------

_bad_string = st.sampled_from([
    '"', '"abc', '"abc\\', '"\\u12', '"\\uZZZZ"', '"\\x41"', '"a"b"',
    '"\\uD800', '"unterminated',
])

_bad_number = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "1e", "1e+", "1.2.3",
    "1e309x", "- 1", "--1", "1_000", "Infinity", "NaN", "1e1e1",
])

_ws = st.text(alphabet=" \t\n\r", max_size=3)

# ---------- recursive structure ----------

def _key():
    return st.one_of(_string(), _bad_string)

def _value_leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _bad_string,
        _bad_number,
    )

# near-valid-but-malformed raw fragments
_malformed = st.sampled_from([
    "[1,,2]", "[,]", "[,1]", "[1 2]", "{,}", '{"a"}', '{"a":}',
    '{"a" : }', '{"a":1,,"b":2}', '{:1}', '{"a":1 "b":2}',
    "[1,2,,]", "{a:1}", "{'a':1}", "//x", "/* */1", "'x'",
    "1abc", "[]xyz", "1 garbage", "true false", "[1,2]]", "{{}}",
    '{"a":1}}', "[[[]", "]]]", "}", "]", ",", ":",
])

def _obj(draw):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        return "{}"
    parts = []
    for _ in range(n):
        k = draw(_key())
        v = draw(_value())
        parts.append(k + draw(_ws) + ":" + draw(_ws) + v)
    body = ("," + draw(_ws)).join(parts)
    trailing = draw(st.one_of(st.just(""), st.just(",")))
    return "{" + draw(_ws) + body + trailing + draw(_ws) + "}"

def _arr(draw):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        return "[]"
    parts = [draw(_value()) for _ in range(n)]
    body = ("," + draw(_ws)).join(parts)
    trailing = draw(st.one_of(st.just(""), st.just(",")))
    return "[" + draw(_ws) + body + trailing + draw(_ws) + "]"

_value = st.deferred(lambda: _value_strategy)

_value_strategy = st.one_of(
    _value_leaf(),
    st.deferred(lambda: _obj_strategy),
    st.deferred(lambda: _arr_strategy),
)

_obj_strategy = st.builds(_obj, st.integers())  # placeholder; replaced below
# Use @st.composite properly instead of builds for recursion.

@st.composite
def _obj_c(draw):
    return _obj(draw)

@st.composite
def _arr_c(draw):
    return _arr(draw)

def _value_c():
    return st.one_of(
        _value_leaf(),
        _obj_c(),
        _arr_c(),
    )

# Recursive value via st.recursive
_value_rec = st.recursive(
    _value_leaf(),
    lambda children: st.one_of(
        st.lists(
            st.tuples(children, _ws),
            max_size=5,
        ).map(lambda ps: "[" + ("," + _ws).join(v + w for v, w in ps) + "]"),
        st.lists(
            st.tuples(_key(), _ws, st.just(":"), _ws, children, _ws),
            max_size=5,
        ).map(lambda ps: "{" + ",".join(k + w1 + ":" + w2 + v + w3 for k, w1, _, w2, v, w3 in ps) + "}"),
        children,
    ),
)

# ---------- top-level strategy ----------

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=200)
    return depth.map(lambda d: "[" * d + "]" * d)

def _deep_obj_nesting():
    depth = st.integers(min_value=1, max_value=100)
    return depth.map(lambda d: '{"a":' * d + "1" + "}" * d)

_top = st.one_of(
    _value_rec,
    _malformed,
    _deep_nesting(),
    _deep_obj_nesting(),
    _ws.map(lambda w: w),  # whitespace only
    st.just(""),
    st.just("{}"),
    st.just("[]"),
    st.just('{"a":1,"a":2}'),
    st.just('{"a":1,}'),
    st.just("[1,2,]"),
    st.just("1e309"),
    st.just("-"),
    st.just('"\x00"'),
    st.just('"\\uD800"'),
)

strategy = _top