from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

def _esc():
    simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
    uni = st.tuples(st.just("\\u"), st.text(alphabet=_hex, min_size=4, max_size=4)).map("".join)
    # surrogate-style escapes and lone surrogates
    surr = st.sampled_from([
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
        "\\uD83D", "\\uDE00", "\\uD800\\uDC00", "\\uDBFF\\uDFFF",
    ])
    return st.one_of(simple, uni, surr)

_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

def _string_body():
    return st.one_of(
        st.text(alphabet=_safe_char, max_size=8),
        st.lists(st.one_of(_safe_char.map(str), _esc()), max_size=6).map("".join),
    )

def _string():
    return st.tuples(st.just('"'), _string_body(), st.just('"')).map("".join)

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=10, max_value=10**18).map(str),
        st.integers(min_value=10**18, max_value=10**30).map(str),
    )

def _frac():
    return st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=20)).map("".join)

def _exp():
    return st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map("".join)

def _number():
    core = st.tuples(
        st.sampled_from(["", "-"]),
        _int_part(),
        st.one_of(st.none(), _frac()),
        st.one_of(st.none(), _exp()),
    ).map(lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or ""))
    # extreme magnitudes / overflow-ish
    extreme = st.sampled_from([
        "1e309", "-1e309", "1e308", "1e-309", "1e-400", "1E999", "-1E999",
        "1" + "0" * 300, "0." + "0" * 300 + "1",
        "1e2147483647", "1e-2147483648", "1e" + "9" * 20,
        "0e0", "-0", "-0.0", "0.0", "1e01", "1E+01",
    ])
    return st.one_of(core, extreme)

# ---------- recursive values ----------

def _value(depth):
    leaf = st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
    )
    if depth <= 0:
        return leaf
    return st.one_of(leaf, _obj(depth - 1), _arr(depth - 1))

def _pair(depth):
    return st.tuples(_string(), st.just(":"), _value(depth)).map("".join)

def _obj(depth):
    inner = st.one_of(
        st.just("{}"),
        st.lists(_pair(depth), min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}"),
    )
    return inner

def _arr(depth):
    inner = st.one_of(
        st.just("[]"),
        st.lists(_value(depth), min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
    )
    return inner

# ---------- depth control near 2048 ----------

def _depth():
    return st.one_of(
        st.integers(min_value=0, max_value=3),
        st.integers(min_value=2000, max_value=2050),
    )

def _deep_wrap(depth, inner):
    # wrap inner in arrays/objects to reach target depth
    def wrap(d):
        s = inner
        for _ in range(d):
            s = "[" + s + "]"
        return s
    return st.just(depth).map(wrap)

def _deep_value():
    return _depth().flatmap(lambda d: _deep_wrap(d, st.one_of(
        st.just("0"), _string(), st.just("true"), st.just("null"),
    )))

# ---------- malformed / near-valid ----------

def _malformed():
    return st.sampled_from([
        "", " ", ",", ":", "[", "]", "{", "}", "[,]", "{,}", "[1,]", "[,1]",
        '{"a"}', '{"a":}', '{"a" 1}', '{:"a"}', '{"a":1,}', '{"a":1,,}',
        '["a" "b"]', '["a",,]', '[1 2]', '{"a":1 "b":2}',
        '"unterminated', '"unterminated\\', "'single'", '"\\u12"', '"\\uZZZZ"',
        '"\\x41"', "+1", ".5", "1.", "01", "-01", "00", "0x10", "1e", "1e+",
        "--1", "1..2", "1.2.3", "truex", "nullx", "nul", "True", "NULL",
        "1abc", "1 garbage", "[]xyz", "{}trailing", "-", "-.", "-e5",
        "\u00e9", "\u2603", "[] []", "{} {}",
        "[1,2,3", '{"a":1', "[[[", "]]]", "{{}}",
        '"\\uD800"', '"\\uDC00"', '"\\uD800\\uDC00"',
        '{"k":0,"k":1}', '{"k":1,"k":2,"k":3}',
        '{"\\u0000":1}', '["\\u0000"]',
        '{"a":{"b":{"c":[1,2,{"d":null}]}}}',
        "1e309", "-1e309", "1e-400", "9" * 400,
    ])

# ---------- top-level strategy ----------

def _valid_top():
    return st.one_of(
        _value(3),
        _deep_value(),
        st.just("{}"),
        st.just("[]"),
        st.just("null"),
        st.just("true"),
        st.just("false"),
        _number(),
        _string(),
    )

def _with_trailing():
    return st.tuples(_valid_top(), st.sampled_from(["", " ", "x", "garbage", "[]", "{}", "1", "\n"])).map(
        lambda t: t[0] + t[1]
    )

def _duplicate_keys():
    return st.tuples(
        _string(),
        _value(2),
        _value(2),
    ).map(
        lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
    )

strategy = st.one_of(
    _valid_top(),
    _with_trailing(),
    _malformed(),
    _duplicate_keys(),
    _deep_value(),
)