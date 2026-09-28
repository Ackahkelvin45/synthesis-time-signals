```python
from hypothesis import strategies as st
import json

# Helper: hex digit string
hex4 = st.tuples(st.integers(min_value=0, max_value=15),
                 st.integers(min_value=0, max_value=15),
                 st.integers(min_value=0, max_value=15),
                 st.integers(min_value=0, max_value=15)).map(
    lambda t: ''.join("{:x}".format(x) for x in t)
)

# Characters safe for unescaped JSON string content (no control, no quote, no backslash, no NUL)
safe_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters='"\\"')

# Basic JSON escapes (extended with C-style hex escapes to exercise C parser handling)
simple_esc = st.one_of(
    st.sampled_from(['\\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    st.text(alphabet=list('0123456789abcdefABCDEF'), min_size=2, max_size=2).map(lambda s: '\\x' + s)
)

# Unicode escape sequences, including surrogate escapes (D800-DFFF)
unicode_escape = st.one_of(
    hex4.map(lambda h: '\\u' + h),
    # surrogate high (D800-DFFF) explicit
    st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda i: '\\u' + format(i, '04x'))
)

# Valid quoted JSON string (with optional escapes)
valid_string = st.one_of(
    # plain content
    st.text(alphabet=safe_char, min_size=0, max_size=20).map(lambda s: '"' + s + '"'),
    # content mixed with escapes
    st.lists(st.one_of(safe_char.map(str), simple_esc, unicode_escape), min_size=0, max_size=20).map(
        lambda parts: '"' + ''.join(parts) + '"'
    ),
    # include explicit \u0000 escape (six-character)
    hex4.map(lambda h: '"\\u' + h + '"' )
)

# Unterminated string: opening quote with no closing quote
unterminated_string = st.one_of(
    st.text(alphabet=safe_char, min_size=0, max_size=50).map(lambda s: '"' + s),
    st.lists(st.one_of(safe_char.map(str), simple_esc, unicode_escape), min_size=0, max_size=20).map(
        lambda parts: '"' + ''.join(parts)  # no trailing "
    )
)

# Missing opening quote (bare content that looks like a string without quotes)
missing_open_quote = st.one_of(
    st.text(alphabet=safe_char, min_size=1, max_size=50),
    # Add C-style block comments as plausible "bare" tokens to exercise C parser comment handling
    st.tuples(
        st.just('/*'),
        st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127).filter(lambda c: c != '\x00'), min_size=0, max_size=50),
        st.just('*/')
    ).map(lambda t: ''.join(t)),
    # Add C++-style line comments optionally terminated by newline (or EOF)
    st.tuples(
        st.just('//'),
        st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127).filter(lambda c: c not in ('\x00', '\n', '\r')), min_size=0, max_size=50),
        st.sampled_from(['\n', '\r\n', ''])
    ).map(lambda t: ''.join(t))
)

# Number builders
digits = st.text(alphabet=st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=10)
nonzero_first_int = st.tuples(st.sampled_from(list("123456789")), st.text(alphabet=st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=0, max_size=9)).map(lambda t: t[0] + t[1])
int_part = st.one_of(st.just("0"), nonzero_first_int)

# Valid number according to grammar (but may be extreme via exponent)
def make_valid_number():
    frac = st.one_of(st.none(), st.text(alphabet=st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=8).map(lambda s: '.' + s))
    exp = st.one_of(st.none(),
                    st.tuples(st.sampled_from(['e', 'E']), st.sampled_from(['+', '-', '']), st.text(alphabet=st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=4)).map(
                        lambda t: t[0] + t[1] + t[2]
                    ),
                    # extreme exponent branch
                    st.sampled_from(['e308', 'e309', 'e9999', 'E9999']).map(lambda s: s)
                    )
    sign = st.one_of(st.just(''), st.just('-'))
    return st.tuples(sign, int_part, frac, exp).map(lambda t: t[0] + t[1] + (t[2] or '') + (t[3] or ''))

valid_number = make_valid_number()

# Malformed/near-valid numbers to exercise parser leniency/edge-cases
malformed_number = st.one_of(
    st.text(alphabet=st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=5).map(lambda s: '+' + s),  # leading +
    st.text(alphabet=st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=5).map(lambda s: '01' + s),  # leading zero + extra
    st.text(alphabet=st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=0, max_size=5).map(lambda s: '.' + s),  # .5 style (maybe lenient)
    st.text(alphabet=st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=5).map(lambda s: s + '.'),  # trailing dot
    st.sampled_from(['-', '-.'])  # lone sign variants accepted as 0 by parser
)

# Literal tokens
literals = st.sampled_from(['true', 'false', 'null'])

# A quoted key for object pairs (keys should usually be valid strings)
key_string = st.one_of(
    st.text(alphabet=safe_char, min_size=0, max_size=20).map(lambda s: '"' + s + '"'),
    # also allow keys with escapes
    st.lists(st.one_of(safe_char.map(str), simple_esc, unicode_escape), min_size=0, max_size=12).map(lambda parts: '"' + ''.join(parts) + '"')
)

# Base (non-recursive) JSON "value" pieces (strings, numbers, literals, and near-misses)
base_value = st.one_of(
    valid_string,
    unterminated_string,
    missing_open_quote,
    valid_number,
    malformed_number,
    literals
)

# Recursive construction for arrays/objects (valid and near-valid/malformed variants)
def extend(children):
    # children is a strategy producing complete value strings (could be valid or malformed)
    # Array constructions
    array_valid = st.lists(children, min_size=0, max_size=6).map(lambda vals: '[' + ','.join(vals) + ']')
    # Malformed arrays: double commas, trailing commas, missing brackets
    array_malformed = st.one_of(
        st.lists(children, min_size=1, max_size=6).map(lambda vals: '[' + ','.join(vals) + ',]'),  # trailing comma
        st.lists(children, min_size=2, max_size=6).map(lambda vals: '[' + ',,'.join(vals) + ']'),  # double commas by joining with ',,'
        st.lists(children, min_size=1, max_size=6).map(lambda vals: ','.join(vals) + ']'),  # missing opening bracket
        st.lists(children, min_size=1, max_size=6).map(lambda vals: '[' + ','.join(vals))  # missing closing bracket (unterminated)
    )
    # Object constructions
    # Normal pairs
    pair = st.tuples(key_string, children).map(lambda kv: kv[0] + ':' + kv[1])
    obj_valid = st.lists(pair, min_size=0, max_size=6).map(lambda pairs: '{' + ','.join(pairs) + '}')
    # Malformed objects: duplicate keys, missing colons, double commas, trailing commas, unterminated
    def make_pairs_with_dups(pairs):
        # sometimes duplicate keys: duplicate the first key
        if not pairs:
            return pairs
        return pairs + [pairs[0]]
    obj_dup_keys = st.lists(pair, min_size=1, max_size=5).map(make_pairs_with_dups).map(lambda pairs: '{' + ','.join(pairs) + '}')
    obj_malformed = st.one_of(
        st.lists(pair, min_size=1, max_size=6).map(lambda pairs: '{' + ','.join(pairs) + ',}'),  # trailing comma
        st.lists(pair, min_size=2, max_size=6).map(lambda pairs: '{' + ',,'.join(pairs) + '}'),  # double commas
        st.lists(st.tuples(key_string, children), min_size=1, max_size=6).map(lambda pairs: '{' + ','.join([k + v for (k, v) in pairs]) + '}'),  # missing colons (k + v instead of k:v)
        st.lists(pair, min_size=1, max_size=6).map(lambda pairs: '{' + ','.join(pairs)),  # unterminated (no closing brace)
        obj_dup_keys
    )
    return st.one_of(array_valid, array_malformed, obj_valid, obj_malformed)

# The recursive value strategy (uses st.recursive for obj/arr recursion)
recursive_values = st.recursive(base_value, extend, max_leaves=2000)

# Deep nesting generator (using @st.composite is allowed for recursive productions)
@st.composite
def deep_nesting(draw):
    # Choose array or object nesting
    kind = draw(st.sampled_from(['array', 'object']))
    # Concentrate depths near the parser limit (~2048). Pick mostly near 2000..2050 but allow some smaller values.
    depth = draw(st.one_of(
        st.integers(min_value=1800, max_value=2048),  # many legal/deep cases
        st.integers(min_value=2049, max_value=2060),  # slightly-overlimit (will be rejected cleanly)
        st.integers(min_value=100, max_value=500)     # some smaller deep cases
    ))
    # Base inside content: either 0, null, or an unterminated string sometimes
    inner = draw(st.one_of(st.just('0'), st.just('null'), unterminated_string, valid_string))
    if kind == 'array':
        # Build nested array: '[' * depth + inner + ']' * depth
        return '[' * depth + inner + ']' * depth
    else:
        # Build nested object: '{' * depth + '"k":' + inner + '}' * depth
        # Use a simple key to avoid huge key generation runtime
        return '{' * depth + '"k":' + inner + '}' * depth

# Top-level strategy optionally appends trailing garbage (parser accepts trailing content)
trailing_garbage = st.one_of(
    st.just(''),
    st.sampled_from([' ', '\n', '\r\n']),
    st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127).filter(lambda c: c != '\x00'), min_size=1, max_size=20)  # avoid raw NUL
)

# Combine everything into the final strategy. Include recursive_values, deep nesting, and some specifically malformed top-level combos.
top_level_choices = st.one_of(
    recursive_values,
    deep_nesting(),
    # near-valid-but-malformed top-level constructs
    st.one_of(
        # value followed by trailing content
        st.tuples(recursive_values, trailing_garbage).map(lambda t: t[0] + t[1]),
        # double top-level values concatenated (parser will accept leading value)
        st.tuples(recursive_values, recursive_values).map(lambda t: t[0] + t[1]),
        # unterminated top-level string alone
        unterminated_string,
        # lone plus or dot-number
        malformed_number,
        # leading plus sign alone or leading +
        st.sampled_from(['+', '+1', '+0', '+e']),
        # Leading dot forms
        st.sampled_from(['.5', '.123', '1.', '01'])
    )
)

# Final exported strategy: produce str and ensure no raw NUL character '\x00' in output
strategy = top_level_choices.filter(lambda s: '\x00' not in s)
```