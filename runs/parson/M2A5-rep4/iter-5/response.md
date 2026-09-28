```python
from hypothesis import strategies as st
import json

# Helper pieces for strings and escapes (never emit a raw NUL char)
_safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-+*/%#<>[]=;:.,&|^~()\\\"\t\n\r"
_hex4 = "0123456789abcdefABCDEF"

raw_piece = st.text(alphabet=_safe_chars, min_size=0, max_size=6)
hex4 = st.text(alphabet=_hex4, min_size=4, max_size=4)
unicode_escape = hex4.map(lambda h: "\\u" + h)
surrogate_escape = st.sampled_from(["\\uD800", "\\uDFFF", "\\uDBFF", "\\uDC00"])
esc_basic = st.sampled_from(['\\\\', '\\"', '\\b', '\\f', '\\n', '\\r', '\\t'])
escape_seq = st.one_of(esc_basic, unicode_escape, surrogate_escape)

string_segment = st.one_of(raw_piece, escape_seq)
# Typical valid quoted string
string_token = st.lists(string_segment, min_size=0, max_size=5).map("".join).map(lambda s: '"' + s + '"")
# Explicitly include a \u0000 escape variant (six-character escape)
string_token = st.one_of(string_token, st.just('"\\u0000"'))
# Unterminated/malformed string (missing closing quote)
unterminated_string = st.lists(string_segment, min_size=1, max_size=6).map("".join).map(lambda s: '"' + s)

# Number construction: valid numbers and a set of malformed/edge numbers
int_part = st.one_of(st.just("0"), st.integers(min_value=1, max_value=10 ** 6).map(str))
frac_part = st.one_of(st.just(""), st.builds(lambda f: "." + f, st.text(alphabet="0123456789", min_size=1, max_size=6)))
exp_part = st.one_of(st.just(""), st.builds(lambda e, s, d: e + s + d,
                                             st.sampled_from(["e", "E"]),
                                             st.sampled_from(["", "+", "-"]),
                                             st.text(alphabet="0123456789", min_size=1, max_size=4)))
number_valid = st.tuples(st.sampled_from(["", "-"]), int_part, frac_part, exp_part).map(lambda t: t[0] + t[1] + t[2] + t[3])

# Malformed / interesting numeric cases (leading +, .5, 1., 01, extreme exponents/overflow, lone sign)
number_malformed = st.sampled_from([
    "+1", ".5", "1.", "01", "1e309", "1e9999", "-", "-.", "+", "0000", "00.1"
])
number_strategy = st.one_of(number_valid, number_malformed)

literals = st.sampled_from(["true", "false", "null"])
empty_structs = st.sampled_from(["{}", "[]"])

# Helper to build pair strings safely (map tuples to joined strings; do not join tuples directly later)
def make_pair_strategy(value_strategy):
    # key must be a STRING token (not arbitrary value)
    key = string_token
    pair = st.tuples(key, value_strategy).map(lambda t: t[0] + ":" + t[1])
    return pair

# Extend function for recursion: produce objects and arrays (including malformed variants)
def extend(children):
    # children produces VALUE strings (possibly nested)
    pair = make_pair_strategy(children)
    pairs_list = st.lists(pair, min_size=0, max_size=4).map(",".join)

    # Valid object
    valid_obj = pairs_list.map(lambda s: "{" + s + "}" if s != "" else "{}")

    # Duplicate keys: pick one key and several values to force duplicates
    dup_obj = st.tuples(string_token, st.lists(children, min_size=1, max_size=4)).map(
        lambda t: "{" + ",".join(t[0] + ":" + v for v in t[1]) + "}"
    )

    # Missing colon (pairs concatenated without ':')
    missing_colon_pair = st.tuples(string_token, children).map(lambda t: t[0] + t[1])
    missing_colon_obj = st.lists(missing_colon_pair, min_size=1, max_size=4).map(lambda lst: "{" + ",".join(lst) + "}")

    # Double-commas object (introduce an extra comma)
    double_comma_obj = pairs_list.map(lambda s: "{" + (s + ",," + s if s else ",,") + "}")

    # Trailing comma object
    trailing_comma_obj = pairs_list.map(lambda s: "{" + (s + "," if s else "") + "}")

    # Unterminated object (missing closing brace)
    unterminated_obj = pairs_list.map(lambda s: "{" + s)

    obj_variant = st.one_of(valid_obj, dup_obj, missing_colon_obj, double_comma_obj, trailing_comma_obj, unterminated_obj)

    # Arrays
    elems_list = st.lists(children, min_size=0, max_size=6).map(",".join)
    valid_arr = elems_list.map(lambda s: "[" + s + "]" if s != "" else "[]")
    double_comma_arr = elems_list.map(lambda s: "[" + (s + ",," + s if s else ",,") + "]")
    trailing_comma_arr = elems_list.map(lambda s: "[" + (s + "," if s else "") + "]")
    unterminated_arr = elems_list.map(lambda s: "[" + s)

    arr_variant = st.one_of(valid_arr, double_comma_arr, trailing_comma_arr, unterminated_arr)

    return st.one_of(obj_variant, arr_variant)

# Base values fed into recursion
base_value = st.one_of(
    literals,
    number_strategy,
    string_token,
    empty_structs,
)

# Recursive JSON-ish strategy (uses recursive composition for obj/arr)
recursive_values = st.recursive(base_value, extend, max_leaves=200)

# Deep nesting generators concentrated near the parser's nesting limit (~2048)
deep_nesting_depth = st.one_of(
    st.integers(min_value=1, max_value=5),
    st.integers(min_value=100, max_value=300),
    st.integers(min_value=10, max_value=800),
    st.integers(min_value=1900, max_value=2048),
)

deep_array = deep_nesting_depth.map(lambda n: "[" * n + "0" + "]" * n)
# Deep object with repeated {"k": <inner>}
deep_object = deep_nesting_depth.map(lambda n: ("{\"k\":" * n) + "0" + ("}" * n))

# Trailing content after a complete value (parser accepts trailing garbage)
trailing_garbage = st.text(alphabet=_safe_chars + "{}[],:+-eE", min_size=1, max_size=20)
value_with_trailing = st.tuples(recursive_values, trailing_garbage).map(lambda t: t[0] + t[1])

# Additional malformed standalone pieces
malformed_top_level = st.one_of(
    unterminated_string,
    st.just("["),  # truncated
    st.just("{"),  # truncated
    st.just(",,,"),  # garbage
    st.just(":-"),  # garbage
)

# Final strategy: mix of recursive, deep nesting, trailing-content cases, and malformed cases
strategy = st.one_of(
    recursive_values,
    deep_array,
    deep_object,
    value_with_trailing,
    malformed_top_level,
)
```