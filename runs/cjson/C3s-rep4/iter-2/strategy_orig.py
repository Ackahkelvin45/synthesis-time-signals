from hypothesis import strategies as st
import json

# --- scalar building blocks -------------------------------------------------

def _json_safe_char():
    # printable ASCII except quote and backslash
    return st.characters(
        min_codepoint=0x20,
        max_codepoint=0x7E,
        blacklist_characters='"\\',
    )


def _string_body_char():
    # includes raw control bytes and NUL, which the parser accepts
    return st.one_of(
        _json_safe_char(),
        st.characters(min_codepoint=0x00, max_codepoint=0x1F),
    )


_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])


def _unicode_escape():
    # well-formed \uXXXX, including surrogates (lone surrogates are rejected)
    return st.builds(
        lambda h: '\\u' + h,
        st.text(alphabet='0123456789abcdefABCDEF', min_size=4, max_size=4),
    )


def _string_content():
    return st.one_of(
        st.lists(_string_body_char(), min_size=0, max_size=8).map(''.join),
        st.lists(st.one_of(_escapes, _unicode_escape()), min_size=0, max_size=6).map(''.join),
        st.sampled_from(['', 'a', '\x00', '\x01', '\\u0000', '\\ud800', '\\udfff', '\n', '\t']),
    )


def _string():
    return _string_content().map(lambda s: '"' + s + '"')


# --- number building blocks -------------------------------------------------

def _int_part():
    return st.one_of(
        st.just('0'),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.sampled_from(['01', '007', '00']),
    )


def _frac_part():
    return st.one_of(
        st.just(''),
        st.just('.'),
        st.integers(min_value=0, max_value=10**9).map(lambda n: '.' + str(n)),
        st.sampled_from(['.0', '.00', '.5']),
    )


def _exp_part():
    return st.one_of(
        st.just(''),
        st.sampled_from(['e0', 'E0', 'e+1', 'e-1', 'e309', 'e308', 'e1000', 'e-1000', 'e01']),
        st.integers(min_value=-400, max_value=400).map(lambda n: 'e' + str(n)),
    )


def _number():
    return st.builds(
        lambda s, i, f, e: s + i + f + e,
        st.one_of(st.just(''), st.just('-')),
        _int_part(),
        _frac_part(),
        _exp_part(),
    )


# --- recursive value strategy ----------------------------------------------

_leaf = st.one_of(
    _string(),
    _number(),
    st.sampled_from(['true', 'false', 'null']),
)

# malformed near-valid fragments
_malformed = st.one_of(
    st.sampled_from([
        '{"a":1,}', '[1,2,]', '{"a" 1}', '{a:1}', '{"a":}',
        '[,]', '[,1]', '[1,,2]', '{"a":1,,}',
        '"unterminated', '"a\\', '"\\u12', '"\\ud800"', '"\\x41"',
        "'single'", '{', '[', '}', ']', ':', ',', '{"a":', '{:1}',
        '-', '+1', '.5', '1.', 'NaN', 'Infinity', '-Infinity',
        '0x10', '01', '1e', '1e+', '--1', 'tru', 'nul', 'fals',
        '\ufeff', '\x00', '1\x00', '{"a\x00":1}',
    ]),
)


def _composite(children):
    def build(draw):
        kind = draw(st.integers(min_value=0, max_value=3))
        if kind == 0:
            n = draw(st.integers(min_value=0, max_value=3))
            items = [draw(children) for _ in range(n)]
            return '[' + ','.join(items) + ']'
        if kind == 1:
            n = draw(st.integers(min_value=0, max_value=3))
            pairs = []
            for _ in range(n):
                k = draw(st.one_of(_string(), st.sampled_from(['"a"', '"b"', '"a"', '"\\u0000"'])))
                v = draw(children)
                pairs.append(k + ':' + v)
            return '{' + ','.join(pairs) + '}'
        if kind == 2:
            # duplicate keys
            n = draw(st.integers(min_value=1, max_value=4))
            pairs = ['"k":' + draw(children) for _ in range(n)]
            return '{' + ','.join(pairs) + '}'
        # malformed
        return draw(_malformed)
    return build


_value = st.recursive(
    _leaf,
    lambda children: st.builds(_composite(children)),
    max_leaves=12,
)


# --- deep nesting near the 1000-level limit --------------------------------

def _deep(depth):
    inner = st.one_of(_leaf, _malformed)
    # build a chain of `depth` wrappers
    return st.just(depth).map(lambda d: '[' * d + '0' + ']' * d)


_depth_near_limit = st.one_of(
    st.integers(min_value=0, max_value=1100).map(lambda d: '[' * d + '0' + ']' * d),
    st.integers(min_value=0, max_value=1100).map(lambda d: '{' + '"a":' * d + '0' + '}' * d),
    st.sampled_from([
        1000, 1001, 999, 998, 1002,
    ]).map(lambda d: '[' * d + '0' + ']' * d),
    st.sampled_from([1000, 1001, 999]).map(lambda d: '{' + '"a":' * d + '0' + '}' * d),
)


# --- top-level combination --------------------------------------------------

def _with_ws(s):
    return st.tuples(
        st.text(alphabet=' \t\n\r', min_size=0, max_size=3),
        st.just(s),
        st.text(alphabet=' \t\n\r', min_size=0, max_size=3),
    ).map(lambda t: t[0] + t[1] + t[2])


_value_with_ws = _value.flatmap(lambda s: _with_ws(s))

_trailing = st.one_of(
    st.just(''),
    st.sampled_from(['abc', ' 1 2', '\x00', ' junk', ']', '}', ',']),
)


def _add_trailing(t):
    return t[0] + t[1]


strategy = st.one_of(
    _value_with_ws,
    _depth_near_limit,
    _malformed,
    st.tuples(_value_with_ws, _trailing).map(_add_trailing),
    st.sampled_from(['', ' ', '\x00', '\ufeff', '\ufeff1', '\ufeff{}']),
)