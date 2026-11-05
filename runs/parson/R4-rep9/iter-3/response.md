```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_simple_esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_unicode_esc = _hex4().map(lambda h: "\\u" + h)

_surrogate_esc = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD834\\uDD1E",
    "\\uD800\\uD800",
    "\\uDC00\\uDC00",
    "\\uD800",
    "\\uDC00",
])

_esc = st.one_of(_simple_esc, _unicode_esc, _surrogate_esc)

_str_piece = st.one_of(_safe_char, _esc)

_string_literal = st.lists(_str_piece, min_size=0, max_size=8).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_lead = st.builds(
    lambda d, rest: d + rest,
    st.sampled_from("123456789"),
    st.text("0123456789", min_size=0, max_size=6),
)
_int_part = st.one_of(st.just("0"), _nonzero_lead, _int_digits)

_frac = st.tuples(st.just("."), st.text("0123456789", min_size=1, max_size=6)).map(
    lambda t: t[0] + t[1]
)
_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text("0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "1E400", "1e-400", "-1e-400",
    "1.7976931348623157e308", "1.7976931348623159e308",
    "4.9e-324", "2.2250738585072014e-308",
    "0e0", "-0", "-0.0", "0.0", "1" + "0" * 400,
    "123456789012345678901234567890",
    "1e999999999", "1e-999999999",
])

_valid_number = st.one_of(
    st.tuples(
        st.sampled_from(["", "-"]),
        _int_part,
        st.one_of(st.just(""), _frac),
        st.one_of(st.just(""), _exp),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    _extreme_number,
)

_malformed_number = st.sampled_from([
    "-", "-.", "+1", "+0.5", ".5", "-.5", "1.", "01", "00", "-01",
    "1e", "1e+", "1e-", "1.2.3", "--1", "0x10", "1_000", "Infinity",
    "NaN", "-Infinity", "1e309x",
])

_number = st.one_of(_valid_number, _malformed_number)

# ---------------------------------------------------------------------------
# Malformed string fragments
# ---------------------------------------------------------------------------

_malformed_string = st.sampled_from([
    '"',
    '"abc',
    '"abc\\',
    '"abc\\"',
    '"\\u12"',
    '"\\uZZZZ"',
    '"\\x41"',
    '"a\nb"',
    '"a\tb"',
    '"a\x01b"',
    '"\x7f"',
    '"\\u0000"',
    '"ok"',
])

# ---------------------------------------------------------------------------
# Recursive value / object / array generation
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \n "])

def _join(parts):
    return "".join(parts)

_key = st.one_of(_string_literal, _malformed_string)

_scalar_text = st.one_of(
    _string_literal,
    _number,
    st.sampled_from(["true", "false", "null"]),
    _malformed_string,
)

def _extend(children):
    child = children

    pair = st.tuples(_key, _ws, st.just(":"), _ws, child).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

    obj = st.one_of(
        st.just("{}"),
        st.just("{ }"),
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        st.tuples(_string_literal, child).map(
            lambda t: '{"k":' + t[1] + ',"k":' + t[1] + "}"
        ),
        st.tuples(_string_literal, child).map(
            lambda t: "{" + t[0] + ":" + t[1] + ",}"
        ),
        st.tuples(_string_literal, child).map(
            lambda t: "{" + t[0] + " " + t[1] + "}"
        ),
    )

    arr = st.one_of(
        st.just("[]"),
        st.just("[ ]"),
        st.lists(child, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(child, min_size=1, max_size=3).map(
            lambda vs: "[" + ",".join(vs) + ",]"
        ),
        st.lists(child, min_size=2, max_size=3).map(
            lambda vs: "[" + ",,".join(vs) + "]"
        ),
    )

    return st.one_of(obj, arr)

_recursive_value = st.recursive(
    _scalar_text,
    _extend,
    max_leaves=12,
)

# ---------------------------------------------------------------------------
# Deep nesting near the 2048 limit
# ---------------------------------------------------------------------------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

_deep_nesting = st.one_of(
    st.integers(min_value=2000, max_value=2050).map(
        lambda d: _deep(d, "[", "]", "1")
    ),
    st.integers(min_value=2000, max_value=2050).map(
        lambda d: _deep(d, '{"a":', "}", "1")
    ),
    st.integers(min_value=2049, max_value=2100).map(
        lambda d: _deep(d, "[", "]", "0")
    ),
    st.integers(min_value=1000, max_value=1025).map(
        lambda d: _deep(d, '[{"a":', "}]", "1")
    ),
    st.integers(min_value=2040, max_value=2050).map(
        lambda d: "[" * d + "]" * d
    ),
)

# ---------------------------------------------------------------------------
# Trailing content / lenient forms
# ---------------------------------------------------------------------------

_trailing = st.one_of(
    _recursive_value,
    st.tuples(_recursive_value, st.sampled_from(["x", " garbage", " []xyz",
                                                 "1abc", "null", "{", "]"]))
    .map(lambda t: t[0] + t[1]),
)

_lenient_number = st.sampled_from(["-", "-.", "+", ".5", "1.", "01", "00"])

# ---------------------------------------------------------------------------
# Strings that exercise the serializer's per-character switch cases.
# The serializer walks every byte of the parsed string and emits an escape
# for each special char.  To hit all branches we need parsed string values
# containing each control byte, quote, backslash, slash, and high bytes.
# We craft JSON *source* text that parses to such strings (using \uXXXX
# escapes for control chars, since raw control chars are illegal in JSON).
# ---------------------------------------------------------------------------

_serializer_control_escapes = [
    "\\u0000", "\\u0001", "\\u0002", "\\u0003", "\\u0004", "\\u0005",
    "\\u0006", "\\u0007", "\\b", "\\t", "\\n", "\\u000b", "\\f", "\\r",
    "\\u000e", "\\u000f", "\\u0010", "\\u0011", "\\u0012", "\\u0013",
    "\\u0014", "\\u0015", "\\u0016", "\\u0017", "\\u0018", "\\u0019",
    "\\u001a", "\\u001b", "\\u001c", "\\u001d", "\\u001e", "\\u001f",
]

_serializer_escape_chars = ["\\\"", "\\\\", "\\/"]

# A source string literal whose parsed value contains MANY special chars,
# so a single serialize call exercises most switch cases.
_serializer_kitchen_sink = st.lists(
    st.one_of(
        st.sampled_from(_serializer_control_escapes),
        st.sampled_from(_serializer_escape_chars),
        st.sampled_from(list("abcXYZ0123 /~!@#$%^&*()[]{}")),
        _unicode_esc,
    ),
    min_size=1,
    max_size=48,
).map(lambda parts: '"' + "".join(parts) + '"')

# A source string containing every control escape at least once.
_serializer_full_controls = st.just(
    '"' + "".join(_serializer_control_escapes)
    + '\\"\\\\\\/abcXYZ' + '"'
)

# Strings with a slash, to exercise the parson_escape_slashes branch.
_serializer_slashes = st.lists(
    st.one_of(st.sampled_from(["\\/", "/", "a", "\\\"", "\\\\"])),
    min_size=1,
    max_size=16,
).map(lambda parts: '"' + "".join(parts) + '"')

_serializer_strings = st.one_of(
    _serializer_kitchen_sink,
    _serializer_full_controls,
    _serializer_slashes,
)

# Wrap serializer-target strings in containers so serialize/copy/equals/get
# code paths are actually reached (a bare scalar may be short-circuited).
_serializer_document = st.one_of(
    _serializer_strings,
    st.tuples(_serializer_strings).map(lambda t: "[" + t[0] + "]"),
    st.tuples(_serializer_strings).map(lambda t: '{"k":' + t[0] + "}"),
    st.tuples(_serializer_strings, _serializer_strings).map(
        lambda t: "[" + t[0] + "," + t[1] + "]"
    ),
    st.tuples(_serializer_strings, _serializer_strings).map(
        lambda t: '{"a":' + t[0] + ',"b":' + t[1] + "}"
    ),
    # nested so deep_copy recurses through object/array nodes
    st.tuples(_serializer_strings).map(
        lambda t: '{"a":{"b":[' + t[0] + ',{"c":' + t[0] + "}]}}"
    ),
    # duplicate keys / equal structures to exercise json_value_equals
    st.tuples(_serializer_strings).map(
        lambda t: "[" + t[0] + "," + t[0] + "]"
    ),
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

_wellformed_or_edge = st.one_of(
    _recursive_value,
    _deep_nesting,
    _trailing,
    _lenient_number,
    _malformed_string,
    _malformed_number,
    _serializer_document,
    st.just(""),
    st.just(" "),
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
)

strategy = _wellformed_or_edge
```