Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- basic lexical pieces ----------

# SAFECODEPOINT: printable-ish chars excluding " and \ and control chars.
# We deliberately include some control chars via escapes below, not raw.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # no surrogates as raw chars
    blacklist_characters='"\\\x00',
    min_codepoint=0x20,
    max_codepoint=0x10FFFF,
)

# Control characters that must be escaped inside strings
_control_chars = st.integers(min_value=0x01, max_value=0x1F).map(chr)

# Escapes: \" \\ \/ \b \f \n \r \t plus \uXXXX
_simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.lists(_hex, min_size=4, max_size=4).map(lambda xs: "".join(xs))

_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes (lone and paired), plus \u0000 (NUL escape, six chars, safe)
_surrogate_escape = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD800\\uDC00",  # valid pair
    "\\uDBFF\\uDFFF",  # valid pair
    "\\uD800\\uD800",  # malformed pair
    "\\uDC00",         # lone low surrogate
    "\\u0000",         # NUL escape (allowed, six chars)
])

_escape = st.one_of(_simple_escapes, _unicode_escape, _surrogate_escape)

# A string body element is either a safe char or an escape
_string_body_element = st.one_of(
    _safe_chars.map(str),
    _escape,
)

# ---------- strings ----------

def _make_string(body):
    return '"' + "".join(body) + '"'

_string_body = st.lists(_string_body_element, min_size=0, max_size=12).map("".join)
_string = _string_body.map(_make_string)

# Unterminated string (malformed)
_unterminated_string = _string_body.map(lambda b: '"' + b)

# ---------- numbers ----------

# Valid integer part (no leading zeros)
_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.tuples(
        st.integers(min_value=1, max_value=9).map(str),
        st.lists(st.integers(min_value=0, max_value=9).map(str), min_size=1, max_size=10).map("".join),
    ).map(lambda t: t[0] + t[1]),
)

# Extreme magnitudes / exponents
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

# Malformed numbers (leading +, lone .5, leading zeros, lone -, trailing dot)
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

# We build recursive structures using st.recursive.
# Leaf values: string, number, literal, plus malformed variants.

_leaf = st.one_of(
    _string,
    _number,
    _literal,
    _malformed_number,
    _unterminated_string,
)

def _value_strategy(children):
    return st.one_of(_leaf, children)

# Build a recursive strategy:
# obj is a list of pairs joined; arr is a list of values joined.
# Depth control: st.recursive with max_leaves and a depth parameter via recursion.

# To concentrate around depth ~2048 we allow a "depth budget" mechanism.
# We generate a recursive JSON-ish tree with a depth limit, then also
# provide a separate deep-nesting strategy for arrays/objects near 2048.

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

# recursive strategy: children is a strategy producing either obj or arr strings
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

# Generate arrays nested to a depth near 2048.
# We use flatmap on an integer depth to build the string.
_deep_array = st.integers(min_value=1900, max_value=2100).map(
    lambda d: "[" * d + "]" * d
)

_deep_object = st.integers(min_value=1900, max_value=2100).map(
    lambda d: "{" + '"k":' * d + "null" + "}" * d
)

# Mixed deep nesting: alternate [ and { with a leaf
_deep_mixed = st.integers(min_value=1900, max_value=2100).flatmap(
    lambda d: st.integers(min_value=0, max_value=d).map(
        lambda k: "[" * k + "{" + '"a":' * (d - k) + "0" + "}" * (d - k) + "]" * k
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

# Near-valid-but-malformed
_malformed = st.sampled_from([
    # double commas
    "[1,,2]", "[,1]", "[1,]", "{\"a\":1,,}",
    # missing colons
    '{"a" 1}', '{"a"}', '{"a":}', '{:1}',
    # unterminated
    '"abc', '[1,2', '{"a":1', '{"a"',
    # trailing commas
    "[1,2,]", '{"a":1,}',
    # bad literals
    "tru", "fals", "nul", "True", "NULL",
    # empty / whitespace
    "", " ", "\n", "\t",
    # trailing content (accepted by the parser)
    "1abc", "1 garbage", "[]xyz", "{}extra", "null trailing",
    # lone sign (accepted -> 0)
    "-", "-.",
    # leading plus / dot
    "+1", ".5", "1.",
    # leading zeros
    "01", "-01",
])

# Trailing content after a complete value
_trailing = st.tuples(
    _recursive_value,
    st.sampled_from(["abc", " garbage", "xyz", " 123", "null", "[]", "{}", "/*c*/", "\n\n"]),
).map(lambda t: t[0] + t[1])

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
    # bare numbers and strings at top level
    _number,
    _string,
    _literal,
    _malformed_number,
)
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.