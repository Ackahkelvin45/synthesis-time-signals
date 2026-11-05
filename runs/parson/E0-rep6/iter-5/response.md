EDIT: broaden_exploration

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- strings ----------

_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\x00"\\',
)

_ESC_SIMPLE = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
_HEX = st.sampled_from("0123456789abcdefABCDEF")
_ESC_UNICODE = st.tuples(st.just("\\u"), _HEX, _HEX, _HEX, _HEX).map(_join)

# A high surrogate must be followed by a low surrogate to form a valid pair.
# Generate complete surrogate pairs (valid) and lone surrogates (invalid) separately.
# High surrogate range: D800-DBFF
_HIGH_SURR = st.tuples(
    st.just("\\u"),
    st.sampled_from(["D", "d"]),
    st.sampled_from("89ABab"),
    _HEX,
    _HEX,
).map(_join)

# Low surrogate range: DC00-DFFF
_LOW_SURR = st.tuples(
    st.just("\\u"),
    st.sampled_from(["D", "d"]),
    st.sampled_from("CDEFcdef"),
    _HEX,
    _HEX,
).map(_join)

_SURROGATE_PAIR = st.tuples(_HIGH_SURR, _LOW_SURR).map(_join)
_SURROGATE_LONE = st.one_of(_HIGH_SURR, _LOW_SURR)

_ESC = st.one_of(_ESC_SIMPLE, _ESC_UNICODE, _SURROGATE_PAIR, _SURROGATE_LONE)

_string_body = st.one_of(_SAFE, _ESC)

_STRING = st.tuples(
    st.just('"'),
    st.lists(_string_body, max_size=8).map(_join),
    st.just('"'),
).map(_join)

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), st.lists(st.sampled_from("0123456789"), max_size=5).map(_join)).map(_join),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=40).map(_join),
    )

def _frac_part():
    return st.tuples(st.just("."), st.lists(st.sampled_from("0123456789"), min_size=1, max_size=25).map(_join)).map(_join)

def _exp_part():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=4).map(_join),
    ).map(_join)

_EXTREME_EXP = st.sampled_from([
    "e308", "e309", "e400", "e999", "e-308", "e-400", "e-999",
    "E+308", "E+309", "e+999", "e-999", "e0000000000000001",
])

_NUMBER = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part(),
    st.one_of(st.none(), _frac_part()),
    st.one_of(st.none(), _exp_part(), _EXTREME_EXP),
).map(lambda p: p[0] + p[1] + (p[2] or "") + (p[3] or ""))

# ---------- keywords ----------

_LITERAL = st.sampled_from(["true", "false", "null"])

# ---------- recursive structure ----------

# depth control: concentrate near 2048 occasionally, but keep most small
_depth_choice = st.one_of(
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=4, max_value=16),
    st.sampled_from([32, 64, 128, 256, 512, 1024, 2000, 2047, 2048, 2049, 2100]),
)

def _wrap_depth(depth, inner):
    # produce nested arrays/objects of the given depth around inner
    if depth <= 0:
        return inner
    opener = st.sampled_from(["[", '{"k":'])
    closer = st.sampled_from(["]", "}"])
    return st.tuples(opener, inner, closer).map(_join)

def _nest(depth, inner):
    if depth <= 0:
        return inner
    opener, closer = ("[", "]")
    s = inner
    for _ in range(depth):
        s = st.tuples(st.just(opener), s, st.just(closer)).map(_join)
    return s

# base values
_base = st.one_of(_STRING, _NUMBER, _LITERAL)

# shallow recursive structure
def _obj_or_arr(children):
    pair = st.tuples(_STRING, st.just(":"), children).map(_join)
    obj_full = st.tuples(
        st.just("{"),
        st.lists(pair, min_size=1, max_size=3).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(_join)
    obj_empty = st.just("{}")
    arr_full = st.tuples(
        st.just("["),
        st.lists(children, min_size=1, max_size=3).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(_join)
    arr_empty = st.just("[]")
    return st.one_of(obj_empty, arr_empty, obj_full, arr_full)

_value = st.recursive(_base, _obj_or_arr, max_leaves=8)

# ---------- malformed / near-valid ----------

_malformed = st.one_of(
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just('{"a":1,,}'),
    st.just('{"a" 1}'),
    st.just('{"a":}'),
    st.just("{:1}"),
    st.just('{"a":1,}'),
    st.just("[1,]"),
    st.just('"unterminated'),
    st.just("'single'"),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("-01"),
    st.just("-"),
    st.just("-."),
    st.just("tru"),
    st.just("nul"),
    st.just("fals"),
    st.just(""),
    st.just(" "),
    st.just("\t\n\r "),
    st.just("{}{}"),
    st.just("[]x"),
    st.just("1abc"),
    st.just("1 garbage"),
    st.just("null trailing"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just('{"k":0,"k":1}'),
    st.just('{"a":1,"a":2,"b":3}'),
    st.just('"\\uD800"'),
    st.just('"\\uDC00"'),
    st.just('"\\uD800\\uDC00"'),
    st.just('"\\u0000"'),
    st.just('"a\\u0000b"'),
    st.just('"\\q"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('{"a":1 "b":2}'),
    st.just("[1 2]"),
    st.just("[[[["),
    st.just("]]]]"),
    st.just("{{}}"),
    st.just('{"a":{"b":{"c":}}}'),
)

# ---------- deep nesting near cap ----------

def _deep(depth):
    return st.tuples(
        st.just("["),
        st.just("0"),
        st.just("]" * depth),
    ).map(_join).map(lambda s: "[" * depth + "0" + "]" * depth)

_deep_strategy = st.builds(
    lambda d: "[" * d + "0" + "]" * d,
    st.one_of(
        st.sampled_from([2047, 2048, 2049, 2050, 2100, 3000]),
        st.integers(min_value=0, max_value=2048),
    ),
)

_deep_obj = st.builds(
    lambda d: '{"a":' * d + "0" + "}" * d,
    st.one_of(st.sampled_from([2047, 2048, 2049, 2100]), st.integers(min_value=0, max_value=2048)),
)

# ---------- mixed deep nesting near cap ----------

def _mixed_nest(depth):
    # Alternate array and object nesting to exercise both depth counters.
    def build(d):
        parts = []
        for i in range(d):
            if i % 2 == 0:
                parts.append("[")
            else:
                parts.append('{"a":')
        s = "".join(parts) + "0"
        closers = []
        for i in range(d):
            if (d - 1 - i) % 2 == 0:
                closers.append("]")
            else:
                closers.append("}")
        return s + "".join(closers)
    return st.builds(build, st.just(depth))

_mixed_deep = st.builds(
    _mixed_nest,
    st.just(0),
).flatmap(lambda _: st.builds(
    lambda d: _build_mixed(d),
    st.one_of(
        st.sampled_from([2047, 2048, 2049, 2050, 2100, 3000]),
        st.integers(min_value=0, max_value=2048),
    ),
))

def _build_mixed(d):
    parts = []
    for i in range(d):
        if i % 2 == 0:
            parts.append("[")
        else:
            parts.append('{"a":')
    s = "".join(parts) + "0"
    closers = []
    for i in range(d):
        if (d - 1 - i) % 2 == 0:
            closers.append("]")
        else:
            closers.append("}")
    return s + "".join(closers)

# ---------- broaden exploration: whitespace, multi-element containers, varied keys ----------

_WS = st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "])

def _ws(v):
    # sprinkle optional insignificant whitespace around a token
    return st.tuples(_WS, v, _WS).map(_join)

_key = st.one_of(
    _STRING,
    st.sampled_from([
        '"a"', '"b"', '"k"', '"key"', '""', '"long_key_name"',
        '"a b"', '"a\\tb"', '"\\u0041"', '"0"', '"1"',
    ]),
)

def _arr_varied(children):
    return st.tuples(
        st.just("["),
        _WS,
        st.lists(_ws(children), min_size=0, max_size=6).map(lambda vs: ("," + _WS).join(vs)),
        _WS,
        st.just("]"),
    ).map(_join)

def _obj_varied(children):
    pair = st.tuples(_ws(_key), st.just(":"), _ws(children)).map(_join)
    return st.tuples(
        st.just("{"),
        _WS,
        st.lists(pair, min_size=0, max_size=6).map(lambda ps: ("," + _WS).join(ps)),
        _WS,
        st.just("}"),
    ).map(_join)

_value_ws = st.recursive(
    st.one_of(_base, _ws(_base)),
    lambda children: st.one_of(_arr_varied(children), _obj_varied(children)),
    max_leaves=10,
)

# ---------- combined ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "1", "[]", "null"])).map(_join)

strategy = st.one_of(
    _value,
    _value_ws,
    _malformed,
    _deep_strategy,
    _deep_obj,
    _mixed_deep,
    _with_trailing(_value),
    _with_trailing(_NUMBER),
    _with_trailing(_STRING),
)
```