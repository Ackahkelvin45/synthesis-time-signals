```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07'
    '\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17'
    '\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_SIMPLE_ESCAPES = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_HEX = "0123456789abcdefABCDEF"
_hex4 = st.text(alphabet=_HEX, min_size=4, max_size=4)
_unicode_escape = _hex4.map(lambda h: "\\u" + h)

_SURROGATE_ESCAPES = st.sampled_from(
    [
        "\\ud800", "\\udbff", "\\udc00", "\\udfff",
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
        "\\u0000", "\\u001f", "\\u007f", "\\uffff",
        "\\u00e9", "\\u20ac", "\\u4e2d",
        "\\ud83d\\ude00", "\\ud800\\udc00", "\\udbff\\udfff",
        "\\uD83D\\uDE00", "\\uD800\\uDC00",
    ]
)

_STRING_BODY = st.one_of(
    _SAFE_CHARS,
    _SIMPLE_ESCAPES,
    _unicode_escape,
    _SURROGATE_ESCAPES,
)

_string = st.lists(_STRING_BODY, max_size=12).map("".join).map(lambda s: '"' + s + '"')

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

_FRAC = st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n).zfill(1))

_EXP = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=400).map(str),
)

_legal_number = st.builds(
    lambda neg, i, f, e: neg + i + f + e,
    st.sampled_from(["", "-"]),
    _INT,
    st.one_of(st.just(""), _FRAC),
    st.one_of(st.just(""), _EXP),
)

_extreme_numbers = st.sampled_from(
    [
        "1e309", "-1e309", "1E309", "1e308", "1e-309", "1e999999",
        "-1e999999", "0e0", "0e999", "1e+308", "1e-308",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1.7976931348623157e309",
        "2.2250738585072014e-308",
        "1e2147483647", "1e-2147483648",
        "0.0000000000000000000000000000001",
        "99999999999999999999999999999999999999",
    ]
)

_malformed_numbers = st.sampled_from(
    [
        "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "-01", "00",
        "1.e5", "0x1f", "1_000", "--1", "1..2", "1e", "1e+", "1e-",
    ]
)

_number = st.one_of(_legal_number, _extreme_numbers, _malformed_numbers)

_ATOM = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_WS = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t "])

_dup_pair = st.builds(
    lambda k, v1, v2, ws: ws + k + ws + ":" + ws + v1 + ws + "," + ws + k + ws + ":" + ws + v2 + ws,
    _string,
    _ATOM,
    _ATOM,
    _WS,
)

_json_value = st.recursive(
    _ATOM,
    lambda children: st.one_of(
        st.builds(
            lambda ws, vals: ws + "[" + ws + ("," + ws).join(vals) + ws + "]",
            _WS,
            st.lists(children, min_size=0, max_size=5),
        ),
        st.builds(
            lambda ws, pairs: ws + "{" + ws + ("," + ws).join(pairs) + ws + "}",
            _WS,
            st.lists(
                st.builds(
                    lambda k, v, w: w + k + w + ":" + w + v + w,
                    _string,
                    children,
                    _WS,
                ),
                min_size=0,
                max_size=5,
            ),
        ),
        st.builds(
            lambda ws, p: ws + "{" + ws + p + ws + "}",
            _WS,
            _dup_pair,
        ),
    ),
    max_leaves=20,
)

_DEPTHS = st.one_of(
    st.integers(min_value=0, max_value=10),
    st.integers(min_value=1000, max_value=2100),
    st.sampled_from([2000, 2040, 2047, 2048, 2049, 2050, 2100, 3000]),
)

_deep_nesting = st.builds(
    lambda d, opener, closer, inner: opener * d + inner + closer * d,
    _DEPTHS,
    st.sampled_from(["[", "{"]),
    st.sampled_from(["]", "}"]),
    st.one_of(st.just(""), _ATOM),
)

_deep_balanced = _DEPTHS.map(
    lambda d: "[" * d + "0" + "]" * d
)

_deep_balanced_obj = _DEPTHS.map(
    lambda d: '{"k":' * d + "0" + "}" * d
)

_malformed = st.sampled_from(
    [
        "[1,,2]", "[,]", "[1,]", '{"a":1,,}', '{"a":1,}', "{,}",
        "[1,2,]", '{"a":1,"b":2,}',
        '{"a" 1}', '{"a"}', '{"a":}', '{:1}', '{"a":1 "b":2}',
        '"abc', '"', '{"a":"abc}', '["abc]', '"abc\\"',
        "[1,2", '{"a":1', "[", "{", "[[[", "{{{",
        "]", "}", "[}]", "{]}", "[]]", "{}]",
        "+1", ".5", "01", "-01", "1.", "-", "-.",
        "[1 2]", "truefalse", "nul", "tru", "fals",
        "{\"a\":}", "{\"a\":,}", "[,1]",
        '{"a":1}garbage', "1abc", "[]xyz", "nullnull",
        "\"\\u12\"", "\"\\uGGGG\"", "\"\\x41\"", "\"\\\"",
    ]
)

_trailing = st.builds(
    lambda v, t: v + t,
    _json_value,
    st.sampled_from(["", " ", "garbage", "xyz", "1abc", "[]", "{}", "null", "\n", "\t"]),
)

# ---------------------------------------------------------------------------
# Valid documents that exercise serialize / deep-copy / equals / validate.
# These are guaranteed valid JSON so the parser can hand them to those
# routines.  We make them richer and more numerous to hit the 0%-covered
# functions.
# ---------------------------------------------------------------------------

# A compact but rich valid value, built without whitespace noise.
_compact_value = st.recursive(
    st.one_of(
        _string,
        _legal_number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    ),
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=6).map(
            lambda vals: "[" + ",".join(vals) + "]"
        ),
        st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                _string,
                children,
            ),
            min_size=0,
            max_size=6,
        ).map(lambda pairs: "{" + ",".join(pairs) + "}"),
    ),
    max_leaves=25,
)

_valid_doc = st.builds(
    lambda v, ws: v + ws,
    _compact_value,
    st.sampled_from(["", " ", "\n", "\r\n", "\t", "  \n"]),
)

_valid_doc_rich_strings = st.builds(
    lambda a, b: '{"s":"' + a + '","t":"' + b + '","n":' + "1" + "}",
    st.one_of(_SURROGATE_ESCAPES, _SIMPLE_ESCAPES, _unicode_escape),
    st.one_of(_SURROGATE_ESCAPES, _SIMPLE_ESCAPES, _unicode_escape),
)

# A valid document that is guaranteed to round-trip through serialize:
# it contains only plain ASCII-safe strings, legal numbers, booleans, null,
# and nested arrays/objects.  This maximizes the chance the parser actually
# reaches json_serialize_string / json_serialize_to_buffer_r / deep_copy /
# equals / validate on a successful parse.
_plain_string = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Pc"),
        whitelist_characters=" _-./",
    ),
    min_size=0,
    max_size=8,
).map(lambda s: '"' + s + '"')

_plain_atom = st.one_of(
    _plain_string,
    _legal_number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_plain_value = st.recursive(
    _plain_atom,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=4).map(
            lambda vals: "[" + ",".join(vals) + "]"
        ),
        st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                _plain_string,
                children,
            ),
            min_size=0,
            max_size=4,
        ).map(lambda pairs: "{" + ",".join(pairs) + "}"),
    ),
    max_leaves=15,
)

# Valid documents with interesting string content designed to hit the
# serializer's escape-emission branches (control chars, quotes, backslashes,
# and non-ASCII code points that must be re-escaped or passed through).
_serialize_torture_string = st.one_of(
    # Raw control characters that must be re-escaped on serialize.
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Cc",),
            blacklist_characters="\x00",
        ),
        min_size=1,
        max_size=4,
    ),
    # Quote / backslash / slash characters that need escaping.
    st.text(alphabet=st.sampled_from(['"', "\\", "/"]), min_size=1, max_size=4),
    # Non-ASCII BMP characters that may serialize as-is or as \uXXXX.
    st.text(
        alphabet=st.characters(
            min_codepoint=0x80,
            max_codepoint=0xFFFF,
            blacklist_categories=("Cs",),
        ),
        min_size=1,
        max_size=4,
    ),
    # Astral characters (above U+FFFF) requiring surrogate-pair escaping.
    st.text(
        alphabet=st.characters(
            min_codepoint=0x10000,
            max_codepoint=0x10FFFF,
            blacklist_categories=("Cs",),
        ),
        min_size=1,
        max_size=3,
    ),
).map(lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"')

_serialize_torture_doc = st.builds(
    lambda a, b, c: '{"a":' + a + ',"b":[' + b + "," + c + "]}",
    _serialize_torture_string,
    _serialize_torture_string,
    _serialize_torture_string,
)

# Valid documents with deeply nested but balanced structures that exercise
# deep-copy and equals recursion on successfully parsed values.
_valid_deep_doc = st.builds(
    lambda d, leaf: "[" * d + leaf + "]" * d,
    st.integers(min_value=1, max_value=64),
    _plain_atom,
)

_valid_deep_obj_doc = st.builds(
    lambda d, leaf: '{"k":' * d + leaf + "}" * d,
    st.integers(min_value=1, max_value=64),
    _plain_atom,
)

# Valid documents with objects containing many distinct keys, to exercise
# equals/validate over larger member sets.
_valid_wide_obj = st.builds(
    lambda pairs: "{" + ",".join(pairs) + "}",
    st.lists(
        st.builds(
            lambda k, v: k + ":" + v,
            _plain_string,
            _plain_atom,
        ),
        min_size=0,
        max_size=12,
    ),
)

# A valid document wrapped in a JSON array to vary the top-level container.
_valid_array_doc = st.builds(
    lambda vals: "[" + ",".join(vals) + "]",
    st.lists(_plain_atom, min_size=0, max_size=12),
)

# ---------------------------------------------------------------------------
# NEW: rich, deeply-structured valid documents that force the parser down the
# success path all the way to serialize / deep-copy / equals / validate.
# These combine plain atoms (so serialization round-trips) with rich nesting
# and many members, maximizing recursive coverage of the 0%-covered routines.
# ---------------------------------------------------------------------------

_rich_key = st.one_of(
    _plain_string,
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
        ),
        min_size=1,
        max_size=6,
    ).map(lambda s: '"' + s + '"'),
)

# A guaranteed-valid value (plain atoms only) with rich nesting and wide
# containers.  This is what actually reaches serialize/deep_copy/equals.
_roundtrip_value = st.recursive(
    _plain_atom,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=8).map(
            lambda vals: "[" + ",".join(vals) + "]"
        ),
        st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                _rich_key,
                children,
            ),
            min_size=0,
            max_size=8,
        ).map(lambda pairs: "{" + ",".join(pairs) + "}"),
    ),
    max_leaves=40,
)

# Wrap the roundtrip value in various top-level shapes to vary entry points.
_roundtrip_doc = st.one_of(
    _roundtrip_value,
    st.builds(lambda v: "[" + v + "]", _roundtrip_value),
    st.builds(lambda v: '{"root":' + v + "}", _roundtrip_value),
    st.builds(
        lambda v, ws: v + ws,
        _roundtrip_value,
        st.sampled_from(["", " ", "\n", "\r\n", "\t", "  \n", "\n\t "]),
    ),
)

# A document with many duplicate keys to exercise equals/validate over
# member sets where equality must compare values.
_dup_key_doc = st.builds(
    lambda k, vals: "{" + ",".join(k + ":" + v for v in vals) + "}",
    _plain_string,
    st.lists(_plain_atom, min_size=2, max_size=6),
)

# A document that is a large array of nested arrays/objects to stress
# deep_copy and equals recursion breadth.
_wide_nested_array = st.builds(
    lambda vals: "[" + ",".join(vals) + "]",
    st.lists(_roundtrip_value, min_size=0, max_size=10),
)

# A document with mixed valid nesting depths designed to exercise
# deep-copy recursion at moderate depth (well under limits).
_moderate_deep = st.builds(
    lambda d, leaf, kind: (
        ("[" * d + leaf + "]" * d)
        if kind == 0
        else ('{"k":' * d + leaf + "}" * d)
    ),
    st.integers(min_value=1, max_value=40),
    _plain_atom,
    st.integers(min_value=0, max_value=1),
)

# ---------------------------------------------------------------------------
# NEW: bare-atom valid documents.  The 0%-covered functions (serialize,
# deep_copy, equals, validate) are likely only invoked for *valid* documents
# whose top-level value is a scalar (string / number / literal).  Many of the
# existing "valid" generators wrap everything in containers, so add explicit
# top-level scalars that guarantee a successful parse reaching those routines.
# ---------------------------------------------------------------------------

_bare_scalar_doc = st.one_of(
    # Top-level strings with escaped content (hits json_serialize_string).
    _serialize_torture_string,
    _plain_string,
    # Top-level legal numbers.
    _legal_number,
    # Top-level literals.
    st.just("true"),
    st.just("false"),
    st.just("null"),
    # Top-level string with simple escapes.
    st.builds(
        lambda a, b: '"' + a + b + '"',
        st.one_of(_SIMPLE_ESCAPES, st.just("")),
        st.one_of(_SIMPLE_ESCAPES, st.just("")),
    ),
    # Top-level string with \u escapes.
    st.builds(
        lambda a: '"' + a + '"',
        _unicode_escape,
    ),
)

# A guaranteed-valid document whose top level is an object with a single
# scalar member, ensuring serialize/deep_copy/equals/validate run on a
# non-trivial but reliably-valid value.
_single_member_doc = st.builds(
    lambda k, v: "{" + k + ":" + v + "}",
    _plain_string,
    _plain_atom,
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _json_value,
    _deep_nesting,
    _deep_balanced,
    _deep_balanced_obj,
    _malformed,
    _trailing,
    _extreme_numbers,
    _malformed_numbers,
    _valid_doc,
    _valid_doc_rich_strings,
    _serialize_torture_doc,
    _valid_deep_doc,
    _valid_deep_obj_doc,
    _valid_wide_obj,
    _valid_array_doc,
    _roundtrip_doc,
    _dup_key_doc,
    _wide_nested_array,
    _moderate_deep,
    _bare_scalar_doc,
    _single_member_doc,
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("{}"),
    st.just("[]"),
    st.just('""'),
    st.just("0"),
    st.just('{"k":0,"k":1}'),
    st.just("1e309"),
    st.just("[" * 2048 + "0" + "]" * 2048),
    st.just("[" * 2049 + "0" + "]" * 2049),
)
```