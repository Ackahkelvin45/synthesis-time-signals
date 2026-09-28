from hypothesis import strategies as st
import json

# Helper alphabets (no imports beyond allowed ones)
_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_SAFE_PUNCT = " ,-.:;_()[]{}<>!?@#%&*+="  # avoid quote and backslash here
_HEX = "0123456789abcdefABCDEF"

# Control characters we may embed inside strings (explicitly exclude NUL)
_CTRL_CHARS = [chr(i) for i in range(1, 32)]  # \x01 .. \x1f (exclude \x00)

# Escape sequences allowed
_escape_simple = st.sampled_from([r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'])
_escape_unicode = st.builds(lambda h: r'\u' + h, st.text(_HEX, min_size=4, max_size=4))
# Surrogate-range escapes (high and low surrogates)
_escape_surrogate = st.sampled_from([r'\uD800', r'\uDBFF', r'\uDC00', r'\uDFFF'])

# String content pieces: either raw safe text, a control char, or an escape sequence
_string_text_piece = st.text(_ALPHA + _DIGITS + _SAFE_PUNCT, min_size=1, max_size=8)
_string_piece = st.one_of(_string_text_piece, st.sampled_from(_CTRL_CHARS), _escape_simple, _escape_unicode, _escape_surrogate)

# Well-formed JSON string: quoted and composed of pieces.
well_formed_string = st.lists(_string_piece, min_size=0, max_size=8).map(lambda parts: '"' + ''.join(parts) + '"')

# Unterminated or malformed string variants (start quote but no end, or missing start)
unterminated_string = st.lists(_string_piece, min_size=0, max_size=8).map(lambda parts: '"' + ''.join(parts))  # missing closing quote
no_start_quote_string = st.lists(_string_piece, min_size=1, max_size=8).map(lambda parts: ''.join(parts) + '"')  # missing opening quote

# Combined string token strategy including edge cases (never include literal NUL char)
string_token = st.one_of(
    well_formed_string,
    _escape_unicode.map(lambda u: '"' + u + '"'),  # single unicode escape as string
    _escape_surrogate.map(lambda u: '"' + u + '"'),  # surrogate escape inside quotes
    unterminated_string,
    no_start_quote_string,
)

# Number token variants, including many malformed/edge forms
_integer = st.integers(min_value=-10**6, max_value=10**6).map(str)
_leading_zero_int = st.integers(min_value=0, max_value=999).map(lambda n: "0" + str(n))  # e.g., 01, 00...
_decimal = st.tuples(st.integers(min_value=-9999, max_value=9999), st.integers(min_value=0, max_value=9999)).map(lambda t: f"{t[0]}.{abs(t[1])}")
_dot_leading = st.sampled_from([".5", "+.5", "-.5"])
_trailing_dot = st.sampled_from(["1.", "123."])
_lone_sign = st.sampled_from(["-", "+"])  # parser treats lone '-' as zero; include plus as near-valid
_sign_dot = st.sampled_from(["-.", "+."])  # malformed
_leading_plus = st.integers(min_value=0, max_value=10**6).map(lambda n: "+" + str(n))
_exp_normal = st.tuples(st.integers(min_value=1, max_value=9), st.integers(min_value=-10, max_value=10)).map(lambda t: f"{t[0]}e{t[1]}")
_exp_large = st.sampled_from(["1e309", "-1e309", "1e9999", "9.99e999"])  # likely overflow non-finite
_exp_with_leading_zeros = st.builds(lambda m, e: f"{m}e{e}", st.integers(min_value=1, max_value=9), st.text(_DIGITS, min_size=1, max_size=3))
_leading_zero_allowed_exp = st.text(_DIGITS, min_size=1, max_size=3).map(lambda s: "1e" + (s if s else "0"))

number_token = st.one_of(
    _integer,
    _leading_zero_int,
    _decimal,
    _dot_leading,
    _trailing_dot,
    _lone_sign,
    _sign_dot,
    _leading_plus,
    _exp_normal,
    _exp_large,
    _exp_with_leading_zeros,
    _leading_zero_allowed_exp,
)

# Literals
literal_token = st.one_of(*([st.just("true")] * 6 + [st.just("false")] * 6 + [st.just("null")]))

# Malformed tokens and near-valid examples to exercise parser leniency/strictness
malformed_tokens = st.sampled_from([
    "1abc",      # trailing garbage after number (parser accepts leading value)
    "01",        # leading zero in integer (grammar forbids it)
    "+1",        # leading plus (near-valid)
    "NaN",       # definitely non-number (malformed)
    "Infinity",  # non-finite literal
])

# Base (non-recursive) value strategy
leaf_value = st.one_of(
    string_token,
    number_token,
    literal_token,
    malformed_tokens,
)

# Keys for objects: generate some strings (without surrounding quotes yet), may include duplicates
_key_piece = st.text(_ALPHA + _DIGITS + "_-", min_size=0, max_size=6)
key_string = _key_piece.map(lambda s: s)  # we'll add quotes when building pairs

# Now build recursive object/array construction using st.recursive
def extend(children):
    # pair generation (well-formed and malformed variants)
    # well-formed pair: "key":value
    pair_well = st.tuples(key_string, children).map(lambda kv: f'"{kv[0]}":{kv[1]}')
    # missing colon: "key" value
    pair_missing_colon = st.tuples(key_string, children).map(lambda kv: f'"{kv[0]}"{kv[1]}')
    # empty key allowed: "" : value
    pair_empty_key = children.map(lambda v: f'""{":" if True else ""}{v}')  # keep as well-formed with empty key
    # duplicate-key-friendly list of pairs (the lists strategy below allows duplicates)
    pair_variant = st.one_of(pair_well, pair_missing_colon, pair_empty_key)

    # object variants
    def obj_from_pairs(pairs):
        # pairs is a Python list of strings
        if not pairs:
            return "{}"
        # choose between well-formed join, trailing comma, double-comma insertion
        joined = ",".join(pairs)
        trailing = "{" + joined + ",}"
        double_comma = "{" + joined.replace(",", ",,") + "}"
        well = "{" + joined + "}"
        return st.sampled_from([well, trailing, double_comma]).example()  # note: .example used only internally; we avoid it below

    # Instead of using example(), we produce strategies for object forms:
    pairs_list = st.lists(pair_variant, min_size=1, max_size=4)  # duplicates allowed
    obj_well = pairs_list.map(lambda lst: "{" + ",".join(lst) + "}")
    obj_trailing = pairs_list.map(lambda lst: "{" + ",".join(lst) + ",}")
    # double commas: insert an extra comma between every pair (may produce invalid JSON)
    obj_double_commas = pairs_list.map(lambda lst: "{" + ",,".join(lst) + "}")
    obj_missing_pairs = st.tuples(key_string).map(lambda t: "{" + f'"{t[0]}"' + "}")  # single key with no value
    obj_strategy = st.one_of(obj_well, obj_trailing, obj_double_commas, obj_missing_pairs, st.just("{}"))

    # arrays
    arr_values_list = st.lists(children, min_size=1, max_size=6)
    arr_well = arr_values_list.map(lambda lst: "[" + ",".join(lst) + "]")
    arr_trailing = arr_values_list.map(lambda lst: "[" + ",".join(lst) + ",]")
    arr_double_commas = arr_values_list.map(lambda lst: "[" + ",,".join(lst) + "]")
    arr_missing_commas = arr_values_list.map(lambda lst: "[" + " ".join(lst) + "]")
    arr_strategy = st.one_of(arr_well, arr_trailing, arr_double_commas, arr_missing_commas, st.just("[]"))

    return st.one_of(obj_strategy, arr_strategy)

# Build recursive value strategy (objects and arrays built via extend)
value_recursive = st.recursive(leaf_value, extend, max_leaves=50)

# Deep nesting near the parser limit: create explicit deep arrays or objects (but avoid literal NUL)
# Use small probability of generating these huge strings to concentrate around the nested cap
deep_array = st.integers(min_value=1800, max_value=2050).flatmap(
    lambda n: st.just("[" * n + "0" + "]" * n)
)
deep_object = st.integers(min_value=1800, max_value=2050).flatmap(
    lambda n: st.just("{" + '"k":' + ("[" * (n - 1) + "0" + "]" * (n - 1)) + "}")
)

# Top-level trailing content after a complete value is accepted by the parser; include it sometimes
with_trailing = st.tuples(value_recursive, st.sampled_from(["", " ", "garbage", "xyz", "\n", " //extra"])).map(lambda t: t[0] + t[1])

# Sometimes produce a lone '-' or '-.' which the parser treats leniently
lone_sign_variant = st.sampled_from(["-", "-."])

# Compose final strategy: mix of recursive values, deep nests, trailing-content variants, and direct leaves
strategy = st.one_of(
    value_recursive,
    deep_array,
    deep_object,
    with_trailing,
    lone_sign_variant,
)