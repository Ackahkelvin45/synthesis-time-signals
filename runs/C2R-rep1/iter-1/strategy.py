from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Legal JSON string characters (raw, unescaped) that are SAFECODEPOINT.
# Includes NUL and other control bytes deliberately (parser takes explicit len).
_safe_chars = (
    st.characters(min_codepoint=0x00, max_codepoint=0x1F)  # control bytes incl NUL
    | st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF)
)

# Escapes allowed by ESC fragment.
_short_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex = st.sampled_from('0123456789abcdefABCDEF')
_unicode_escape = st.builds(
    lambda a, b, c, d: '\\u' + a + b + c + d,
    _hex, _hex, _hex, _hex,
)

# Surrogate escapes explicitly (high/low surrogates as raw \uXXXX).
_surrogate_escape = st.sampled_from([
    '\\uD800', '\\uDBFF', '\\uDC00', '\\uDFFF',
    '\\uD834\\uDD1E',  # valid pair
    '\\uD800\\uD800',  # invalid pair (two highs)
    '\\uDC00',         # lone low
])

_escape = _short_escapes | _unicode_escape | _surrogate_escape

# Characters inside a JSON string: raw safe chars or escape sequences.
_string_unit = _safe_chars.map(lambda c: c) | _escape

# A JSON string literal (possibly malformed -> handled separately in malformed).
_json_string = st.lists(_string_unit, max_size=12).map(lambda parts: '"' + ''.join(parts) + '"')

# Unterminated / malformed string variants.
_malformed_string = st.lists(_string_unit, max_size=8).map(lambda parts: '"' + ''.join(parts))

# ---------- numbers ----------

_digit = st.sampled_from('0123456789')
_nonzero = st.sampled_from('123456789')

_int_part = st.one_of(
    st.just('0'),
    st.builds(lambda h, t: h + t, _nonzero, st.lists(_digit, max_size=6).map(''.join)),
)

_frac_part = st.lists(_digit, min_size=1, max_size=6).map(lambda ds: '.' + ''.join(ds))

_exp_part = st.builds(
    lambda e, s, ds: e + s + ''.join(ds),
    st.sampled_from(['e', 'E']),
    st.sampled_from(['', '+', '-']),
    st.lists(_digit, min_size=1, max_size=4),
)

_number = st.builds(
    lambda sign, ip, fr, ex: sign + ip + fr + ex,
    st.sampled_from(['', '-']),
    _int_part,
    st.one_of(st.just(''), _frac_part),
    st.one_of(st.just(''), _exp_part),
)

# Extreme magnitudes / overflow / weird-but-accepted forms.
_extreme_numbers = st.sampled_from([
    '1e309', '-1e309', '1e-309', '1e999999', '-1e999999',
    '1e308', '1.7976931348623157e308', '1e-323', '0e0', '0e999',
    '1E+309', '1e+00000000000000000001',
    '1234567890123456789012345678901234567890',
    '-0', '0.0', '0e-0',
    '-',  # lone minus is accepted by parser
    '1e01', '1e01', '1E01',
])

_number_full = _number | _extreme_numbers

# Malformed number forms (rejected by parser, good edge inputs).
_malformed_numbers = st.sampled_from([
    '+1', '.5', '1.', '01', '00', '0x1F', '1e', '1e+', '--1', '1..2', '1.2.3',
    '1e1e1', '- 1', '1_000',
])

# ---------- literals ----------

_literal = st.sampled_from(['true', 'false', 'null'])

# ---------- recursive structure ----------

def _pair(key, value):
    return key + ':' + value

# Build recursive values with st.recursive.
# Leaves: strings, numbers, literals.
# Recursive: arrays and objects.
_json_value = st.recursive(
    st.one_of(_json_string, _number_full, _literal),
    lambda children: st.one_of(
        # array: [] or [v, v, ...] or [v, ... ,] (single trailing comma)
        st.one_of(
            st.just('[]'),
            st.lists(children, min_size=1, max_size=6).map(lambda vs: '[' + ','.join(vs) + ']'),
            st.lists(children, min_size=1, max_size=6).map(lambda vs: '[' + ','.join(vs) + ',]'),
        ),
        # object: {} or {k:v, ...} or with single trailing comma
        # bias toward objects with members
        st.one_of(
            st.just('{}'),
            st.lists(
                st.tuples(_json_string, children).map(lambda kv: kv[0] + ':' + kv[1]),
                min_size=1, max_size=6,
            ).map(lambda ps: '{' + ','.join(ps) + '}'),
            st.lists(
                st.tuples(_json_string, children).map(lambda kv: kv[0] + ':' + kv[1]),
                min_size=1, max_size=6,
            ).map(lambda ps: '{' + ','.join(ps) + ',}'),
        ),
    ),
    max_leaves=30,
)

# Objects with duplicate keys explicitly.
_dup_key_obj = st.builds(
    lambda k, v1, v2: '{' + k + ':' + v1 + ',' + k + ':' + v2 + '}',
    _json_string, _json_value, _json_value,
)

# Deep nesting: vary depth freely (no cap). Build nested arrays/objects.
def _deep(depth):
    return st.builds(
        lambda inner, d: '[' * d + inner + ']' * d,
        _json_value,
        st.just(depth),
    )

_deep_array = st.integers(min_value=0, max_value=200).flatmap(
    lambda d: st.builds(lambda inner: '[' * d + inner + ']' * d, _json_value)
)
_deep_object = st.integers(min_value=0, max_value=100).flatmap(
    lambda d: st.builds(
        lambda inner: '{"a":' * d + inner + '}' * d,
        _json_value,
    )
)

# ---------- near-valid-but-malformed ----------

_malformed = st.one_of(
    # double commas
    st.just('[1,,2]'), st.just('{,}'), st.just('{"a":1,,}'),
    st.just('[,1]'), st.just('[,]'), st.just('{"a":1,,"b":2}'),
    st.just('[1,2,,]'),
    # missing colons
    st.just('{"a" 1}'), st.just('{"a"}'), st.just('{"a":}'),
    st.just('{:1}'), st.just('{1:2}'),
    # unterminated strings
    _malformed_string,
    st.just('"abc'), st.just('{"a":"b'),
    # leading + / .5 / 01
    _malformed_numbers,
    # trailing content after complete value
    st.just('1abc'), st.just('[]xyz'), st.just('1 garbage'),
    st.just('true false'), st.just('{}[]'),
    # bare keys / single quotes / comments
    st.just('{a:1}'), st.just("'x'"), st.just('//x'), st.just('/* */1'),
    # stray tokens
    st.just('}'), st.just(']'), st.just(':'), st.just(','),
    st.just('{"a":1}}'), st.just('[1,2]]'),
    # whitespace-only / empty
    st.just(''), st.just('   '), st.just('\x00'),
)

# ---------- top-level strategy ----------

# Bias toward objects with members (the stressed first-pass path).
_objects_with_members = st.lists(
    st.tuples(_json_string, _json_value).map(lambda kv: kv[0] + ':' + kv[1]),
    min_size=1, max_size=8,
).map(lambda ps: '{' + ','.join(ps) + '}')

strategy = st.one_of(
    # bias: objects with members (weighted by repetition)
    _objects_with_members,
    _objects_with_members,
    _objects_with_members,
    _dup_key_obj,
    _json_value,
    _deep_array,
    _deep_object,
    _malformed,
    # lone values
    _json_string,
    _number_full,
    _literal,
).map(lambda s: s if isinstance(s, str) else str(s))