```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _unicode_escape():
    return st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map("".join)

def _simple_escape():
    return st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _escape():
    return st.one_of(_simple_escape(), _unicode_escape())

# control / NUL bytes and other raw codepoints allowed inside strings
def _raw_char():
    return st.one_of(
        st.characters(min_codepoint=0, max_codepoint=0x1F),  # control + NUL
        st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF).filter(
            lambda c: c not in '"\\'
        ),
    )

def _string_body_piece():
    return st.one_of(_escape(), _raw_char())

def _string_body():
    return st.lists(_string_body_piece(), max_size=8).map("".join)

def json_string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.integers(min_value=1, max_value=9).map(str),
    )

def _frac_part():
    return st.tuples(st.just("."), st.integers(min_value=0, max_value=10**9).map(str)).map("".join)

def _exp_part():
    return st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=10**5).map(str),
    ).map("".join)

def json_number():
    sign = st.sampled_from(["", "-"])
    base = st.tuples(sign, _int_part()).map("".join)
    frac = st.one_of(st.just(""), _frac_part())
    exp = st.one_of(st.just(""), _exp_part())
    normal = st.tuples(base, frac, exp).map("".join)

    # extremes / overflow / non-finite
    extreme = st.sampled_from(
        [
            "1e309", "-1e309", "1e308", "-1e308", "1e999999", "-1e999999",
            "1E309", "1e+309", "1e-309", "1e-999999",
            "0e0", "-0", "-0.0", "0.0", "1e0", "1E0",
            "123456789012345678901234567890",
            "1.7976931348623157e308", "1.7976931348623159e308",
            "5e-324", "2.2250738585072014e-308",
            "9" * 40, "1" + "0" * 30 + "e" + "9" * 10,
        ]
    )
    # parser-accepted lone '-'
    lone = st.just("-")
    return st.one_of(normal, extreme, lone)

# ---------- malformed near-valid fragments ----------

malformed_number = st.sampled_from(
    ["+1", ".5", "1.", "01", "0x1F", "1e", "1e+", "--1", "+", ".", "1..2", "1e1.2"]
)

unterminated_string = st.sampled_from(
    ['"abc', '"', '"\\', '"\\u12', '"\\uZZZZ', '"abc\\"', '"line\nbreak']
)

# ---------- recursive structure ----------

json_value = st.deferred(lambda: _value)

def _value():
    return st.one_of(
        json_string(),
        json_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        json_obj(),
        json_arr(),
        # malformed near-valid leaves
        malformed_number,
        unterminated_string,
    )

def _pair():
    return st.tuples(json_string(), st.just(":"), json_value).map("".join)

# malformed pairs (missing colon, double colon, etc.)
def _bad_pair():
    return st.one_of(
        st.tuples(json_string(), json_value).map("".join),          # missing colon
        st.tuples(json_string(), st.just("::"), json_value).map("".join),
        st.tuples(json_string(), st.just(":"), st.just(","), json_value).map("".join),
        st.tuples(json_string(), st.just(":"), json_value, json_value).map("".join),
    )

def _obj_members():
    return st.lists(
        st.one_of(_pair(), _bad_pair()),
        min_size=1,
        max_size=6,
    )

def _obj_body():
    members = _obj_members()
    # build: "{" + ",".join(members) + optional trailing comma + "}"
    def build(ms):
        inner = ",".join(ms)
        trailing = st.booleans()
        return inner, trailing
    return st.tuples(members, st.booleans()).map(
        lambda mt: "{" + ",".join(mt[0]) + ("," if mt[1] else "") + "}"
    )

def _arr_values():
    return st.lists(json_value, min_size=1, max_size=6)

def _arr_body():
    return st.tuples(_arr_values(), st.booleans()).map(
        lambda vt: "[" + ",".join(vt[0]) + ("," if vt[1] else "") + "]"
    )

def json_obj():
    return st.one_of(
        st.just("{}"),
        st.just("{,}"),
        st.just("{:}"),
        st.just('{"a"}'),
        st.just('{"a":}'),
        _obj_body(),
    )

def json_arr():
    return st.one_of(
        st.just("[]"),
        st.just("[,]"),
        st.just("[1,,2]"),
        st.just("[,1]"),
        _arr_body(),
    )

# ---------- deep nesting ----------

def _deep_obj_chain():
    # nested objects to stress first-pass memory measurement
    return st.integers(min_value=1, max_value=2000).map(
        lambda n: "{" + '"k":' * n + "0" + "}" * n
    )

def _deep_arr_chain():
    return st.integers(min_value=1, max_value=5000).map(
        lambda n: "[" * n + "0" + "]" * n
    )

def _deep_mixed_chain():
    def build(n):
        parts = []
        for i in range(n):
            parts.append("{" + '"a":' if i % 2 == 0 else "[")
        parts.append("null")
        for i in reversed(range(n)):
            parts.append("}" if i % 2 == 0 else "]")
        return "".join(parts)
    return st.integers(min_value=1, max_value=1000).map(build)

deep_nesting = st.one_of(_deep_obj_chain(), _deep_arr_chain(), _deep_mixed_chain())

# ---------- top-level value with optional trailing garbage / whitespace ----------

def _ws():
    return st.lists(st.sampled_from([" ", "\t", "\n", "\r"]), max_size=4).map("".join)

trailing_garbage = st.sampled_from(
    ["1abc", "[]xyz", "1 garbage", "true false", "nullnull", "{} {}", "]\x00", "1\x00"]
)

# ---------- recursive strategy assembly ----------

# Use st.recursive for obj/arr/value so the structure is genuinely recursive.
# Base cases: primitives + malformed leaves. Recursive: obj/arr built from value.
base = st.one_of(
    json_string(),
    json_number(),
    st.just("true"),
    st.just("false"),
    st.just("null"),
    malformed_number,
    unterminated_string,
    st.just("{}"),
    st.just("[]"),
    st.just("{,}"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    deep_nesting,
    trailing_garbage,
)

def _extend(children):
    # children is a strategy producing json value strings
    def make_obj(v):
        # object with members (biased)
        def build(ms):
            return "{" + ",".join(ms) + "}"
        return st.lists(
            st.tuples(json_string(), st.just(":"), v).map("".join),
            min_size=1,
            max_size=5,
        ).map(build)

    def make_arr(v):
        return st.lists(v, min_size=1, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]")

    return st.one_of(make_obj(children), make_arr(children))

recursive_value = st.recursive(base, _extend, max_leaves=30)

# ---------- bias toward valid JSON ----------

def _valid_value():
    return st.one_of(
        json_string(),
        json_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
        _valid_obj(),
        _valid_arr(),
    )

def _valid_obj():
    return st.lists(
        st.tuples(json_string(), st.just(":"), _valid_value()).map("".join),
        min_size=0,
        max_size=6,
    ).map(lambda ms: "{" + ",".join(ms) + "}")

def _valid_arr():
    return st.lists(
        _valid_value(),
        min_size=0,
        max_size=6,
    ).map(lambda xs: "[" + ",".join(xs) + "]")

valid_value = st.recursive(
    st.one_of(
        json_string(),
        json_number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    ),
    lambda children: st.one_of(
        st.lists(
            st.tuples(json_string(), st.just(":"), children).map("".join),
            min_size=0,
            max_size=5,
        ).map(lambda ms: "{" + ",".join(ms) + "}"),
        st.lists(children, min_size=0, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]"),
    ),
    max_leaves=30,
)

def _top_level(v):
    return st.one_of(
        # mostly valid JSON
        valid_value,
        st.tuples(_ws(), valid_value, _ws()).map("".join),
        # occasional malformed / edge cases
        v,
        st.lists(
            st.tuples(json_string(), st.just(":"), v).map("".join),
            min_size=1,
            max_size=6,
        ).map(lambda ms: "{" + ",".join(ms) + "}"),
        st.tuples(v, trailing_garbage).map("".join),
    )

strategy = _top_level(recursive_value)
```