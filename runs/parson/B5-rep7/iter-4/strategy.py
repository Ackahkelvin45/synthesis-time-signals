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

# ---------- combined ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "1", "[]", "null"])).map(_join)

# structured deep nesting mixing arrays and objects near the depth cap
_deep_mixed = st.builds(
    lambda d: "".join(
        ("[" if i % 2 == 0 else '{"a":') for i in range(d)
    ) + "0" + "".join(
        ("]" if i % 2 == 0 else "}") for i in reversed(range(d))
    ),
    st.one_of(
        st.sampled_from([2047, 2048, 2049, 2100]),
        st.integers(min_value=0, max_value=2048),
    ),
)

# wide structures to stress list/object element counts
_wide = st.one_of(
    st.builds(
        lambda n: "[" + ",".join(["0"] * n) + "]",
        st.one_of(st.sampled_from([100, 1000, 10000, 100000]), st.integers(min_value=0, max_value=2000)),
    ),
    st.builds(
        lambda n: "{" + ",".join('"k%d":0' % i for i in range(n)) + "}",
        st.one_of(st.sampled_from([100, 1000, 10000]), st.integers(min_value=0, max_value=2000)),
    ),
)

# whitespace-padded valid values (JSON allows insignificant whitespace)
_WS = st.sampled_from([" ", "\t", "\n", "\r\n", "  "])

_padded = st.builds(
    lambda a, v, b: a + v + b,
    st.lists(_WS, max_size=2).map(_join),
    _value,
    st.lists(_WS, max_size=2).map(_join),
)

# well-formed JSON documents built the same way the parser sees them, but
# generated from a structural model so that valid inputs are more diverse
# and more likely to exercise deeper/richer parse paths than the shallow
# hand-rolled `_value` above.
def _json_value(depth):
    if depth <= 0:
        return st.one_of(_STRING, _NUMBER, _LITERAL)
    child = st.deferred(lambda: _json_value(depth - 1))
    return st.one_of(
        _STRING,
        _NUMBER,
        _LITERAL,
        st.tuples(
            st.just("["),
            st.lists(child, max_size=4).map(lambda vs: ",".join(vs)),
            st.just("]"),
        ).map(_join),
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_STRING, st.just(":"), child).map(_join),
                max_size=4,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map(_join),
    )

_rich_value = _json_value(3)

# ---------- mutation-based fuzzing ----------

# Take a valid document and apply small structural mutations to reach
# near-valid states (truncation, byte flips, insertions) that targeted
# hand-written malformed cases often miss.
_MUT_BYTES = st.sampled_from(list('{}[],:"\\ 0123456789eE+-.tfnul'))

def _mutate(s):
    # single cheap deterministic mutation chosen by index
    if not s:
        return s
    op = hash(s) % 5
    i = hash(s[::-1]) % len(s)
    if op == 0:
        return s[:i]
    if op == 1:
        return s[:i] + s[i + 1:]
    if op == 2:
        return s[:i] + s[i] * 2 + s[i + 1:]
    if op == 3:
        return s[:i] + s[i].swapcase() + s[i + 1:]
    return s + s[:min(len(s), 4)]

_mutated = st.tuples(_value, st.integers(min_value=0, max_value=3)).map(
    lambda p: _mutate(p[0]) if p[1] == 0 else _mutate(_mutate(p[0]))
)

# ---------- combined ----------

strategy = st.one_of(
    _value,
    _rich_value,
    _malformed,
    _deep_strategy,
    _deep_obj,
    _deep_mixed,
    _wide,
    _padded,
    _mutated,
    _with_trailing(_value),
    _with_trailing(_NUMBER),
    _with_trailing(_STRING),
)