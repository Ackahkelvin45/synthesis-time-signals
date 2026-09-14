Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf / value strategies
# ---------------------------------------------------------------------------

_valid_escapes = st.sampled_from(
    ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']
)

_hex = st.integers(min_value=0, max_value=0xFFFF).map(lambda n: format(n, '04x'))
_unicode_escape = _hex.map(lambda h: '\\u' + h)

_control_byte = st.sampled_from(
    ['\x00', '\x01', '\x1f', '\x0b', '\x0c', '\x7f']
)

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
    return '"' + body

_str_literal = st.lists(_string_body_unit, max_size=8).map(
    lambda parts: '"' + ''.join(parts) + '"'
)

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
    key = st.one_of(_str_literal, _unterminated_string)
    return st.tuples(key, st.just(':'), value_st).map(
        lambda t: t[0] + t[1] + t[2]
    )


def _obj_strategy(value_st):
    pair = _pair_strategy(value_st)
    members = st.lists(pair, min_size=1, max_size=5)

    def build(members_list):
        body = ','.join(members_list)
        return '{' + body + '}'

    def build_trailing(members_list):
        body = ','.join(members_list)
        return '{' + body + ',}'

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
# Top-level strategy: bias toward VALID JSON.
# ---------------------------------------------------------------------------

# A strictly valid value: valid strings, valid numbers, valid literals, and
# recursive valid objects/arrays.
def _valid_value_strategy():
    return st.recursive(
        st.one_of(
            _str_literal,
            _valid_number,
            st.sampled_from(['true', 'false', 'null']),
        ),
        lambda children: st.one_of(
            _valid_obj_strategy(children),
            _valid_arr_strategy(children),
        ),
        max_leaves=40,
    )


def _valid_pair_strategy(value_st):
    return st.tuples(_str_literal, st.just(':'), value_st).map(
        lambda t: t[0] + t[1] + t[2]
    )


def _valid_obj_strategy(value_st):
    pair = _valid_pair_strategy(value_st)
    members = st.lists(pair, min_size=0, max_size=5)

    def build(members_list):
        return '{' + ','.join(members_list) + '}'

    return members.map(build)


def _valid_arr_strategy(value_st):
    elems = st.lists(value_st, min_size=0, max_size=6)

    def build(elems_list):
        return '[' + ','.join(elems_list) + ']'

    return elems.map(build)


_valid_value = _valid_value_strategy()


def _valid_deep_nesting():
    depth = st.integers(min_value=1, max_value=200)

    def make(d):
        return st.tuples(
            st.just('{'),
            st.just('"a":'),
            st.just('[' * d),
        ).map(lambda t: t[0] + t[1] + t[2] + '1' + ']' * d + '}')

    return depth.flatmap(make)


def _valid_whitespace_variant():
    ws = st.text(alphabet=' \t\n\r', max_size=4)

    def wrap(v):
        return st.tuples(ws, st.just(v), ws).map(lambda t: t[0] + t[1] + t[2])

    return _valid_value.flatmap(wrap)


# ---------------------------------------------------------------------------
# Near-crash intensifier: structurally mutate around a known crashing input.
# ---------------------------------------------------------------------------

_CRASH_SEED = '{"a":' + '[' * 64 + '1' + ']' * 64 + '}'


def _near_crash_mutations():
    # Character-level mutations around the crash seed.
    positions = st.integers(min_value=0, max_value=len(_CRASH_SEED) - 1)
    replacement = st.sampled_from(['', ',', ':', '{', '}', '[', ']', '"', '\\'])

    def splice(pos_and_repl):
        pos, repl = pos_and_repl
        return _CRASH_SEED[:pos] + repl + _CRASH_SEED[pos:]

    single_splice = st.tuples(positions, replacement).map(splice)

    def delete_char(pos):
        return _CRASH_SEED[:pos] + _CRASH_SEED[pos + 1:]

    single_delete = positions.map(delete_char)

    # Depth perturbations around the crash depth.
    depth = st.integers(min_value=1, max_value=400)

    def make_depth(d):
        return '{' + '"a":' + '[' * d + '1' + ']' * d + '}'

    depth_variant = depth.flatmap(lambda d: st.just(make_depth(d)))

    # Unbalanced brackets around the crash structure.
    open_count = st.integers(min_value=1, max_value=400)
    close_count = st.integers(min_value=0, max_value=400)

    def make_unbalanced(t):
        o, c = t
        return '{' + '"a":' + '[' * o + '1' + ']' * c + '}'

    unbalanced = st.tuples(open_count, close_count).map(make_unbalanced)

    # Crash seed with a nested object/array inserted at the leaves.
    inner = st.sampled_from(['{}', '[]', 'null', 'true', 'false', '0', '""'])

    def make_nested(inner_val):
        return '{' + '"a":' + '[' * 64 + inner_val + ']' * 64 + '}'

    nested_variant = inner.map(make_nested)

    # Repeat the crash seed to stress the parser's depth tracking.
    repeat = st.integers(min_value=1, max_value=8)

    def make_repeat(n):
        return '[' * 64 + _CRASH_SEED + ']' * 64 + (',' + _CRASH_SEED) * (n - 1)

    repeated = repeat.map(make_repeat)

    return st.one_of(
        single_splice,
        single_delete,
        depth_variant,
        unbalanced,
        nested_variant,
        repeated,
        st.just(_CRASH_SEED),
    )


strategy = st.one_of(
    # Overwhelmingly bias toward VALID JSON.
    _valid_value,
    _valid_obj_strategy(_valid_value),
    _valid_arr_strategy(_valid_value),
    _valid_deep_nesting(),
    _valid_whitespace_variant(),
    # A small fraction of near-valid / malformed inputs for coverage.
    st.tuples(_valid_value, st.just(' '), st.just('garbage')).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.just(''),
    st.just('   '),
    # Intensify near-crash exploration around the known crashing input.
    _near_crash_mutations(),
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 59.07,
  "region_coverage_pct": 59.07
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.