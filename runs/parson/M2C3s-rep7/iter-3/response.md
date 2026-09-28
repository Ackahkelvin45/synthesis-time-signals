```python
from hypothesis import strategies as st
import json

# Helper: hex4 generator as string of 4 hex digits
hex_digits = '0123456789abcdef'
hex4 = st.tuples(*[st.sampled_from(list(hex_digits)) for _ in range(4)]).map(''.join)

# Surrogate-start prefixes D8..DF
surrogate_prefix = st.sampled_from(['D8','D9','DA','DB','DC','DD','DE','DF'])
surrogate = st.tuples(surrogate_prefix,
                      st.sampled_from(list(hex_digits)),
                      st.sampled_from(list(hex_digits))).map(lambda t: '\\u' + t[0] + t[1] + t[2])

# Basic safe text for inside strings (avoid quote and backslash and control 0x00)
safe_text = st.text(min_size=1, max_size=6, alphabet=st.characters(min_codepoint=0x20,
                                                                   blacklist_characters='"\\'))

# Simple escape sequences as they appear in JSON source (Python literals must escape backslashes)
simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

# Unicode escapes and explicit \u0000 (the six-character escape is allowed; raw NUL is not)
unicode_escape = st.tuples(st.just('\\u'), hex4).map(''.join)
u0000_escape = st.just('\\u0000')

# Raw control characters (except NUL) to produce near-valid-but-malformed strings
raw_control = st.characters(min_codepoint=1, max_codepoint=0x1F).map(lambda c: c)

# Fragments that can appear inside a JSON string literal (some intentionally malformed)
string_fragment = st.one_of(
    safe_text,
    simple_escapes,
    unicode_escape,
    surrogate,
    u0000_escape,
    raw_control
)

# Build a JSON string token; include proper and unterminated variants
string_content = st.lists(string_fragment, min_size=0, max_size=6).map(''.join)
proper_string = string_content.map(lambda s: '"' + s + '"')
unterminated_end = string_content.map(lambda s: '"' + s)   # missing closing quote
unterminated_start = string_content.map(lambda s: s + '"') # missing opening quote
empty_string = st.just('""')
strings_strategy = st.one_of(proper_string, unterminated_end, unterminated_start, empty_string)

# NUMBER strategy: valid numbers plus malformed / edge cases
int_part = st.one_of(st.just('0'), st.integers(min_value=1, max_value=10**6).map(str))
frac_part = st.one_of(st.just(''), st.tuples(st.just('.'), st.integers(min_value=0, max_value=10**6).map(str)).map(''.join))
exp_part = st.one_of(
    st.just(''),
    st.tuples(st.sampled_from(['e', 'E']), st.sampled_from(['', '+', '-']), st.integers(min_value=0, max_value=1000).map(str)).map(lambda t: t[0] + t[1] + t[2])
)
sign = st.one_of(st.just(''), st.just('-'))
valid_number = st.tuples(sign, int_part, frac_part, exp_part).map(''.join)

# Special extreme/exponent cases (including overflow-like exponents)
extreme_numbers = st.sampled_from([
    '1e309', '-1e309', '1e10000', '-1e10000', '9.999e9999', '1E309'
])

# Malformed/near-valid numeric forms
malformed_numbers = st.sampled_from([
    '+1', '+0', '+123',   # leading plus (near-valid)
    '.5', ' .5',         # lone fractional (near-valid in some parsers)
    '1.', '2.',          # trailing dot
    '01', '00', '0123',  # leading zeros (forbidden by grammar)
    '-', '-.', '+',      # lone signs (parser treats '-' as 0)
    '1e', '1e+', '1e-',
    '1e01'               # exponent with leading zero (allowed by grammar but edge)
])

number_strategy = st.one_of(valid_number, extreme_numbers, malformed_numbers)

# Literal values
literal_values = st.sampled_from(['true', 'false', 'null'])

# Keys for objects (using the string token generator; includes malformed keys intentionally)
keys_strategy = strings_strategy

# Recursive construction for arrays and objects using st.recursive
base_value = st.one_of(strings_strategy, number_strategy, literal_values)

def make_array_variants(child):
    # proper arrays, empty, trailing commas and double-commas (malformed)
    proper = st.lists(child, min_size=1, max_size=4).map(lambda lst: '[' + ','.join(lst) + ']')
    empty = st.just('[]')
    trailing_comma = st.lists(child, min_size=1, max_size=4).map(lambda lst: '[' + ','.join(lst) + ',]')
    double_commas = st.lists(child, min_size=2, max_size=4).map(lambda lst: '[' + ',,'.join(lst) + ']')
    leading_comma = st.lists(child, min_size=1, max_size=4).map(lambda lst: '[,' + ','.join(lst) + ']')
    missing_bracket = st.lists(child, min_size=1, max_size=4).map(lambda lst: '[' + ','.join(lst))  # no closing
    return st.one_of(proper, empty, trailing_comma, double_commas, leading_comma, missing_bracket)

def make_object_variants(child):
    # well-formed pairs
    pairs_proper = st.lists(st.tuples(keys_strategy, child), min_size=1, max_size=4).map(
        lambda kvs: '{' + ','.join(k + ':' + v for (k, v) in kvs) + '}'
    )
    empty = st.just('{}')
    # duplicate keys scenario (explicit duplicate)
    duplicate = st.tuples(keys_strategy, child, child).map(lambda t: '{' + t[0] + ':' + t[1] + ',' + t[0] + ':' + t[2] + '}')
    # trailing comma, missing colon, double commas, missing brace
    trailing_comma = st.lists(st.tuples(keys_strategy, child), min_size=1, max_size=4).map(
        lambda kvs: '{' + ','.join(k + ':' + v for (k, v) in kvs) + ',}'
    )
    missing_colon = st.lists(st.tuples(keys_strategy, child), min_size=1, max_size=4).map(
        lambda kvs: '{' + ','.join(k + v for (k, v) in kvs) + '}'  # remove colon
    )
    double_commas = st.lists(st.tuples(keys_strategy, child), min_size=2, max_size=4).map(
        lambda kvs: '{' + ',,'.join(k + ':' + v for (k, v) in kvs) + '}'
    )
    missing_brace = st.lists(st.tuples(keys_strategy, child), min_size=1, max_size=4).map(
        lambda kvs: '{' + ','.join(k + ':' + v for (k, v) in kvs)  # no closing brace
    )
    return st.one_of(pairs_proper, empty, duplicate, trailing_comma, missing_colon, double_commas, missing_brace)

# Use recursive to build nested arrays/objects
recursive_values = st.recursive(
    base_value,
    lambda children: st.one_of(make_array_variants(children), make_object_variants(children)),
    max_leaves=50
)

# Explicit deep-nesting generator to concentrate around parser nesting limit (~2048)
# We create very deep arrays (or objects) near the limit to hit parser depth handling
deep_nesting_arrays = st.integers(min_value=2000, max_value=2050).map(lambda n: '[' * n + '0' + ']' * n)
deep_nesting_objects = st.integers(min_value=2000, max_value=2050).map(lambda n: '{' * n + '"k":0' + '}' * n)

# Trailing-content variant: parser accepts trailing garbage after a valid leading value
trailing_garbage = st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E))
with_trailing = st.tuples(recursive_values, trailing_garbage).map(lambda t: ' ' + t[0] + t[1])

# Combine everything into the final strategy. Include simple base values and deep cases.
strategy = st.one_of(
    recursive_values,
    deep_nesting_arrays,
    deep_nesting_objects,
    with_trailing,
    st.tuples(st.sampled_from(['//comment\n', '/*comment*/\n']), recursive_values).map(lambda t: t[0] + t[1]),
)
```