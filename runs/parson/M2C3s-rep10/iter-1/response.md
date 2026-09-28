```python
from hypothesis import strategies as st
import json

# Alphabet pieces (avoid raw NUL '\x00')
_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
_PUNCT = ".,:;_+-*/%&|?=!@#^()[]<>~`"
_KEY_ALPH = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"

# Simple escape pieces: JSON simple escapes and unicode escapes (including surrogate range)
_simple_esc = st.sampled_from(["\\n", "\\t", "\\r", "\\b", "\\f", "\\\"", "\\\\", "\\/"])
_hex4 = st.integers(min_value=0, max_value=0xFFFF).map(lambda x: "\\u" + format(x, "04x"))
_surrogate = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda x: "\\u" + format(x, "04x"))

# Safe chunks for string content (excluding " and \ and NUL)
_safe_chunk = st.text(alphabet=_ALPHA + _PUNCT, min_size=0, max_size=8)

# Build JSON-like STRING variants (valid and intentionally malformed)
_string_piece = st.one_of(_safe_chunk, _simple_esc, _hex4, _surrogate)
# Valid quoted string
quoted_string = st.lists(_string_piece, min_size=0, max_size=6).map(lambda parts: '"' + "".join(parts) + '"')
# Unterminated string (missing closing quote)
unterminated_string = st.lists(_string_piece, min_size=1, max_size=6).map(lambda parts: '"' + "".join(parts))
# Missing opening quote (dangling closing quote)
missing_open_quote = st.lists(_string_piece, min_size=1, max_size=6).map(lambda parts: "".join(parts) + '"')
# String with unescaped control-like token sequences (near-invalid)
raw_control_inside = st.lists(st.one_of(st.text(alphabet="\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10", min_size=1, max_size=3), _safe_chunk, _simple_esc), min_size=1, max_size=4).map(lambda ps: '"' + "".join(ps) + '"')

# NUMBER generators
# Valid integer: either '0' or non-zero leading digit followed by digits (no leading zeros)
_nonzero_int = st.tuples(st.sampled_from(list("123456789")), st.text(alphabet="0123456789", min_size=0, max_size=18)).map(lambda t: t[0] + t[1])
_int_part = st.one_of(st.just("0"), _nonzero_int)
_frac = st.one_of(st.just(""), st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=12)))
_exp = st.one_of(
    st.just(""),
    st.builds(lambda s, d: "e" + (s if s else "") + d,
              st.one_of(st.just(""), st.sampled_from(["+", "-"])),
              st.text(alphabet="0123456789", min_size=1, max_size=5))
)
_valid_number = st.builds(lambda sign, i, f, e: (sign if sign else "") + i + f + e,
                          st.one_of(st.just(""), st.just("-")),
                          _int_part,
                          _frac,
                          _exp)

# Near-valid / malformed number variants
_plus_leading = st.builds(lambda s: "+" + s, st.builds(lambda i, f, e: i + f + e, _int_part, _frac, _exp))
_leading_dot = st.builds(lambda digits: "." + digits, st.text(alphabet="0123456789", min_size=1, max_size=10))  # .5 style
_trailing_dot = st.builds(lambda i: i + ".", st.one_of(st.just("0"), _nonzero_int))  # 1. style (invalid per grammar)
_leading_zero_bad = st.builds(lambda rest: "0" + rest, st.text(alphabet="0123456789", min_size=1, max_size=5))  # 01
_extreme_exp = st.sampled_from(["1e309", "-1e400", "9e9999", "1e10000", "1e-10000"])
_lone_signs = st.sampled_from(["-", "-."])  # parser accepts these leniently

number_variant = st.one_of(_valid_number, _plus_leading, _leading_dot, _trailing_dot, _leading_zero_bad, _extreme_exp, _lone_signs)

# Base non-recursive values for st.recursive
base_value = st.one_of(
    quoted_string,
    number_variant,
    st.sampled_from(["true", "false", "null"]),
    st.just("{}"),
    st.just("[]"),
    unterminated_string,
    missing_open_quote,
    raw_control_inside,
)

# Recursive construction for obj and arr using st.recursive
def _extend(children):
    # Proper object: list of pairs "k":value
    def make_obj(pairs):
        # pairs: list of (k, v) tuples where k is key string and v is already a serialized value string
        inner = ",".join('"' + k + '":' + v for k, v in pairs)
        return "{" + inner + "}"
    obj = st.lists(st.tuples(st.text(alphabet=_KEY_ALPH, min_size=0, max_size=8), children),
                   min_size=0, max_size=6).map(make_obj)

    # Duplicate-key object: create two pairs with the same key (to exercise duplicate-key rejection)
    dup_obj = st.tuples(st.text(alphabet=_KEY_ALPH, min_size=1, max_size=6), children, children).map(
        lambda t: '{"%s":%s,"%s":%s}' % (t[0], t[1], t[0], t[2])
    )

    # Malformed object variants: trailing comma, double commas, missing colon
    trailing_comma_obj = st.lists(st.tuples(st.text(alphabet=_KEY_ALPH, min_size=1, max_size=6), children),
                                  min_size=1, max_size=5).map(
        lambda pairs: "{" + ",".join('"' + k + '":' + v for k, v in pairs) + ",}"
    )
    double_comma_obj = st.lists(st.tuples(st.text(alphabet=_KEY_ALPH, min_size=1, max_size=6), children),
                                min_size=2, max_size=5).map(
        lambda pairs: "{" + ",,".join('"' + k + '":' + v for k, v in pairs) + "}"
    )
    missing_colon_obj = st.lists(st.tuples(st.text(alphabet=_KEY_ALPH, min_size=1, max_size=6), children),
                                 min_size=1, max_size=4).map(
        lambda pairs: "{" + ",".join('"' + k + '"' + v for k, v in pairs) + "}"
    )

    # Proper array
    arr = st.lists(children, min_size=0, max_size=6).map(lambda vals: "[" + ",".join(vals) + "]")

    # Malformed array variants: trailing comma, double commas
    trailing_comma_arr = st.lists(children, min_size=1, max_size=6).map(lambda vals: "[" + ",".join(vals) + ",]")
    double_comma_arr = st.lists(children, min_size=2, max_size=6).map(lambda vals: "[" + ",,".join(vals) + "]")

    return st.one_of(obj, dup_obj, trailing_comma_obj, double_comma_obj, missing_colon_obj, arr, trailing_comma_arr, double_comma_arr)

recursive_values = st.recursive(base_value, _extend, max_leaves=200)

# Deep nesting near parser limit (concentrate around 1900-2048)
deep_array = st.integers(min_value=1900, max_value=2048).map(lambda n: ("[" * n) + "0" + ("]" * n))
deep_object = st.integers(min_value=1900, max_value=2048).map(lambda n: ("{" + '"a":') * n + "0" + ("}" * n))

# Duplicate-keys explicit examples
duplicate_keys_examples = st.sampled_from([
    '{"k":0,"k":1}',
    '{"k": {"k":1},"k":2}',
    '{"a":1,"a":2,"a":3}'
])

# Trailing content after a complete value (parser accepts trailing content)
trailing_content = st.one_of(
    st.just("[]garbage"),
    st.just("1abc"),
    st.builds(lambda v, tail: v + tail,
              st.one_of(quoted_string, _valid_number, st.sampled_from(["true", "null", "false"]), st.just("[]"), st.just("{}")),
              st.text(alphabet=_ALPHA + _PUNCT, min_size=1, max_size=10))
)

# Misc malformed snippets: lone tokens, comment-like (though parser strict entry won't handle comments)
misc_malformed = st.sampled_from([
    '[,]',    # double comma like
    '[1,,2]', # double comma
    '{"a" 1}', # missing colon
    '{"a":1 "b":2}', # missing comma
    '{"unterminated": "oops}', # unterminated string inside
    '"unterminated top', # top-level unterminated
    '+1', # leading plus
    '.5', # leading dot
    '01', # leading zero
    '1.', # trailing dot
])

# Combine many variants into final top-level strategy
strategy = st.one_of(
    recursive_values,
    deep_array,
    deep_object,
    duplicate_keys_examples,
    trailing_content,
    misc_malformed,
    # also allow single tokens (valid or near-valid)
    quoted_string,
    unterminated_string,
    missing_open_quote,
    number_variant,
)
```