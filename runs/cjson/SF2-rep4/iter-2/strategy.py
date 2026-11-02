from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

def _esc():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    hexd = st.sampled_from('0123456789abcdefABCDEF')
    uni = st.tuples(*([hexd] * 4)).map(lambda t: '\\u' + ''.join(t))
    return st.one_of(simple, uni)

def _safe_char():
    # printable-ish ascii excluding quote and backslash, plus some unicode
    ascii_safe = st.characters(
        min_codepoint=0x20, max_codepoint=0x7E,
        blacklist_characters='"\\'
    )
    unicode_safe = st.characters(
        min_codepoint=0xA0, max_codepoint=0x2FFF,
        blacklist_categories=('Cs',)
    )
    return st.one_of(ascii_safe, unicode_safe)

def _raw_control_char():
    # raw control bytes / NUL are accepted by the parser inside strings
    return st.one_of(
        st.just('\x00'),
        st.just('\t'),
        st.just('\n'),
        st.just('\r'),
        st.characters(min_codepoint=0, max_codepoint=0x1F),
    )

def _string_body_piece():
    return st.one_of(_safe_char(), _esc(), _raw_control_char())

# ---------- numbers ----------

def _digits_nonzero_first():
    return st.tuples(
        st.sampled_from('123456789'),
        st.text(alphabet='0123456789', min_size=0, max_size=20),
    ).map(lambda t: t[0] + t[1])

def _int_part():
    return st.one_of(
        st.just('0'),
        _digits_nonzero_first(),
        # deliberately malformed-ish integer parts the parser tolerates
        st.text(alphabet='0123456789', min_size=1, max_size=20),  # leading zeros
        st.just('0x10'),
        st.just('0XFF'),
        st.just('0xdeadBEEF'),
    )

def _frac_part():
    return st.one_of(
        st.just(''),
        st.tuples(
            st.just('.'),
            st.text(alphabet='0123456789', min_size=1, max_size=20),
        ).map(lambda t: t[0] + t[1]),
        st.just('.'),  # trailing dot accepted
    )

def _exp_part():
    return st.one_of(
        st.just(''),
        st.tuples(
            st.sampled_from(['e', 'E']),
            st.sampled_from(['', '+', '-']),
            st.text(alphabet='0123456789', min_size=1, max_size=6),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # overflow magnitudes
        st.just('e309'),
        st.just('E400'),
        st.just('e-400'),
        st.just('e999999'),
    )

def _number():
    sign = st.sampled_from(['', '-'])
    return st.tuples(sign, _int_part(), _frac_part(), _exp_part()).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

# ---------- malformed number fragments (rejected cases) ----------

def _bad_number():
    return st.one_of(
        st.just('-'),
        st.just('+1'),
        st.just('+0'),
        st.just('.5'),
        st.just('-.5'),
        st.just('NaN'),
        st.just('Infinity'),
        st.just('-Infinity'),
        st.just('undefined'),
        st.just('truex'),
        st.just('nullx'),
    )

# ---------- recursive value ----------

def _string():
    return st.tuples(
        st.just('"'),
        st.lists(_string_body_piece(), min_size=0, max_size=12).map(''.join),
        st.just('"'),
    ).map(lambda t: t[0] + t[1] + t[2])

def _unterminated_string():
    return st.tuples(
        st.just('"'),
        st.lists(_string_body_piece(), min_size=0, max_size=8).map(''.join),
    ).map(lambda t: t[0] + t[1])

def _ws():
    return st.text(alphabet=' \t\n\r', min_size=0, max_size=3)

def _make_value(draw, value):
    return draw(value)

def _value_strategy():
    return st.recursive(
        st.one_of(
            _string(),
            _number(),
            st.just('true'),
            st.just('false'),
            st.just('null'),
            _bad_number(),
        ),
        lambda children: st.one_of(
            _make_arr(children),
            _make_obj(children),
        ),
        max_leaves=40,
    )

def _make_arr(children):
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return '[]'
        parts = [draw(_ws())]
        for i in range(n):
            if i > 0:
                parts.append(',')
                parts.append(draw(_ws()))
            parts.append(draw(children))
            parts.append(draw(_ws()))
        return '[' + ''.join(parts) + ']'
    return arr()

def _make_obj(children):
    @st.composite
    def obj(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return '{}'
        parts = [draw(_ws())]
        for i in range(n):
            if i > 0:
                parts.append(',')
                parts.append(draw(_ws()))
            parts.append(draw(_string()))
            parts.append(draw(_ws()))
            parts.append(':')
            parts.append(draw(_ws()))
            parts.append(draw(children))
            parts.append(draw(_ws()))
        return '{' + ''.join(parts) + '}'
    return obj()

# ---------- edge cases ----------

def _deep_nesting():
    # concentrate near the 1000-level limit
    @st.composite
    def deep(draw):
        depth = draw(st.integers(min_value=995, max_value=1005))
        kind = draw(st.sampled_from(['arr', 'obj']))
        inner = draw(st.one_of(_number(), _string(), st.just('null')))
        if kind == 'arr':
            return '[' * depth + inner + ']' * depth
        else:
            return '{"k":' * depth + inner + '}' * depth
    return deep()

def _deep_flat():
    # a single long array / object at moderate depth
    @st.composite
    def flat(draw):
        n = draw(st.integers(min_value=0, max_value=200))
        elems = draw(st.lists(_number(), min_size=n, max_size=n))
        return '[' + ','.join(elems) + ']'
    return flat()

def _malformed_structures():
    return st.one_of(
        st.just('[,]'),
        st.just('[1,,2]'),
        st.just('[1,]'),
        st.just('{,}'),
        st.just('{"a":1,}'),
        st.just('{"a" 1}'),
        st.just('{"a"}'),
        st.just('{:1}'),
        st.just('{"a":}'),
        st.just('[1 2]'),
        st.just('{"a":1 "b":2}'),
        st.just("'single'"),
        st.just('{a:1}'),
        st.just('{"a":1'),
        st.just('[1,2'),
        st.just('{"\\ud800":1}'),
        st.just('"\\ud800"'),
        st.just('"\\udfff"'),
        st.just('"\\ud800\\udc00"'),
        st.just('"\\uD83D\\uDE00"'),
        st.just('"\\x41"'),
        st.just('"\\q"'),
        st.just(''),
        st.just('   '),
        st.just('\ufeff1'),
        st.just('\ufeff{"a":1}'),
        st.just('1\x00'),
        st.just('"a\x00b"'),
        st.just('true\x00'),
        st.just('1abc'),
        st.just('1 2'),
        st.just('{}[]'),
    )

def _surrogate_strings():
    hexd = st.sampled_from('0123456789abcdefABCDEF')
    @st.composite
    def s(draw):
        n = draw(st.integers(min_value=1, max_value=4))
        parts = []
        for _ in range(n):
            parts.append(draw(st.one_of(
                st.tuples(*([hexd] * 4)).map(lambda t: '\\u' + ''.join(t)),
                _safe_char(),
            )))
        return '"' + ''.join(parts) + '"'
    return s()

# ---------- top-level ----------

_value = _value_strategy()

def _top_level():
    return st.one_of(
        _value,
        _deep_nesting(),
        _deep_flat(),
        _malformed_structures(),
        _surrogate_strings(),
        _unterminated_string(),
        st.tuples(
            _ws(),
            _value,
            _ws(),
        ).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(
            _value,
            st.text(min_size=1, max_size=5),
        ).map(lambda t: t[0] + t[1]),
    )

strategy = _top_level()