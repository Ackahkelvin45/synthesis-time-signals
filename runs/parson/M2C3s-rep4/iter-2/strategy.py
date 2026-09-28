from hypothesis import strategies as st
import json

# Helper alphabets (avoid raw NUL '\x00')
_SAFE_CHARS = [chr(c) for c in range(0x20, 0x7F) if chr(c) not in {'"', '\\'}]  # printable except " and \
_CONTROL_CHARS = [chr(c) for c in range(1, 0x20)]  # control chars excluding NUL (0)
_HEX = '0123456789abcdefABCDEF'

def _u_escape():
    return st.builds(lambda h: '\\u' + h, st.text(alphabet=_HEX, min_size=4, max_size=4))

# valid/interesting JSON string pieces (including surrogate escapes)
_valid_string_piece = st.one_of(
    st.sampled_from(_SAFE_CHARS),
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    _u_escape(),
    st.builds(lambda s: s, st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-.:,', min_size=0, max_size=6))
)

_valid_json_string = st.lists(_valid_string_piece, min_size=0, max_size=8).map(''.join).map(lambda s: '"' + s + '"')

# unterminated strings: missing closing or missing opening
_unterminated_string = st.one_of(
    st.lists(_valid_string_piece, min_size=1, max_size=8).map(''.join).map(lambda s: '"' + s),  # missing closing
    st.lists(_valid_string_piece, min_size=1, max_size=8).map(''.join).map(lambda s: s + '"'),   # missing opening
)

# string containing raw control characters (but never raw NUL)
_control_string = st.lists(
    st.one_of(
        st.sampled_from(_SAFE_CHARS),
        st.sampled_from(_CONTROL_CHARS),
        _u_escape()
    ), min_size=0, max_size=8
).map(''.join).map(lambda s: '"' + s + '"')

# Various number forms: valid per grammar and malformed near-valid variants.
_int_valid = st.one_of(
    st.just("0"),
    st.builds(lambda s: s, st.text(alphabet='123456789', min_size=1, max_size=1)) .flatmap(
        lambda first: st.builds(lambda rest: first + rest, st.text(alphabet='0123456789', min_size=0, max_size=5))
    )
)

_fraction = st.one_of(
    st.just(''),  # no fraction
    st.builds(lambda d: '.' + d, st.text(alphabet='0123456789', min_size=1, max_size=6))
)

_exp = st.one_of(
    st.just(''),
    st.builds(lambda s: 'e' + s, st.text(alphabet='+-0123456789', min_size=1, max_size=6)),
    st.builds(lambda s: 'E' + s, st.text(alphabet='+-0123456789', min_size=1, max_size=6))
)

_valid_number = st.builds(lambda sign, i, f, e: (sign or '') + i + f + e,
                          st.one_of(st.just(''), st.just('-')),
                          _int_valid,
                          _fraction,
                          _exp)

# malformed/near-valid numbers
_malformed_number = st.one_of(
    # leading plus
    st.builds(lambda s: '+' + s, _valid_number),
    # bare fraction
    st.builds(lambda f: f, st.one_of(st.just('.5'), st.just('.123'))),
    # trailing dot
    st.builds(lambda i: i + '.', st.one_of(st.just('1'), st.just('123'))),
    # leading zero with extra digits (01)
    st.builds(lambda d: '0' + d, st.text(alphabet='0123456789', min_size=1, max_size=3)),
    # huge exponents that overflow (non-finite)
    st.one_of(st.just('1e309'), st.just('-1e400'), st.just('9e9999')),
)

# literals and lone-sign oddity
_literals = st.sampled_from(['true', 'false', 'null'])
_lone_sign = st.sampled_from(['-', '-.'])

# Base atomic value strategy (including interesting malformed atomic values)
base_value = st.one_of(
    _valid_json_string,
    _unterminated_string,
    _control_string,
    _valid_number,
    _malformed_number,
    _literals,
    _lone_sign
)

# Mutation helpers for arrays/objects: produce variants like trailing commas, double commas, missing colons, duplicate keys
def _array_from_list(items):
    """items: list of string values"""
    if not items:
        return '[]'
    # produce variants
    variants = []
    # normal
    variants.append('[' + ','.join(items) + ']')
    # trailing comma
    variants.append('[' + ','.join(items) + ',]')
    # double comma somewhere
    if len(items) >= 2:
        i = 1
        parts = items[:i] + [''] + items[i:]
        variants.append('[' + ','.join(parts) + ']')
    # missing closing bracket
    variants.append('[' + ','.join(items))
    # missing opening bracket
    variants.append(','.join(items) + ']')
    return variants[0]  # strategy will pick which variant by selecting variant-producing construction

def _pair_from_key_value(k, v):
    # Produce variants for pair: normal, missing colon, duplicate key (key repeated), stray comma
    variants = []
    variants.append(f'{k}:{v}')  # normal
    variants.append(f'{k}{v}')   # missing colon
    variants.append(f'{k}:{v},{k}:{v}')  # duplicate pair inline (not strictly a single pair but used for object content)
    return variants[0]

# The recursive strategy for arrays/objects using st.recursive
def _extend(children):
    # children is a strategy producing serialized JSON-like values (strings)
    # arrays: produce empty or small arrays, with some malformed variants
    arrays = st.lists(children, min_size=0, max_size=4).map(lambda lst: (
        '[]' if len(lst) == 0 else (
            '[' + ','.join(lst) + ']'
        )
    ))
    # arrays with additional malformed mutations
    arrays_mut = st.lists(children, min_size=1, max_size=4).map(lambda lst: (
        # randomly pick one mutation by encoding multiple possibilities separated by a marker;
        # we'll just return several common mutated forms by cycling through deterministic rule:
        '[' + ','.join(lst) + ']',                # normal
    ))
    # objects: produce pairs; keys are strings (sometimes duplicate)
    def build_obj(pairs):
        if not pairs:
            return '{}'
        # pairs is list of (k_str, v_str) tuples
        kvs = pairs
        # normal
        normal = '{' + ','.join(k + ':' + v for (k, v) in kvs) + '}'
        # trailing comma
        trailing = '{' + ','.join(k + ':' + v for (k, v) in kvs) + ',}'
        # double commas
        if len(kvs) >= 2:
            parts = [k + ':' + v for (k, v) in kvs]
            parts.insert(1, '')  # create double comma
            double = '{' + ','.join(parts) + '}'
        else:
            double = normal
        # missing colon in first pair
        miss_colon = '{' + (kvs[0][0] + kvs[0][1]) + (',' + ','.join(k + ':' + v for (k, v) in kvs[1:]) if len(kvs) > 1 else '') + '}'
        # duplicate keys: repeat first key
        dup = '{' + kvs[0][0] + ':' + kvs[0][1] + ',' + kvs[0][0] + ':' + (kvs[1][1] if len(kvs) > 1 else kvs[0][1]) + (' ,' + ','.join(k + ':' + v for (k, v) in kvs[2:]) if len(kvs) > 2 else '') + '}'
        # missing closing brace
        openmiss = '{' + ','.join(k + ':' + v for (k, v) in kvs)
        # missing opening brace
        closemiss = ','.join(k + ':' + v for (k, v) in kvs) + '}'
        # choose one deterministically to keep strategy simple: return a union later
        return normal, trailing, double, miss_colon, dup, openmiss, closemiss

    # Build object pairs strategy: keys as strings (valid or duplicated), values from children
    key_valid = st.lists(_valid_string_piece, min_size=1, max_size=3).map(''.join).map(lambda s: '"' + s + '"')
    # sometimes reuse the same key to force duplicates
    obj_pairs = st.lists(st.tuples(st.one_of(key_valid, _valid_json_string), children), min_size=0, max_size=4)

    objects = obj_pairs.map(build_obj).map(lambda variants: variants[0])  # pick normal for base; other variants accessible elsewhere

    # For richer malformed objects/arrays we will also produce mutated forms via explicit constructions
    # Compose combined strategy
    return st.one_of(arrays, objects)

# Use st.recursive to produce nested structures
recursive_values = st.recursive(base_value, _extend, max_leaves=100)

# Additional handcrafted deep nesting near parser cap (around 2048)
_deep_array = st.integers(min_value=2000, max_value=2050).map(lambda n: '[' * n + '0' + ']' * n)
_deep_object = st.integers(min_value=2000, max_value=2050).map(lambda n: '{' * n + '"k":0' + '}' * n)

# Trailing-content acceptance: value followed by arbitrary bytes/words (the parser accepts trailing content)
_trailing_content = st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \t\n\r!@#$%^&*()-_=+[]{};:\',.<>/?', min_size=1, max_size=20)

# Compose various malformed orchestrations: insert double commas, missing colons, unterminated top-level string, leading garbage
def _mutate_top_level(s):
    # Given a candidate serialized value s, produce a variety of near-valid-but-malformed strings
    choices = []
    choices.append(s)                         # original
    choices.append(s + 'garbage')             # trailing content
    choices.append(s + ',,')                  # trailing commas after value (accepted as trailing content)
    # insert random double comma inside if possible
    if ',' in s:
        choices.append(s.replace(',', ',,' , 1))
    # if object-like, remove a colon
    if ':' in s:
        choices.append(s.replace(':', '', 1))
    # unterminated top-level string
    choices.append(s + '"')                   # stray quote appended
    # prepend plus to numbers to test leading +
    choices.append('+' + s)
    # leading garbage
    choices.append('xyz' + s)
    # return one of them
    return st.sampled_from(choices)

# A strategy to take a generated recursive_value and wrap/mutate it into many fuzz variants
@st.composite
def mutated_top_level(draw):
    v = draw(recursive_values)
    # small chance to pick a deep nesting instead
    if draw(st.booleans()):
        v = draw(st.one_of(_deep_array, _deep_object, recursive_values))
    # sometimes insert raw control char sequences (not NUL) into places outside strings to create malformed JSON
    if draw(st.booleans()):
        ctrl = draw(st.sampled_from(_CONTROL_CHARS))
        # insert somewhere
        pos = draw(st.integers(min_value=0, max_value=len(v)))
        v = v[:pos] + ctrl + v[pos:]
    # Now pick further top-level mutation
    pick = draw(st.sampled_from(list(_mutate_top_level(v).example() for _ in range(6)) )) if False else None
    # (Note: .example() can't be used; instead create explicit list)
    variants = []
    variants.append(v)
    variants.append(v + 'garbage')
    variants.append(v + ',,')
    if ',' in v:
        variants.append(v.replace(',', ',,', 1))
    if ':' in v:
        variants.append(v.replace(':', '', 1))
    variants.append(v + '"')
    variants.append('+' + v)
    variants.append('xyz' + v)
    # return one of the variants
    return draw(st.sampled_from(variants))

# Because .example() isn't allowed in strategies, above uses an explicit list of variants and sampled_from.

# Final strategy: include plain recursive values, mutated ones, deep nesting, and some raw malformed constructs
strategy = st.one_of(
    recursive_values,
    mutated_top_level(),
    _deep_array,
    _deep_object,
    # some handcrafted malformed top-level strings
    st.sampled_from([
        '',                  # empty input
        '[,]',               # double comma within array
        '{"a" "b"}',         # missing colon
        '{"a":1,,"b":2}',    # double comma in object
        '{"k":0,"k":1}',     # duplicate keys (expected rejection by parser)
        '01',                # leading zero digit violation
        '.5',                # bare fraction
        '+1',                # leading plus
        '1e309',             # numeric overflow
        '-.',                # lone sign with dot
        '"unterminated',     # unterminated string
        '"\\uD800"',         # surrogate escape
        '"\\u0000"',         # explicit \u0000 inside string (six-character, allowed)
        '["a",\n\t]',        # trailing comma with whitespace
        '{"a": [1,2,3]} trailing',  # trailing content after complete value
        '/* comment */',     # C-style comment to exercise parser branches handling comments
    ])
).map(lambda s: s if isinstance(s, str) else str(s))