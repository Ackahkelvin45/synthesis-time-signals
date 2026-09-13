Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf / primitive strategies
# ---------------------------------------------------------------------------

# Safe, ordinary string contents (no raw control chars, no raw NUL).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00',
    min_codepoint=0x20,
)

# Escapes that are legal inside a JSON string.
_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))
_unicode_esc = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes (legal as text in the grammar; may be rejected downstream).
_hi_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF).map(
    lambda n: "\\u%04x" % n
)
_lo_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)

# Escaped NUL / control as text (NOT a raw NUL byte).
_escaped_nul = st.just("\\u0000")
_escaped_ctrl = st.integers(min_value=0x01, max_value=0x1F).map(
    lambda n: "\\u%04x" % n
)

_string_piece = st.one_of(
    _safe_chars.map(str),
    _escapes,
    _unicode_esc,
    _hi_surrogate,
    _lo_surrogate,
    _escaped_nul,
    _escaped_ctrl,
)

# Build a quoted JSON string.
_json_string = st.lists(_string_piece, min_size=0, max_size=12).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# ---------------------------------------------------------------------------
# Number strategies
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str).flatmap(
        lambda d: st.lists(
            st.integers(min_value=0, max_value=9).map(str),
            min_size=0, max_size=8,
        ).map(lambda rest: d + "".join(rest))
    ),
    # Extreme magnitudes as literal digit runs.
    st.sampled_from([
        "1" * 309,
        "9" * 320,
        "1234567890123456789012345678901234567890",
        "0" * 1,  # placeholder, replaced below
    ]),
)

# Clean the placeholder-ish values: keep only well-formed int parts.
_int_part = _int_part.filter(lambda s: s == "0" or (s[0] != "0"))

_frac = st.lists(
    st.integers(min_value=0, max_value=9).map(str),
    min_size=1, max_size=8,
).map(lambda ds: "." + "".join(ds))

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.lists(st.integers(min_value=0, max_value=9).map(str),
             min_size=1, max_size=4).map(lambda ds: "".join(ds)),
).map(lambda t: t[0] + t[1] + t[2])

_sign = st.sampled_from(["", "-"])

_number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.none(), _frac),
    st.one_of(st.none(), _exp),
).map(lambda t: t[0] + t[1] + (t[2] or "") + (t[3] or ""))

# Numeric edge cases: overflow, huge exponents, tiny/huge, negative zero.
_extreme_numbers = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "1e-400",
    "1E+309", "1E-309", "1e999999999",
    "0", "-0", "0.0", "-0.0", "0e0", "0E-0",
    "1.7976931348623157e308",
    "2.2250738585072014e-308",
    "1" + "0" * 308,
    "1" + "0" * 400,
    "123456789012345678901234567890",
])

_number_or_extreme = st.one_of(_number, _extreme_numbers)

# ---------------------------------------------------------------------------
# Malformed / near-valid fragments
# ---------------------------------------------------------------------------

# Lone "-" (parser accepts as 0); leading +; ".5"; "1."; leading zeros.
_malformed_numbers = st.sampled_from([
    "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "00", "-01",
    "1e", "1e+", "1e-", "0x1", "1.2.3", "--1", "1..2",
])

# Unterminated strings, bad escapes, raw-looking control text.
_malformed_strings = st.sampled_from([
    '"', '"abc', '"abc\\', '"\\x41"', '"\\u12"', '"\\uZZZZ"',
    '"unterminated', '"a\nb"', '"\\u"',
])

# Structural malformations.
_malformed_struct = st.sampled_from([
    "{", "}", "[", "]", "{,}", "[,]", '{"a":}', '{"a" 1}',
    '{"a":1,}', "[1,]", "[1 2]", '{"a":1 "b":2}', "[1,,2]",
    '{"a"::1}', '{:1}', "[,1]", "[1,,]",
    "tru", "fals", "nul", "TRUE", "Null", "undefined",
])

_malformed = st.one_of(
    _malformed_numbers,
    _malformed_strings,
    _malformed_struct,
)

# Trailing content after a complete value (accepted by this parser).
_trailing = st.sampled_from([
    "abc", " garbage", "xyz", " 123", "null", "{}", "[]", "//x", "/*x*/",
])

# ---------------------------------------------------------------------------
# Recursive JSON value strategy
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the parser's 2048 nesting cap, but keep the
# recursive construction shallow enough to be fast. We use a moderate base
# depth plus explicit deep-nesting generators for the cap region.
_MAX_REC_DEPTH = 6

_leaves = st.one_of(
    _json_string,
    _number_or_extreme,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _malformed,
)

def _value_strategy(depth):
    if depth <= 0:
        return _leaves

    inner = _value_strategy(depth - 1)

    # Object with pairs (may include duplicate keys).
    key = st.one_of(_json_string, _json_string, st.just('"k"'), st.just('"a"'))
    pair = st.tuples(key, inner).map(lambda t: t[0] + ":" + t[1])
    obj = st.one_of(
        st.just("{}"),
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
    )

    # Array.
    arr = st.one_of(
        st.just("[]"),
        st.lists(inner, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
    )

    return st.one_of(_leaves, obj, arr)

_recursive_value = st.recursive(
    _leaves,
    lambda children: st.one_of(
        # object
        st.one_of(
            st.just("{}"),
            st.lists(
                st.tuples(
                    st.one_of(_json_string, st.just('"k"'), st.just('"a"')),
                    children,
                ).map(lambda t: t[0] + ":" + t[1]),
                min_size=1, max_size=4,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
        ),
        # array
        st.one_of(
            st.just("[]"),
            st.lists(children, min_size=1, max_size=4).map(
                lambda vs: "[" + ",".join(vs) + "]"
            ),
        ),
    ),
    max_leaves=_MAX_REC_DEPTH,
)

# ---------------------------------------------------------------------------
# Deep nesting near the 2048 cap
# ---------------------------------------------------------------------------

def _deep_nesting():
    # Depth concentrated near the cap: around 2000-2100, plus a few just over.
    depth = st.one_of(
        st.integers(min_value=1900, max_value=2100),
        st.sampled_from([2047, 2048, 2049, 2050, 3000]),
    )
    return depth.flatmap(lambda d: st.one_of(
        # nested arrays: [ [ [ ... ] ] ]
        st.just("[" * d + "]" * d),
        # nested arrays with a leaf at the bottom
        st.just("[" * d + "0" + "]" * d),
        # nested objects
        st.just('{"a":' * d + "null" + "}" * d),
        # mixed
        st.just('{"a":[' * d + "1" + "]}" * d),
    ))

_deep = _deep_nesting()

# ---------------------------------------------------------------------------
# Duplicate-key objects (expect rejection) and other edge composites
# ---------------------------------------------------------------------------

_dup_keys = st.sampled_from([
    '{"k":0,"k":1}',
    '{"a":1,"a":2,"a":3}',
    '{"x":{"y":1},"x":{"y":2}}',
    '{"k":[1,2],"k":[3,4]}',
    '{"":0,"":1}',
])

_empties = st.sampled_from(["{}", "[]", "{ }", "[ ]", "{}[]", "[]{}"])

# ---------------------------------------------------------------------------
# Broadened structural exploration: diverse accepted shapes
# ---------------------------------------------------------------------------

# Keys drawn from a wider pool (whitespace, unicode escapes, long keys, empty).
_broad_keys = st.one_of(
    _json_string,
    st.just('""'),
    st.just('" "'),
    st.just('"\\u0000"'),
    st.just('"\\uD834\\uDD1E"'),
    st.just('"key with spaces"'),
    st.just('"' + "k" * 64 + '"'),
    st.just('"0"'),
    st.just('"true"'),
    st.just('"null"'),
)

# Whitespace variations sprinkled around structural tokens.
_ws = st.sampled_from(["", " ", "  ", "\t", "\n", "\r\n", " \t "])

def _spaced(tok):
    return st.tuples(_ws, st.just(tok), _ws).map(lambda t: t[0] + t[1] + t[2])

# Broadened recursive value: wider fan-out, mixed nesting, whitespace.
_broad_leaves = st.one_of(
    _leaves,
    _json_string,
    _number_or_extreme,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

def _broad_value(depth):
    if depth <= 0:
        return _broad_leaves

    inner = _broad_value(depth - 1)

    pair = st.tuples(_broad_keys, inner).map(lambda t: t[0] + ":" + t[1])
    pair_ws = st.tuples(_broad_keys, _ws, st.just(":"), _ws, inner).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

    obj = st.one_of(
        _spaced("{}"),
        st.lists(st.one_of(pair, pair_ws), min_size=1, max_size=8).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        st.lists(st.one_of(pair, pair_ws), min_size=1, max_size=8).map(
            lambda ps: "{" + ", ".join(ps) + "}"
        ),
    )

    arr = st.one_of(
        _spaced("[]"),
        st.lists(inner, min_size=1, max_size=8).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(inner, min_size=1, max_size=8).map(
            lambda vs: "[" + ", ".join(vs) + "]"
        ),
        st.lists(inner, min_size=1, max_size=8).map(
            lambda vs: "[ " + " , ".join(vs) + " ]"
        ),
    )

    return st.one_of(_broad_leaves, obj, arr)

_broad_recursive = st.recursive(
    _broad_leaves,
    lambda children: st.one_of(
        st.one_of(
            _spaced("{}"),
            st.lists(
                st.one_of(
                    st.tuples(_broad_keys, children).map(
                        lambda t: t[0] + ":" + t[1]
                    ),
                    st.tuples(_broad_keys, _ws, st.just(":"), _ws, children).map(
                        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
                    ),
                ),
                min_size=1, max_size=8,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
        ),
        st.one_of(
            _spaced("[]"),
            st.lists(children, min_size=1, max_size=8).map(
                lambda vs: "[" + ",".join(vs) + "]"
            ),
            st.lists(children, min_size=1, max_size=8).map(
                lambda vs: "[ " + " , ".join(vs) + " ]"
            ),
        ),
    ),
    max_leaves=8,
)

# Shallow-but-wide composites: many siblings, mixed types.
_wide_array = st.lists(
    st.one_of(
        _json_string, _number_or_extreme,
        st.just("true"), st.just("false"), st.just("null"),
        st.just("{}"), st.just("[]"),
    ),
    min_size=3, max_size=16,
).map(lambda vs: "[" + ",".join(vs) + "]")

_wide_object = st.lists(
    st.tuples(_broad_keys, st.one_of(
        _json_string, _number_or_extreme,
        st.just("true"), st.just("false"), st.just("null"),
        st.just("{}"), st.just("[]"),
    )).map(lambda t: t[0] + ":" + t[1]),
    min_size=3, max_size=16,
).map(lambda ps: "{" + ",".join(ps) + "}")

# Alternating / irregular nesting shapes.
_irregular = st.sampled_from([
    '[{"a":[{"b":[{"c":[]}]}]}]',
    '{"a":[1,{"b":[2,{"c":[3]}]}]}',
    '[[[[{"a":1}]]]]',
    '{"a":{"b":{"c":{"d":{"e":1}}}}}',
    '[1,[2,[3,[4,[5]]]]]',
    '{"a":[],"b":{},"c":[{}],"d":{"e":[]}}',
    '[{},[],{"a":[]},[{}]]',
    '{"x":[[[1]]],"y":{"z":[[2]]}}',
    '[[],[[]],[[[]]]]',
    '{"a":[true,false,null,0,"",{},[]]}',
])

# Whitespace-rich documents.
_whitespace_rich = st.sampled_from([
    " { } ",
    " [ ] ",
    " {  \"a\"  :  1  } ",
    " [  1  ,  2  ,  3  ] ",
    "\n{\n\t\"a\":\n\t[1,2,3]\n}\n",
    "{\"a\":\n1,\n\"b\":\n2}",
    "[ 1 , [ 2 , [ 3 ] ] ]",
    "\t\t{\"k\":\t\"v\"}\t\t",
])

# Top-level scalar variety (parser accepts bare scalars).
_scalar_docs = st.one_of(
    _json_string,
    _number_or_extreme,
    st.just("true"), st.just("false"), st.just("null"),
    st.just(" true "), st.just(" null "), st.just(" false "),
)

# ---------------------------------------------------------------------------
# NEW: broadened exploration — diverse accepted structures
# ---------------------------------------------------------------------------

# (a) Widened recursive grammar: deeper, wider, and with more key/value shapes.
def _diverse_value(depth):
    if depth <= 0:
        return _broad_leaves

    inner = _diverse_value(depth - 1)

    pair = st.tuples(_broad_keys, inner).map(lambda t: t[0] + ":" + t[1])
    pair_ws = st.tuples(_broad_keys, _ws, st.just(":"), _ws, inner).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )
    obj = st.one_of(
        _spaced("{}"),
        st.lists(st.one_of(pair, pair_ws), min_size=1, max_size=12).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        st.lists(st.one_of(pair, pair_ws), min_size=1, max_size=12).map(
            lambda ps: "{" + ", ".join(ps) + "}"
        ),
        st.lists(st.one_of(pair, pair_ws), min_size=1, max_size=12).map(
            lambda ps: "{ " + " , ".join(ps) + " }"
        ),
    )
    arr = st.one_of(
        _spaced("[]"),
        st.lists(inner, min_size=1, max_size=12).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(inner, min_size=1, max_size=12).map(
            lambda vs: "[" + ", ".join(vs) + "]"
        ),
        st.lists(inner, min_size=1, max_size=12).map(
            lambda vs: "[ " + " , ".join(vs) + " ]"
        ),
    )
    return st.one_of(_broad_leaves, obj, arr)

_diverse_recursive = st.recursive(
    _broad_leaves,
    lambda children: st.one_of(
        st.one_of(
            _spaced("{}"),
            st.lists(
                st.one_of(
                    st.tuples(_broad_keys, children).map(
                        lambda t: t[0] + ":" + t[1]
                    ),
                    st.tuples(_broad_keys, _ws, st.just(":"), _ws, children).map(
                        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
                    ),
                ),
                min_size=1, max_size=12,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
        ),
        st.one_of(
            _spaced("[]"),
            st.lists(children, min_size=1, max_size=12).map(
                lambda vs: "[" + ",".join(vs) + "]"
            ),
            st.lists(children, min_size=1, max_size=12).map(
                lambda vs: "[ " + " , ".join(vs) + " ]"
            ),
        ),
    ),
    max_leaves=12,
)

# (b) Document-level wrappers: leading/trailing whitespace and newlines around
#     complete documents, exercising the parser's top-level whitespace handling.
_doc_wrap = st.tuples(
    st.sampled_from(["", " ", "  ", "\n", "\t", "\r\n", "\n\n"]),
    _diverse_recursive,
    st.sampled_from(["", " ", "  ", "\n", "\t", "\r\n", "\n\n"]),
).map(lambda t: t[0] + t[1] + t[2])

# (c) Mixed containers with a single deep branch alongside flat siblings.
_mixed_depth = st.one_of(
    st.tuples(
        _diverse_recursive,
        st.lists(
            st.one_of(_broad_leaves, st.just("{}"), st.just("[]")),
            min_size=1, max_size=6,
        ),
    ).map(lambda t: "[" + t[0] + "," + ",".join(t[1]) + "]"),
    st.tuples(
        _diverse_recursive,
        st.lists(
            st.one_of(_broad_leaves, st.just("{}"), st.just("[]")),
            min_size=1, max_size=6,
        ),
    ).map(lambda t: "[" + ",".join(t[1]) + "," + t[0] + "]"),
)

# (d) Empty and minimal container permutations.
_empty_permutations = st.sampled_from([
    "{}", "[]", "[{}]", "[[]]", "{{}}", "{[ ]}", "[ { } ]",
    '{"a":{}}', '{"a":[]}', '[{"a":[]}]', '[[[]]]',
])

# (e) Objects with many distinct keys (exercises key handling at width).
_many_keys = st.lists(
    st.tuples(
        st.integers(min_value=0, max_value=9999).map(
            lambda n: '"k%d"' % n
        ),
        st.one_of(
            _json_string, _number_or_extreme,
            st.just("true"), st.just("false"), st.just("null"),
        ),
    ).map(lambda t: t[0] + ":" + t[1]),
    min_size=5, max_size=24,
).map(lambda ps: "{" + ",".join(ps) + "}")

# (f) Nested arrays of arrays with scalar payloads at varying depths.
def _array_ladder():
    return st.integers(min_value=1, max_value=40).flatmap(
        lambda d: st.sampled_from([
            "[" * d + "1" + "]" * d,
            "[" * d + '"x"' + "]" * d,
            "[" * d + "true" + "]" * d,
            "[" * d + "null" + "]" * d,
        ])
    )

_array_ladder = _array_ladder()

# (g) Objects nested through arrays and vice versa, alternating wrappers.
def _alternating():
    return st.integers(min_value=1, max_value=40).flatmap(
        lambda d: st.sampled_from([
            '{"a":' * d + "1" + "}" * d,
            '{"a":' * d + '["x"]' + "}" * d,
            "[{" + '"a":1}' + "]" * 1,
            "[" + '{"a":[' * d + "1" + "]}" * d + "]",
        ])
    )

_alternating = _alternating()

# (h) Long flat arrays / objects to stress width without depth.
_long_flat = st.one_of(
    st.lists(
        st.one_of(
            _number_or_extreme,
            _json_string,
            st.just("true"), st.just("false"), st.just("null"),
        ),
        min_size=20, max_size=80,
    ).map(lambda vs: "[" + ",".join(vs) + "]"),
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=999).map(lambda n: '"k%d"' % n),
            _number_or_extreme,
        ).map(lambda t: t[0] + ":" + t[1]),
        min_size=20, max_size=80,
    ).map(lambda ps: "{" + ",".join(ps) + "}"),
)

_broadened = st.one_of(
    _broad_recursive,
    _diverse_recursive,
    _doc_wrap,
    _mixed_depth,
    _empty_permutations,
    _many_keys,
    _array_ladder,
    _alternating,
    _long_flat,
    _wide_array,
    _wide_object,
    _irregular,
    _whitespace_rich,
    _scalar_docs,
)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

_value_with_trailing = st.tuples(_recursive_value, _trailing).map(
    lambda t: t[0] + t[1]
)

strategy = st.one_of(
    _recursive_value,
    _value_with_trailing,
    _broadened,
    _deep,
    _dup_keys,
    _empties,
    _malformed,
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 143,
    "reject": 207
  },
  "acceptance_rate": 0.409,
  "max_nesting_depth": 4134,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "false",
    "json",
    "null",
    "obj",
    "pair",
    "true",
    "value"
  ],
  "productions_gap": [],
  "cap_distance_mass": 0.021,
  "novelty": 46,
  "divergences": 97,
  "divergence_examples": [
    "b'{\"k0\":0,\"k0\":0,\"k0\":0,\"k0\":0,\"k0\":0,\"k0\":0,\"k0\":0,\"k0\":0,\"k0\":0,\"k0\":0,\"k0\":0,\"k'",
    "b'[]{}'",
    "b'{\"k0\":\"\",\"k0\":\"\",\"k0\":\"\",\"k0\":\"\",\"k0\":\"\"}'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **generate_nesting_toward_cap** — target depth 1500-2048.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.