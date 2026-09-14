```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf / value strategies
# ---------------------------------------------------------------------------

# Escapes that are always valid inside a JSON string.
_valid_escapes = st.sampled_from(
    ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']
)

# \uXXXX escapes, including lone/dangling surrogates (parser accepts them).
_hex = st.integers(min_value=0, max_value=0xFFFF).map(lambda n: format(n, '04x'))
_unicode_escape = _hex.map(lambda h: '\\u' + h)

# A raw NUL or other control byte (allowed by the harness, faithful length).
_control_byte = st.sampled_from(
    ['\x00', '\x01', '\x1f', '\x0b', '\x0c', '\x7f']
)

# Characters that are safe inside a JSON string per the grammar.
_safe_char = st.characters(
    blacklist_categories=('Cs',),
    blacklist_characters='\\"',
).filter(lambda c: ord(c) > 0x1F)

_string_body_unit = st.one_of(
    _safe_char,
    _valid_escapes,
    _unicode_escape,
    _control_byte,
)

def _make_string(body):
    # Occasionally wrap in quotes, occasionally leave unterminated.
    return '"' + body

# A well-formed JSON string literal.
_str_literal = st.lists(_string_body_unit, max_size=8).map(
    lambda parts: '"' + ''.join(parts) + '"'
)

# Unterminated string (near-valid-but-malformed).
_unterminated_string = st.lists(_string_body_unit, min_size=1, max_size=6).map(
    lambda parts: '"' + ''.join(parts)
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text(alphabet='0123456789', min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just('0'),
        st.tuples(st.sampled_from('123456789'),
                  st.text(alphabet='0123456789', max_size=6)).map(
                      lambda t: t[0] + t[1]),
    )

_int_part = _int_part()

_exp_part = st.one_of(
    st.just(''),
    st.tuples(
        st.sampled_from('eE'),
        st.sampled_from(['', '+', '-']),
        st.text(alphabet='0123456789', min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_frac_part = st.one_of(
    st.just(''),
    st.tuples(st.just('.'), st.text(alphabet='0123456789', min_size=1, max_size=6)).map(
        lambda t: t[0] + t[1]),
)

_valid_number = st.tuples(
    st.sampled_from(['', '-']),
    _int_part,
    _frac_part,
    _exp_part,
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# Extreme magnitudes / exponents (overflow -> inf is accepted).
_extreme_number = st.one_of(
    st.sampled_from([
        '1e309', '-1e309', '1e-309', '1e999999', '-1e999999',
        '1E308', '1e400', '-0', '0.0', '1e+308', '1e-308',
        '123456789012345678901234567890',
        '0.0000000000000000000000000001',
        '9' * 40,
    ]),
    st.tuples(
        st.sampled_from(['', '-']),
        st.text(alphabet='0123456789', min_size=1, max_size=3),
        st.sampled_from(['e', 'E']),
        st.sampled_from(['', '+', '-']),
        st.text(alphabet='0123456789', min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
)

# Near-valid-but-malformed number forms (parser rejects most; lone '-' accepted).
_malformed_number = st.sampled_from([
    '+1', '.5', '1.', '01', '0x1F', '-', '--1', '1..2',
    '1e', '1e+', '00', '007', '-01', '.', '1.e5', '+.5',
])

_number = st.one_of(
    _valid_number,
    _extreme_number,
    _malformed_number,
)

# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

def _value_strategy():
    return st.recursive(
        st.one_of(
            _str_literal,
            _unterminated_string,
            _number,
            st.sampled_from(['true', 'false', 'null']),
            st.just('-'),
        ),
        lambda children: st.one_of(
            _obj_strategy(children),
            _arr_strategy(children),
        ),
        max_leaves=40,
    )


def _pair_strategy(value_st):
    # Bias toward object members (stressed first-pass path).
    key = st.one_of(_str_literal, _unterminated_string)
    return st.tuples(key, st.just(':'), value_st).map(
        lambda t: t[0] + t[1] + t[2]
    )


def _obj_strategy(value_st):
    pair = _pair_strategy(value_st)
    members = st.lists(pair, min_size=1, max_size=5)

    def build(members_list):
        # Occasionally emit a single trailing comma.
        body = ','.join(members_list)
        return '{' + body + '}'

    def build_trailing(members_list):
        body = ','.join(members_list)
        return '{' + body + ',}'

    # Empty object, normal object, trailing-comma object, duplicate keys.
    dup_key = st.tuples(
        _str_literal,
        st.just(':'),
        value_st,
        st.just(','),
        _str_literal,
        st.just(':'),
        value_st,
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4] + t[5] + t[6])

    dup_duplicate = st.tuples(_str_literal, value_st).flatmap(
        lambda kv: st.tuples(
            st.just(kv[0]),
            st.just(':'),
            st.just(kv[1]),
            st.just(','),
            st.just(kv[0]),
            st.just(':'),
            value_st,
        )
    ).map(lambda t: ''.join(t))

    return st.one_of(
        st.just('{}'),
        members.map(build),
        members.map(build_trailing),
        dup_key.map(lambda s: '{' + s + '}'),
        dup_duplicate.map(lambda s: '{' + s + '}'),
    )


def _arr_strategy(value_st):
    elems = st.lists(value_st, min_size=1, max_size=6)

    def build(elems_list):
        return '[' + ','.join(elems_list) + ']'

    def build_trailing(elems_list):
        return '[' + ','.join(elems_list) + ',]'

    # Malformed arrays: double commas, leading comma, lone comma.
    malformed = st.sampled_from([
        '[,]', '[,1]', '[1,,2]', '[1,2,,]', '[,]',
        '[1 2]', '[1;2]', '[1',
    ])

    return st.one_of(
        st.just('[]'),
        elems.map(build),
        elems.map(build_trailing),
        malformed,
    )


# ---------------------------------------------------------------------------
# Top-level strategy: bias toward objects with members, allow deep nesting.
# ---------------------------------------------------------------------------

_value = _value_strategy()

# Deeply nested structures (objects/arrays) to stress first-pass measurement.
def _deep_nesting():
    depth = st.integers(min_value=1, max_value=200)

    def make(d):
        # Nested objects and arrays.
        return st.tuples(
            st.just('{'),
            st.just('"a":'),
            st.just('[' * d),
        ).map(lambda t: t[0] + t[1] + t[2] + '1' + ']' * d + '}')

    return depth.flatmap(make)


def _malformed_object():
    return st.sampled_from([
        '{', '}', '{"a"', '{"a":', '{"a":1', '{"a" 1}',
        '{"a":1,}', '{"a":1,,}', '{,}', '{:1}',
        '{"a":1 "b":2}',
    ])


def _malformed_array():
    return st.sampled_from([
        '[', ']', '[1', '[1,', '[1 2]', '[1,,2]', '[,1]', '[,]',
    ])


strategy = st.one_of(
    # Bias toward objects with members.
    _obj_strategy(_value),
    _arr_strategy(_value),
    _value,
    _deep_nesting(),
    _malformed_object(),
    _malformed_array(),
    # Extra whitespace / trailing garbage variants.
    st.tuples(_value, st.just(' '), st.just('garbage')).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(_value, _value).map(lambda t: t[0] + t[1]),
    st.just(''),
    st.just('   '),
    st.just('\x00'),
)
```