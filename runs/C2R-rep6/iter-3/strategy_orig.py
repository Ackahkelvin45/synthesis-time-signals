from hypothesis import strategies as st
import json

# --- Leaf strategies -------------------------------------------------------

# Strings that appear inside JSON double quotes (the raw content, no quotes).
# Includes escapes, unicode escapes, surrogates, NUL and control bytes.
_escapes = st.sampled_from([
    '\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
])

_unicode_escapes = st.builds(
    lambda h: '\\u' + h,
    st.text(alphabet='0123456789abcdefABCDEF', min_size=4, max_size=4),
)

# Surrogate pair / lone surrogate style escapes
_surrogates = st.sampled_from([
    '\\uD800', '\\uDBFF', '\\uDC00', '\\uDFFF',
    '\\uD83D\\uDE00', '\\uD800\\uD800', '\\uDC00\\uD800',
    '\\u0000', '\\u001F', '\\uFFFF', '\\u000a',
])

# Control chars and NUL bytes embedded raw in strings
_control = st.sampled_from([
    '\x00', '\x01', '\x08', '\x0b', '\x0c', '\x1f', '\x7f',
    '\u2028', '\u2029', '\ufeff',
])

_safe_chars = st.characters(
    blacklist_categories=('Cs',),
    blacklist_characters='"\\',
    min_codepoint=0x20,
)

# String body: mix of safe chars, escapes, unicode escapes, controls.
_string_body = st.one_of(
    st.lists(_safe_chars, min_size=0, max_size=12).map(''.join),
    st.lists(
        st.one_of(
            _safe_chars,
            _escapes,
            _unicode_escapes,
            _surrogates,
            _control,
        ),
        min_size=0,
        max_size=16,
    ).map(''.join),
)

# A valid JSON string token (with surrounding quotes).
json_string = _string_body.map(lambda s: '"' + s + '"')

# --- Numbers ---------------------------------------------------------------

_int_part = st.one_of(
    st.just('0'),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=1, max_value=10**300).map(str),
)

_frac_part = st.one_of(
    st.just(''),
    st.integers(min_value=0, max_value=10**12).map(lambda n: '.' + str(n)),
    st.just('.' + '9' * 20),
)

_exp_part = st.one_of(
    st.just(''),
    st.builds(
        lambda sign, digits: 'e' + sign + digits,
        st.sampled_from(['', '+', '-']),
        st.integers(min_value=0, max_value=10**4).map(str),
    ),
    # overflow / extreme exponents
    st.sampled_from(['e309', 'e308', 'e-309', 'e-400', 'e9999', 'E+999']),
)

_optional_sign = st.sampled_from(['', '-'])

json_number = st.builds(
    lambda sign, ip, fp, ep: sign + ip + fp + ep,
    _optional_sign,
    _int_part,
    _frac_part,
    _exp_part,
)

# Near-valid / malformed number forms (still useful edge inputs).
malformed_number = st.sampled_from([
    '+1', '.5', '1.', '01', '0x1F', '-', '-.5', '-01', '1e', '1e+', '--1',
    '1..2', '00', '1_000', 'Infinity', 'NaN', '1e309', '1e999999',
])

# --- Recursive value / object / array --------------------------------------

# We use st.recursive to build nested obj/arr.  The `value` strategy is the
# recursive one; leaves are scalars, and the recursive step builds obj/arr.

def _pair(key, val):
    return key + ':' + val

def _obj_from_pairs(pairs):
    return '{' + ','.join(pairs) + '}'

def _arr_from_vals(vals):
    return '[' + ','.join(vals) + ']'

# Object members: bias toward objects with members (stressed path).
def _object_members(value_strategy):
    pair = st.tuples(json_string, value_strategy).map(lambda t: _pair(t[0], t[1]))
    return st.lists(pair, min_size=1, max_size=6)

def _object_with_members(value_strategy):
    return _object_members(value_strategy).map(_obj_from_pairs)

def _empty_object():
    return st.just('{}')

def _array_of(value_strategy):
    return st.lists(value_strategy, min_size=0, max_size=5).map(_arr_from_vals)

def _object_with_trailing_comma(value_strategy):
    pair = st.tuples(json_string, value_strategy).map(lambda t: _pair(t[0], t[1]))
    return st.lists(pair, min_size=1, max_size=4).map(
        lambda ps: '{' + ','.join(ps) + ',}'
    )

def _array_with_trailing_comma(value_strategy):
    return st.lists(value_strategy, min_size=1, max_size=4).map(
        lambda vs: '[' + ','.join(vs) + ',]'
    )

def _duplicate_keys(value_strategy):
    # Same key repeated with different values
    return st.builds(
        lambda k, v1, v2: '{' + k + ':' + v1 + ',' + k + ':' + v2 + '}',
        json_string,
        value_strategy,
        value_strategy,
    )

# Malformed near-valid constructs
def _malformed(value_strategy):
    return st.one_of(
        # double commas
        st.builds(lambda a, b: '[' + a + ',,' + b + ']', value_strategy, value_strategy),
        st.builds(lambda a, b: '{' + a + ',,' + b + '}', json_string, value_strategy),
        # missing colon
        st.builds(lambda k, v: '{' + k + ' ' + v + '}', json_string, value_strategy),
        # trailing content
        st.builds(lambda v: v + ' garbage', value_strategy),
        st.builds(lambda v: v + 'abc', value_strategy),
        # unterminated string
        st.just('"unterminated'),
        st.just('"unterminated\\'),
        st.just('{"a":"unterminated'),
        # lone tokens
        st.just('[,]'),
        st.just('[,1]'),
        st.just('[1,,2]'),
        st.just('{a:1}'),
        st.just("'x'"),
        st.just('//comment'),
        st.just('/* comment */1'),
        # malformed numbers as whole values
        malformed_number,
    )

# Scalars (non-recursive leaves)
_scalar = st.one_of(
    json_string,
    json_number,
    st.sampled_from(['true', 'false', 'null']),
    malformed_number,
)

# Recursive value strategy.
value = st.recursive(
    _scalar,
    lambda children: st.one_of(
        _empty_object(),
        _object_with_members(children),
        _object_with_trailing_comma(children),
        _duplicate_keys(children),
        _array_of(children),
        _array_with_trailing_comma(children),
        _malformed(children),
    ),
    max_leaves=30,
)

# Deep nesting: long chains of [ and { to stress first-pass memory measurement.
_deep_array = st.integers(min_value=0, max_value=200).map(
    lambda n: '[' * n + ']' * n
)
_deep_object = st.integers(min_value=0, max_value=200).map(
    lambda n: '{"a":' * n + 'null' + '}' * n
)
_deep_mixed = st.integers(min_value=0, max_value=150).map(
    lambda n: ('[{"a":' * n) + '1' + ('}]' * n)
)

# Whitespace-padded values (WS is skipped)
_ws = st.sampled_from([' ', '\t', '\n', '\r', '  ', '\n\t'])

def _pad(v):
    return st.tuples(_ws, st.just(v), _ws).map(lambda t: t[0] + t[1] + t[2])

# --- Near-crash intensification --------------------------------------------
# The last run produced a UBSan crash (null-pointer + non-zero offset) reachable
# via structurally malformed inputs like b'-', b'{"\\uD800":1}', b'[1,2,]'.
# We mutate structurally *around* those crashing seeds: keep the same skeletal
# shape (lone token, object-with-surrogate-key, trailing-comma array) but vary
# the surrounding bytes, nesting, whitespace, and sibling content so the parser
# is driven through the same code path with perturbed state.

_ws_any = st.sampled_from(['', ' ', '\t', '\n', '\r', '  ', '\n\t', '\r\n'])

# Lone-token family around b'-' (sign / number-prefix fragments).
_lone_token = st.sampled_from([
    '-', '+', '.', '-.', '+.', '--', '+-', '-e', 'e', 'E', '.e', '-e-',
    '0', '-0', '+0', '0.', '-0.', '..', '-..', 'e+', 'e-', '-1e', '1e-',
])

# Surrogate-key object family around b'{"\\uD800":1}'.
_surrogate_key = st.sampled_from([
    '\\uD800', '\\uDBFF', '\\uDC00', '\\uDFFF', '\\uD83D\\uDE00',
    '\\uD800\\uD800', '\\uDC00\\uD800', '\\u0000', '\\uFFFF',
])
_surrogate_val = st.one_of(
    st.sampled_from(['1', '0', '-1', 'null', 'true', 'false', '[]', '{}', '""']),
    json_string,
    json_number,
)

def _surrogate_obj():
    return st.builds(
        lambda lead, key, val, tail: lead + '{"' + key + '":' + val + '}' + tail,
        _ws_any,
        _surrogate_key,
        _surrogate_val,
        _ws_any,
    )

def _surrogate_obj_nested():
    return st.builds(
        lambda n, key, val: (
            '{' * n + '"' + key + '":' + val + '}' * n
        ),
        st.integers(min_value=1, max_value=8),
        _surrogate_key,
        _surrogate_val,
    )

# Trailing-comma array family around b'[1,2,]'.
def _trailing_comma_arr():
    inner = st.one_of(
        st.sampled_from(['1', '0', '-1', 'null', 'true', 'false', '""', '[]', '{}']),
        json_string,
        json_number,
    )
    return st.builds(
        lambda lead, a, b, tail: lead + '[' + a + ',' + b + ',]' + tail,
        _ws_any,
        inner,
        inner,
        _ws_any,
    )

def _trailing_comma_arr_nested():
    inner = st.one_of(st.sampled_from(['1', 'null', 'true', '[]', '{}']))
    return st.builds(
        lambda n, v: '[' * n + v + ',]' + ']' * (n - 1),
        st.integers(min_value=1, max_value=8),
        inner,
    )

# Structural perturbation around a crashing seed: insert/duplicate/truncate
# delimiters and whitespace so we stay on the same parser path.
def _perturb(seed):
    return st.builds(
        lambda pre, post, dup: pre + seed + post + (seed if dup else ''),
        _ws_any,
        _ws_any,
        st.booleans(),
    )

_crash_seeds = ['-', '{"\\uD800":1}', '[1,2,]']

def _mutated_crash_seed():
    return st.builds(
        lambda seed, pre, mid, post, dup_mid: (
            pre + seed[:len(seed) // 2] + mid + seed[len(seed) // 2:] + post
            + (mid if dup_mid else '')
        ),
        st.sampled_from(_crash_seeds),
        _ws_any,
        _ws_any,
        _ws_any,
        st.booleans(),
    )

# Delimiter-heavy framings that keep the parser in the same region.
def _delimiter_framing():
    return st.builds(
        lambda a, b, c, d, v: a + b + c + v + d,
        st.sampled_from(['', '[', '{', '[{', '{"a":']),
        st.sampled_from(['', ',', ',,', '":', ':']),
        st.sampled_from(['', ' ', '\t', '\n']),
        st.sampled_from(['', ']', '}', '}]', ',]', ',}']),
        st.one_of(
            st.sampled_from(_crash_seeds),
            _lone_token,
            _surrogate_obj(),
            _trailing_comma_arr(),
        ),
    )

# --- Intensified structural mutation around crash seeds --------------------
# We take a crashing seed and perform byte-level structural mutations that
# preserve the skeletal shape driving into the null-pointer+offset path:
# truncate at every prefix length, splice in delimiters/whitespace/NUL at
# arbitrary positions, duplicate/split on structural boundaries, and nest
# the seed inside matched/unmatched delimiters.

def _seed_split_mutate(seed):
    # Split the seed at an arbitrary index and inject a fragment in between.
    def build(seed_str, i, frag, pre, post, dup):
        i = min(i, len(seed_str))
        body = seed_str[:i] + frag + seed_str[i:]
        if dup:
            body = body + seed_str
        return pre + body + post
    return st.builds(
        build,
        st.just(seed),
        st.integers(min_value=0, max_value=len(seed)),
        st.one_of(
            st.sampled_from([
                '', ',', ',,', ':', '::', '}', ']', '{}', '[]', '"', '\\',
                '\x00', '\x01', '\xff', ' ', '\t', '\n', '\r',
                '\\uD800', '\\uDC00', '\\uD83D\\uDE00',
            ]),
            _ws_any,
        ),
        _ws_any,
        _ws_any,
        st.booleans(),
    )

def _seed_truncations(seed):
    # Every prefix of the seed, plus every prefix with a trailing byte.
    n = len(seed)
    return st.builds(
        lambda i, tail: seed[:i] + tail,
        st.integers(min_value=0, max_value=n),
        st.one_of(
            st.just(''),
            st.sampled_from([',', ']', '}', ':', '"', '\\', '\x00', ' ']),
        ),
    )

def _seed_nest(seed):
    # Wrap the seed in N matched or unbalanced delimiters.
    return st.builds(
        lambda n, m, open_c, close_c: (
            open_c * n + seed + close_c * m
        ),
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=0, max_value=20),
        st.sampled_from(['[', '{', '[{', '{"a":', '"']),
        st.sampled_from([']', '}', '}]', ',]', ',}', '"']),
    )

def _seed_byte_splice(seed):
    # Insert arbitrary JSON-ish bytes at a random position, repeated k times.
    frag = st.sampled_from([
        '', ',', ',,', ':', '::', '}', ']', '{}', '[]', '"', '\\', '/',
        '\x00', '\x01', '\x7f', '\xff', ' ', '\t', '\n', '\r',
        '\\uD800', '\\uDC00', '\\uDFFF', '\\uD83D\\uDE00',
        '-', '+', '.', 'e', 'E', '0', '1', 'null', 'true', 'false',
    ])
    return st.builds(
        lambda i, k, pre, post: (
            pre + seed[:i] + (frag.example() * k) + seed[i:] + post
        ),
        st.integers(min_value=0, max_value=len(seed)),
        st.integers(min_value=0, max_value=4),
        _ws_any,
        _ws_any,
    )

def _seed_struct_mutate(seed):
    # Replace structural characters of the seed with other delimiters.
    return st.builds(
        lambda mapping, pre, post: (
            pre + ''.join(mapping.get(c, c) for c in seed) + post
        ),
        st.just({
            '{': st.sampled_from(['{', '[', '', '"', '\\']).example(),
            '}': st.sampled_from(['}', ']', '', '"', '\\']).example(),
            '[': st.sampled_from(['[', '{', '', '"', '\\']).example(),
            ']': st.sampled_from([']', '}', '', '"', '\\']).example(),
            ':': st.sampled_from([':', ',', '', '"', '\\']).example(),
            ',': st.sampled_from([',', ':', '', '"', '\\']).example(),
            '"': st.sampled_from(['"', '\\', '', "'"]).example(),
        }),
        _ws_any,
        _ws_any,
    )

def _intensified_crash(seed):
    return st.one_of(
        _seed_split_mutate(seed),
        _seed_truncations(seed),
        _seed_nest(seed),
        _seed_byte_splice(seed),
        _seed_struct_mutate(seed),
    )

_intensified_near_crash = st.one_of(
    [_intensified_crash(s) for s in _crash_seeds]
)

_near_crash = st.one_of(
    _lone_token,
    _surrogate_obj(),
    _surrogate_obj_nested(),
    _trailing_comma_arr(),
    _trailing_comma_arr_nested(),
    _mutated_crash_seed(),
    _delimiter_framing(),
    _perturb('-'),
    _perturb('{"\\uD800":1}'),
    _perturb('[1,2,]'),
    _intensified_near_crash,
)

# Top-level strategy: a JSON value, optionally padded, plus special edge cases.
strategy = st.one_of(
    value,
    _deep_array,
    _deep_object,
    _deep_mixed,
    st.just('{}'),
    st.just('[]'),
    st.just(''),
    st.just(' '),
    st.just('\x00'),
    st.just('{"a":\x00}'),
    st.just('["\x00"]'),
    st.just('"\x00"'),
    st.just('{"a":1,"a":2}'),
    st.just('[1,2,]'),
    st.just('{"a":1,}'),
    st.just('1e309'),
    st.just('-'),
    st.just('{"\\uD800":1}'),
    st.just('"\\uD83D\\uDE00"'),
    st.just('{"a":1} garbage'),
    value.flatmap(_pad),
    _near_crash,
)