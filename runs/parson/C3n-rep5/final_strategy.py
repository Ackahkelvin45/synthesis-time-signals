from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Scalar / leaf generators
# ---------------------------------------------------------------------------

# A "safe" string body: printable ASCII plus escapes, no raw NUL or control.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

# JSON string escapes (valid)
_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

# \uXXXX escapes, including surrogates and edge hex.
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_escape = _hex4.map(lambda h: "\\u" + h)

# Surrogate-specific escapes (lone high/low surrogates).
_surrogate_escape = st.sampled_from(
    ["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\u0000", "\\u001F", "\\uFFFF"]
)

# Valid string fragments
_string_piece = st.one_of(
    _escapes,
    _unicode_escape,
    _surrogate_escape,
    _safe_chars.filter(lambda c: c not in '"\\' and c != "\x00"),
)

_valid_string = st.builds(
    lambda pieces: '"' + "".join(pieces) + '"',
    st.lists(_string_piece, max_size=12),
)

# Malformed strings (unterminated, bad escape, raw control-ish)
_malformed_string = st.one_of(
    st.builds(lambda s: s[:-1], _valid_string),  # drop closing quote
    st.just('"'),
    st.just('"abc'),
    st.builds(lambda s: s + "\\", _valid_string),  # trailing backslash
    st.just('"\\x"'),
    st.just('"\\u12"'),  # short unicode escape
    st.just('"\\uZZZZ"'),
)

# Strings crafted to exercise json_serialize_string (serialization path).
# Include characters requiring escaping and a variety of lengths.
_serialize_string = st.builds(
    lambda s: json.dumps(s),
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\x00",
        ),
        max_size=40,
    ),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=18)

# valid-ish integer
_valid_int = st.one_of(
    st.just("0"),
    st.builds(
        lambda d: d[0].lstrip("0") + d[1:] if d[0] != "0" else d,
        st.tuples(st.sampled_from("123456789"), _int_digits),
    ).map(lambda t: t[0] + t[1] if isinstance(t, tuple) else t),
)

# simpler safe valid integer
_valid_int = st.one_of(
    st.just("0"),
    st.builds(lambda a, b: a + b, st.sampled_from("123456789"), _int_digits),
)

_frac = st.builds(lambda d: "." + d, _int_digits)
_exp = st.builds(
    lambda e, sign, d: e + sign + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    _int_digits,
)

_valid_number = st.builds(
    lambda sign, ip, fp, ex: sign + ip + fp + ex,
    st.sampled_from(["", "-"]),
    _valid_int,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

# extreme / overflow-y numbers
_extreme_number = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e308"),
    st.just("1e-309"),
    st.just("1e999999"),
    st.just("-1e999999"),
    st.just("1e-999999"),
    st.builds(lambda d: d + "e" + "9" * 10, _int_digits),
    st.builds(lambda d: d + "e-" + "9" * 10, _int_digits),
    st.just("0.00000000000000000000000000001"),
    st.just("99999999999999999999999999999999999999"),
)

# malformed numbers (leading +, leading zeros, lone dot, lone sign)
_malformed_number = st.sampled_from(
    ["+1", "01", "007", ".5", "1.", "-", "-.", "+", "1e", "1e+", "e1",
     "--1", "1..2", "0x1", "1_000", "NaN", "Infinity", "-Infinity"]
)

_number = st.one_of(_valid_number, _extreme_number, _malformed_number)

# ---------------------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------------------

# Depth control: concentrate near the parser cap (~2048).
# We keep generated depth small-to-moderate in the recursive strategy and
# separately emit targeted deep-nesting strings near the limit.

_literal = st.sampled_from(["true", "false", "null"])

_leaf_value = st.one_of(
    _valid_string,
    _malformed_string,
    _serialize_string,
    _number,
    _literal,
)

# Duplicate-key-prone key pool
_key_pool = st.one_of(
    _valid_string,
    _serialize_string,
    st.sampled_from(['"k"', '"a"', '"b"', '"key"', '""', '"dup"']),
)

_pair_sep = st.sampled_from([":", ":", ":", ""])  # occasionally missing colon
_elem_sep = st.sampled_from([",", ",", ","])       # occasionally missing comma

def _make_object(pairs):
    if not pairs:
        return "{}"
    parts = []
    for k, colon, v in pairs:
        parts.append(k + colon + v)
    return "{" + ",".join(parts) + "}"

def _make_array(items):
    if not items:
        return "[]"
    return "[" + ",".join(items) + "]"

_value = st.recursive(
    _leaf_value,
    lambda children: st.one_of(
        st.builds(
            _make_object,
            st.lists(
                st.tuples(_key_pool, _pair_sep, children),
                max_size=4,
            ),
        ),
        st.builds(
            _make_array,
            st.lists(children, max_size=4),
        ),
    ),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Targeted structural edge cases
# ---------------------------------------------------------------------------

def _deep_nesting(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

# Depth near the 2048 cap (concentrate just below / at / slightly above).
_near_cap_depth = st.one_of(
    st.integers(min_value=1, max_value=16),
    st.integers(min_value=2000, max_value=2050),
    st.sampled_from([1024, 2047, 2048, 2049, 2050]),
)

_deep_array = st.builds(
    lambda d, inner: "[" * d + inner + "]" * d,
    _near_cap_depth,
    st.one_of(st.just(""), st.just("0"), st.just('"x"')),
)

_deep_object = st.builds(
    lambda d: '{"a":' * d + "0" + "}" * d,
    _near_cap_depth,
)

_empty = st.sampled_from(["{}", "[]", " { } ", "[\n]", "{\t}"])

_duplicate_keys = st.sampled_from([
    '{"k":0,"k":1}',
    '{"a":1,"a":2,"a":3}',
    '{"x":{"y":1},"x":2}',
    '{"":1,"":2}',
])

_trailing_content = st.builds(
    lambda v, t: v + t,
    _value,
    st.sampled_from(["", " garbage", "abc", "xyz", "]", "}", "0", "null"]),
)

# Near-valid-but-malformed top-level forms
_malformed_toplevel = st.sampled_from([
    '{"a":1,}',
    '[1,2,]',
    '{"a" 1}',
    '{"a":}',
    '{:1}',
    '[,]',
    '[1,,2]',
    '{,}',
    '{"a":1 "b":2}',
    '[1 2]',
    '{"a":1',
    '[1,2',
    '"unterminated',
    '{"a":"unterminated}',
    'tru',
    'fals',
    'nul',
    'True',
    'NULL',
    '\\u0041',
    '{"a":1}{"b":2}',
])

# Embedded NUL escape (six-char) inside strings — fine, not a raw NUL.
_nul_escape = st.sampled_from([
    '"\\u0000"',
    '{"a":"\\u0000"}',
    '["\\u0000","x"]',
    '"a\\u0000b"',
])

# ---------------------------------------------------------------------------
# Serialization round-trip coverage for json_serialize_string
# ---------------------------------------------------------------------------

# Strings that force every branch of the serializer's escape table:
# quotes, backslashes, all short escapes, control chars, and \uXXXX fallbacks.
_serialize_escape_heavy = st.one_of(
    st.sampled_from([
        '"',
        '\\',
        '/',
        '\b',
        '\f',
        '\n',
        '\r',
        '\t',
        '\x01',
        '\x1f',
        '\x7f',
        'a"b\\c/d\be\ff\ng\rh\ti',
        '\x00\x01\x02\x1f\x7f',
        'quote:" backslash:\\ slash:/',
        'mixed "\n\t\\ \u00e9 \u4e2d \U0001F600',
        '',
    ]),
    st.builds(
        lambda s: json.dumps(s),
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters="\x00",
            ),
            max_size=200,
        ),
    ),
    # Round-trip: valid serialized JSON strings re-encoded.
    st.builds(
        lambda s: json.dumps(json.dumps(s)),
        st.text(alphabet="abc\"\\/\n\t\x01\x1f", max_size=60),
    ),
)

# ---------------------------------------------------------------------------
# Dedicated json_serialize_string coverage
# ---------------------------------------------------------------------------
# The parser exposes a serializer (json_serialize_string /
# json_serialize_to_buffer_r) that is only reached through a dedicated
# serialization entry point. To exercise it we must feed it *already-parsed*
# values, i.e. valid JSON documents that the harness will then serialize.
# These documents are guaranteed-valid JSON spanning every value type and
# every string-escape branch (short escapes, control chars, \uXXXX fallbacks,
# long strings, empty strings, unicode planes).

def _ser_escape_string():
    # A JSON string literal whose *decoded* content hits every escape branch.
    return st.builds(
        lambda s: json.dumps(s),
        st.one_of(
            st.sampled_from([
                '"',
                '\\',
                '/',
                '\b',
                '\f',
                '\n',
                '\r',
                '\t',
                '\x00',
                '\x01',
                '\x1f',
                '\x7f',
                'a"b\\c/d\be\ff\ng\rh\ti',
                '\x00\x01\x02\x1f\x7f',
                'quote:" backslash:\\ slash:/',
                'mixed "\n\t\\ \u00e9 \u4e2d \U0001F600',
                '',
                'plain ascii string',
                '\u0000\u001f\u007f\u0080\u00ff',
            ]),
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="\x00",
                ),
                max_size=300,
            ),
            st.text(alphabet="abc\"\\/\n\t\x01\x1f\x7f", max_size=120),
        ),
    )

_ser_string = _ser_escape_string()

# Valid JSON values of every shape, so that a serializer invoked on the
# parsed result walks every type branch.
_ser_scalar = st.one_of(
    _ser_string,
    _valid_number,
    st.sampled_from(["true", "false", "null", "0", "-0", "1e0"]),
)

_ser_value = st.recursive(
    _ser_scalar,
    lambda children: st.one_of(
        st.builds(
            lambda items: "[" + ",".join(items) + "]",
            st.lists(children, max_size=6),
        ),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(
                    lambda k, v: k + ":" + v,
                    _ser_string,
                    children,
                ),
                max_size=6,
            ),
        ),
    ),
    max_leaves=25,
)

# Serializer-targeted documents: valid JSON with escape-heavy strings at
# every nesting level and in both keys and values.
_ser_document = st.one_of(
    _ser_value,
    st.builds(
        lambda s: s,
        _ser_string,
    ),
    st.builds(
        lambda items: "[" + ",".join(items) + "]",
        st.lists(_ser_string, min_size=1, max_size=8),
    ),
    st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(
            st.builds(lambda k, v: k + ":" + v, _ser_string, _ser_string),
            min_size=1,
            max_size=8,
        ),
    ),
    st.builds(
        lambda a, b, c: "[" + a + "," + b + "," + c + "]",
        _ser_string,
        _ser_value,
        _ser_string,
    ),
)

# ---------------------------------------------------------------------------
# Direct json_serialize_string coverage
# ---------------------------------------------------------------------------
# json_serialize_string is reached only when the harness serializes a parsed
# value. Emit documents that are guaranteed-valid JSON (so parsing succeeds)
# and whose decoded strings force every branch of the serializer's escape
# table: short escapes, control chars, \uXXXX fallbacks, DEL, unicode planes,
# long strings, and empty strings. These are wrapped in arrays/objects so the
# serializer walks nested string values and keys.

def _ser_direct_string():
    return st.builds(
        lambda s: s,
        st.one_of(
            st.sampled_from([
                '""',
                '"\\""',
                '"\\\\"',
                '"\\/"',
                '"\\b"',
                '"\\f"',
                '"\\n"',
                '"\\r"',
                '"\\t"',
                '"\\u0000"',
                '"\\u0001"',
                '"\\u001f"',
                '"\\u007f"',
                '"\\u0080"',
                '"\\u00ff"',
                '"\\u2028"',
                '"\\u2029"',
                '"\\ud83d\\ude00"',
                '"\\u4e2d\\u6587"',
                '"a\\"b\\\\c/d\\be\\ff\\ng\\rh\\ti"',
                '"\\u0000\\u0001\\u0002\\u001f\\u007f"',
                '"quote:\\" backslash:\\\\ slash:/"',
                '"plain ascii string"',
                '"' + "x" * 300 + '"',
            ]),
            st.builds(
                lambda s: json.dumps(s),
                st.text(
                    alphabet=st.characters(
                        blacklist_categories=("Cs",),
                        blacklist_characters="\x00",
                    ),
                    max_size=300,
                ),
            ),
            st.builds(
                lambda s: json.dumps(s),
                st.text(alphabet="abc\"\\/\n\t\x01\x1f\x7f", max_size=120),
            ),
        ),
    )

_ser_direct_value = st.one_of(
    _ser_direct_string(),
    _valid_number,
    st.sampled_from(["true", "false", "null", "0", "-0", "1e0"]),
)

_ser_direct_document = st.one_of(
    _ser_direct_string(),
    st.builds(
        lambda items: "[" + ",".join(items) + "]",
        st.lists(_ser_direct_value, min_size=1, max_size=8),
    ),
    st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                _ser_direct_string(),
                _ser_direct_value,
            ),
            min_size=1,
            max_size=8,
        ),
    ),
    st.builds(
        lambda a, b, c: "[" + a + "," + b + "," + c + "]",
        _ser_direct_string(),
        _ser_direct_value,
        _ser_direct_string(),
    ),
    st.builds(
        lambda a, b, c: "{" + a + ":" + b + "," + c + ":0}",
        _ser_direct_string(),
        _ser_direct_value,
        _ser_direct_string(),
    ),
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _value,
    _empty,
    _deep_array,
    _deep_object,
    _duplicate_keys,
    _trailing_content,
    _malformed_toplevel,
    _nul_escape,
    _extreme_number,
    _malformed_number,
    _valid_string,
    _malformed_string,
    _serialize_string,
    _serialize_escape_heavy,
    _ser_document,
    _ser_direct_document,
).filter(lambda s: "\x00" not in s)