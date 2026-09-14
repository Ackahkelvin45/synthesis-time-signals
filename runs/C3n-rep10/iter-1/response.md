```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

def _unicode_escape():
    return st.builds(lambda h: "\\u" + h, _hex4())

def _simple_escape():
    return st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _escape():
    return st.one_of(_simple_escape(), _unicode_escape())

# SAFECODEPOINT: anything except quote, backslash, and control chars 0x00-0x1F
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

def _string_body():
    return st.one_of(
        st.text(alphabet=_safe_char, max_size=8),
        _escape(),
        st.lists(st.one_of(st.text(alphabet=_safe_char, max_size=4), _escape()), max_size=4).map("".join),
    )

def _string():
    return _string_body().map(lambda b: '"' + b + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.from_regex(r"[1-9][0-9]{0,5}", fullmatch=True),
        st.integers(min_value=0, max_value=10**18).map(str),
    )

def _frac():
    return st.from_regex(r"\.[0-9]{1,6}", fullmatch=True)

def _exp():
    return st.from_regex(r"[Ee][+-]?[0-9]{1,4}", fullmatch=True)

def _number():
    valid = st.builds(
        lambda s, i, f, e: s + i + f + e,
        st.sampled_from(["", "-"]),
        _int_part(),
        st.one_of(st.just(""), _frac()),
        st.one_of(st.just(""), _exp()),
    )
    extremes = st.sampled_from([
        "1e309", "-1e309", "1e-309", "1E+308", "1e999999", "-1e999999",
        "1e-999999", "0e0", "0E-0", "-0", "-0.0", "1e01",
        "123456789012345678901234567890",
        "-123456789012345678901234567890.123456789e12345",
    ])
    lone_minus = st.just("-")
    return st.one_of(valid, extremes, lone_minus)

# ---------- malformed number forms (near-valid) ----------

def _bad_number():
    return st.sampled_from([
        "+1", "+0.5", ".5", "-.5", "1.", "01", "00", "-01", "0x1F",
        "1e", "1e+", "1e-", "1.e5", "--1", "1..2", ".", "+", "1e309e",
        "0.", "-0.", "1.2.3",
    ])

# ---------- malformed fragments ----------

def _malformed():
    return st.sampled_from([
        "[,]", "[,1]", "[1,,2]", "{,}", "{,}", '{"a":1,,}',
        '{"a" 1}', '{"a":}', '{:1}', '{"a":1 "b":2}',
        '"unterminated', '"\\', '"\\u12"', '"\\uZZZZ"',
        "[1,2", '{"a":1', "]", "}", ",", ":", "true false",
        "1abc", "[]xyz", "nullx", "tru", "nul", "fals",
        "{a:1}", "'x'", "//comment", "/*c*/1", "[1,]extra",
        "{\"a\":1,}", "[1,2,]",
    ])

# ---------- recursive structure ----------

_json_strategy = None

def _value():
    return st.one_of(
        st.deferred(lambda: _json_strategy),
        _string(),
        _number(),
        _bad_number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed(),
    )

def _pair():
    return st.builds(
        lambda k, v: k + ":" + v,
        _string(),
        _value(),
    )

def _pair_bad():
    return st.sampled_from([
        '"a" 1', '"a":', '"a"::1', '"a"1',
        '"dup":1',
    ])

def _obj():
    empty = st.just("{}")
    members = st.lists(_pair(), min_size=1, max_size=5).map(lambda ps: "{" + ",".join(ps) + "}")
    dup = st.lists(
        st.builds(lambda k, v: k + ":" + v, st.just('"k"'), _value()),
        min_size=2, max_size=5,
    ).map(lambda ps: "{" + ",".join(ps) + "}")
    trailing = st.lists(_pair(), min_size=1, max_size=4).map(
        lambda ps: "{" + ",".join(ps) + ",}"
    )
    bad = st.lists(_pair_bad(), min_size=1, max_size=3).map(
        lambda ps: "{" + ",".join(ps) + "}"
    )
    return st.one_of(empty, members, dup, trailing, bad)

def _arr():
    empty = st.just("[]")
    members = st.lists(_value(), min_size=1, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]")
    trailing = st.lists(_value(), min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + ",]")
    bad = st.sampled_from(["[1,,2]", "[,1]", "[,]", "[1,2,,]"])
    return st.one_of(empty, members, trailing, bad)

_json_strategy = st.recursive(
    st.one_of(
        _string(),
        _number(),
        _bad_number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed(),
    ),
    lambda children: st.one_of(
        _obj_with(children),
        _arr_with(children),
    ),
    max_leaves=25,
)

def _obj_with(children):
    empty = st.just("{}")
    members = st.lists(
        st.builds(lambda k, v: k + ":" + v, _string(), children),
        min_size=1, max_size=4,
    ).map(lambda ps: "{" + ",".join(ps) + "}")
    dup = st.lists(
        st.builds(lambda k, v: k + ":" + v, st.just('"k"'), children),
        min_size=2, max_size=4,
    ).map(lambda ps: "{" + ",".join(ps) + "}")
    trailing = st.lists(
        st.builds(lambda k, v: k + ":" + v, _string(), children),
        min_size=1, max_size=3,
    ).map(lambda ps: "{" + ",".join(ps) + ",}")
    return st.one_of(empty, members, dup, trailing)

def _arr_with(children):
    empty = st.just("[]")
    members = st.lists(children, min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]")
    trailing = st.lists(children, min_size=1, max_size=3).map(lambda vs: "[" + ",".join(vs) + ",]")
    return st.one_of(empty, members, trailing)

# ---------- deep nesting & NUL/control injection ----------

def _deep():
    depth = st.integers(min_value=1, max_value=64)
    kind = st.sampled_from(["arr", "obj", "mix"])
    def build(d, k):
        if k == "arr":
            return "[" * d + "]" * d
        if k == "obj":
            return '{"a":' * d + "0" + "}" * d
        # mix
        return "".join("[" if i % 2 == 0 else "{" for i in range(d)) + \
               "0" + \
               "".join("]" if i % 2 == 1 else "}" for i in reversed(range(d)))
    return st.builds(build, depth, kind)

_nul_control = st.sampled_from(["\x00", "\x01", "\x1f", "\x0b", "\x0c", "\x7f"])

def _with_nul():
    return st.builds(
        lambda a, b, c: a + b + c,
        st.one_of(st.just(""), _string()),
        _nul_control,
        st.one_of(st.just(""), _string(), _number()),
    )

# ---------- top-level ----------

strategy = st.one_of(
    _json_strategy,
    _deep(),
    _with_nul(),
    _obj(),
    _arr(),
    _malformed(),
    _bad_number(),
    st.one_of(
        st.just("{}"),
        st.just("[]"),
        st.just('{"a":1,"a":2}'),
        st.just("[1,2,]"),
        st.just('{"a":1,}'),
        st.just("1e309"),
        st.just("-"),
        st.just('"\x00"'),
        st.just('"\\uD800"'),
        st.just('"\\uDC00"'),
        st.just('"\\uD800\\uDC00"'),
        st.just("\x00"),
    ),
)
```