from hypothesis import strategies as st
import json

# ---------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------

# Characters that are safe inside a JSON string (no raw control chars,
# no raw NUL, no quote, no backslash).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) > 0x1F)

# Escape sequences that may appear inside a string.
_hex = st.characters(whitelist_categories=("Nd", "Nl"), whitelist_characters="0123456789abcdefABCDEF")

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_escapes = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
)

# Surrogate escapes and other interesting \uXXXX values.
_surrogate_escapes = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\u0000",
    "\\uD83D", "\\uDE00", "\\uD83D\\uDE00", "\\uFFFF", "\\uFFFE",
])

_string_piece = st.one_of(
    _safe_chars.map(str),
    _simple_escapes,
    _unicode_escapes,
    _surrogate_escapes,
)

# A valid JSON string (with quotes).
json_string = st.builds(
    lambda pieces: '"' + "".join(pieces) + '"',
    st.lists(_string_piece, min_size=0, max_size=12),
)

# ---------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.builds(
        lambda first, rest: first + rest,
        st.integers(min_value=1, max_value=9).map(str),
        st.text(alphabet="0123456789", min_size=0, max_size=15),
    ),
)

_frac_part = st.builds(
    lambda digits: "." + digits,
    st.text(alphabet="0123456789", min_size=1, max_size=15),
)

_exp_part = st.builds(
    lambda e, sign, digits: e + sign + digits,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=5),
)

# "Normal" numbers.
_normal_number = st.builds(
    lambda sign, ip, fp, ep: sign + ip + fp + ep,
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.just(""), _frac_part),
    st.one_of(st.just(""), _exp_part),
)

# Extreme numbers: huge exponents, tiny, overflow triggers, etc.
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "1e-400", "1e400",
    "0e0", "0e999999", "-0", "-0.0", "0.0", "1E+308", "1E-308",
    "1234567890123456789012345678901234567890",
    "-1234567890123456789012345678901234567890",
    "1.7976931348623157e308", "2.2250738585072014e-308",
    "1e1000000", "-1e1000000", "9" * 40, "-" + "9" * 40,
    "0." + "0" * 20 + "1",
    "1" + "0" * 100,
])

# Near-valid-but-malformed numbers (leniency probes).
_malformed_number = st.sampled_from([
    "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "007",
    "00", "-01", "1e", "1e+", "1e-", "1.2.3", "--1", "1..2",
    "0x1f", "Infinity", "-Infinity", "NaN", "1_000",
])

number = st.one_of(_normal_number, _extreme_number, _malformed_number)

# ---------------------------------------------------------------
# Malformed pieces (near-valid inputs)
# ---------------------------------------------------------------

_unterminated_string = st.builds(
    lambda pieces: '"' + "".join(pieces),
    st.lists(_string_piece, min_size=0, max_size=8),
)

_bad_string = st.one_of(
    _unterminated_string,
    st.just('"\\'),
    st.just('"abc'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('"\\x41"'),
    st.just("'single quoted'"),
)

# ---------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------

# We build these with st.recursive.  Depth is naturally bounded, but we
# additionally bias toward "interesting depth" near 2048 via a separate
# deep-nesting strategy below.

_key = st.one_of(
    json_string,
    st.sampled_from(['"k"', '"a"', '"key"', '""', '"\\u0000"', '"\\uD800"']),
)

# Malformed keys / separators for near-valid objects.
_bad_pair = st.sampled_from([
    '"k" 1', '"k":', '"k"', ':1', '"k"::1', 'k:1', '"k"=1',
])

# A "leaf" value (no recursion).
_leaf = st.one_of(
    json_string,
    number,
    st.sampled_from(["true", "false", "null"]),
    _bad_string,
)

def _value_strategy():
    return st.recursive(
        _leaf,
        lambda children: st.one_of(
            # arrays
            st.builds(
                lambda items: "[" + ",".join(items) + "]",
                st.lists(children, min_size=0, max_size=5),
            ),
            # objects
            st.builds(
                lambda pairs: "{" + ",".join(pairs) + "}",
                st.lists(
                    st.builds(
                        lambda k, v: k + ":" + v,
                        _key,
                        children,
                    ),
                    min_size=0,
                    max_size=5,
                ),
            ),
            # duplicate-key objects (expect rejection)
            st.builds(
                lambda v: '{"dup":0,"dup":' + v + "}",
                children,
            ),
            # near-valid malformed containers
            st.sampled_from([
                "[,]", "[1,,2]", "[1,2,]", "[1 2]", "[1;2]",
                "{,}", '{"a":1,}', '{"a":1,,}', '{"a" 1}',
                '{"a":}', '{:1}', '{"a":1 "b":2}',
                "[", "{", "]", "}", "[}", "{]",
            ]),
        ),
        max_leaves=20,
    )

_value = _value_strategy()

# ---------------------------------------------------------------
# Deep nesting near the 2048 limit
# ---------------------------------------------------------------

# Depth near 2048: 2040..2055 (some just under, some just over).
_near_limit_depth = st.integers(min_value=2040, max_value=2055)

def _deep_array(depth):
    return "[" * depth + "]" * depth

def _deep_object(depth):
    return '{"a":' * depth + "null" + "}" * depth

def _deep_mixed(depth):
    # alternate [ and {, close with matching ] and }
    opens = "".join("[" if i % 2 == 0 else "{" for i in range(depth))
    closes = "".join("]" if i % 2 == 0 else "}" for i in range(depth))[::-1]
    # fix close ordering: reverse of opens
    closes = "".join("]" if c == "[" else "}" for c in reversed(opens))
    return opens + "0" + closes

_deep = st.one_of(
    _near_limit_depth.map(_deep_array),
    _near_limit_depth.map(_deep_object),
    _near_limit_depth.map(_deep_mixed),
    st.integers(min_value=1, max_value=10).map(_deep_array),
    st.integers(min_value=1, max_value=10).map(_deep_object),
)

# ---------------------------------------------------------------
# Trailing content (accepted by this parser)
# ---------------------------------------------------------------

_trailing = st.sampled_from([
    "abc", " garbage", "xyz", "  ", "\n", "trailing",
    "{}", "[]", "1", "null", "/* comment */", "// line",
])

def _with_trailing(v):
    return v + _trailing.example() if False else v

# ---------------------------------------------------------------
# Serialization-exercise inputs (json_serialize_string coverage)
# ---------------------------------------------------------------

# Strings designed to be parsed then re-serialized, exercising
# json_serialize_string's escape/quote/backslash/control-char branches.
_serialize_string = st.one_of(
    json_string,
    st.builds(
        lambda pieces: '"' + "".join(pieces) + '"',
        st.lists(
            st.one_of(
                _safe_chars.map(str),
                _simple_escapes,
                _unicode_escapes,
                _surrogate_escapes,
                st.sampled_from([
                    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
                    "\\u0000", "\\u001f", "\\u007f", "\\u0080",
                    "\\u00e9", "\\u4e2d", "\\uD83D\\uDE00",
                ]),
            ),
            min_size=0,
            max_size=16,
        ),
    ),
)

# Containers full of strings of varied shapes, forcing the serializer
# to walk many string values.
_serialize_container = st.one_of(
    st.builds(
        lambda items: "[" + ",".join(items) + "]",
        st.lists(_serialize_string, min_size=1, max_size=8),
    ),
    st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                _serialize_string,
                st.one_of(_serialize_string, number, st.sampled_from(["true", "false", "null"])),
            ),
            min_size=1,
            max_size=8,
        ),
    ),
)

_serialize_input = st.one_of(_serialize_string, _serialize_container)

# ---------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------

def _top_level():
    return st.one_of(
        _value,
        _deep,
        # serialization-exercise inputs
        _serialize_input,
        # trailing content after a complete value
        st.tuples(_value, _trailing).map(lambda t: t[0] + t[1]),
        # whitespace-padded values
        st.tuples(
            st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
            _value,
            st.sampled_from(["", " ", "\t", "\n"]),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # empty containers and lone tokens
        st.sampled_from([
            "{}", "[]", "null", "true", "false", "0", "-0",
            "", " ", "\n", "\t",
        ]),
        # lone sign leniency
        st.sampled_from(["-", "-.", "-e", "-0"]),
    )

# ---------------------------------------------------------------
# Serialization-focused top level (json_serialize_string coverage)
# ---------------------------------------------------------------

# Build a JSON string literal from raw (unescaped) source characters,
# forcing json_serialize_string to escape quotes, backslashes, and
# control characters when the parsed value is re-serialized.
_raw_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
)

def _escaped_string_literal():
    return st.builds(
        lambda pieces: '"' + "".join(pieces) + '"',
        st.lists(
            st.one_of(
                _raw_char.map(str),
                st.just('\\"'),
                st.just("\\\\"),
                st.just("\\/"),
                st.just("\\b"),
                st.just("\\f"),
                st.just("\\n"),
                st.just("\\r"),
                st.just("\\t"),
                st.just("\\u0000"),
                st.just("\\u001f"),
                st.just("\\u007f"),
                st.just("\\u0080"),
                st.just("\\u00e9"),
                st.just("\\u4e2d"),
                st.just("\\uD83D\\uDE00"),
            ),
            min_size=1,
            max_size=24,
        ),
    )

_serialize_probe = st.one_of(
    _escaped_string_literal(),
    st.builds(
        lambda items: "[" + ",".join(items) + "]",
        st.lists(_escaped_string_literal(), min_size=1, max_size=10),
    ),
    st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                _escaped_string_literal(),
                _escaped_string_literal(),
            ),
            min_size=1,
            max_size=10,
        ),
    ),
)

# ---------------------------------------------------------------
# json_serialize_string coverage: raw control chars, quotes, backslashes,
# and multi-byte UTF-8 characters embedded in parsed string values.
# These are fed through a parse -> serialize round trip by the harness,
# so the string contents must be valid JSON string bodies that decode
# to characters exercising every branch of json_serialize_string.
# ---------------------------------------------------------------

# Raw (unescaped) characters that json_serialize_string must escape,
# wrapped as JSON string bodies so the parser accepts them.
_serialize_trigger_char = st.sampled_from([
    "\\\"",       # escaped quote -> serialized as \"
    "\\\\",       # escaped backslash -> serialized as \\
    "\\b",        # backspace control char
    "\\f",        # form feed control char
    "\\n",        # newline control char
    "\\r",        # carriage return control char
    "\\t",        # tab control char
    "\\u0000",    # NUL
    "\\u0001",    # low control
    "\\u001f",    # highest C0 control
    "\\u007f",    # DEL
    "\\u0080",    # first non-ASCII
    "\\u00ff",    # Latin-1
    "\\u07ff",    # 2-byte UTF-8 boundary
    "\\u0800",    # 3-byte UTF-8 start
    "\\uffff",    # 3-byte UTF-8 end
    "\\ud83d\\ude00",  # surrogate pair -> 4-byte UTF-8
    "\\u2028",    # line separator
    "\\u2029",    # paragraph separator
    "\\/",        # forward slash
    "a", "Z", "0", " ", "~", "!", "\\u00e9", "\\u4e2d",
])

# A single JSON string literal whose body mixes all the trigger chars.
_serialize_trigger_string = st.builds(
    lambda pieces: '"' + "".join(pieces) + '"',
    st.lists(_serialize_trigger_char, min_size=1, max_size=24),
)

# Arrays/objects packed with trigger strings so the serializer must
# walk many string values in one call.
_serialize_trigger_container = st.one_of(
    st.builds(
        lambda items: "[" + ",".join(items) + "]",
        st.lists(_serialize_trigger_string, min_size=1, max_size=12),
    ),
    st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                _serialize_trigger_string,
                _serialize_trigger_string,
            ),
            min_size=1,
            max_size=12,
        ),
    ),
)

# Nested containers so the serializer recurses into arrays/objects.
_serialize_trigger_nested = st.recursive(
    _serialize_trigger_string,
    lambda children: st.one_of(
        st.builds(
            lambda items: "[" + ",".join(items) + "]",
            st.lists(children, min_size=1, max_size=6),
        ),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(
                    lambda k, v: k + ":" + v,
                    _serialize_trigger_string,
                    children,
                ),
                min_size=1,
                max_size=6,
            ),
        ),
    ),
    max_leaves=15,
)

_serialize_trigger = st.one_of(
    _serialize_trigger_string,
    _serialize_trigger_container,
    _serialize_trigger_nested,
)

strategy = st.one_of(_top_level(), _serialize_probe, _serialize_trigger)