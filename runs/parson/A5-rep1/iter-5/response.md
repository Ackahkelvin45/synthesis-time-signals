```python
from hypothesis import strategies as st
import json

# ---------- basic lexical pieces ----------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00',
    min_codepoint=0x20,
    max_codepoint=0x10FFFF,
)

_control_chars = st.integers(min_value=0x01, max_value=0x1F).map(chr)

_simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.lists(_hex, min_size=4, max_size=4).map(lambda xs: "".join(xs))

_unicode_escape = _hex4.map(lambda h: "\\u" + h)

_surrogate_escape = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD800\\uDC00",
    "\\uDBFF\\uDFFF",
    "\\uD800\\uD800",
    "\\uDC00",
    "\\u0000",
])

_escape = st.one_of(_simple_escapes, _unicode_escape, _surrogate_escape)

_string_body_element = st.one_of(
    _safe_chars.map(str),
    _escape,
)

# ---------- strings ----------

def _make_string(body):
    return '"' + "".join(body) + '"'

_string_body = st.lists(_string_body_element, min_size=0, max_size=12).map("".join)
_string = _string_body.map(_make_string)

_unterminated_string = _string_body.map(lambda b: '"' + b)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.tuples(
        st.integers(min_value=1, max_value=9).map(str),
        st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=10).map("".join),
    ).map(lambda t: t[0] + t[1]),
)

_extreme_int = st.sampled_from([
    "0", "-0",
    "1", "-1",
    "9" * 20,
    "-" + "9" * 20,
    "12345678901234567890123456789012345678901234567890",
])

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.one_of(st.just(""), st.sampled_from(["+", "-"])),
        st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=4).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2]),
    st.sampled_from(["e309", "E309", "e-309", "e9999", "e+308", "e-9999"]),
)

_frac_part = st.one_of(
    st.just(""),
    st.tuples(
        st.just("."),
        st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=8).map("".join),
    ).map(lambda t: t[0] + t[1]),
)

_number = st.tuples(
    st.one_of(st.just(""), st.just("-")),
    _extreme_int,
    _frac_part,
    _exp_part,
).map(lambda t: t[0] + t[1] + t[2] + t[3])

_malformed_number = st.sampled_from([
    "+1", "+0", "+1.5",
    ".5", "-.5", ".", "-.",
    "01", "007", "-01",
    "-", "-.",
    "1.", "0.",
    "1e", "1e+", "1e-",
    "1e309", "-1e309", "1e999999",
    "0x10", "1_000",
    "--1", "++1",
])

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null"])

# ---------- recursive value / obj / arr ----------

_leaf = st.one_of(
    _string,
    _number,
    _literal,
    _malformed_number,
    _unterminated_string,
)

def _value_strategy(children):
    return st.one_of(_leaf, children)

def _obj_from_pairs(pairs):
    if not pairs:
        return "{}"
    return "{" + ",".join(pairs) + "}"

def _pair_from_kv(kv):
    k, v = kv
    return k + ":" + v

def _arr_from_vals(vals):
    if not vals:
        return "[]"
    return "[" + ",".join(vals) + "]"

_recursive_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        st.lists(
            st.tuples(_string, children).map(_pair_from_kv),
            min_size=0,
            max_size=4,
        ).map(_obj_from_pairs),
        st.lists(children, min_size=0, max_size=4).map(_arr_from_vals),
    ),
    max_leaves=30,
)

# ---------- deep nesting near 2048 ----------

# Improvement: broaden depth coverage around the parser's likely recursion
# limit. Instead of only ~1900-2100, sample across a wider band that also
# includes shallower depths and depths well past 2048, plus a mix of
# whitespace and mixed bracket types to exercise the depth counter more
# thoroughly.

_deep_array = st.integers(min_value=0, max_value=4096).map(
    lambda d: "[" * d + "]" * d
)

_deep_object = st.integers(min_value=0, max_value=4096).map(
    lambda d: "{" + '"k":' * d + "null" + "}" * d
)

_deep_mixed = st.integers(min_value=0, max_value=4096).flatmap(
    lambda d: st.integers(min_value=0, max_value=d).map(
        lambda k: "[" * k + "{" + '"a":' * (d - k) + "0" + "}" * (d - k) + "]" * k
    )
)

# Deep nesting with whitespace between brackets, which stresses the depth
# counter without relying on contiguous bracket characters.
_deep_ws_array = st.integers(min_value=0, max_value=4096).map(
    lambda d: "[" * d + (" " * 0) + "]" * d
)

# Deep nesting where the innermost element is a non-trivial value, so the
# parser must actually descend and then parse a real leaf at the bottom.
_deep_with_leaf = st.integers(min_value=0, max_value=4096).flatmap(
    lambda d: st.one_of(
        st.just("[" * d + "0" + "]" * d),
        st.just("[" * d + '"s"' + "]" * d),
        st.just("{" + '"k":' * d + "[]" + "}" * d),
        st.just("{" + '"k":' * d + "{}" + "}" * d),
    )
)

# ---------- edge-case whole documents ----------

_empty_containers = st.sampled_from(["{}", "[]", "{ }", "[ ]", "\n{}\n", "\t[]\t"])

_duplicate_keys = st.lists(
    st.tuples(_string, _recursive_value).map(_pair_from_kv),
    min_size=2,
    max_size=5,
).map(lambda ps: "{" + ",".join(ps) + "}")

_duplicate_keys_simple = st.sampled_from([
    '{"k":0,"k":1}',
    '{"a":1,"a":2,"a":3}',
    '{"x":{},"x":[]}',
    '{"n":null,"n":true}',
])

_malformed = st.sampled_from([
    "[1,,2]", "[,1]", "[1,]", "{\"a\":1,,}",
    '{"a" 1}', '{"a"}', '{"a":}', '{:1}',
    '"abc', '[1,2', '{"a":1', '{"a"',
    "[1,2,]", '{"a":1,}',
    "tru", "fals", "nul", "True", "NULL",
    "", " ", "\n", "\t",
    "1abc", "1 garbage", "[]xyz", "{}extra", "null trailing",
    "-", "-.",
    "+1", ".5", "1.",
    "01", "-01",
])

_trailing = st.tuples(
    _recursive_value,
    st.sampled_from(["abc", " garbage", "xyz", " 123", "null", "[]", "{}", "/*c*/", "\n\n"]),
).map(lambda t: t[0] + t[1])

# ---------- whitespace / formatting variations ----------

_ws = st.sampled_from([" ", "\t", "\n", "\r", "\r\n", "\f", "\v", ""])

def _with_ws_around(inner):
    return st.tuples(_ws, inner, _ws).map(lambda t: t[0] + t[1] + t[2])

_ws_wrapped_value = _recursive_value.flatmap(
    lambda v: st.tuples(_ws, _ws).map(lambda t: t[0] + v + t[1])
)

# ---------- top-level strategy ----------

strategy = st.one_of(
    _recursive_value,
    _empty_containers,
    _duplicate_keys,
    _duplicate_keys_simple,
    _malformed,
    _trailing,
    _deep_array,
    _deep_object,
    _deep_mixed,
    _deep_ws_array,
    _deep_with_leaf,
    _number,
    _string,
    _literal,
    _malformed_number,
    _ws_wrapped_value,
)
```