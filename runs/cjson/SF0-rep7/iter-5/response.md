```python
import json
from hypothesis import strategies as st

# ---------- scalar / leaf strategies ----------

_num_int = st.one_of(
    st.integers(min_value=-(10**30), max_value=10**30),
    st.integers(min_value=-(2**63), max_value=2**63),
    st.sampled_from([0, -0, 1, -1, 10, 100, 1000]),
)

_num_str = st.one_of(
    _num_int.map(str),
    st.sampled_from([
        "1e309", "-1e309", "1e-309", "1e308", "-1e308",
        "1E+400", "1e-400", "0e0", "0e999", "1e01",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1.7976931348623157e308",
        "2.2250738585072014e-308",
        "5e-324",
    ]),
    st.sampled_from(["01", "-01", "007", "00", "1.", "0.", "-1.", "0x10", "0xFF", "-0x1a"]),
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
)

_hex = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_unicode_escape = st.one_of(
    _hex.map(lambda h: "\\u" + h),
    st.sampled_from([
        "\\ud800", "\\udfff", "\\ud83d\\ude00", "\\u0000",
        "\\uD834\\uDD1E", "\\uFFFF", "\\u00e9", "\\u2603",
    ]),
)

_simple_escape = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_raw_control = st.integers(min_value=0, max_value=0x1F).map(chr)

_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

_string_body_piece = st.one_of(
    _safe_char,
    _simple_escape,
    _unicode_escape,
    _raw_control,
    st.sampled_from(["\x00", "\x1f", "\x7f", "\ufeff"]),
)

_string_body = st.lists(_string_body_piece, max_size=12).map("".join)

_quoted_string = _string_body.map(lambda s: '"' + s + '"')

_malformed_string = st.one_of(
    _string_body.map(lambda s: '"' + s),
    _string_body.map(lambda s: '"' + s + "'"),
    st.sampled_from(['"\\x"', '"\\u12"', '"\\uZZZZ"', '"', "'abc'"]),
)

# ---------- recursive value strategy ----------

_leaf = st.one_of(
    _quoted_string,
    _malformed_string,
    _num_str,
    st.sampled_from(["true", "false", "null", "NaN", "Infinity", "-Infinity"]),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

def _pair(value):
    key = st.one_of(_quoted_string, _string_body.map(lambda s: '"' + s + '"'))
    colon = st.sampled_from([":", ":", " :", ": ", " : "])
    return st.tuples(key, colon, value).map(lambda t: t[0] + t[1] + t[2])

def _bad_pair(value):
    return st.one_of(
        st.tuples(_quoted_string, value).map(lambda t: t[0] + t[1]),
        st.tuples(_quoted_string, value).map(lambda t: t[0] + "::" + t[1]),
        value.map(lambda v: ": " + v),
    )

def _obj(value):
    inner = st.one_of(
        st.lists(_pair(value), min_size=0, max_size=4).map(
            lambda ps: ",".join(ps)
        ),
        st.tuples(_pair(value), _pair(value)).map(lambda t: t[0] + "," + t[1]),
    )
    bracketed = st.tuples(
        st.just("{"), _ws, inner, _ws, st.just("}")
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])
    malformed = st.one_of(
        st.tuples(st.just("{"), inner).map(lambda t: t[0] + t[1]),
        st.tuples(st.just("{"), inner, st.just(",}")).map(lambda t: t[0] + t[1] + t[2]),
        st.just("{}"),
        st.just("{,}"),
        st.just("{:}"),
    )
    return st.one_of(bracketed, malformed)

def _arr(value):
    inner = st.lists(value, min_size=0, max_size=4).map(
        lambda vs: ",".join(vs)
    )
    bracketed = st.tuples(
        st.just("["), _ws, inner, _ws, st.just("]")
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])
    malformed = st.one_of(
        st.tuples(st.just("["), inner).map(lambda t: t[0] + t[1]),
        st.tuples(st.just("["), inner, st.just(",]")).map(lambda t: t[0] + t[1] + t[2]),
        st.just("[]"),
        st.just("[,]"),
        st.just("[1,]"),
        st.just("[1,,2]"),
    )
    return st.one_of(bracketed, malformed)

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=20,
)

# ---------- depth-focused strategies near the 1000 limit ----------

def _deep_array(depth):
    return "[" * depth + "0" + "]" * depth

def _deep_object(depth):
    return '{"a":' * depth + "0" + "}" * depth

_depth_strategy = st.one_of(
    st.integers(min_value=990, max_value=1010),
    st.integers(min_value=0, max_value=50),
    st.sampled_from([500, 999, 1000, 1001, 1002]),
)

_deep = st.one_of(
    _depth_strategy.map(_deep_array),
    _depth_strategy.map(_deep_object),
)

# ---------- malformed / near-valid inputs ----------

_malformed = st.one_of(
    st.sampled_from([
        "", " ", "\n", "\t",
        "-", "+1", ".5", "-.5", "+.5",
        "01", "1.", "0x10",
        "NaN", "Infinity", "-Infinity",
        "[1,]", "[,]", "{,}", "{:}", "{'a':1}",
        "{a:1}", "['a']", "'abc'",
        '"\\ud800"', '"\\udfff"', '"\\u12"', '"\\uZZZZ"',
        '"\\x"', '"unterminated', '"',
        "[", "]", "{", "}", "[1", "{1", "{\"a\"", "{\"a\":",
        "tru", "fals", "nul", "truex", "falsey", "nullz",
        "\ufeff", "\ufeff1", "\ufeff{}",
        "\x00", "\x001", "1\x00", "\x00\x00",
    ]),
    st.tuples(_value, st.sampled_from(["abc", " 1 2", "\x00", "xyz", "{}[]"])).map(
        lambda t: t[0] + t[1]
    ),
    st.just('{"a":1,,"b":2}'),
    st.just('{"a" 1}'),
    st.just('{"a":1 "b":2}'),
    st.just("[1,,2]"),
    st.just('{"a":1,}'),
)

# ---------- top-level combination ----------

_valid_doc = st.one_of(
    st.tuples(_value, _ws).map(lambda t: t[0] + t[1]),
    _value,
)

_boundary_inject = st.tuples(
    st.sampled_from(["\x00", "\ufeff", "\x1f", "\x7f", "\\ud800", "\\udfff"]),
    st.sampled_from(["", " ", "[" , "{", "]", "}", ",", ":", "0", '"a"']),
    _value,
    st.sampled_from(["", " ", "[", "{", "]", "}", ",", ":", "0", '"a"']),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# IMPROVEMENT: broaden the depth-focused strategy so it also produces
# *hybrid* deep documents that interleave arrays and objects, and inject
# trailing garbage / missing closers at the deep boundary. Pure repeated
# "["*N or '{"a":'*N only tests one nesting shape; mixing the two bracket
# kinds and truncating the closing tail exercises the parser's depth counter
# across both container types and the error path at the exact limit.
def _deep_mixed(depth):
    return "".join(
        "[" if i % 2 == 0 else '{"a":' for i in range(depth)
    ) + "0" + "".join(
        "]" if i % 2 == 0 else "}" for i in reversed(range(depth))
    )

_deep_hybrid = st.one_of(
    _depth_strategy.map(_deep_mixed),
    st.tuples(_depth_strategy, st.sampled_from(["", ",", "\x00", "1"])).map(
        lambda t: _deep_array(t[0]) + t[1]
    ),
    st.tuples(_depth_strategy, st.sampled_from([1, 2, 3])).map(
        lambda t: _deep_object(t[0])[:-t[1]]
    ),
)

strategy = st.one_of(
    _valid_doc,
    _valid_doc,
    _valid_doc,
    _valid_doc,
    _valid_doc,
    _deep,
    _deep_hybrid,
    _malformed,
    _value.map(lambda v: "\ufeff" + v),
    _value.map(lambda v: v[: len(v) // 2] + "\x00" + v[len(v) // 2:]),
    _boundary_inject,
)
```