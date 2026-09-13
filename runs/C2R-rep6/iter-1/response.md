```python
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
)
```