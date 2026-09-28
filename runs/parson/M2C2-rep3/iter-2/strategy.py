from hypothesis import strategies as st
import json

# Helper pieces
_HEX4 = st.builds(lambda a,b,c,d: "".join([a,b,c,d]),
                  st.sampled_from("0123456789abcdefABCDEF"),
                  st.sampled_from("0123456789abcdefABCDEF"),
                  st.sampled_from("0123456789abcdefABCDEF"),
                  st.sampled_from("0123456789abcdefABCDEF"))

# Safe printable characters for valid JSON strings (no quote, no backslash, no NUL, no control)
_SAFE_CHARS = (
    [chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C) and c != 0x00]
    + ["\u00A0", "\u2000", "©", "✓"]
)
safe_char = st.sampled_from(_SAFE_CHARS)

# Escape fragments
basic_esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
unicode_esc = _HEX4.map(lambda h: '\\u' + h)
unicode_surrogate = st.sampled_from(['\\uD800', '\\uD834', '\\uDFFF', '\\uDC00', '\\uD83D', '\\uDE00'])

escape_fragment = st.one_of(basic_esc, unicode_esc, unicode_surrogate)

# Valid string literal fragments (no control chars), plus some escapes
valid_str_fragment = st.one_of(safe_char, escape_fragment)

# Malformed / near-valid fragments: include control bytes except NUL, and bad escapes
_control_chars = [chr(c) for c in range(1, 0x20) if c != 0x00]
bad_escape = st.sampled_from(['\\uZZZZ', '\\x00', '\\'])  # intentionally malformed escapes
malformed_fragment = st.one_of(st.sampled_from(_control_chars), bad_escape, st.just('"'), st.just('\n'))

# Valid string literal: quoted, may include escapes
string_literal_valid = st.lists(valid_str_fragment, min_size=0, max_size=6).map(lambda parts: '"' + ''.join(parts) + '"')

# Unterminated string (missing closing quote)
string_literal_unterminated = st.lists(st.one_of(valid_str_fragment, malformed_fragment), min_size=0, max_size=6).map(lambda parts: '"' + ''.join(parts))

# String with explicit \u0000 (escaped NUL) and surrogate escapes
string_literal_with_u0000 = st.lists(st.one_of(valid_str_fragment, st.just('\\u0000'), st.sampled_from(['\\uD800','\\uD801','\\uDFFF'])), min_size=0, max_size=6).map(lambda parts: '"' + ''.join(parts) + '"')

# String containing raw control characters (still not raw NUL)
string_literal_raw_control = st.lists(st.one_of(valid_str_fragment, st.sampled_from(_control_chars)), min_size=0, max_size=6).map(lambda parts: '"' + ''.join(parts) + '"')

# Numbers: mix of valid, extreme, and near-malformed forms
int_no_leading_zero = st.one_of(
    st.just("0"),
    st.sampled_from(list("123456789")).map(lambda a: a),
    st.integers(min_value=1, max_value=10).map(str)
)
# Simpler number generators by explicit variants to control edge cases:
number_valid_integer = st.one_of(
    st.integers(min_value=0, max_value=999999).map(str),
    st.integers(min_value=-999999, max_value=-1).map(str)
)
number_valid_fraction = st.one_of(
    st.tuples(st.integers(min_value=-9999, max_value=9999).map(str), st.integers(min_value=1, max_value=99999).map(lambda s: '.' + str(s))).map(lambda t: t[0] + t[1]),
    st.tuples(st.integers(min_value=-9999, max_value=9999).map(str), st.just('.'), st.integers(min_value=0, max_value=99999).map(str)).map(lambda t: t[0] + t[1] + t[2])  # allows "1." (near-valid)
)
number_with_exponent = st.one_of(
    st.integers(min_value=-999, max_value=999).map(str).flatmap(lambda base: st.one_of(st.just(base + 'e+308'), st.just(base + 'e309'), st.just(base + 'E9999'), st.just(base + 'e-9999'))),
    st.sampled_from(['1e309', '2E308', '1e-9999', '-1e9999', '1e308', '9.99e307'])
)
number_malformed = st.sampled_from(['+.5', '.5', '01', '+1', '-', '-.', '1.', '1.e10', '1e', 'e10', '++1'])
number_strategy = st.one_of(number_valid_integer, number_valid_fraction, number_with_exponent, number_malformed)

# Keywords
keyword = st.sampled_from(["true", "false", "null"])

# Small building block for a value (leaves)
leaf_value = st.one_of(
    string_literal_valid,
    string_literal_with_u0000,
    string_literal_raw_control,
    string_literal_unterminated,
    number_strategy,
    keyword
)

# Deep nesting helpers: mostly near parser limit (~2048). We avoid absurdly huge sizes.
deep_nesting_near_limit = st.one_of(
    st.integers(min_value=2000, max_value=2056),
    st.integers(min_value=1960, max_value=2048),
    st.integers(min_value=0, max_value=8)
)

def _obj_variants(values_strategy):
    # Valid object with up to a few pairs
    pair = st.tuples(string_literal_valid, values_strategy).map(lambda kv: kv[0] + ":" + kv[1])
    valid_obj = st.lists(pair, min_size=0, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}")
    # Object with duplicate keys (explicit small pattern)
    dup_obj = st.lists(values_strategy, min_size=2, max_size=4).map(
        lambda vals: '{"dup":' + vals[0] + ',"dup":' + vals[1] + (' , "dup":' + vals[2] if len(vals) > 2 else '') + '}'
    )
    # Malformed object variants: missing colon, double commas, trailing comma
    malformed_missing_colon = st.lists(st.tuples(string_literal_valid, values_strategy).map(lambda kv: kv[0] + kv[1]), min_size=1, max_size=3).map(lambda parts: "{" + ",".join(parts) + "}")
    double_commas = st.builds(lambda pieces: "{" + pieces + "}", st.just('"a":1,, "b":2'))
    trailing_comma = st.lists(pair, min_size=1, max_size=4).map(lambda pairs: "{" + ",".join(pairs) + ",}")
    # Deep nested object: {"a": {"a": {...  } } }
    deep_obj = deep_nesting_near_limit.map(lambda n: ("{" + '"a":' ) * n + '0' + ("}" ) * n)
    return st.one_of(valid_obj, dup_obj, malformed_missing_colon, double_commas, trailing_comma, deep_obj)

def _arr_variants(values_strategy):
    # Valid array
    valid_arr = st.lists(values_strategy, min_size=0, max_size=6).map(lambda vals: "[" + ",".join(vals) + "]")
    # Malformed: double commas, trailing comma
    double_commas = st.just("[1,,2]")
    trailing_comma = st.lists(values_strategy, min_size=1, max_size=6).map(lambda vals: "[" + ",".join(vals) + ",]")
    missing_commas = st.lists(values_strategy, min_size=2, max_size=4).map(lambda vals: "[" + "".join(vals) + "]")
    # Deep nested array: [ [ [ 0 ] ] ]
    deep_arr = deep_nesting_near_limit.map(lambda n: ("[" * n) + "0" + ("]" * n))
    return st.one_of(valid_arr, double_commas, trailing_comma, missing_commas, deep_arr)

# Use st.recursive to assemble nested JSON text strings.
# children strategy will be used as textual values (already strings)
def _extend(children):
    return st.one_of(
        _obj_variants(children),
        _arr_variants(children)
    )

# Primary recursive strategy for JSON text as strings
# Limit max_leaves so tests don't explode
strategy = st.recursive(leaf_value, _extend, max_leaves=50)

# Additional top-level variants that the parser accepts or is interesting:
# - trailing content after a complete value
# - a lone '-' or '-.' (the parser treats as 0)
# We'll incorporate by broadening the final strategy to include these forms.
strategy = st.one_of(
    strategy,
    st.tuples(strategy, st.sampled_from([" ", "  ", "garbage", "xyz", "\nXYZ"])).map(lambda t: t[0] + t[1]),
    st.sampled_from(["-", "-.", "+", "+1", ".5", "01", "1e309", "1e9999", "Infinity", "NaN"])
)