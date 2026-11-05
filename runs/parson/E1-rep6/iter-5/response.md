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

_SURROGATE = st.tuples(
    st.just("\\u"),
    st.sampled_from(["D", "d"]),
    st.sampled_from("89ABab"),
    _HEX,
    _HEX,
).map(_join)

_ESC = st.one_of(_ESC_SIMPLE, _ESC_UNICODE, _SURROGATE)

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

# Concentrate depth generation tightly around the parser's nesting cap so
# that cap_distance_mass (currently only 0.027) is exercised heavily.
_cap_depth = st.one_of(
    st.sampled_from([2046, 2047, 2048, 2049, 2050, 2051, 2052, 2060]),
    st.integers(min_value=2040, max_value=2060),
    st.integers(min_value=2000, max_value=2100),
)

_deep_strategy = st.builds(
    lambda d: "[" * d + "0" + "]" * d,
    _cap_depth,
)

_deep_obj = st.builds(
    lambda d: '{"a":' * d + "0" + "}" * d,
    _cap_depth,
)

# Alternating array/object nesting near the cap to stress mixed-depth handling.
_deep_mixed = st.builds(
    lambda d: "".join("[{" if i % 2 == 0 else '{"a":' for i in range(d))
    + "0"
    + "".join("}]" if i % 2 == 0 else "}" for i in range(d)),
    _cap_depth,
)

# ---------- upweighted production: richer / wider arrays & objects ----------

# Wider, multi-element arr/obj/pair structures to exercise productions
# (arr, obj, pair, value) that the run under-used relative to scalars.
_wide_pair = st.tuples(
    _STRING,
    st.just(":"),
    st.one_of(_STRING, _NUMBER, _LITERAL),
).map(_join)

_wide_obj = st.tuples(
    st.just("{"),
    st.lists(_wide_pair, min_size=1, max_size=6).map(lambda ps: ",".join(ps)),
    st.just("}"),
).map(_join)

_wide_arr = st.tuples(
    st.just("["),
    st.lists(st.one_of(_STRING, _NUMBER, _LITERAL, _wide_obj), min_size=1, max_size=6).map(
        lambda vs: ",".join(vs)
    ),
    st.just("]"),
).map(_join)

_wide_structures = st.one_of(_wide_arr, _wide_obj)

# ---------- upweighted production: null literal ----------
# The run never produced an accepted `null` production; bias generation
# toward bare `null` and structures that embed `null` values.
_null_biased = st.one_of(
    st.just("null"),
    st.tuples(st.just("["), st.lists(st.just("null"), min_size=1, max_size=4).map(lambda vs: ",".join(vs)), st.just("]")).map(_join),
    st.tuples(
        st.just("{"),
        st.lists(
            st.tuples(_STRING, st.just(":null")).map(_join),
            min_size=1, max_size=4,
        ).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(_join),
    st.tuples(
        st.just("["),
        st.lists(
            st.one_of(st.just("null"), _NUMBER, _STRING, st.just("true"), st.just("false")),
            min_size=1, max_size=5,
        ).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(_join),
)

# ---------- broaden exploration: structural variety ----------

# Whitespace-padded valid values (JSON permits whitespace around tokens).
_WS = st.sampled_from(["", " ", "  ", "\t", "\n", "\r\n", " \t "])

def _padded(v):
    return st.tuples(_WS, v, _WS).map(_join)

# Nested mixed structures with whitespace and deeper variety, exercising
# the recursive grammar more broadly (nested arr/obj combinations).
_mixed_nested = st.builds(
    lambda a, b, c, d: a + b + c + d,
    st.sampled_from(["[", "{"]),
    st.one_of(
        st.just("1"),
        st.just('"x"'),
        st.just("null"),
        st.just("[1,2]"),
        st.just('{"k":1}'),
    ),
    st.sampled_from([",", ":", ""]),
    st.sampled_from(["]", "}", "}", "]"]),
)

# Arrays/objects with varied element counts and mixed scalar types.
_varied_arr = st.builds(
    lambda vs: "[" + ",".join(vs) + "]",
    st.lists(
        st.one_of(_STRING, _NUMBER, _LITERAL),
        min_size=0, max_size=10,
    ),
)

_varied_obj = st.builds(
    lambda ps: "{" + ",".join(ps) + "}",
    st.lists(
        st.tuples(_STRING, st.just(":"), st.one_of(_STRING, _NUMBER, _LITERAL)).map(_join),
        min_size=0, max_size=8,
    ),
)

_broad = st.one_of(
    _padded(_value),
    _padded(_NUMBER),
    _padded(_STRING),
    _padded(_LITERAL),
    _mixed_nested,
    _varied_arr,
    _varied_obj,
)

# ---------- combined ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "1", "[]", "null"])).map(_join)

strategy = st.one_of(
    _value,
    _wide_structures,
    _null_biased,
    _broad,
    _malformed,
    _deep_strategy,
    _deep_obj,
    _deep_mixed,
    _with_trailing(_value),
    _with_trailing(_NUMBER),
    _with_trailing(_STRING),
)
```