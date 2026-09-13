Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- primitive building blocks ----------

# Keys: bias toward simple ASCII keys, but include unicode escapes and control bytes.
_ascii_key = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    min_size=0,
    max_size=8,
)

_escaped_key = st.sampled_from(
    [
        "\\n",
        "\\t",
        "\\r",
        "\\b",
        "\\f",
        "\\/",
        "\\\\",
        "\\\"",
        "\\u0000",
        "\\u001f",
        "\\u0041",
        "\\uD800",
        "\\uDC00",
        "\\uD83D\\uDE00",
        "\\uFFFF",
        "\\u00e9",
    ]
)

_key_body = st.one_of(_ascii_key, _escaped_key)
_key = _key_body.map(lambda s: '"' + s + '"')

# Numbers: valid forms plus the parser's lenient/extreme cases.
_valid_int = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
    st.integers(min_value=-(10**6), max_value=-1).map(str),
)

_frac = st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n))

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=400).map(str),
).map(lambda t: "".join(t))

_number = st.one_of(
    _valid_int,
    st.tuples(_valid_int, _frac).map(lambda t: "".join(t)),
    st.tuples(_valid_int, _exp).map(lambda t: "".join(t)),
    st.tuples(_valid_int, _frac, _exp).map(lambda t: "".join(t)),
    # extreme magnitudes / overflow
    st.sampled_from(
        [
            "1e309",
            "-1e309",
            "1e400",
            "1E+999",
            "1e-999",
            "1e308",
            "1.7976931348623157e308",
            "2.2250738585072014e-308",
            "0.0",
            "-0",
            "-0.0",
            "1e01",
            "1e00",
            "123456789012345678901234567890",
        ]
    ),
    # parser leniency: lone '-'
    st.just("-"),
    # near-valid malformed numbers
    st.sampled_from(
        [
            "+1",
            ".5",
            "1.",
            "01",
            "007",
            "0x1F",
            "1e",
            "1e+",
            "--1",
            "1..2",
            "00",
            "-",
            "1_000",
        ]
    ),
)

# Strings: valid content plus escapes, control bytes, NUL, surrogates.
_safe_char = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x7E,
    blacklist_characters='"\\',
)

_control_char = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\x7f"]
)

_escape = st.sampled_from(
    [
        "\\n",
        "\\t",
        "\\r",
        "\\b",
        "\\f",
        "\\/",
        "\\\\",
        "\\\"",
        "\\u0000",
        "\\u0001",
        "\\u001f",
        "\\u0041",
        "\\u00e9",
        "\\uD800",
        "\\uDC00",
        "\\uDFFF",
        "\\uD83D\\uDE00",
        "\\uFFFF",
        "\\uABCD",
        "\\uabcd",
    ]
)

_string_inner = st.one_of(
    st.text(alphabet=_safe_char, min_size=0, max_size=8),
    _control_char,
    _escape,
)

_string = st.one_of(
    st.lists(_string_inner, min_size=0, max_size=4).map("".join).map(lambda s: '"' + s + '"'),
    # unterminated string
    st.lists(_string_inner, min_size=0, max_size=4).map("".join).map(lambda s: '"' + s),
)

# ---------- recursive JSON values ----------

_json_value = st.deferred(lambda: _value)

_ws = st.sampled_from(["", " ", "  ", "\n", "\t", "\r\n", " \t "])

_obj_member = st.tuples(_key, st.just(":"), _json_value).map(lambda t: t[0] + t[1] + t[2])

_obj = st.one_of(
    st.just("{}"),
    st.tuples(
        st.just("{"),
        st.lists(_obj_member, min_size=1, max_size=4).map(lambda ms: ",".join(ms)),
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # trailing comma variant
    st.tuples(
        st.just("{"),
        st.lists(_obj_member, min_size=1, max_size=3).map(lambda ms: ",".join(ms)),
        st.just(",}"),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # duplicate keys
    st.tuples(
        st.just("{"),
        _key,
        st.just(":1,"),
        _key,
        st.just(":2}"),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
)

_arr = st.one_of(
    st.just("[]"),
    st.tuples(
        st.just("["),
        st.lists(_json_value, min_size=1, max_size=4).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # trailing comma
    st.tuples(
        st.just("["),
        st.lists(_json_value, min_size=1, max_size=3).map(lambda vs: ",".join(vs)),
        st.just(",]"),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_value = st.one_of(
    _string,
    _number,
    _obj,
    _arr,
    st.sampled_from(["true", "false", "null"]),
)

# ---------- malformed / near-valid whole documents ----------

_malformed = st.sampled_from(
    [
        "[1,,2]",
        "[,]",
        "[,1]",
        "{,}",
        '{"a" 1}',
        '{"a":}',
        '{"a":1,,"b":2}',
        "{:1}",
        "{1:2}",
        "[1 2]",
        '{"a":1 "b":2}',
        "tru",
        "nul",
        "fals",
        "tru e",
        "1abc",
        "[]xyz",
        "1 garbage",
        "true false",
        "// comment",
        "/* c */ 1",
        "'x'",
        "{a:1}",
        "",
        " ",
        "\x00",
        "{}extra",
        "[1,2,3",
        '{"a":1',
        '"unterminated',
        "{'single':1}",
        "\xef\xbb\xbf{}",
    ]
)

# ---------- deep nesting ----------

_deep_obj = st.integers(min_value=1, max_value=60).map(
    lambda n: "{" + '{"k":' * n + "1" + "}" * n + "}"
)

_deep_arr = st.integers(min_value=1, max_value=200).map(
    lambda n: "[" * n + "]" * n
)

# ---------- near-crash intensification ----------

# The crash signature points at a null-pointer offset applied while parsing
# (ubsan:applying-non-zero-offset-to-null-pointer), which is typical of the
# parser dereferencing a pointer past a missing/empty token. Intensify by
# generating structurally-mutated variants around inputs that stress empty
# and boundary tokens: empty containers, lone punctuation, truncated
# documents, and empty strings/keys.

_CRASH_SEEDS = [
    "",
    " ",
    "\x00",
    "[",
    "]",
    "{",
    "}",
    ":",
    ",",
    '"',
    "-",
    "[]",
    "{}",
    "[,]",
    "{,}",
    '""',
    "[]extra",
    "[1,2,3",
    '{"a":1',
    '"unterminated',
    '{"":1}',
    "[:]",
    "{:}",
    "[[]]",
    "{\"\":{}}",
    "[,]",
    "{,}",
    "[ ]",
    "{ }",
    "[\x00]",
    '{"a":}',
    '{"a" 1}',
]

# Structural mutations applied to a seed: truncate, wrap, splice punctuation.
def _mutate(seed, op):
    if op == "truncate":
        return seed[: max(0, len(seed) // 2)]
    if op == "wrap_arr":
        return "[" + seed + "]"
    if op == "wrap_obj":
        return '{"k":' + seed + "}"
    if op == "prepend_punct":
        return "," + seed
    if op == "append_punct":
        return seed + ":"
    if op == "dup":
        return seed + seed
    if op == "wrap_str":
        return '"' + seed + '"'
    if op == "empty_arr":
        return "[" + seed + ",]"
    if op == "empty_obj":
        return "{" + seed + ",}"
    if op == "drop_last":
        return seed[:-1] if seed else seed
    if op == "prefix_bracket":
        return "[" + seed
    if op == "suffix_brace":
        return seed + "}"
    return seed

_MUT_OPS = [
    "truncate",
    "wrap_arr",
    "wrap_obj",
    "prepend_punct",
    "append_punct",
    "dup",
    "wrap_str",
    "empty_arr",
    "empty_obj",
    "drop_last",
    "prefix_bracket",
    "suffix_brace",
]

# Apply a chain of mutations (1..4) to a seed, intensifying around the crash.
def _mutate_chain(seed, ops):
    s = seed
    for op in ops:
        s = _mutate(s, op)
    return s

# Single-step mutation, as before.
_single_mut = st.tuples(
    st.sampled_from(_CRASH_SEEDS),
    st.sampled_from(_MUT_OPS),
).map(lambda t: _mutate(t[0], t[1]))

# Multi-step mutation chains: 2..4 mutations applied in sequence, biased
# toward seeds that already triggered the crash (empty/boundary tokens).
_multi_mut = st.tuples(
    st.sampled_from(_CRASH_SEEDS),
    st.lists(st.sampled_from(_MUT_OPS), min_size=2, max_size=4),
).map(lambda t: _mutate_chain(t[0], t[1]))

# Splice two crash seeds together with punctuation separators at the boundary.
_SPLICE_SEPS = ["", ":", ",", "[", "]", "{", "}", '"', "-", "\x00", " "]

_splice = st.tuples(
    st.sampled_from(_CRASH_SEEDS),
    st.sampled_from(_SPLICE_SEPS),
    st.sampled_from(_CRASH_SEEDS),
    st.sampled_from(_SPLICE_SEPS),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# Deep-boundary variants: wrap a crash seed in many brackets/braces/quotes,
# which stresses the null-pointer offset at unmatched-token boundaries.
_boundary_depth = st.integers(min_value=1, max_value=8)

_deep_boundary = st.tuples(
    _boundary_depth,
    st.sampled_from(_CRASH_SEEDS),
    st.sampled_from(["[", "{", '"', "(", ""]),
    st.sampled_from(["]", "}", '"', ")", ""]),
).map(lambda t: t[2] * t[0] + t[1] + t[3] * t[0])

# Truncated-prefix variants: take a crash seed and progressively cut it,
# exercising the parser at every partial-token boundary.
def _prefixes(seed):
    return [seed[:i] for i in range(len(seed) + 1)]

_prefix_cuts = st.sampled_from(_CRASH_SEEDS).flatmap(
    lambda seed: st.sampled_from(_prefixes(seed))
)

# Also generate short random punctuation soup around the crash alphabet.
_crash_alphabet = st.sampled_from(list('{}[],:"\\ \n\t\x00-0123456789.truefalsn'))

_crash_soup = st.lists(_crash_alphabet, min_size=0, max_size=12).map("".join)

# Intensified near-crash pool: single mutations, multi-step mutation chains,
# splices, deep-boundary wraps, truncated prefixes, and punctuation soup.
_near_crash = st.one_of(
    _single_mut,
    _multi_mut,
    _splice,
    _deep_boundary,
    _prefix_cuts,
    _crash_soup,
    st.sampled_from(_CRASH_SEEDS),
)

# ---------- top-level strategy ----------

_document = st.one_of(
    _value,
    _malformed,
    _deep_obj,
    _deep_arr,
    _near_crash,
)

strategy = _document
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 9,
    "reject": 11,
    "crash": 102
  },
  "acceptance_rate": 0.074,
  "max_nesting_depth": 2,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "json",
    "obj",
    "value"
  ],
  "productions_gap": [
    "pair",
    "arr",
    "true",
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 3,
  "divergences": 1,
  "divergence_examples": [
    "b'\"@@38ZC.?\\\\uDC00\"'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.