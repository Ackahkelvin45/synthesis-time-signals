```python
from hypothesis import strategies as st
import json

# ---- Helpers ----

# JSON-safe quoted string using json.dumps (will escape control chars incl NUL as \u0000)
quoted = st.text(min_size=0, max_size=20).map(json.dumps)

# Explicitly-crafted string variants to exercise \uXXXX and surrogate escapes, control escapes,
# and unterminated string variants.
escaped_unicode = st.sampled_from([
    r'"\u0000"',      # explicit escaped NUL inside string (six chars)
    r'"\u00FF"',      # hex
    r'"\uD800"',      # high surrogate
    r'"\uDC00"',      # low surrogate
    r'"\uD800\uDC00"',# combined surrogate pair escape
    r'"\n\t\r"',      # common backslash escapes (note: backslashes included in literal)
    r'"\b\f\/"',      # other escapes
    r'"\\""',         # embedded quote escape
])

# Unterminated string variants (near-valid-but-malformed)
unterminated_string = st.sampled_from([
    '"' ,                 # just opening quote
    '"abc',               # opening but no closing
    r'"\uD8',             # truncated unicode escape
    r'"\',                # backslash at end (malformed)
]).map(lambda s: s)  # already string tokens

# Valid numbers following JSON syntax (no leading zeros except 0)
def make_valid_number():
    sign = st.one_of(st.just('-'), st.just(''), st.just(''))
    int_part = st.one_of(
        st.just('0'),
        st.integers(min_value=1, max_value=10**6).map(str)
    )
    frac = st.one_of(st.just(''), st.tuples(st.just('.'), st.integers(min_value=0, max_value=999999).map(lambda n: str(n))).map(lambda t: ''.join(t)))
    exp = st.one_of(st.just(''), st.tuples(st.sampled_from(['e','E']), st.one_of(st.just(''), st.sampled_from(['+','-'])), st.integers(min_value=0, max_value=9999).map(str)).map(lambda t: ''.join(t)))
    return st.tuples(sign, int_part, frac, exp).map(lambda parts: ''.join(parts))

valid_number = make_valid_number()

# Edge numeric cases: leading plus, .5, 01, lone '-', big exponents/overflow-like
weird_numbers = st.one_of(
    st.just('+1'),          # leading plus (near-valid-but-malformed)
    st.just('.5'),          # missing leading zero
    st.just('01'),          # leading zero on non-zero int
    st.just('-'),           # lone sign (parser accepts to 0)
    st.sampled_from(['1e309', '1e400', '-1e400', '9e9999']),  # extreme exponents likely to overflow
    st.integers(min_value=10**10, max_value=10**15).map(str)   # huge integer
)

# true/false/null tokens
literals = st.sampled_from(['true', 'false', 'null'])

# Key string strategy (for object keys) - must be a JSON string token
key_string = st.text(min_size=0, max_size=8).map(json.dumps)

# Base atomic JSON pieces (strings, numbers, literals, empty container tokens, and some malformed atoms)
base_atom = st.one_of(
    quoted,
    escaped_unicode,
    valid_number,
    weird_numbers,
    literals,
    st.just('{}'),
    st.just('[]'),
    unterminated_string
)

# ---- Recursive construction of JSON values (objects/arrays) using st.recursive ----
def extend_children(children):
    # children is a SearchStrategy producing string fragments that are valid-ish values
    # Build arrays (valid), objects (valid), and several malformed variants.
    # Arrays
    arrays = st.lists(children, min_size=0, max_size=4).map(lambda lst: '[' + ','.join(lst) + ']')

    # Objects (valid): list of (key, value) pairs
    pairs = st.lists(st.tuples(key_string, children), min_size=0, max_size=4).map(
        lambda kvs: '{' + ','.join(k + ':' + v for k, v in kvs) + '}'
    )

    # Force duplicate keys variant
    def dup_obj_builder():
        # pick one key and two values (duplicate keys). We build as {"k":v,"k":v2}
        return st.tuples(key_string, children, children).map(lambda t: '{' + t[0] + ':' + t[1] + ',' + t[0] + ':' + t[2] + '}')

    dup_obj = dup_obj_builder()

    # Malformed object: missing colon between key and value
    missing_colon = st.lists(st.tuples(key_string, children), min_size=1, max_size=3).map(
        lambda kvs: '{' + ','.join(k + ' ' + v for k, v in kvs) + '}'
    )

    # Malformed arrays: double commas, trailing commas, extra commas
    double_commas = st.lists(children, min_size=2, max_size=4).map(
        lambda vals: '[' + ','.join(vals[:1]) + ',,' + ','.join(vals[1:]) + ']'
    )
    trailing_comma = st.lists(children, min_size=1, max_size=4).map(lambda vals: '[' + ','.join(vals) + ',]')

    # Unterminated object (missing closing brace)
    unterminated_obj = st.lists(st.tuples(key_string, children), min_size=1, max_size=3).map(
        lambda kvs: '{' + ','.join(k + ':' + v for k, v in kvs)
    )

    return st.one_of(arrays, pairs, dup_obj, missing_colon, double_commas, trailing_comma, unterminated_obj)

# The recursive JSON-ish strategy (produces many valid and near-valid variants)
recursive_json = st.recursive(base_atom, extend_children, max_leaves=20)

# ---- Deep nesting strategy (use @st.composite-like building via st.builds/st.deferred) ----
@st.composite
def deep_nesting(draw):
    # Choose a depth concentrated near the parser limit (~2048), but occasionally smaller.
    # Cap slightly above to hit rejection path sometimes (but not astronomically huge).
    depth = draw(st.one_of(
        st.integers(min_value=0, max_value=50),                    # shallow
        st.integers(min_value=1800, max_value=2050),               # near-limit
        st.integers(min_value=100, max_value=500)                  # medium
    ))
    # Choose whether to build arrays or objects
    kind = draw(st.sampled_from(['array', 'object']))
    # Start with a simple inner value
    inner = draw(st.one_of(st.just('0'), st.just('null'), quoted, valid_number, literals))
    # Build nested structure: repeated wrapping
    s = inner
    if kind == 'array':
        for i in range(depth):
            s = '[' + s + ']'
    else:
        # For objects, use a simple key; sometimes reuse same key to create duplicates deeper
        key = draw(key_string)
        for i in range(depth):
            # Alternate between empty object and object with the previous nested value
            if i % 10 == 0:
                s = '{' + key + ':' + s + '}'
            else:
                s = '{' + key + ':' + s + '}'
    return s

# ---- Trailing content strategy (parser accepts trailing garbage after a value) ----
trailing_content = st.tuples(recursive_json, st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ -!@#$', min_size=1, max_size=20)).map(
    lambda t: t[0] + ' ' + t[1]
)

# ---- Near-valid-but-malformed tokens (other ad-hoc cases) ----
malformed_numbers = st.sampled_from([
    '+123',    # leading plus
    '.5',      # fractional without leading zero
    '1.',      # trailing dot
    '01',      # leading zero on non-zero
    '-',       # lone sign
    '-.',      # sign and dot
])

double_comma_top = st.builds(lambda a,b: '[' + a + ',,' + b + ']', quoted, valid_number)
missing_colon_top = st.builds(lambda k,v: '{' + k + ' ' + v + '}', key_string, quoted)
unterminated_top = st.sampled_from([ '"abc', '{"a":1', '[1,2,', '"\uD8' ])

# ---- Final composed top-level strategy ----
strategy = st.one_of(
    recursive_json,
    deep_nesting(),
    trailing_content,
    malformed_numbers,
    double_comma_top,
    missing_colon_top,
    unterminated_top,
).filter(lambda s: '\x00' not in s)
```