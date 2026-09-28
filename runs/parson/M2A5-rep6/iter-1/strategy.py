from hypothesis import strategies as st
import json

# Safe pieces for building JSON string literals (avoid raw NUL '\x00')
safe_char = st.characters(min_codepoint=0x20, blacklist_characters=['"', '\\'])
safe_text = st.text(alphabet=safe_char, min_size=0, max_size=8)

# Escape sequences and unicode-escapes (including surrogate-range examples)
simple_escapes = st.one_of(*(st.just(s) for s in ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']))
hex4 = st.text('0123456789abcdefABCDEF', min_size=4, max_size=4)
unicode_escape = st.builds(lambda h: '\\u' + h, hex4)
surrogate_escape = st.one_of(st.just('\\uD800'), st.just('\\uDC00'), st.just('\\uDFFF'))

# Control bytes except NUL (produce as raw control inside string literal to exercise parser)
control_char = st.characters(min_codepoint=1, max_codepoint=0x1F, blacklist_characters=['\x00', '"', '\\'])
control_piece = control_char.map(lambda c: c)

# Pieces that may appear inside a JSON string literal (valid or intentionally malformed)
string_piece = st.one_of(safe_text, simple_escapes, unicode_escape, surrogate_escape, control_piece)

# Valid-ish JSON string literal (may contain escaped \u0000 but never raw NUL)
json_string = st.lists(string_piece, min_size=0, max_size=5).map(''.join).map(lambda s: '"' + s + '"')

# Unterminated string variants (start-quote without ending quote)
unterminated_string = st.lists(string_piece, min_size=0, max_size=6).map(''.join).map(lambda s: '"' + s)

# Numbers: valid forms and near-valid / malformed / extreme exponents (including overflow like 1e309)
valid_integer = st.integers(min_value=0, max_value=10_000).map(str)
neg_integer = st.integers(min_value=-10_000, max_value=-1).map(str)
fraction = st.tuples(st.text('0123456789', min_size=1, max_size=8), st.text('0123456789', min_size=1, max_size=8)).map(lambda t: t[0] + '.' + t[1])
exp = st.integers(min_value=-1000, max_value=1000).map(lambda e: 'e' + ('+' if e >= 0 else '') + str(e))
with_exp = st.tuples(st.text('0123456789', min_size=1, max_size=10), exp).map(lambda t: t[0] + t[1])
# Extreme/overflow exponents and mantissas
huge_exp = st.one_of(st.just('1e309'), st.just('1e9999'), st.builds(lambda m, e: m + 'e' + str(e),
                                                                  st.text('9', min_size=50, max_size=300),
                                                                  st.integers(min_value=300, max_value=10000)))
# Malformed/near-valid numbers
leading_plus = st.tuples(st.just('+'), st.integers(min_value=0, max_value=9999)).map(lambda t: t[0] + str(t[1]))
leading_dot = st.builds(lambda frac: '.' + frac, st.text('0123456789', min_size=1, max_size=8))
trailing_dot = st.builds(lambda i: i + '.', st.text('0123456789', min_size=1, max_size=8))
leading_zero_bad = st.builds(lambda s: '0' + s, st.text('0123456789', min_size=1, max_size=8))
number_literal = st.one_of(valid_integer, neg_integer, fraction, with_exp, huge_exp,
                           leading_plus, leading_dot, trailing_dot, leading_zero_bad)

# JSON literals
literals = st.sampled_from(['true', 'false', 'null'])

# Base (non-recursive) JSON value pieces
base_value = st.one_of(json_string, number_literal, literals)

# Helper key strategy for object member keys (JSON strings)
key_strat = json_string

# A strategy to construct malformed object pair strings in several ways
def pair_from(key_s, value_s):
    # produce proper pair and some malformed variants (missing colon, extra colon, bare key)
    proper = st.tuples(key_s, value_s).map(lambda kv: kv[0] + ':' + kv[1])
    missing_colon = st.tuples(key_s, value_s).map(lambda kv: kv[0] + kv[1])  # no colon
    extra_colon = st.tuples(key_s, value_s).map(lambda kv: kv[0] + '::' + kv[1])
    bare_key = key_s  # key only
    return st.one_of(proper, missing_colon, extra_colon, bare_key)

# Recursive construction for arrays and objects using st.recursive
def extend_children(children):
    # arrays: empty [], normal, trailing comma, double-comma, extra garbage inside
    arrays = st.one_of(
        st.just('[]'),
        st.lists(children, min_size=0, max_size=6).map(lambda elems: '[' + ','.join(elems) + ']'),
        st.lists(children, min_size=1, max_size=6).map(lambda elems: '[' + ','.join(elems) + ',]'),  # trailing comma
        st.lists(children, min_size=2, max_size=6).map(lambda elems: '[' + ','.join(elems[:1]) + ',,' + ','.join(elems[1:]) + ']'),  # double comma
        st.lists(children, min_size=0, max_size=6).map(lambda elems: '[' + ','.join(elems) + ']garbage')  # trailing content
    )

    # objects: empty {}, normal, duplicate keys, trailing comma, missing commas, malformed commas
    def mk_obj_from_pairs(pairs):
        # pairs is list of "key:value" strings or malformed pair strings
        if not pairs:
            return '{}'
        return '{' + ','.join(pairs) + '}'

    pairs_list = st.lists(pair_from(key_strat, children), min_size=0, max_size=6)
    objs = st.one_of(
        pairs_list.map(lambda ps: mk_obj_from_pairs(ps)),
        pairs_list.map(lambda ps: mk_obj_from_pairs(ps)[:-1] + ',}'),  # make trailing-comma malformed (replace last char before final brace)
        # duplicate keys: create few unique keys then repeat to force duplication
        st.deferred(lambda: st.builds(
            lambda keys, vals: '{' + ','.join(k + ':' + v for k, v in zip(keys, vals)) + '}',
            st.lists(key_strat, min_size=1, max_size=3).map(lambda ks: ks * 2),  # duplicate keys by repetition
            st.lists(children, min_size=2, max_size=6)
        )),
        # missing commas: glue pairs without commas occasionally
        pairs_list.map(lambda ps: '{' + ''.join(ps) + '}'),
        # double commas in objects
        pairs_list.map(lambda ps: '{' + (',,'.join(ps) if ps else '') + '}')
    )
    return st.one_of(arrays, objs)

# Build a recursive JSON value strategy (strings representing JSON text)
recursive_value = st.recursive(base_value, extend_children, max_leaves=50)

# Deep nesting generator concentrating near the parser limit (~2048)
deep_nesting = st.one_of(
    st.integers(min_value=1900, max_value=2050).map(lambda d: '[' * d + '0' + ']' * d),   # deep arrays
    st.integers(min_value=1900, max_value=2050).map(lambda d: '{' * d + '"k":0' + '}' * d)  # deep (malformed) repeated braces
)

# Trailing garbage after a complete value (parser is lenient and accepts leading value)
trailing_garbage = st.tuples(recursive_value, st.text(min_size=1, max_size=20)).map(lambda t: t[0] + t[1])

# A few intentionally unterminated / cut inputs: start of an object/array and then truncated
truncated_structures = st.one_of(
    st.just('['),
    st.just('{'),
    st.builds(lambda s: s[:-1], recursive_value).filter(lambda s: len(s) > 0)  # chop off last char
)

# Combine many modes to maximize coverage of edge-cases and malformed-but-near-valid inputs
strategy = st.one_of(
    recursive_value,
    deep_nesting,
    trailing_garbage,
    unterminated_string,
    truncated_structures,
    # raw single tokens too
    base_value,
    literals,
    number_literal
)