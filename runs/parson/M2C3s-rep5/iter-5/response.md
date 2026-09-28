```python
from hypothesis import strategies as st
import json

# --- Helpers for building JSON fragments without emitting raw NUL (0x00) ---

# Safe printable ASCII (space..~) excluding quote and backslash for some raw content generation
printable_no_quote = st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\"')
# Digits for number parts
digits = st.characters(whitelist_characters='0123456789')
# Hex digit generator for \uXXXX escapes
hex4 = st.text(alphabet=list('0123456789abcdefABCDEF'), min_size=4, max_size=4)
# Surrogate codepoints generator (D800..DFFF) as 4-hex uppercase
surrogate = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda i: format(i, '04X'))

# --- STRING variants ---
# 1) Well-formed JSON string via json.dumps (will include quotes)
json_dumps_string = st.text(alphabet=printable_no_quote, min_size=0, max_size=12).map(json.dumps)

# 2) Raw-control-containing string (no NUL). Wrap with quotes explicitly so these are raw controls inside quotes.
raw_control_string = st.text(
    alphabet=st.characters(min_codepoint=0, max_codepoint=31),  # control chars excluding NUL
    min_size=1, max_size=6
).map(lambda s: '"' + s + '"')

# 3) Explicit Unicode escape sequences like "\uXXXX" inserted literally
unicode_escape_string = hex4.map(lambda hx: '"\\u' + hx + '"')

# 4) Surrogate pairs inserted literally: e.g. "\uD834\uDD1E"
surrogate_pair_string = st.tuples(surrogate, surrogate).map(lambda p: '"\\u' + p[0] + '\\u' + p[1] + '"')

# 5) Unterminated string (missing closing quote)
unterminated_string = st.text(alphabet=printable_no_quote, min_size=0, max_size=10).map(lambda s: '"' + s)

# 6) Malformed escape sequences (e.g., backslash at end, unknown escape like "\x")
malformed_escape = st.text(alphabet=printable_no_quote, min_size=0, max_size=8).map(lambda s: '"' + s + '\\' + '"')  # ends with a dangling backslash inside quotes

# Combined string strategy (returns a quoted string or unterminated/malformed variant)
string_strategy = st.one_of(
    json_dumps_string,
    raw_control_string,
    unicode_escape_string,
    surrogate_pair_string,
    unterminated_string,
    malformed_escape,
)

# Ensure keys used for objects are usually valid quoted strings (prefer valid keys)
key_string_valid = json_dumps_string

# --- NUMBER variants ---
# Valid integer (no leading zeros except '0')
valid_int = st.one_of(
    st.just('0'),
    st.integers(min_value=1, max_value=10 ** 9).map(str)
)

# Optional fractional part
fraction = st.one_of(
    st.just(''),
    st.integers(min_value=0, max_value=10 ** 8).map(lambda s: '.' + str(s))
)

# Optional exponent
exp = st.one_of(
    st.just(''),
    st.tuples(st.sampled_from(['e', 'E']), st.sampled_from(['+', '-', '']), st.integers(min_value=0, max_value=999)).map(lambda t: t[0] + t[1] + str(t[2]))
)

# Well-formed number by grammar: optional '-' + INT + optional frac + optional exp
valid_number = st.tuples(st.sampled_from(['', '-']), valid_int, fraction, exp).map(lambda t: t[0] + t[1] + t[2] + t[3])

# Malformed/edge-case numbers
malformed_numbers = st.one_of(
    st.sampled_from(['+1', '+0', '+123', '.5', '-.5', '1.', '01', '-','+.','-.', '1e', '1e+', '1e-']),
    # very large exponents/magnitudes (may overflow; parser is known to reject non-finite)
    st.tuples(st.integers(min_value=1, max_value=9).map(str), st.integers(min_value=300, max_value=2000)).map(lambda t: t[0] + 'e' + str(t[1])),
    # explicit overflow-like forms
    st.sampled_from(['1e309', '-1e400', '9e9999'])
)

number_strategy = st.one_of(valid_number, malformed_numbers)

# --- Atomic values (strings, numbers, true/false/null) ---
atomic = st.one_of(
    string_strategy,
    number_strategy,
    st.just('true'),
    st.just('false'),
    st.just('null'),
)

# --- Recursive construction for arrays/objects using st.recursive ---
def array_variants(child):
    # well-formed array
    arr_good = st.lists(child, min_size=0, max_size=4).map(lambda items: '[' + ','.join(items) + ']')
    # trailing comma
    arr_trailing = st.lists(child, min_size=1, max_size=4).map(lambda items: '[' + ','.join(items) + ',]')
    # double comma (e.g., [a,,b]) - if fewer than 2 items, fallback to single-item double-comma variant
    def make_double(lst):
        if len(lst) >= 2:
            return '[' + lst[0] + ',,' + lst[1] + ((',' + ','.join(lst[2:]) ) if len(lst) > 2 else '') + ']'
        else:
            return '[' + (lst[0] if lst else '') + ',,]'
    arr_double_comma = st.lists(child, min_size=0, max_size=4).map(make_double)
    # empty array explicit
    arr_empty = st.just('[]')
    return st.one_of(arr_good, arr_trailing, arr_double_comma, arr_empty)

def object_variants(child):
    # pair: key (quoted) : value
    pair = st.tuples(key_string_valid, child).map(lambda kv: kv[0] + ':' + kv[1])

    # well-formed object
    obj_good = st.lists(pair, min_size=0, max_size=4).map(lambda pairs: '{' + ','.join(pairs) + '}')

    # trailing comma
    obj_trailing = st.lists(pair, min_size=1, max_size=4).map(lambda pairs: '{' + ','.join(pairs) + ',}')

    # duplicate keys: pick one key and repeat it with different values
    def make_dup(pairs):
        if not pairs:
            return '{}'
        # repeat the first key twice
        first = pairs[0]
        # extract key part up to colon
        k = first.split(':', 1)[0]
        rest = pairs[1:]
        return '{' + k + ':' + first.split(':',1)[1] + ',' + k + ':' + (rest[0].split(':',1)[1] if rest else 'null') + ((',' + ','.join(rest[1:])) if len(rest) > 1 else '') + '}'
    obj_dup_keys = st.lists(pair, min_size=1, max_size=4).map(make_dup)

    # missing colon (e.g., "k" value) - intentionally malformed
    missing_colon = st.tuples(key_string_valid, child).map(lambda kv: '{' + kv[0] + ' ' + kv[1] + '}')

    # double commas inside object
    def make_double_obj(pairs):
        if not pairs:
            return '{,}'
        if len(pairs) == 1:
            return '{' + pairs[0] + ',,}'
        return '{' + pairs[0] + ',,' + pairs[1] + ((',' + ','.join(pairs[2:])) if len(pairs) > 2 else '') + '}'
    obj_double_comma = st.lists(pair, min_size=0, max_size=4).map(make_double_obj)

    # unterminated object (missing closing brace)
    obj_unterminated = st.lists(pair, min_size=0, max_size=3).map(lambda pairs: '{' + ','.join(pairs))

    return st.one_of(obj_good, obj_trailing, obj_dup_keys, missing_colon, obj_double_comma, obj_unterminated, st.just('{}'))

# Use st.recursive to generate nested arrays/objects
recursive_values = st.recursive(
    atomic,
    lambda children: st.one_of(
        array_variants(children),
        object_variants(children),
    ),
    max_leaves=50  # keep recursive exploration manageable; deep nesting handled separately
)

# --- Deep nesting near parser limit (targeting ~2048 depth) ---
# Build deeply nested arrays like [[[...0...]]]
deep_nesting = st.integers(min_value=1000, max_value=2048).map(lambda depth: ('[' * depth) + '0' + (']' * depth))

# --- Trailing-content variant: a complete value followed by arbitrary trailing bytes (accepted by target parser) ---
trailing_garbage = st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E), min_size=1, max_size=20)
trailing_variant = st.tuples(recursive_values, trailing_garbage).map(lambda t: t[0] + t[1])

# --- Combine everything into the final strategy ---
strategy = st.one_of(
    recursive_values,
    deep_nesting,
    trailing_variant,
    # also include some atomic malformed pieces at top-level to catch edge parsing behaviors
    st.one_of(string_strategy, number_strategy, st.just('-'), st.just(''), st.just(' ')),
    st.one_of(st.just('// comment\n'), st.just('/* comment */'), st.just('\ufeff')),
)
```