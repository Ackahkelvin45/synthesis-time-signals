from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

# safe ASCII chars for strings (no quote, no backslash, no control)
_safe_ascii = st.characters(
    min_codepoint=0x20, max_codepoint=0x7E,
    blacklist_characters='"\\',
)

# control bytes including NUL, allowed inside emitted strings (parser handles length)
_control = st.characters(min_codepoint=0x00, max_codepoint=0x1F)

# unicode chars beyond ASCII (valid UTF-8 codepoints, excluding surrogates)
_unicode = st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF)

# a raw char that can appear inside a JSON string body (escaped or not)
_raw_string_char = st.one_of(_safe_ascii, _control, _unicode)

# valid escape sequences
_short_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex = st.sampled_from('0123456789abcdefABCDEF')
_unicode_escape = st.tuples(st.just('\\u'), _hex, _hex, _hex, _hex).map(''.join)

# surrogate escapes (lone high/low surrogates and valid pairs)
_surrogate_escape = st.one_of(
    st.tuples(st.just('\\u'), st.just('D'), _hex, _hex, _hex).map(''.join),
    st.tuples(st.just('\\u'), st.just('d'), _hex, _hex, _hex).map(''.join),
)

_escape = st.one_of(_short_escapes, _unicode_escape, _surrogate_escape)

# string body = mix of raw chars and escapes
_string_body = st.lists(
    st.one_of(_raw_string_char, _escape),
    max_size=12,
).map(''.join)

# a well-formed JSON string literal
_string = st.tuples(st.just('"'), _string_body, st.just('"')).map(''.join)

# ---------- numbers ----------

_digit = st.integers(min_value=0, max_value=9).map(str)
_nonzero = st.integers(min_value=1, max_value=9).map(str)

_int_part = st.one_of(
    st.just('0'),
    st.tuples(_nonzero, st.lists(_digit, max_size=18).map(''.join)).map(''.join),
)

_sign = st.sampled_from(['', '-'])

_frac = st.tuples(st.just('.'), st.lists(_digit, min_size=1, max_size=18).map(''.join)).map(''.join)

_exp = st.tuples(
    st.sampled_from(['e', 'E']),
    st.sampled_from(['', '+', '-']),
    st.lists(_digit, min_size=1, max_size=6).map(''.join),
).map(''.join)

# extreme magnitudes / overflow exponents
_extreme_exp = st.sampled_from([
    'e309', 'e308', 'e-309', 'e-400', 'E+999', 'e999999',
    'e-999999', 'e0', 'E-0', 'e+0',
])

_number = st.one_of(
    # plain int
    st.tuples(_sign, _int_part).map(''.join),
    # int with fraction
    st.tuples(_sign, _int_part, _frac).map(''.join),
    # int with exponent
    st.tuples(_sign, _int_part, _exp).map(''.join),
    # int with fraction and exponent
    st.tuples(_sign, _int_part, _frac, _exp).map(''.join),
    # extreme exponent overflow
    st.tuples(_sign, _int_part, _extreme_exp).map(''.join),
    # lone '-' (parser accepts)
    st.just('-'),
)

# ---------- malformed number forms (near-valid) ----------

_malformed_number = st.sampled_from([
    '+1', '+0', '+1.5', '.5', '-.5', '1.', '01', '00', '007',
    '0x1F', '0X1f', '-01', '-00', '1..2', '1e', '1e+', '1e-',
    '--1', '1.2.3', '1 2', '1e1.5', '+', '.', 'e5', 'Infinity',
    'NaN', '-Infinity',
])

# ---------- literals ----------

_literal = st.sampled_from(['true', 'false', 'null'])

# ---------- recursive value / obj / arr ----------

# Forward declaration via st.recursive
_json_value = st.deferred(lambda: _value)

# A pair: STRING ':' value
_pair = st.tuples(_string, st.just(':'), _json_value).map(''.join)

# Object: either {} or { pair (, pair)* [,] }
_obj = st.one_of(
    st.just('{}'),
    st.tuples(
        st.just('{'),
        st.lists(_pair, min_size=1, max_size=5),
        st.just('}'),
    ).map(lambda t: t[0] + ','.join(t[1]) + t[2]),
    # trailing comma variant (parser accepts one)
    st.tuples(
        st.just('{'),
        st.lists(_pair, min_size=1, max_size=5),
        st.just(',}'),
    ).map(lambda t: t[0] + ','.join(t[1]) + t[2]),
)

# Array: [] or [ value (, value)* [,] ]
_arr = st.one_of(
    st.just('[]'),
    st.tuples(
        st.just('['),
        st.lists(_json_value, min_size=1, max_size=5),
        st.just(']'),
    ).map(lambda t: t[0] + ','.join(t[1]) + t[2]),
    st.tuples(
        st.just('['),
        st.lists(_json_value, min_size=1, max_size=5),
        st.just(',]'),
    ).map(lambda t: t[0] + ','.join(t[1]) + t[2]),
)

# malformed object/array variants
_malformed_obj = st.sampled_from([
    '{', '}', '{a:1}', "{'a':1}", '{,}', '{,1}', '{"a"}',
    '{"a":}', '{"a":1,,}', '{"a" 1}', '{"a"::1}', '{"a":1',
    '{"a":1,, "b":2}', '{:1}', '{"a":1,,"b":2}',
])

_malformed_arr = st.sampled_from([
    '[', ']', '[,]', '[,1]', '[1,,2]', '[1 2]', '[1;2]',
    '[1,2', '[1,2,,]', '[1,2,,3]', '[]]', '[[',
])

# ---------- value ----------

_value = st.one_of(
    _string,
    _number,
    _literal,
    _obj,
    _arr,
    _malformed_number,
    _malformed_obj,
    _malformed_arr,
    # unterminated string
    st.tuples(st.just('"'), _string_body).map(''.join),
    # lone quote
    st.just('"'),
)

# ---------- top-level: json : value EOF ----------

# Use st.recursive to encourage depth variation
_recursive_value = st.recursive(
    st.one_of(_string, _number, _literal, _malformed_number),
    lambda children: st.one_of(
        st.tuples(
            st.just('{'),
            st.lists(
                st.tuples(_string, st.just(':'), children).map(''.join),
                min_size=1, max_size=5,
            ),
            st.just('}'),
        ).map(lambda t: t[0] + ','.join(t[1]) + t[2]),
        st.tuples(
            st.just('['),
            st.lists(children, min_size=1, max_size=5),
            st.just(']'),
        ).map(lambda t: t[0] + ','.join(t[1]) + t[2]),
    ),
    max_leaves=20,
)

# Deep nesting generator: objects with members (stressed first-pass path)
_deep_obj = st.integers(min_value=1, max_value=200).flatmap(
    lambda depth: st.just('{"a":' * depth + '1' + '}' * depth)
)

_deep_arr = st.integers(min_value=1, max_value=200).flatmap(
    lambda depth: st.just('[' * depth + '1' + ']' * depth)
)

# duplicate keys variant
_dup_keys = st.lists(_string, min_size=2, max_size=6).flatmap(
    lambda keys: st.just(
        '{' + ','.join('{}:{}'.format(k, '1') for k in keys) + '}'
    )
)

# NUL/control-heavy strings
_nul_string = st.tuples(
    st.just('"'),
    st.lists(st.one_of(_control, _safe_ascii), min_size=1, max_size=8).map(''.join),
    st.just('"'),
).map(''.join)

_obj_with_nul = st.tuples(
    st.just('{"'),
    _nul_string,
    st.just('":'),
    _recursive_value,
    st.just('}'),
).map(''.join)

# ---------- near-crash mutations ----------
# The crash signature is a UBSan "applying-non-zero-offset-to-null-pointer"
# in the parse function, and divergences cluster around negative exponents
# and control-byte strings. Intensify by mutating structurally around those
# near-crash inputs: exponent magnitudes, NUL/control placement, and
# truncated/segmented forms that stress the same pointer-offset path.

# Negative/positive exponent variations around the 1e309 boundary
_near_crash_exp = st.one_of(
    st.sampled_from([
        '1e309', '-1e309', '1e308', '1e310', '1e-309', '1e-308',
        '1e-400', '1e999999', '1e-999999', '0e309', '-0e309',
        '1E309', '1e+309', '1e-309', '1.0e309', '-1.0e309',
        '1e2147483647', '1e-2147483648', '1e2147483648',
        '1e4294967295', '1e4294967296', '1e-4294967296',
        '9e999999999', '1e0000000309', '1e000000000309',
    ]),
    # number with exponent multiplied by deep structure
    st.tuples(
        _sign,
        _int_part,
        st.sampled_from(['e', 'E']),
        st.sampled_from(['', '+', '-']),
        st.lists(_digit, min_size=1, max_size=12).map(''.join),
    ).map(''.join),
)

# Control/NUL chars placed at parse-boundary positions
_near_crash_ctrl = st.one_of(
    st.sampled_from([
        '\x00', '"\x00"', '{"a":\x00}', '[\x00]', '{"\x00":1}',
        '"\x1f"', '"\x05ma\x06"', '"\x01"', '"\x02"', '"\x03"',
        '"\x04"', '"\x1e"', '"\x1f"', '"a\x00b"', '"a\x1fb"',
        '{"a":"\x00"}', '["\x00"]', '"\x00\x01\x02\x03"',
        '\x00\x00', '\x1f\x1f', '"\x7f"', '"\x00\x7f"',
        '{"\x00":"\x1f"}', '["\x00","\x1f"]',
    ]),
    # random control-byte strings of varying length
    st.lists(_control, min_size=1, max_size=10).map(''.join),
    # control bytes embedded in otherwise valid structure
    st.tuples(
        st.just('"'),
        st.lists(st.one_of(_control, _safe_ascii), min_size=1, max_size=6).map(''.join),
        st.just('"'),
    ).map(''.join),
)

# Structural mutations around the crashing input: truncation, segmentation,
# and re-joining of exponent/control fragments.
# INTENSIFIED: focus on the `[1,2,]` divergence and the null-pointer-offset
# crash path. Build arrays/objects whose elements are exponent/control
# fragments, plus trailing-comma arrays with control bytes at boundaries.
_near_crash_structural = st.one_of(
    # truncated exponent numbers
    st.sampled_from([
        '1e30', '1e3', '1e', '1e+', '1e-', '-1e30', '-1e3',
        '-1e', '-1e+', '-1e-', '1e309', '1e3090', '1e30900',
    ]),
    # exponent fragments joined with control bytes
    st.tuples(
        st.sampled_from(['1e', '-1e', '1E', '-1E']),
        st.one_of(_control, _digit),
        st.lists(_digit, max_size=8).map(''.join),
    ).map(''.join),
    # negative number with trailing control byte
    st.tuples(
        st.sampled_from(['-', '']),
        _int_part,
        st.one_of(_control, st.just('')),
    ).map(''.join),
    # numbers adjacent to control bytes (token boundary stress)
    st.tuples(
        st.one_of(_control, st.just('')),
        st.sampled_from(['1e309', '-1e309', '1e-309', '0']),
        st.one_of(_control, st.just('')),
    ).map(''.join),
    # --- INTENSIFICATION: arrays/objects built from near-crash atoms ---
    # trailing-comma arrays wrapping exponent/control atoms (matches the
    # `[1,2,]` divergence signature and stresses the same parse path)
    st.lists(
        st.one_of(
            st.sampled_from(['1', '2', '1e309', '-1e309', '1e-309', '0', '-0']),
            st.lists(_control, min_size=1, max_size=4).map(''.join),
            _near_crash_exp,
        ),
        min_size=1, max_size=6,
    ).flatmap(
        lambda items: st.sampled_from([
            '[' + ','.join(items) + ',]',
            '[' + ','.join(items) + ']',
            '[' + ','.join(items) + ',,]',
        ])
    ),
    # objects whose keys/values are near-crash fragments (trailing comma too)
    st.lists(
        st.tuples(
            st.one_of(_string, _nul_string, st.just('"\x00"')),
            st.one_of(
                st.sampled_from(['1', '-1', '1e309', '-1e309', '1e-309', '0']),
                _near_crash_exp,
                st.lists(_control, min_size=1, max_size=4).map(''.join),
            ),
        ),
        min_size=1, max_size=5,
    ).flatmap(
        lambda pairs: st.sampled_from([
            '{' + ','.join('{}:{}'.format(k, v) for k, v in pairs) + '}',
            '{' + ','.join('{}:{}'.format(k, v) for k, v in pairs) + ',}',
        ])
    ),
    # control byte glued to structural delimiters (pointer-offset stress)
    st.tuples(
        st.one_of(_control, st.just('')),
        st.sampled_from(['[1,2,]', '{"a":1,}', '[1e309,]', '{"a":1e309,}',
                         '[1,2', '{"a":1', ',]', ',}']),
        st.one_of(_control, st.just('')),
    ).map(''.join),
    # deep nesting of trailing-comma containers around an exponent atom
    st.integers(min_value=1, max_value=60).flatmap(
        lambda depth: st.just(
            '[' * depth + '1e309' + ',]' * depth
        )
    ),
    st.integers(min_value=1, max_value=60).flatmap(
        lambda depth: st.just(
            '{"a":' * depth + '1e-309' + ',}' * depth
        )
    ),
)

# ---------- top-level strategy ----------

strategy = st.one_of(
    # core recursive values
    _recursive_value,
    # deep nesting
    _deep_obj,
    _deep_arr,
    # duplicate keys
    _dup_keys,
    # NUL/control byte strings
    _nul_string,
    _obj_with_nul,
    # empty containers
    st.just('{}'),
    st.just('[]'),
    # trailing comma
    st.just('[1,2,]'),
    st.just('{"a":1,}'),
    # lone '-' and overflow
    st.just('-'),
    st.just('1e309'),
    st.just('-1e309'),
    # surrogates
    st.just('"\\uD800"'),
    st.just('"\\uDC00"'),
    st.just('"\\uD800\\uDC00"'),
    # raw NUL byte
    st.just('\x00'),
    st.just('"\x00"'),
    st.just('{"a":\x00}'),
    # malformed top-level
    st.sampled_from([
        '1abc', '[]xyz', 'true false', '1 garbage',
        '{', '[', '"', 'tru', 'nul', 'fals',
        '{"a":1', '[1,2', '{"a":1}}', '[1,2]]',
        '{"a":1,,"b":2}', '[1,,2]', '[,]', '[,1]',
        '+1', '.5', '01', '-', '--',
    ]),
    # intensified near-crash mutations
    _near_crash_exp,
    _near_crash_ctrl,
    _near_crash_structural,
)