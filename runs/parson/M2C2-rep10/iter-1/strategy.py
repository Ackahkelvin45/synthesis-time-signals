from hypothesis import strategies as st
import json

# Helper alphabets (avoid raw NUL '\x00' in any generated raw character)
SAFE_ASCII = ''.join(chr(i) for i in range(0x20, 0x7F) if i not in (34, 92))  # printable ASCII excluding " and \
CONTROL_CHARS = [chr(i) for i in range(1, 0x20)]  # raw control bytes except NUL; allowed per requirements (but no raw NUL)

# Unicode-escape pieces
hex4 = st.integers(min_value=0, max_value=0xFFFF).map(lambda i: format(i, '04X'))
unicode_escape = hex4.map(lambda h: '\\u' + h)
# Surrogate pair: high D800-DBFF and low DC00-DFFF
surrogate_pair = st.tuples(
    st.integers(min_value=0xD800, max_value=0xDBFF),
    st.integers(min_value=0xDC00, max_value=0xDFFF),
).map(lambda pr: '\\u' + format(pr[0], '04X') + '\\u' + format(pr[1], '04X'))

# Common short escapes
short_escapes = st.sampled_from(['\\n', '\\r', '\\t', '\\b', '\\f', '\\\\', '\\"', '\\/'])

# Pieces that can appear inside a string (both valid and intentionally malformed variants)
string_piece = st.one_of(
    st.text(alphabet=SAFE_ASCII, min_size=1, max_size=8),
    short_escapes,
    unicode_escape,
    surrogate_pair,
    st.sampled_from(CONTROL_CHARS).map(lambda c: c),  # raw control byte (not NUL)
)

# Valid quoted JSON string (uses escapes for control points or raw safe ascii)
valid_quoted_string = st.lists(string_piece, min_size=0, max_size=6).map(lambda parts: '"' + ''.join(parts) + '"')

# Malformed string variants: unterminated, unterminated escape, unescaped quote inside, bare control inserted
unterminated_quote = st.lists(string_piece, min_size=0, max_size=6).map(lambda parts: '"' + ''.join(parts))  # missing closing quote
unterminated_escape = st.lists(string_piece, min_size=0, max_size=6).map(lambda parts: '"' + ''.join(parts) + '\\')  # trailing backslash
unescaped_quote_inside = st.lists(string_piece, min_size=0, max_size=5).map(lambda parts: '"' + ''.join(parts) + '"' + '"')  # extra quote inserted (malformed)
bare_control_in_string = st.lists(st.one_of(st.text(alphabet=''), st.sampled_from(CONTROL_CHARS)), min_size=1, max_size=4).map(
    lambda parts: '"' + ''.join(parts) + '"'  # raw control bytes inside quotes
)

malformed_quoted_string = st.one_of(unterminated_quote, unterminated_escape, unescaped_quote_inside, bare_control_in_string)

# Keys for objects should usually be valid JSON strings; include duplicates via object construction
key_string = valid_quoted_string

# Number strategies: valid, extremes, and near-valid-malformed forms
# Valid integers/floats with optional exponent including extreme exponents
int_valid = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(lambda i: str(i))
)
frac_part = st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.integers(min_value=0, max_value=10**6).map(lambda i: str(i))))
exp_part = st.one_of(st.just(''), st.builds(lambda s: 'e' + s, st.integers(min_value=-1000, max_value=1000).map(lambda i: str(i))))
number_valid = st.tuples(st.one_of(st.just(''), st.just('-')), int_valid, frac_part, exp_part).map(lambda t: t[0] + t[1] + t[2] + t[3])

# Extreme magnitudes explicitly included (including ones that overflow double)
extreme_magnitudes = st.sampled_from(["1e309", "-1e309", "1E400", "9.99e9999", "1e-9999", "1e308", "-1e308"])

# Near-valid but malformed numbers
malformed_numbers = st.sampled_from([
    "+1", "+0",  # leading plus (near-valid)
    ".5",       # leading dot
    "1.",       # trailing dot
    "01",       # leading zero invalid in grammar
    "-",        # lone sign (parser accepts as zero per notes)
    "-.",       # odd lone sign+dot
    "+.5",      # plus + dot
    "00",       # multiple leading zeros
])

number_strategy = st.one_of(number_valid, extreme_magnitudes, malformed_numbers)

# Literal values
literal_strategy = st.sampled_from(["true", "false", "null"])

# Base leaf values (strings, numbers, literals) — strings include both valid and malformed ones
leaf_value = st.one_of(valid_quoted_string, malformed_quoted_string, number_strategy, literal_strategy)

# Function to build object and array strings from lists of children (children are strings representing JSON values)
def make_object_from_pairs(pairs):
    if not pairs:
        return "{}"
    inner = ",".join(k + ":" + v for (k, v) in pairs)
    return "{" + inner + "}"

def make_array_from_vals(vals):
    if not vals:
        return "[]"
    inner = ",".join(vals)
    return "[" + inner + "]"

# Extension function for recursion: produces object/array strings, with both valid and malformed variants
def extend(child):
    # valid objects with 0..5 pairs
    valid_obj = st.lists(st.tuples(key_string, child), min_size=0, max_size=5).map(make_object_from_pairs)

    # duplicate-keys object: ensure at least one duplicate key
    def make_dup(pairs):
        if not pairs:
            # make at least one pair duplicated
            k = '"dup"'
            return "{" + ",".join([k + ":" + "null"] * 2) + "}"
        # pick a key from pairs to duplicate
        k, v = pairs[0]
        dup_list = [(k, v)] + pairs
        return make_object_from_pairs(dup_list)
    dup_keys_obj = st.lists(st.tuples(key_string, child), min_size=1, max_size=4).map(make_dup)

    # malformed object variants: missing colon, double commas, trailing comma before closing, extra comma tokens
    def make_missing_colon(pairs):
        if not pairs:
            return "{"
        # omit colon for first pair
        k, v = pairs[0]
        rest = pairs[1:]
        inner = k + v  # missing colon
        if rest:
            inner += "," + ",".join(k2 + ":" + v2 for (k2, v2) in rest)
        return "{" + inner + "}"
    missing_colon_obj = st.lists(st.tuples(key_string, child), min_size=1, max_size=4).map(make_missing_colon)

    def make_double_commas(pairs):
        if not pairs:
            return "{,}"
        # insert an extra comma after first item
        parts = [pairs[0][0] + ":" + pairs[0][1]]
        parts.append("")  # empty spot leads to double comma
        parts += [k + ":" + v for (k, v) in pairs[1:]]
        return "{" + ",".join(parts) + "}"
    double_commas_obj = st.lists(st.tuples(key_string, child), min_size=0, max_size=4).map(make_double_commas)

    def make_trailing_comma_obj(pairs):
        if not pairs:
            return "{,}"
        inner = ",".join(k + ":" + v for (k, v) in pairs)
        return "{" + inner + ",}"
    trailing_comma_obj = st.lists(st.tuples(key_string, child), min_size=0, max_size=4).map(make_trailing_comma_obj)

    # Valid arrays
    valid_arr = st.lists(child, min_size=0, max_size=6).map(make_array_from_vals)

    # Malformed arrays: double commas, trailing comma, missing commas
    def make_double_commas_arr(vals):
        if not vals:
            return "[,]"
        parts = []
        for i, v in enumerate(vals):
            parts.append(v)
            if i == 0:
                parts.append("")  # empty entry -> double comma
        return "[" + ",".join(parts) + "]"
    double_commas_arr = st.lists(child, min_size=0, max_size=6).map(make_double_commas_arr)

    def make_trailing_comma_arr(vals):
        if not vals:
            return "[,]"
        return "[" + ",".join(vals) + ",]"
    trailing_comma_arr = st.lists(child, min_size=0, max_size=6).map(make_trailing_comma_arr)

    def make_missing_commas(vals):
        # join values without commas between first two -> missing comma
        if len(vals) < 2:
            return "[" + ",".join(vals) + "]"
        inner = vals[0] + vals[1]  # missing comma between first two
        if len(vals) > 2:
            inner += "," + ",".join(vals[2:])
        return "[" + inner + "]"
    missing_commas_arr = st.lists(child, min_size=0, max_size=6).map(make_missing_commas)

    # Mix many possibilities
    return st.one_of(
        valid_obj,
        dup_keys_obj,
        missing_colon_obj,
        double_commas_obj,
        trailing_comma_obj,
        valid_arr,
        double_commas_arr,
        trailing_comma_arr,
        missing_commas_arr,
        # also allow deeply nested explicit small wrappers to combine arrays and objects
        st.builds(lambda a, b: '{"arr":' + a + ',"obj":' + b + '}', valid_arr, valid_obj),
    )

# Build recursive value strategy. Use a high max_leaves to allow deep nesting near parser limit (~2048)
value_strategy = st.recursive(leaf_value, extend, max_leaves=2100)

# Occasionally append trailing garbage after a complete value (the parser accepts trailing content)
trailing_garbage_piece = st.one_of(
    st.text(alphabet=SAFE_ASCII + ''.join(CONTROL_CHARS), min_size=1, max_size=20),
    st.just("garbage"),
    st.just("  abc"),
    st.just("\nxyz"),
    st.just("/*not allowed here*/"),
)

value_with_trailing = st.one_of(
    value_strategy,
    st.tuples(value_strategy, trailing_garbage_piece).map(lambda t: t[0] + t[1])
)

# Final top-level strategy: produce the JSON-text candidates as str.
# This includes many edgecases: empty {} and [], deep nesting (via recursion with high max_leaves),
# duplicate keys (constructed in extend), extreme numbers, unicode escapes, surrogate escapes,
# embedded control bytes (except NUL), and malformed variants (unterminated strings, double commas, missing colons, leading +, .5, 01).
strategy = value_with_trailing