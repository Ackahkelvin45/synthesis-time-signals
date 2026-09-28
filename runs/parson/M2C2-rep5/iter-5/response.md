```python
from hypothesis import strategies as st
import json

# Safe characters for JSON string content (exclude double-quote and backslash;
# exclude U+0000 to avoid raw NUL in generated str)
_safe_char = st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF, blacklist_characters=['"', '\\'])

# Common escape sequences and deliberate \uXXXX sequences including surrogate escapes
_escape_literals = [
    r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
    r'\u0000',  # six-character escape for NUL (allowed)
    r'\u0001', r'\u000A',
    r'\uD800', r'\uDFFF', r'\uDBFF\uDFFF'  # surrogate halves and a surrogate pair
]
_escape_strategy = st.sampled_from(_escape_literals)

# Construct JSON string literal (valid) by concatenating safe chunks and escapes
_string_chunk = st.one_of(
    st.text(_safe_char, min_size=0, max_size=8),
    _escape_strategy
)
_valid_string = st.lists(_string_chunk, min_size=0, max_size=6).map(''.join).map(lambda s: '"' + s + '"')

# Unterminated string: deliberately missing the closing quote
_unterminated_string = _valid_string.map(lambda s: s[:-1])

# Key strings for objects: use valid strings only (unterminated keys would violate grammar)
_key_string = _valid_string

# Number generators: valid and many near-valid/malformed variants
def _int_no_leading_zero():
    # 0 or non-zero leading integer
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**6).map(str)
    )

_valid_number = st.one_of(
    # integers (valid)
    _int_no_leading_zero().map(lambda s: s),
    # negative integers
    _int_no_leading_zero().map(lambda s: "-" + s),
    # fractional numbers (valid)
    st.tuples(_int_no_leading_zero(), st.integers(min_value=0, max_value=10**6).map(str)).map(lambda t: t[0] + "." + (t[1] or "0")),
    # with exponents (valid)
    st.tuples(_int_no_leading_zero(), st.integers(min_value=-308, max_value=308).map(str)).map(lambda t: t[0] + "e" + t[1]),
)

# Malformed or edge-case numbers (near-valid): leading +, .5, 1., 01, extreme exponents (overflow), lone -, plus huge exponents
_number_malformed_literals = [
    "01",       # leading zero
    "+1",       # leading plus (near-valid)
    ".5",       # missing leading 0
    "1.",       # trailing dot
    "-",        # lone sign (parser accepts as 0)
    "-.",       # weird lone minus/dot
    "1e309",    # overflow to INF (parser rejects on numeric overflow)
    "-1E400",
    "1e9999",
    "9e99999",
    "1e+309",
]
_number_malformed = st.sampled_from(_number_malformed_literals)

# Booleans and null
_literal_true = st.just("true")
_literal_false = st.just("false")
_literal_null = st.just("null")

# Base (non-container) values: include valid and malformed strings/numbers and literals
_base_value = st.one_of(
    _valid_string,
    _unterminated_string,  # unterminated string (malformed)
    _valid_number,
    _number_malformed,
    _literal_true,
    _literal_false,
    _literal_null
)

# Recursive construction for objects and arrays using st.recursive
def _extend(children):
    # Normal object with 0..4 pairs (valid)
    obj_pairs = st.lists(st.tuples(_key_string, children), min_size=0, max_size=4).map(
        lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs) + "}"
    )

    # Object with duplicate keys (deliberate edge case). Use same key repeated.
    obj_dup = st.tuples(_key_string, children, children).map(
        lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
    )

    # Object missing colon (malformed)
    obj_missing_colon = st.lists(st.tuples(_key_string, children), min_size=1, max_size=3).map(
        lambda pairs: "{" + ",".join(k + " " + v for (k, v) in pairs) + "}"
    )

    # Object with trailing comma
    obj_trailing_comma = st.lists(st.tuples(_key_string, children), min_size=1, max_size=3).map(
        lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs) + ",}"
    )

    # Object with double commas (e.g., {"a":1,, "b":2})
    obj_double_commas = st.lists(st.tuples(_key_string, children), min_size=2, max_size=3).map(
        lambda pairs: "{" + ",".join(k + ":" + v for (k, v) in pairs[:1]) + ",," + ",".join(k + ":" + v for (k, v) in pairs[1:]) + "}"
    )

    # Empty object
    obj_empty = st.just("{}")

    # Normal array 0..4 values
    arr_normal = st.lists(children, min_size=0, max_size=4).map(lambda vals: "[" + ",".join(vals) + "]")

    # Array with trailing comma
    arr_trailing_comma = st.lists(children, min_size=1, max_size=4).map(lambda vals: "[" + ",".join(vals) + ",]")

    # Array with double commas: [v1,,v2]
    arr_double_commas = st.lists(children, min_size=2, max_size=4).map(
        lambda vals: "[" + ",".join(vals[:1]) + ",," + ",".join(vals[1:]) + "]"
    )

    # Empty array
    arr_empty = st.just("[]")

    # Deep nesting near parser cap: create arrays or objects nested to large depths <= 2048
    # Choose depths biased: small depths common, but include near-cap depths (2000..2048) occasionally
    depth_choice = st.one_of(
        st.integers(min_value=1, max_value=6),  # shallow
        st.sampled_from([2000, 2010, 2030, 2040, 2046, 2047, 2048])  # near the cap
    )
    # Build a deep nested array: "[" * n + child + "]" * n
    deep_array = st.tuples(depth_choice, children).map(lambda t: ("[" * t[0]) + t[1] + ("]" * t[0]))
    # Build a deep nested object: "{" * n + key:child + "}" * n  (use array-like braces repeated)
    deep_object = st.tuples(depth_choice, _key_string, children).map(lambda t: ("{" * t[0]) + t[1] + ":" + t[2] + ("}" * t[0]))

    return st.one_of(
        obj_empty,
        obj_pairs,
        obj_dup,
        obj_missing_colon,
        obj_trailing_comma,
        obj_double_commas,
        arr_empty,
        arr_normal,
        arr_trailing_comma,
        arr_double_commas,
        deep_array,
        deep_object
    )

# Use recursion to build nested obj/arr productions
_value_strategy = st.recursive(_base_value, _extend, max_leaves=10000)

# Allow trailing content after a complete value (the parser accepts trailing content)
_trailing = st.sampled_from(["", " ", "  garbage", "XYZ", "\ntrailing", "123abc"])
_with_trailing = st.tuples(_value_strategy, _trailing).map(lambda t: t[0] + t[1])

# Final top-level strategy: sometimes raw value, sometimes value with trailing garbage
# Added explicit upweighting/include of NUMBER production (_valid_number) to increase NUMBER examples.
strategy = st.one_of(_value_strategy, _with_trailing, _valid_number, _literal_true, _literal_false, _literal_null)
```