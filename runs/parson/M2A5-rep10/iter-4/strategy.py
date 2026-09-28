from hypothesis import strategies as st
import json

# Constants
CAP_DEPTH = 2048

# Helper primitives

# Valid visible ASCII characters for JSON string content (no quote/backslash),
# codepoints U+0020..U+007E excluding " and \
_vis_ascii_no_quote_backslash = st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\"')

# Small printable chunks
_valid_chunk = st.text(alphabet=_vis_ascii_no_quote_backslash, min_size=1, max_size=8)

# Standard JSON escapes as literal two-character sequences in the JSON source
_standard_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

# Hex digit for \uXXXX
_hex_digit = st.sampled_from(list('0123456789abcdefABCDEF'))
_unicode_escape = st.tuples(_hex_digit, _hex_digit, _hex_digit, _hex_digit).map(lambda t: '\\u' + ''.join(t))

# Surrogate-range escapes like \uD800 ... \uDFFF
_surrogate_escape = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda cp: '\\u' + format(cp, '04X'))

# Explicit \u0000 escape (allowed; should be used instead of a raw NUL)
_u0000_escape = st.just('\\u0000')

# Valid JSON STRING token generator (quotes included)
_valid_string_token = st.lists(
    st.one_of(_valid_chunk, _standard_escapes, _unicode_escape, _surrogate_escape, _u0000_escape),
    min_size=0,
    max_size=5
).map(lambda parts: '"' + ''.join(parts) + '"')

# Malformed string token variants (near-valid-but-malformed)
_malformed_string_token = st.one_of(
    # Unterminated string: opening quote, content, no closing quote
    st.lists(
        st.one_of(_valid_chunk, _standard_escapes, _unicode_escape, _surrogate_escape, _u0000_escape),
        min_size=1, max_size=5
    ).map(lambda parts: '"' + ''.join(parts)),
    # Missing opening quote: naked content
    st.lists(_valid_chunk, min_size=1, max_size=4).map(lambda parts: ''.join(parts)),
    # Unterminated escape: ends with a backslash
    st.lists(
        st.one_of(_valid_chunk, _standard_escapes, _unicode_escape, _surrogate_escape),
        min_size=1, max_size=4
    ).map(lambda parts: '"' + ''.join(parts) + '\\'),
    # Raw control character inside (but NEVER raw NUL): include e.g. \x01..\x1F except 0x00
    st.integers(min_value=1, max_value=0x1F).map(lambda cp: '"' + chr(cp) + '"'),
    # Invalid unicode escape sequences (non-hex or truncated)
    st.one_of(
        st.just('"\\uZZZZ"'),
        st.just('"\\u123"'),
        st.just('"\\u12G4"')
    )
)

# Number generators

# Well-formed integer portion: '0' or non-zero leading digit
_int_part = st.one_of(st.just('0'), st.tuples(st.sampled_from(list('123456789')), st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=0, max_size=8)).map(lambda t: t[0] + t[1]))

# Fractional part (.digits)
_frac_part = st.one_of(st.just(''), st.tuples(st.just('.'), st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=6)).map(lambda t: t[0] + t[1]))

# Exponent part
_exp_part = st.one_of(
    st.just(''),
    st.tuples(st.sampled_from(['e', 'E']), st.sampled_from(['+', '-', '']), st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=5)).map(lambda t: t[0] + t[1] + t[2])
)

_number_wellformed = st.tuples(st.one_of(st.just(''), st.just('-')), _int_part, _frac_part, _exp_part).map(lambda t: ''.join(t))

# Malformed/edge number variants: leading +, .5, 1., 01, lone '-', '-.', huge exponents (including overflow-looking)
_number_malformed = st.one_of(
    # leading plus
    st.tuples(st.just('+'), st.one_of(st.just('0'), st.text(st.characters(min_codepoint=ord('1'), max_codepoint=ord('9')), min_size=1, max_size=4))).map(lambda t: ''.join(t)),
    # leading dot
    st.tuples(st.just('.'), st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=6)).map(lambda t: ''.join(t)),
    # trailing dot
    st.tuples(st.one_of(st.just('0'), st.text(st.characters(min_codepoint=ord('1'), max_codepoint=ord('9')), min_size=1, max_size=6)), st.just('.')).map(lambda t: ''.join(t)),
    # leading zero with extra digits like 01
    st.tuples(st.just('0'), st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=6)).map(lambda t: ''.join(t)),
    # lone negative sign or '-.'
    st.just('-'),
    st.just('-.'),
    # extreme exponents/infinities (overflow-like): 1e309, 1e9999, -1E10000
    st.sampled_from(['1e309', '1e9999', '-1E10000', '9e999']),
    # non-digit in exponent
    st.just('1e+'),
    # random tiny/big numbers
    st.tuples(st.one_of(st.just('0'), st.text(st.characters(min_codepoint=ord('1'), max_codepoint=ord('9')), min_size=1, max_size=4)),
              st.just('e'),
              st.sampled_from(['+999', '-999', '01'])).map(lambda t: ''.join(t))
)

_number_token = st.one_of(_number_wellformed, _number_malformed)

# Base (non-recursive) value strategy: includes strings (valid and malformed), numbers, and literals
_base_value = st.one_of(
    _valid_string_token,
    _malformed_string_token,
    _number_token,
    st.just('true'),
    st.just('false'),
    st.just('null')
)

# Recursive construction for arrays and objects using st.recursive
def _make_array_from_children(children):
    # Well-formed arrays: empty or [v,v,...]
    good = st.lists(children, min_size=0, max_size=4).map(lambda items: '[' + ','.join(items) + ']')
    # Trailing comma variant: [a,b,]
    trailing_comma = st.lists(children, min_size=1, max_size=4).map(lambda items: '[' + ','.join(items) + ',]')
    # Double-commas: join and then inject a duplicate comma between two items if >=2 items
    double_commas = st.lists(children, min_size=2, max_size=4).map(lambda items: '[' + ',,'.join(items) + ']')
    # Missing commas: glue items without commas "[a b c]" (near-valid-malformed)
    missing_commas = st.lists(children, min_size=2, max_size=4).map(lambda items: '[' + ' '.join(items) + ']')
    return st.one_of(good, trailing_comma, double_commas, missing_commas)

def _make_object_from_children(children):
    # Pair strategy: use valid string tokens for keys (so duplicates can naturally occur)
    pair = st.tuples(st.one_of(_valid_string_token, _malformed_string_token), children).map(lambda t: t[0] + ':' + t[1])
    # Well-formed objects
    good = st.lists(pair, min_size=0, max_size=4).map(lambda pairs: '{' + ','.join(pairs) + '}')
    # Trailing comma
    trailing_comma = st.lists(pair, min_size=1, max_size=4).map(lambda pairs: '{' + ','.join(pairs) + ',}')
    # Duplicate-keys encouraged by sampling from small key pools (create duplicates)
    def duplicate_pairs(pairs):
        # pairs is a list of pair strings; intentionally duplicate some keys by repeating elements
        if not pairs:
            return '{}'
        # duplicate the first pair
        dup = pairs + [pairs[0]]
        return '{' + ','.join(dup) + '}'
    duplicate_keys = st.lists(pair, min_size=1, max_size=3).map(duplicate_pairs)
    # Missing colons: replace ':' in pairs with space (near-valid-malformed)
    missing_colon = st.lists(st.tuples(_valid_string_token, children), min_size=1, max_size=4).map(
        lambda lst: '{' + ','.join(k + ' ' + v for (k, v) in lst) + '}'
    )
    # Double commas inside object
    double_commas = st.lists(pair, min_size=2, max_size=4).map(lambda pairs: '{' + ',,'.join(pairs) + '}')
    return st.one_of(good, trailing_comma, duplicate_keys, missing_colon, double_commas)

# Use st.recursive for nested obj/arr production
_recursive_values = st.recursive(
    _base_value,
    lambda children: st.one_of(
        _make_array_from_children(children),
        _make_object_from_children(children)
    ),
    max_leaves=50  # allow reasonable recursion depth in typical runs; deep explicit generator below handles extreme depth
)

# Deep nesting generator near CAP_DEPTH (produce arrays nested to a depth near the parser limit)
_deep_nesting = st.one_of(
    # Small depths (useful for quick tests)
    st.integers(min_value=0, max_value=20).map(lambda d: '[' * d + '0' + ']' * d),
    # Depths near the cap: pick from CAP_DEPTH-10 .. CAP_DEPTH (never exceed CAP_DEPTH)
    st.integers(min_value=max(0, CAP_DEPTH - 10), max_value=CAP_DEPTH).map(lambda d: '[' * d + '0' + ']' * d),
    # A mid-large depth range
    st.integers(min_value=100, max_value=min(1000, CAP_DEPTH)).map(lambda d: '[' * d + '0' + ']' * d)
)

# Trailing-garbage strategy: append arbitrary trailing content after a complete value (parser accepts this)
_trailing_garbage = st.text(alphabet=st.characters(min_codepoint=0x09, max_codepoint=0x7E, blacklist_characters=''), min_size=1, max_size=40)

# Mutate a valid or recursive JSON to inject a near-valid-but-malformed tweak
_mutated_variant = st.tuples(_recursive_values, st.sampled_from([
    # Insert random trailing garbage
    lambda s, g: s + g,
    # Replace a comma with double comma (if possible)
    lambda s, g: s.replace(',', ',,', 1),
    # Remove a colon if present
    lambda s, g: s.replace(':', ' ', 1),
    # Drop final closing bracket/brace (unterminated)
    lambda s, g: s[:-1] if len(s) > 0 else s,
    # Add a leading plus to a number at start (if first char looks numeric)
    lambda s, g: ('+' + s) if s and (s[0].isdigit() or s[0] in '-.') else s,
    # Inject an unterminated string at the end
    lambda s, g: s + '"' + g[:10]
]))

_mutated_variant = st.tuples(_recursive_values, _trailing_garbage, st.sampled_from([0,1,2,3,4,5])).map(
    lambda t: (
        # apply transform based on the integer flag deterministically to avoid lambdas in strategy
        t[0] + t[1] if t[2] == 0 else
        t[0].replace(',', ',,', 1) if t[2] == 1 else
        t[0].replace(':', ' ', 1) if t[2] == 2 else
        (t[0][:-1] if len(t[0]) > 0 else t[0]) if t[2] == 3 else
        (('+' + t[0]) if t[0] and (t[0][0].isdigit() or t[0][0] in '-.') else t[0]) if t[2] == 4 else
        (t[0] + '"' + t[1][:10])
    )
)

# Top-level strategy: combine multiple branches to cover wide variety of inputs
strategy = st.one_of(
    # Typical recursive JSON values (both valid and some malformed bits from base)
    _recursive_values,
    # Deeply nested arrays near the parser's nesting cap
    _deep_nesting,
    # Mutated near-valid inputs (double commas, missing colons, trailing garbage, unterminated strings)
    _mutated_variant,
    # Simple values (numbers, strings) with trailing garbage appended explicitly
    st.tuples(st.one_of(_valid_string_token, _number_token, st.just('true'), st.just('false'), st.just('null')), _trailing_garbage).map(lambda t: t[0] + t[1])
)