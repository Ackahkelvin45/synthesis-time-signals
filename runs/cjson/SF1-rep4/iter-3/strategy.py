import json
from hypothesis import strategies as st

# ---------- primitives ----------

_safe_chars = st.characters(
    whitelist_categories=("Lu", "Ll", "Lt", "Lm", "Lo", "Nd", "Nl", "No",
                          "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po", "Sm",
                          "Sc", "Sk", "So", "Zs"),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
                         '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_control_chars = st.sampled_from(
    [chr(i) for i in range(0x20)] + ["\x00", "\x7f"]
)

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map("".join)

_escape_body = st.one_of(
    st.sampled_from(['"', "\\", "/", "b", "f", "n", "r", "t"]),
    _hex4().map(lambda h: "u" + h),
)

_escape = _escape_body.map(lambda b: "\\" + b)

# surrogate escapes (lone -> rejected by target, but interesting)
_surrogate_escape = st.sampled_from(
    ["\\ud800", "\\udbff", "\\udc00", "\\udfff", "\\uD800", "\\uDC00"]
)

_string_char = st.one_of(
    _safe_chars,
    _escape,
    _control_chars,
    _surrogate_escape,
)

def _string_body():
    return st.lists(_string_char, max_size=8).map("".join)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10 ** 18).map(str),
    st.integers(min_value=1, max_value=10 ** 18).map(lambda n: "0" + str(n)),  # leading zeros
    st.integers(min_value=0, max_value=10 ** 18).map(lambda n: "0x" + format(n, "x")),  # hex
)

_frac_part = st.one_of(
    st.integers(min_value=0, max_value=10 ** 9).map(lambda n: "." + str(n)),
    st.just("."),  # trailing dot
)

_exp_part = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.integers(min_value=-400, max_value=400).map(lambda n: "E+" + str(abs(n))),
    st.just("e309"),
    st.just("e999"),
    st.just("e-999"),
    st.just("E308"),
)

_sign = st.one_of(st.just(""), st.just("-"))

def _number():
    return st.tuples(_sign, _int_part).map("".join)

_number_full = st.one_of(
    _number(),
    st.tuples(_sign, _int_part, _frac_part).map("".join),
    st.tuples(_sign, _int_part, _exp_part).map("".join),
    st.tuples(_sign, _int_part, _frac_part, _exp_part).map("".join),
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# ---------- recursive values ----------

_ws = st.sampled_from(["", "", "", " ", "\t", "\n", "\r", " \n\t "])

def _ws_str():
    return _ws

_key = _string_body().map(lambda s: '"' + s + '"')

def _value(draw, depth):
    raise NotImplementedError

# Build with st.recursive
def _make_value_leaf():
    return st.one_of(
        _string_body().map(lambda s: '"' + s + '"'),
        _number_full,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )

def _make_obj(value_strategy):
    def pair():
        return st.tuples(_key, _ws_str(), st.just(":"), _ws_str(), value_strategy).map(
            "".join
        )
    return st.tuples(
        st.just("{"),
        _ws_str(),
        st.lists(pair(), max_size=4).map(lambda ps: ",".join(ps)),
        _ws_str(),
        st.just("}"),
    ).map("".join)

def _make_arr(value_strategy):
    return st.tuples(
        st.just("["),
        _ws_str(),
        st.lists(value_strategy, max_size=4).map(lambda vs: ",".join(vs)),
        _ws_str(),
        st.just("]"),
    ).map("".join)

_value = st.recursive(
    _make_value_leaf(),
    lambda children: st.one_of(_make_obj(children), _make_arr(children)),
    max_leaves=20,
)

# ---------- malformed-but-near-valid ----------

_malformed = st.one_of(
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just("[1,]"),
    st.just('{"a":1,}'),
    st.just('{"a" 1}'),
    st.just('{"a":}'),
    st.just('{a:1}'),
    st.just("'single'"),
    st.just('"unterminated'),
    st.just('"bad\\xescape"'),
    st.just(""),
    st.just("   "),
    st.just("\x00"),
    st.just("\xef\xbb\xbf1"),
    st.just("1abc"),
    st.just("1 2"),
    st.just("01"),
    st.just("1."),
    st.just("0x10"),
    st.just('"\\ud800"'),
    st.just('"a\x00b"'),
    st.just('"a\tb"'),
)

# ---------- deep nesting near the 1000 limit ----------

def _deep(depth):
    return st.just("[" * depth + "]" * depth)

_deep_strategy = st.one_of(
    _deep(999),
    _deep(1000),
    _deep(1001),
    _deep(1002),
    _deep(500),
    st.integers(min_value=0, max_value=1005).map(lambda d: "[" * d + "]" * d),
    st.integers(min_value=0, max_value=1005).map(
        lambda d: '{"a":' * d + "1" + "}" * d
    ),
)

# ---------- top-level ----------

_top = st.one_of(
    _value,
    _malformed,
    _deep_strategy,
    st.tuples(_ws_str(), _value, _ws_str()).map("".join),
    st.tuples(_value, st.just("garbage after")).map("".join),
    st.just("\xef\xbb\xbf").flatmap(lambda bom: _value.map(lambda v: bom + v)),
    # ensure boolean literals are exercised (gap in last run)
    st.just("true"),
    st.just("false"),
    st.tuples(_ws_str(), st.sampled_from(["true", "false"]), _ws_str()).map("".join),
    st.lists(st.sampled_from(["true", "false", "null"]), min_size=1, max_size=4).map(
        lambda vs: "[" + ",".join(vs) + "]"
    ),
)

strategy = _top