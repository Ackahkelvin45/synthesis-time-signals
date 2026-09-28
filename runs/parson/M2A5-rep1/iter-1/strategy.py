from hypothesis import strategies as st
import json

# Build a safe printable ASCII alphabet excluding " (0x22), \ (0x5C), and NUL (0x00)
_safe_printable = "".join(chr(i) for i in range(0x20, 0x7F) if i not in (0x22, 0x5C, 0x00))

# Hex 4 generator (for \uXXXX)
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

# Special surrogate-range generator (e.g. D800..DFFF)
_surrogate_hex = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda i: format(i, "04X"))

# Escape snippets used inside strings (always as six-character sequences like \uXXXX
# or two-character escapes like \n, \t, or escaped quote/backslash)
_escape_snip = st.one_of(
    st.sampled_from(['\\\\', '\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    st.builds(lambda h: '\\u' + h, _hex4),
    st.builds(lambda h: '\\u' + h, _surrogate_hex),
    # include explicit \u0000 (six-character escape, not raw NUL)
    st.just('\\u0000'),
)

# Valid (safe) in-string content (no raw NUL, no " or \)
_safe_str_content = st.text(alphabet=_safe_printable, min_size=0, max_size=20)

# Build valid JSON string literals (properly quoted). Mix safe content and escapes.
_valid_json_string = st.lists(st.one_of(_safe_str_content, _escape_snip), min_size=1, max_size=6).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# Unterminated string (near-valid malformed): opening quote, then content, but no closing quote
_unterminated_string = st.lists(st.one_of(_safe_str_content, _escape_snip), min_size=1, max_size=6).map(
    lambda parts: '"' + "".join(parts)
)

# Keys for objects should be valid JSON strings (not unterminated) mostly, but allow duplicate key names
_key_string = _valid_json_string

# NUMBER variants: valid according to grammar plus near-valid/malformed variants
_valid_number = st.one_of(
    # canonical integers (0 or non-leading-zero)
    st.integers(min_value=0, max_value=10 ** 9).map(lambda n: str(n)) ,  # 0..large
    st.integers(min_value=1, max_value=10 ** 9).map(lambda n: "-" + str(n)),  # negative
    # fractional and exponent forms
    st.builds(lambda a, b: a + '.' + b, st.integers(min_value=0, max_value=10 ** 9).map(str), st.text(alphabet="0123456789", min_size=1, max_size=6)),
    st.builds(lambda a, e: a + 'e' + e, st.integers(min_value=1, max_value=10 ** 9).map(str), st.text(alphabet="+-0123456789", min_size=1, max_size=4)),
    # extreme exponents that may overflow (e.g., 1e309)
    st.sampled_from(['1e308', '1e309', '1e400', '-1e309', '2e1024', '9e9999']),
    # lone sign variants (parser accepts lone '-' as 0; include '-','-.')
    st.sampled_from(['-', '-.']),
)

# Near-valid but malformed numbers: leading +, .5, 1., leading zero like 01
_malformed_numbers = st.sampled_from(['+1', '+123.4', '.5', '1.', '01', '-01', '+01'])

# Combine number choices into a single numbers strategy
_number_text = st.one_of(_valid_number, _malformed_numbers)

# Literal values
_literals = st.sampled_from(['true', 'false', 'null'])

# Base (non-recursive) values: strings, numbers, literals, and unterminated string (to exercise parser)
_base_value = st.one_of(_valid_json_string, _unterminated_string, _number_text, _literals)

# Recursive builder for arrays and objects
def _recursive_builder(children):
    # children is a strategy that produces full JSON textual values (strings)
    # Arrays:
    arr_valid = st.one_of(
        st.just('[]'),
        st.lists(children, min_size=1, max_size=5).map(lambda vals: '[' + ','.join(vals) + ']'),
        # trailing comma in array: e.g. [1,2,]
        st.lists(children, min_size=1, max_size=4).map(lambda vals: '[' + ','.join(vals) + ',]'),
        # double commas: e.g. [1,,2]
        st.lists(children, min_size=2, max_size=4).map(lambda vals: '[' + (',,'.join(vals)) + ']'),
        # unterminated array: no closing bracket
        st.lists(children, min_size=1, max_size=4).map(lambda vals: '[' + ','.join(vals)),
    )

    # Objects:
    def make_obj(pairs):
        if not pairs:
            return '{}'
        # pairs is list of (key,value) tuples already encoded as strings
        return '{' + ','.join(k + ':' + v for (k, v) in pairs) + '}'

    # Generate lists of pairs (allow duplicate keys by sampling keys from small set)
    pair = st.tuples(_key_string, children)
    obj_valid = st.one_of(
        st.just('{}'),
        st.lists(pair, min_size=1, max_size=5).map(make_obj),
        # trailing comma in object: {"a":1,}
        st.lists(pair, min_size=1, max_size=4).map(lambda ps: '{' + ','.join(k + ':' + v for (k, v) in ps) + ',}'),
        # double commas in object: {"a":1,, "b":2}
        st.lists(pair, min_size=2, max_size=4).map(lambda ps: '{' + (',,'.join(k + ':' + v for (k, v) in ps)) + '}'),
        # missing colon: '"a" "b"'
        st.lists(st.tuples(_key_string, children), min_size=1, max_size=3).map(lambda ps: '{' + ','.join(k + ' ' + v for (k, v) in ps) + '}'),
        # unterminated object: missing closing brace
        st.lists(pair, min_size=1, max_size=4).map(lambda ps: '{' + ','.join(k + ':' + v for (k, v) in ps)),
    )

    return st.one_of(arr_valid, obj_valid)

# Use st.recursive to assemble nested JSON textual values
_recursive_values = st.recursive(_base_value, _recursive_builder, max_leaves=200)

# Deep nesting strategies concentrated near the parser limit (~2048).
# These are intentionally large but kept as occasional cases.
_deep_array = st.integers(min_value=2000, max_value=2050).map(lambda d: '[' * d + '0' + ']' * d)
_deep_object = st.integers(min_value=2000, max_value=2050).map(lambda d: ('{"k":' * d) + '0' + '}' * d)

# Trailing-content variants: append arbitrary trailing bytes/words after a complete value
_trailing_garbage = st.sampled_from(['', ' trailing', ' garbage', 'XYZ', '/*junk*/', ' //end', '\nbye'])

# Final top-level strategy: include recursive values, deep nesting, and primitive bases; sometimes append trailing garbage
strategy = st.one_of(
    # Normal recursive/generated JSON-like texts (most cases)
    _recursive_values.flatmap(lambda s: st.just(s)),
    # Deep nesting cases (rare)
    _deep_array,
    _deep_object,
    # Also allow raw base values (primitives) with trailing garbage
    st.one_of(_base_value, _number_text, _literals).flatmap(lambda s: st.just(s)),
).flatmap(lambda s: st.one_of(st.just(s), st.just(s + st.example(_trailing_garbage) if False else s), st.just(s + ' ' + 'TRAIL'), st.just(s + st.example(_trailing_garbage) if False else s)))