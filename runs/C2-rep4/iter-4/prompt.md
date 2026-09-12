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
# Near-crash intensification: structurally mutate around the crashing input.
# The observed crash was on a lone-surrogate string escape, e.g. b'"\\uD800"'.
# We generate structural variants of an array/object containing such strings,
# with small perturbations (extra elements, trailing/leading commas, nesting,
# unterminated variants) to probe the same code path more aggressively.
# ---------------------------------------------------------------------------

# The crashing "seed" string literal: a quoted lone-surrogate escape.
_crash_string = st.sampled_from(
    [
        '"\\uD800"',
        '"\\uDBFF"',
        '"\\uDC00"',
        '"\\uDFFF"',
        '"\\uD800\\uD800"',
        '"\\uDC00\\uDC00"',
        '"\\uD800\\uDC00"',
        '"\\uD800a"',
        '"a\\uD800"',
    ]
)

# Strings that are unterminated variants of the crash seed.
_crash_string_unterminated = st.sampled_from(
    [
        '"\\uD800',
        '"\\uDBFF',
        '"\\uDC00',
        '"\\uDFFF',
        '"\\uD80',
        '"\\uD8',
        '"\\uD',
        '"\\u',
    ]
)

# Small numeric/whitespace perturbations used as siblings.
_crash_sibling = st.one_of(
    st.just("1"),
    st.just("0"),
    st.just("-1"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just(""),
    _crash_string,
)

# Array containing the crash seed, with optional structural perturbations.
_crash_array = st.builds(
    lambda lead, elems, trail, close: "[" + lead + ",".join(elems) + trail + close,
    st.sampled_from(["", ",", " ", "\n"]),
    st.lists(
        st.one_of(_crash_string, _crash_string_unterminated, _crash_sibling),
        min_size=1,
        max_size=4,
    ),
    st.sampled_from(["", ",", ",,", " ", ", "]),
    st.sampled_from(["]", "", "]", " ]"]),
)

# Object containing the crash seed as a value (and possibly key).
_crash_object = st.builds(
    lambda lead, pairs, trail, close: "{" + lead + ",".join(pairs) + trail + close,
    st.sampled_from(["", ",", " ", "\n"]),
    st.lists(
        st.builds(
            lambda k, v: k + ":" + v,
            st.one_of(st.just('"a"'), st.just('"k"'), _crash_string),
            st.one_of(_crash_string, _crash_string_unterminated, _crash_sibling),
        ),
        min_size=1,
        max_size=4,
    ),
    st.sampled_from(["", ",", ",,", " ", ", "]),
    st.sampled_from(["}", "", "}", " }"]),
)

# Nested wrapping of the crash structures to stress depth-sensitive paths.
_crash_nested = st.builds(
    lambda d, inner: "[" * d + inner + "]" * d,
    st.integers(min_value=0, max_value=40),
    st.one_of(_crash_array, _crash_object, _crash_string, _crash_string_unterminated),
)

# Wrapped in an object key position too.
_crash_key = st.builds(
    lambda s: "{" + s + ":1}",
    st.one_of(_crash_string, _crash_string_unterminated),
)

# Bare seeds, possibly with surrounding whitespace.
_crash_bare = st.one_of(
    _crash_string,
    _crash_string_unterminated,
    st.builds(lambda a, b, c: a + b + c, _ws, _crash_string, _ws),
)

# --- Intensified structural mutators around the crashing lone-surrogate seed. ---
# These are byte-/structure-level perturbations that keep the crashing escape
# in the input while varying the surrounding grammar context aggressively.

# Surrogate escape fragments (without surrounding quotes) for splicing.
_surr_escapes = st.sampled_from(
    [
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
        "\\uD800\\uD800", "\\uDC00\\uDC00", "\\uD800\\uDC00",
        "\\uD80", "\\uD8", "\\uD", "\\u",
    ]
)

# Quote/backslash corruption around the surrogate escape.
_quote_corrupt = st.builds(
    lambda pre, esc, mid, post: pre + esc + mid + post,
    st.sampled_from(['"', '""', '\\"', '"\\', '\\', '', '" ']),
    _surr_escapes,
    st.sampled_from(['"', '""', '\\"', '', '\\', '" ', ' "']),
    st.sampled_from(['"', '', '\\"', 'x"', '\\', '" ']),
)

# Deeply nested arrays/objects with the crash string at varying positions.
_deep_crash = st.builds(
    lambda d_open, d_close, inner: d_open + inner + d_close,
    st.integers(min_value=0, max_value=120).map(lambda d: "[" * d),
    st.integers(min_value=0, max_value=120).map(lambda d: "]" * d),
    st.one_of(
        _crash_string,
        _crash_string_unterminated,
        _quote_corrupt,
        st.builds(lambda a, b: a + b, _crash_string, _crash_sibling),
        st.builds(lambda a, b: a + "," + b, _crash_string, _crash_sibling),
    ),
)

# Comma/whitespace-heavy splatter around the seed.
_comma_splatter = st.builds(
    lambda lead, esc, trail: lead + esc + trail,
    st.sampled_from(["", ",", ",,", "[", "{", "[,", "{,", "[ ", "{ "]),
    st.one_of(_crash_string, _crash_string_unterminated, _quote_corrupt),
    st.sampled_from(["", ",", ",,", "]", "}", ",]", ",}", " ]", " }", ","]),
)

# Object/array with the crash key AND crash value plus perturbations.
_crash_kv = st.builds(
    lambda k, sep, v, tail: k + sep + v + tail,
    st.one_of(_crash_string, _crash_string_unterminated, _quote_corrupt),
    st.sampled_from([":", "::", " : ", ":", ": "]),
    st.one_of(_crash_string, _crash_string_unterminated, _quote_corrupt, _crash_sibling),
    st.sampled_from(["", ",", ",,", "}", ",}", "]", ",]"]),
)

# Mixed nesting of arrays and objects around the seed.
_mixed_nest = st.builds(
    lambda d, inner: ("[" * (d // 2)) + ("{" * (d - d // 2)) + inner
                     + ("}" * (d - d // 2)) + ("]" * (d // 2)),
    st.integers(min_value=0, max_value=60),
    st.one_of(_crash_string, _crash_string_unterminated, _quote_corrupt, _crash_kv),
)

# Splice the surrogate escape directly adjacent to structural punctuation.
_adjacent_punct = st.builds(
    lambda a, b, c: a + b + c,
    st.sampled_from(["", "[", "{", ",", ":", " ", "\n", "\t", "[]", "{}"]),
    st.one_of(_crash_string, _crash_string_unterminated, _quote_corrupt),
    st.sampled_from(["", "]", "}", ",", ":", " ", "\n", "\t", "[]", "{}"]),
)

# Concatenations of multiple crash seeds (repetition stress).
_crash_repeat = st.builds(
    lambda sep, items: sep.join(items),
    st.sampled_from(["", ",", " ", ", ", "\n"]),
    st.lists(
        st.one_of(_crash_string, _crash_string_unterminated, _quote_corrupt),
        min_size=1,
        max_size=6,
    ),
)

_crash_intensify = st.one_of(
    _crash_array,
    _crash_object,
    _crash_nested,
    _crash_key,
    _crash_bare,
    _deep_crash,
    _comma_splatter,
    _crash_kv,
    _mixed_nest,
    _adjacent_punct,
    _crash_repeat,
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
    # intensified near-crash structural mutants
    _crash_intensify,
)

strategy = _document
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 9,
    "reject": 36,
    "crash": 9
  },
  "acceptance_rate": 0.167,
  "max_nesting_depth": 36,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "json",
    "obj",
    "value"
  ],
  "productions_gap": [
    "pair",
    "true",
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 6,
  "divergences": 12,
  "divergence_examples": [
    "b'\"\\\\uD800\"'",
    "b'-'",
    "b'[\"\\\\uD800\"]'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.