from hypothesis import strategies as st
import json

# Basic pieces
_hex4 = st.text("0123456789abcdefABCDEF", min_size=4, max_size=4)
_hexdigit = st.sampled_from(list("0123456789abcdefABCDEF"))
_safe_char = st.characters(min_codepoint=1, blacklist_characters='"\\"')  # allow control chars except NUL, disallow quotes/backslash
_simple_esc = st.sampled_from(['\\\\', '\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
_unicode_escape = st.builds(lambda h: '\\u' + h, _hex4)
_surrogate_escape = st.integers(min_value=0xD800, max_value=0xDFFF).map(lambda i: '\\u' + format(i, '04X'))
_invalid_escape = st.sampled_from(['\\q', '\\x', '\\z', '\\9'])

# JSON string variants (valid, escaped, surrogate, malformed/unterminated)
_quoted_valid = st.lists(st.one_of(_safe_char, _simple_esc, _unicode_escape, _surrogate_escape), min_size=0, max_size=12).map(lambda parts: '"' + ''.join(parts) + '"')
_quoted_unterminated = st.lists(st.one_of(_safe_char, _simple_esc, _unicode_escape, _surrogate_escape), min_size=0, max_size=12).map(lambda parts: '"' + ''.join(parts))  # missing closing quote
_quoted_bad_escape = st.lists(st.one_of(_safe_char, _simple_esc, _unicode_escape, _invalid_escape), min_size=0, max_size=12).map(lambda parts: '"' + ''.join(parts) + '"')

# Keys for objects generally use quoted strings (but we include malformed ones as well)
_key_string = st.one_of(_quoted_valid, _quoted_bad_escape, _quoted_unterminated)

# NUMBER generation: both grammar-valid and near-valid / malformed variants, including huge exponents
_digits = st.text("0123456789", min_size=1, max_size=10)
_digits_opt = st.text("0123456789", min_size=0, max_size=10)
_nonzero_first = st.builds(lambda d, rest: d + rest, st.sampled_from(list("123456789")), _digits_opt)
_int_grammar = st.one_of(st.just("0"), _nonzero_first)
_frac = st.one_of(st.just(""), st.builds(lambda dot, d: dot + d, st.just("."), _digits))
_exp = st.one_of(st.just(""), st.builds(lambda e, s, d: e + s + d, st.sampled_from(['e', 'E']), st.sampled_from(['+', '-', '']), st.text("0123456789", min_size=1, max_size=6)))
_number_valid = st.builds(lambda sign, inten, frac, exp: sign + inten + frac + exp, st.one_of(st.just(""), st.just("-")), _int_grammar, _frac, _exp)

# Malformed/edge numbers
_number_leading_plus = st.builds(lambda body: "+" + body, _number_valid)
_number_dot_leading = st.builds(lambda digits: "." + digits, _digits)  # .5 style
_number_trailing_dot = st.builds(lambda i: i + ".", _int_grammar)      # 1. style
_number_leading_zero_bad = st.builds(lambda rest: "0" + rest, _digits)  # 01, 00 etc
_number_lone_sign = st.sampled_from(["-", "-.", "+", "+."])
_number_overflow_examples = st.sampled_from(["1e309", "-1e309", "1e10000", "9e9999", "1E309", "1e+309", "1e-9999"])

_number_strategy = st.one_of(_number_valid, _number_leading_plus, _number_dot_leading, _number_trailing_dot, _number_leading_zero_bad, _number_lone_sign, _number_overflow_examples)

# Literal tokens
_literals = st.sampled_from(["true", "false", "null"])

# Base value candidates (strings, numbers, literals)
_base_value = st.one_of(_quoted_valid, _quoted_bad_escape, _quoted_unterminated, _number_strategy, _literals)

# Build recursive obj/arr with st.recursive. Use composites inside extend to allow controlled malformed variants and duplicate keys.
def _extend(inner):
    # Arrays (valid, trailing comma, double commas, unterminated)
    def _make_array_from_list(vals):
        return "[" + ",".join(vals) + "]"
    def _make_array_trailing(vals):
        return "[" + ",".join(vals) + ("," if vals else "") + "]"
    def _make_array_double_commas(a, b):
        return "[" + ",".join(a) + ",," + ",".join(b) + "]"
    array_valid = st.lists(inner, min_size=0, max_size=6).map(_make_array_from_list)
    array_trailing = st.lists(inner, min_size=1, max_size=6).map(_make_array_trailing)
    array_double = st.tuples(st.lists(inner, min_size=0, max_size=3), st.lists(inner, min_size=0, max_size=3)).map(lambda t: _make_array_double_commas(t[0], t[1]))
    array_unterminated = st.lists(inner, min_size=1, max_size=6).map(lambda vals: "[" + ",".join(vals))  # missing closing bracket

    array_choices = st.one_of(array_valid, array_trailing, array_double, array_unterminated)

    # Objects (with options for duplicate keys and malformed variants). Use composite to draw inner values.
    @st.composite
    def object_builder(draw):
        # create a small pool of keys to increase chance of duplicates
        pool = draw(st.lists(_key_string, min_size=1, max_size=4))
        num_pairs = draw(st.integers(min_value=0, max_value=6))
        pairs = []
        for _ in range(num_pairs):
            key = draw(st.sampled_from(pool))
            val = draw(inner)
            pairs.append((key, val))
        variant = draw(st.sampled_from(["valid", "missing_colon", "trailing_comma", "double_comma", "unterminated"]))
        if variant == "valid":
            body = ",".join(k + ":" + v for (k, v) in pairs)
            return "{" + body + "}"
        elif variant == "missing_colon":
            if not pairs:
                return "{}"
            # pick one pair to remove colon
            i = draw(st.integers(0, len(pairs) - 1))
            pieces = []
            for idx, (k, v) in enumerate(pairs):
                if idx == i:
                    pieces.append(k + " " + v)
                else:
                    pieces.append(k + ":" + v)
            return "{" + ",".join(pieces) + "}"
        elif variant == "trailing_comma":
            body = ",".join(k + ":" + v for (k, v) in pairs)
            trailing = "," if pairs else ""
            return "{" + body + trailing + "}"
        elif variant == "double_comma":
            body = ",".join(k + ":" + v for (k, v) in pairs)
            return "{" + body + ",," + "}"
        else:  # unterminated
            return "{" + ",".join(k + ":" + v for (k, v) in pairs)

    return st.one_of(array_choices, object_builder())

# Recursive strategy for values (uses obj/arr constructors defined above)
_recursive_values = st.recursive(_base_value, _extend, max_leaves=50)

# Special deep nesting strategy: concentrate depths near parser MAX_NESTING (~2048).
# We never emit raw NUL here. These produce either many nested arrays or many nested objects like [[[...]]] or {{{...}}}
_deep_array = st.integers(min_value=1, max_value=2050).map(lambda n: "[" * n + "0" + "]" * n)
_deep_object = st.integers(min_value=1, max_value=2050).map(lambda n: "{" * n + '"k":0' + "}" * n)  # many open braces then one pair then many close braces
# Bias towards depths near the parser limit by mixing ranges
_deep_bias = st.one_of(
    st.integers(min_value=1900, max_value=2048).map(lambda n: "[" * n + "0" + "]" * n),
    st.integers(min_value=2000, max_value=2050).map(lambda n: "{" * n + '"k":0' + "}" * n),
    _deep_array,
    _deep_object
)

# Trailing content after a valid value (parser accepts trailing content)
_trailing_garbage = st.text(min_size=1, max_size=12, alphabet=st.characters(min_codepoint=1, blacklist_characters='\x00'))
_trailing_after_value = st.tuples(_recursive_values, _trailing_garbage).map(lambda t: t[0] + t[1])

# Some standalone malformed-but-interesting tokens (double commas, missing colon, lone '-')
_malformed_tokens = st.one_of(
    st.just('[,]'),
    st.just('{,}'),
    st.just('{"a",}'),
    st.just('{"a" 1}'),
    st.just('{"a":1,,}'),
    st.just('-.'),
    st.just('.'),
    st.just('+1'),
    st.just('01'),  # leading zero
    st.just('/* not allowed here */'),  # parser shouldn't see comments but include as near-valid
    st.just('// comment\n')
)

# Final top-level strategy: mix recursive, deep biased nest, trailing content, and malformed tokens.
_strategy = st.one_of(_recursive_values, _deep_bias, _trailing_after_value, _malformed_tokens)

# Never emit a raw NUL byte: filter out any candidate containing '\x00'
strategy = _strategy.filter(lambda s: '\x00' not in s)