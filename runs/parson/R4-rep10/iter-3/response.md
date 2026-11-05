```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_SAFE = st.characters(
    blacklist_categories=("Cc", "Cs"),
    blacklist_characters='"\\',
)

_ESC = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.builds(
        lambda h: "\\u" + h,
        st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
    ),
    # surrogate escapes
    st.sampled_from([
        "\\ud800", "\\udfff", "\\udc00", "\\ud83d\\ude00",
        "\\uD800\\uDC00", "\\u0000", "\\u001f", "\\u007f",
    ]),
)

_str_char = st.one_of(_SAFE, _ESC)


def _str_body():
    return st.lists(_str_char, min_size=0, max_size=8).map("".join)


def _quoted():
    return _str_body().map(lambda s: '"' + s + '"')


# ---------- numbers ----------

_EXTREME_NUMBERS = st.sampled_from([
    "0", "-0", "1", "-1", "1e309", "-1e309", "1e-309", "1e308",
    "1.7976931348623157e308", "1e400", "-1e400", "1e-400",
    "0.0", "-0.0", "123456789012345678901234567890",
    "9" * 40, "1" + "0" * 300, "1e" + "9" * 5,
    "1E+10", "1e-10", "0e0", "0e999", "1e01", "123.456e-789",
    "1.0e+308", "5e-324", "2.2250738585072014e-308",
])

_normal_number = st.builds(
    lambda sign, ip, frac, exp: sign + ip + frac + exp,
    st.sampled_from(["", "-"]),
    st.one_of(
        st.just("0"),
        st.from_regex(r"[1-9][0-9]{0,6}", fullmatch=True),
    ),
    st.one_of(
        st.just(""),
        st.from_regex(r"\.[0-9]{1,6}", fullmatch=True),
    ),
    st.one_of(
        st.just(""),
        st.builds(
            lambda e, s, d: e + s + d,
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.from_regex(r"[0-9]{1,4}", fullmatch=True),
        ),
    ),
)

_number = st.one_of(_EXTREME_NUMBERS, _normal_number)

# ---------- malformed fragments ----------

_MALFORMED = st.sampled_from([
    "", ",", ",,", ":", "::", "{,}", "[,]", "{,}", '{"a" 1}',
    '{"a":}', '{"a":1,}', "[1,]", "[1,,2]", '"unterminated',
    "+1", ".5", "01", "-", "-.", "1.", "truex", "nul", "tru",
    "fals", '{"a":1 "b":2}', "[1 2]", "{", "}", "[", "]",
    '{"a"::1}', '[,1]', '{"a":1,,"b":2}', '"\x00"',
    "1e", "1e+", "0x10", "Infinity", "NaN", "-Infinity",
    '{"a":1}garbage', "[]xyz", "1abc", "1 garbage",
])

# ---------- recursive JSON ----------

def _make_value(draw, children):
    leaf = st.one_of(
        _quoted(),
        _number,
        st.sampled_from(["true", "false", "null"]),
    )
    if children is None:
        return draw(leaf)
    return draw(st.one_of(leaf, children))


def _make_arr(draw, value):
    n = draw(st.integers(min_value=0, max_value=4))
    items = [draw(value) for _ in range(n)]
    return "[" + ",".join(items) + "]"


def _make_obj(draw, value):
    n = draw(st.integers(min_value=0, max_value=4))
    keys = draw(st.lists(_quoted(), min_size=n, max_size=n, unique=True))
    pairs = [k + ":" + draw(value) for k in keys]
    return "{" + ",".join(pairs) + "}"


def _build_value():
    return st.recursive(
        st.one_of(
            _quoted(),
            _number,
            st.sampled_from(["true", "false", "null"]),
        ),
        lambda children: st.one_of(
            children.flatmap(lambda v: st.just(_make_arr_from(v))),
            children.flatmap(lambda v: st.just(_make_obj_from(v))),
        ),
        max_leaves=20,
    )


def _make_arr_from(v):
    return "[" + v + "]"


def _make_obj_from(v):
    return '{"a":' + v + "}"


_value = _build_value()

# ---------- deep nesting near 2048 ----------

def _deep():
    return st.integers(min_value=1, max_value=2100).flatmap(
        lambda d: st.sampled_from([
            "[" * d + "]" * d,
            "[" * d + "0" + "]" * d,
            '{"a":' * d + "0" + "}" * d,
            "[" * d,  # unterminated deep
            "[" * (d - 1) + "]" * (d - 1) if d > 0 else "[]",
        ])
    )


_deep_strategy = st.one_of(
    _deep(),
    st.integers(min_value=2040, max_value=2060).flatmap(
        lambda d: st.just("[" * d + "]" * d)
    ),
)

# ---------- duplicate keys ----------

def _dup_keys():
    return st.builds(
        lambda k, a, b: '{"' + k + '":' + a + ',"' + k + '":' + b + "}",
        st.text(alphabet="abc", min_size=1, max_size=3),
        _number,
        _number,
    )


# ---------- top-level assembly ----------

_json_value = st.one_of(
    _value,
    _deep_strategy,
    _dup_keys(),
    _MALFORMED,
)

# trailing content (accepted by parser)
def _trailing():
    return st.builds(
        lambda v, t: v + t,
        _value,
        st.sampled_from(["", " ", "x", "garbage", "1abc", "[]xyz", "\n\t"]),
    )


_final = st.one_of(
    _json_value,
    _trailing(),
    _deep_strategy,
    _dup_keys(),
    _MALFORMED,
)

# whitespace variants around a value
def _ws_around():
    return st.builds(
        lambda a, v, b: a + v + b,
        st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
        _value,
        st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
    )


strategy = st.one_of(_final, _ws_around()).filter(lambda s: "\x00" not in s)
```