Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Bytes / characters that are SAFECODEPOINT-ish but include control/NUL on purpose.
_control_chars = st.sampled_from(
    ["\x00", "\x01", "\x1f", "\x7f", "\x08", "\x0b", "\x0c", "\x1e"]
)

# Plain printable ASCII (no quote/backslash) for realistic strings.
_plain_chars = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x7E,
    blacklist_characters='"\\',
)

_unicode_chars = st.characters(min_codepoint=0x00A0, max_codepoint=0x2FFF)

# Escapes that the grammar allows: \" \\ \/ \b \f \n \r \t and \uXXXX
_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_unicode_escape = st.tuples(
    st.just("\\u"),
    _hex,
    _hex,
    _hex,
    _hex,
).map("".join)

# Surrogate escapes (lone high/low surrogates and valid pairs).
_surrogate_escape = st.tuples(
    st.sampled_from(["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF"]),
    st.one_of(
        st.just(""),
        st.tuples(st.sampled_from(["\\uD800", "\\uDBFF"]), _hex, _hex, _hex, _hex).map("".join),
        st.tuples(st.sampled_from(["\\uDC00", "\\uDFFF"]), _hex, _hex, _hex, _hex).map("".join),
    ),
).map("".join)

_string_inner = st.one_of(
    _plain_chars.map(lambda c: c),
    _control_chars,
    _unicode_chars,
    _simple_escapes,
    _unicode_escape,
    _surrogate_escape,
)

# A well-formed JSON string literal.
json_string = st.lists(_string_inner, max_size=12).map(lambda parts: '"' + "".join(parts) + '"')

# Unterminated strings (no closing quote) -- malformed.
unterminated_string = st.lists(_string_inner, min_size=0, max_size=8).map(
    lambda parts: '"' + "".join(parts)
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_digit = st.sampled_from("0123456789")
_nonzero = st.sampled_from("123456789")

# Valid INT: '0' or [1-9][0-9]*
_valid_int = st.one_of(
    st.just("0"),
    st.tuples(_nonzero, st.lists(_digit, max_size=6).map("".join)).map("".join),
)

# Extreme magnitudes / exponents.
_extreme_int = st.sampled_from(
    [
        "0",
        "-0",
        "1",
        "-1",
        "9007199254740993",  # > 2^53
        "18446744073709551616",  # > 2^64
        "1234567890123456789012345678901234567890",
        "-1234567890123456789012345678901234567890",
        "9999999999999999999999999999999999999999",
    ]
)

_frac = st.tuples(st.just("."), st.lists(_digit, min_size=1, max_size=8).map("".join)).map("".join)

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.one_of(st.just(""), st.sampled_from(["+", "-"])),
    st.lists(_digit, min_size=1, max_size=6).map("".join),
).map("".join)

_extreme_exp = st.sampled_from(
    ["e309", "E309", "e-309", "e+308", "e9999", "E-9999", "e2147483648", "e-2147483649"]
)

# Valid number per grammar.
valid_number = st.one_of(
    _valid_int,
    st.tuples(st.just("-"), _valid_int).map("".join),
    st.tuples(_valid_int, _frac).map("".join),
    st.tuples(st.just("-"), _valid_int, _frac).map("".join),
    st.tuples(_valid_int, _exp).map("".join),
    st.tuples(st.just("-"), _valid_int, _exp).map("".join),
    st.tuples(_valid_int, _frac, _exp).map("".join),
    st.tuples(st.just("-"), _valid_int, _frac, _exp).map("".join),
    _extreme_int,
    st.tuples(_extreme_int, _extreme_exp).map("".join),
    st.tuples(st.just("-"), _extreme_int, _extreme_exp).map("".join),
)

# Malformed / near-valid numbers (leading +, .5, 01, trailing dot, lone -, hex).
malformed_number = st.sampled_from(
    [
        "+1",
        "+0",
        ".5",
        "-.5",
        "1.",
        "-1.",
        "01",
        "00",
        "-01",
        "0x1F",
        "0X10",
        "-",
        "--1",
        "1e",
        "1e+",
        "1e-",
        "1..2",
        "1.2.3",
        "Infinity",
        "NaN",
        "1_000",
        "1,2",
    ]
)

number = st.one_of(valid_number, malformed_number)

# ---------------------------------------------------------------------------
# Malformed fragments (double commas, missing colons, etc.)
# ---------------------------------------------------------------------------

_double_comma = st.just(",,")
_missing_colon = st.tuples(json_string, st.just(" ")).map("".join)  # key without colon
_leading_comma = st.just(",")

# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

# We build values with st.recursive. Leaves are scalars; composites are obj/arr.

_scalar = st.one_of(
    json_string,
    number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    # malformed scalars that are still "value-ish"
    unterminated_string,
)

def _join_parts(parts):
    return "".join(parts)

# Object: bias toward objects with members (the stressed path).
# Also include empty {} and duplicate keys and a single trailing comma.
_pair = st.tuples(json_string, st.just(":"), st.deferred(lambda: _value)).map(_join_parts)

_obj_with_members = st.tuples(
    st.just("{"),
    st.lists(_pair, min_size=1, max_size=5).map(lambda ps: ",".join(ps)),
    st.just("}"),
).map(_join_parts)

_obj_empty = st.just("{}")

# Duplicate keys: same key repeated.
_dup_key_pair = st.tuples(
    json_string,
    st.just(":"),
    st.deferred(lambda: _value),
).map(_join_parts)

_obj_dup_keys = st.tuples(
    st.just("{"),
    st.tuples(json_string, st.just(":"), st.deferred(lambda: _value)).map(_join_parts),
    st.just(","),
    st.tuples(json_string, st.just(":"), st.deferred(lambda: _value)).map(_join_parts),
    st.just("}"),
).map(_join_parts)

# Single trailing comma object.
_obj_trailing_comma = st.tuples(
    st.just("{"),
    st.lists(_pair, min_size=1, max_size=3).map(lambda ps: ",".join(ps)),
    st.just(",}"),
).map(_join_parts)

# Malformed object: missing colon, double comma, leading comma.
_obj_malformed = st.one_of(
    st.tuples(st.just("{"), json_string, st.just(" "), st.deferred(lambda: _value), st.just("}")).map(_join_parts),
    st.tuples(st.just("{"), _pair, st.just(",,"), _pair, st.just("}")).map(_join_parts),
    st.tuples(st.just("{"), st.just(","), _pair, st.just("}")).map(_join_parts),
    st.tuples(st.just("{"), _pair, st.just(","), st.just("}")).map(_join_parts),
)

_obj = st.one_of(
    _obj_empty,
    _obj_with_members,
    _obj_dup_keys,
    _obj_trailing_comma,
    _obj_malformed,
)

# Array: empty, with members, trailing comma, malformed.
_arr_empty = st.just("[]")

_arr_with_members = st.tuples(
    st.just("["),
    st.lists(st.deferred(lambda: _value), min_size=1, max_size=5).map(lambda vs: ",".join(vs)),
    st.just("]"),
).map(_join_parts)

_arr_trailing_comma = st.tuples(
    st.just("["),
    st.lists(st.deferred(lambda: _value), min_size=1, max_size=3).map(lambda vs: ",".join(vs)),
    st.just(",]"),
).map(_join_parts)

_arr_malformed = st.one_of(
    st.tuples(st.just("["), st.deferred(lambda: _value), st.just(",,"), st.deferred(lambda: _value), st.just("]")).map(_join_parts),
    st.tuples(st.just("["), st.just(","), st.deferred(lambda: _value), st.just("]")).map(_join_parts),
    st.tuples(st.just("["), st.deferred(lambda: _value), st.just(","), st.just("]")).map(_join_parts),
    st.tuples(st.just("["), st.just(","), st.just("]")).map(_join_parts),
    st.tuples(st.just("["), st.just("]"), st.just("xyz")).map(_join_parts),
    st.tuples(st.just("["), st.just("]"), st.just(" "), st.just("true")).map(_join_parts),
)

_arr = st.one_of(
    _arr_empty,
    _arr_with_members,
    _arr_trailing_comma,
    _arr_malformed,
)

_value = st.recursive(
    _scalar,
    lambda children: st.one_of(
        st.tuples(st.just("{"), _pair, st.just("}")).map(_join_parts),
        _obj,
        _arr,
    ),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Top-level: json : value EOF, with optional whitespace and trailing garbage.
# ---------------------------------------------------------------------------

# Deep nesting helper: many '[' or '{' layers. No depth cap, so vary freely.
def _deep_nesting():
    depth = st.integers(min_value=0, max_value=200)
    open_c = st.sampled_from(["["])
    close_c = st.sampled_from(["]"])
    return st.builds(
        lambda d, o, c: o * d + c * d,
        depth,
        open_c,
        close_c,
    )

_deep_arr = st.integers(min_value=0, max_value=300).map(lambda d: "[" * d + "]" * d)
_deep_obj = st.integers(min_value=0, max_value=300).map(
    lambda d: "{" + '"a":' * d + "null" + "}" * d
)

# NUL / control bytes embedded at top level and inside strings.
_nul_payload = st.one_of(
    st.just("\x00"),
    st.just('"\x00"'),
    st.just('{"a\x00b":1}'),
    st.just('["\x00",1]'),
    st.just("\x00\x01\x02"),
)

# Trailing garbage after a complete value (should be rejected).
_trailing_garbage = st.one_of(
    st.just("1abc"),
    st.just("[]xyz"),
    st.just("1 garbage"),
    st.just("true false"),
    st.just("{}extra"),
)

# Whole documents.
_document = st.one_of(
    _value,
    st.tuples(_ws, _value, _ws).map(_join_parts),
    _deep_arr,
    _deep_obj,
    _nul_payload,
    _trailing_garbage,
    # lone '-' (accepted per notes)
    st.just("-"),
    # top-level malformed
    st.just("{"),
    st.just("}"),
    st.just("["),
    st.just("]"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just("{,}"),
    st.just('{"a":1,}'),
    st.just("[1,2,]"),
    st.just('{"a":1,"a":2}'),
    st.just("1e309"),
    st.just('"\\uD800"'),
    st.just('"\\uDC00\\uD800"'),
    st.just('"unterminated'),
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("0x1F"),
    st.just("// comment"),
    st.just("/* comment */1"),
    st.just("'single'"),
    st.just("{a:1}"),
)

strategy = _document
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 4,
    "reject": 22,
    "crash": 3
  },
  "acceptance_rate": 0.138,
  "max_nesting_depth": 294,
  "productions_accepted": [
    "STRING",
    "arr",
    "json",
    "value"
  ],
  "productions_gap": [
    "obj",
    "pair",
    "NUMBER",
    "true",
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 3,
  "divergences": 2,
  "divergence_examples": [
    "b'\"\\\\uD800\"'",
    "b'[1,2,]'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.