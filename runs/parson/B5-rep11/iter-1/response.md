```python
from hypothesis import strategies as st
import json

# ---------- leaf fragments ----------

_safe_chars = st.characters(
    whitelist_categories=("Lu", "Ll", "Lt", "Lm", "Lo", "Nd", "Nl", "No",
                          "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po", "Sm", "Sc", "Sk", "So"),
    blacklist_characters='"\\\x00',
)

_simple_string_body = st.text(alphabet=_safe_chars, min_size=0, max_size=12)

_escapes = st.sampled_from([
    '\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
])

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_unicode_escape = _hex4.map(lambda h: "\\u" + h)

_surrogate_escape = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD834\\uDD1E", "\\uD83D\\uDE00",
    "\\uD800\\uD800", "\\uDC00\\uDC00",
])

_control_via_escape = st.sampled_from([
    "\\u0000", "\\u0001", "\\u001f", "\\u007f", "\\u0009",
])

_string_piece = st.one_of(
    _simple_string_body,
    _escapes,
    _unicode_escape,
    _surrogate_escape,
    _control_via_escape,
)

_string_body = st.lists(_string_piece, min_size=0, max_size=6).map("".join)

_string = _string_body.map(lambda b: '"' + b + '"')

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=10, max_value=10**18).map(str),
    st.integers(min_value=-10**18, max_value=-1).map(str),
)

_frac_part = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
    st.just(".0"),
)

_exp_part = st.one_of(
    st.just(""),
    st.sampled_from(["e0", "e1", "e-1", "e+1", "E0", "E10", "e01", "e-01",
                     "e308", "e309", "e-309", "e999", "E999", "e-999",
                     "e+308", "e+309", "e2147483647", "e-2147483648"]),
)

_number = st.builds(
    lambda s, i, f, e: s + i + f + e,
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    _frac_part,
    _exp_part,
)

# ---------- malformed / near-valid leaf tokens ----------

_malformed_number = st.sampled_from([
    "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "-01", "00", "0.5.5",
    "1e", "1e+", "1e-", "--1", "1..2", "1e++2", "NaN", "Infinity",
    "-Infinity", "0x10", "1_000",
])

_malformed_string = st.sampled_from([
    '"', '"abc', '"abc\\', '"\\', '"\\u12', '"\\uZZZZ"', '"\\x41"',
    '"a"b"', '"\\uD800"', '""extra"',
])

# ---------- recursive value ----------

_json_value = st.recursive(
    st.one_of(
        _string,
        _number,
        st.sampled_from(["true", "false", "null"]),
        _malformed_number,
        _malformed_string,
    ),
    lambda children: st.one_of(
        _make_obj(children),
        _make_arr(children),
    ),
    max_leaves=40,
)


def _make_obj(children):
    def build(pairs):
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    def pair(value):
        return _string.map(lambda s: s + ":" + value)

    pair_strategy = children.flatmap(pair)
    return st.lists(pair_strategy, min_size=0, max_size=5).map(build)


def _make_arr(children):
    def build(items):
        if not items:
            return "[]"
        return "[" + ",".join(items) + "]"

    return st.lists(children, min_size=0, max_size=5).map(build)


# ---------- deep nesting near 2048 ----------

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=2048)
    kind = st.sampled_from(["arr", "obj"])

    def build(args):
        d, k = args
        if k == "arr":
            return "[" * d + "]" * d
        inner = "{}"
        return "{" + '"k":' * d + inner + "}" * d

    return st.tuples(depth, kind).map(build)


_deep = _deep_nesting()

# ---------- structural edge cases ----------

_edge_cases = st.sampled_from([
    "{}", "[]", '{"a":1,"a":2}', '{"k":0,"k":1}',
    '{"a":1,}', "[1,]", "[,]", "[1,,2]", '{"a"}', '{"a":}', '{:1}',
    "1abc", "1 garbage", "[]xyz", "{}trailing", "truefalse", "nullnull",
    "1e309", "-1e309", "1e-999", '"\u0000"', '"\\u0000"',
    "[\r\n\t ]", '{"":1}', '{"a":"b","c":[true,false,null]}',
    '"\\uD800"', '"\\uDFFF"', '"\\uD834\\uDD1E"',
])

# ---------- top-level combination ----------

_value_with_trailing = st.one_of(
    _json_value,
    _json_value.flatmap(lambda v: st.sampled_from(["", " ", "x", "\n", "0"]).map(lambda t: v + t)),
)

strategy = st.one_of(
    _edge_cases,
    _deep,
    _value_with_trailing,
    st.lists(_string_piece, min_size=0, max_size=4).map(lambda p: '"' + "".join(p) + '"'),
)
```