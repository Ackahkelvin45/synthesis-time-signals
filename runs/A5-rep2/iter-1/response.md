```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _u_escape():
    return st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map("".join)

# escapes: standard short escapes plus \uXXXX (including surrogates D800..DFFF)
_short_esc = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_surrogate_esc = st.tuples(
    st.just("\\u"),
    st.sampled_from("dD"),
    st.sampled_from("89abAB"),
    _hex, _hex,
).map("".join)

_esc = st.one_of(_short_esc, _u_escape(), _surrogate_esc)

# safe code points: anything except ", \, and control 0x00-0x1F
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
    min_codepoint=0x20,
).filter(lambda c: not (0x00 <= ord(c) <= 0x1F))

# raw control bytes / NUL that the parser must handle faithfully
_control_char = st.sampled_from(
    [chr(0x00), chr(0x01), chr(0x08), chr(0x0b), chr(0x0c), chr(0x1f), "\x7f"]
)

_string_body = st.one_of(
    _safe_char,
    _esc,
    _control_char,
)

def _string():
    return st.lists(_string_body, min_size=0, max_size=12).map(
        lambda cs: '"' + "".join(cs) + '"'
    )

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(
        st.integers(min_value=1, max_value=9),
        st.lists(st.integers(min_value=0, max_value=9), max_size=18).map(
            lambda ds: "".join(map(str, ds))
        ),
    ).map(lambda t: str(t[0]) + t[1]),
)

_frac = st.tuples(
    st.just("."),
    st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=18).map(
        lambda ds: "".join(map(str, ds))
    ),
).map("".join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=4).map(
        lambda ds: "".join(map(str, ds))
    ),
).map("".join)

# extreme magnitudes / overflow / underflow
_extreme_exp = st.sampled_from(
    ["e309", "e400", "e9999", "e-9999", "e-400", "E+308", "e+309", "e-324"]
)

_number = st.one_of(
    # well-formed numbers
    st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac),
        st.one_of(st.just(""), _exp),
    ).map("".join),
    # extreme exponent forms
    st.tuples(st.sampled_from(["", "-"]), _int_part, _extreme_exp).map("".join),
    # lone minus (parser accepts)
    st.just("-"),
    # malformed near-valid forms (parser rejects, still useful)
    st.sampled_from([
        "+1", ".5", "1.", "01", "007", "0x1F", "-.5", "-+1",
        "1e", "1e+", "1E-", "--1", "1..2", "00", "1.2.3",
    ]),
)

# ---------- near-valid-but-malformed fragments ----------

_malformed = st.sampled_from([
    "[,]", "[1,,2]", "[,1]", "[1 2]",
    '{"a" 1}', '{"a":1,,"b":2}', '{,}', '{:1}', '{"a":}',
    '"unterminated', "'single'", "{a:1}", "{'a':1}",
    "truee", "nul", "tru", "fals",
    "[1,2,]", '{"a":1,}',  # trailing comma (accepted by parser)
    "1abc", "[]xyz", "1 garbage", "true false",
    "//comment\n1", "/* c */1",
    "\x00", "\x01\x02",
])

# ---------- recursive value ----------

def _value(draw):
    return draw(_value_strategy)

_value_strategy = st.deferred(lambda: _value_strategy_impl)

_value_strategy_impl = st.recursive(
    st.one_of(
        _string(),
        _number,
        st.sampled_from(["true", "false", "null"]),
        _malformed,
    ),
    lambda children: st.one_of(
        _array(children),
        _object(children),
    ),
    max_leaves=20,
)

def _array(children):
    return st.one_of(
        st.just("[]"),
        st.lists(children, min_size=1, max_size=6).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(children, min_size=1, max_size=5).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        ),
    )

def _object(children):
    pair = st.tuples(_string(), st.just(":"), children).map("".join)
    return st.one_of(
        st.just("{}"),
        st.lists(pair, min_size=1, max_size=6).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        st.lists(pair, min_size=1, max_size=5).map(
            lambda ps: "{" + ",".join(ps) + ",}"
        ),
        # duplicate keys: repeat a pair
        st.tuples(
            _string(),
            st.just(":"),
            children,
            st.just(","),
            _string(),
            st.just(":"),
            children,
        ).map("".join).map(lambda s: "{" + s + "}"),
    )

# ---------- deep nesting generators ----------

def _deep_array(depth, inner):
    return "[" * depth + inner + "]" * depth

def _deep_object(depth, inner):
    # {"a":{"a":{...inner...}}}
    return '{"a":' * depth + inner + "}" * depth

_deep = st.one_of(
    st.tuples(
        st.integers(min_value=2, max_value=60),
        st.sampled_from(["0", "1", "null", "true", '"x"', "[]", "{}"]),
    ).map(lambda t: _deep_array(t[0], t[1])),
    st.tuples(
        st.integers(min_value=2, max_value=40),
        st.sampled_from(["0", "1", "null", '"x"']),
    ).map(lambda t: _deep_object(t[0], t[1])),
)

# ---------- top-level strategy ----------

def _top(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        return draw(_deep)
    if choice == 1:
        # empty containers
        return draw(st.sampled_from(["{}", "[]", " \t\n{}", "{} ", "[]\n"]))
    if choice == 2:
        # whitespace-wrapped
        v = draw(_value_strategy)
        return draw(st.sampled_from([" ", "\t", "\n", "\r\n"])) + v
    if choice == 3:
        # bias toward objects with members (stressed first-pass path)
        return draw(_object(_value_strategy))
    # general value
    return draw(_value_strategy)

strategy = st.one_of(
    st.recursive(
        st.one_of(_string(), _number, st.sampled_from(["true", "false", "null"]), _malformed),
        lambda children: st.one_of(_array(children), _object(children)),
        max_leaves=15,
    ),
    st.builds(_top, st.integers(min_value=0, max_value=9)).flatmap(
        lambda _: st.builds(_top_draw)
    ) if False else st.deferred(lambda: _top_strategy),
)

_top_strategy = st.builds(_top, st.integers(min_value=0, max_value=9))

strategy = st.one_of(
    _top_strategy,
    _deep,
    st.just("{}"),
    st.just("[]"),
    st.just("-"),
    st.just('{"a":1,"a":2}'),
    st.just("[1,2,]"),
    st.just('{"a":1,}'),
    st.just("1e309"),
    st.just('"\\uD800"'),
    st.just('"\x00"'),
)
```