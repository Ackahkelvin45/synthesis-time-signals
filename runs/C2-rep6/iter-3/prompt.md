Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf-level strategies
# ---------------------------------------------------------------------------

_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
)

_CTRL = st.sampled_from(
    [
        "\x00",
        "\x01",
        "\x1f",
        "\x0b",
        "\x7f",
        "\u0000",
        "\u001f",
    ]
)

_ESCAPES = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_HEX = st.sampled_from("0123456789abcdefABCDEF")
_UNICODE_ESC = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet=_HEX, min_size=4, max_size=4),
)
_SURROGATE_ESC = st.sampled_from(
    [
        "\\uD800",
        "\\uDBFF",
        "\\uDC00",
        "\\uDFFF",
        "\\uD800\\uDC00",
        "\\uD800\\uD800",
        "\\uDC00\\uD800",
        "\\u0000",
        "\\uFFFF",
    ]
)

_STRING_BODY_ATOM = st.one_of(
    _SAFE.map(str),
    _CTRL,
    _ESCAPES,
    _UNICODE_ESC,
    _SURROGATE_ESC,
)

_STRING = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_STRING_BODY_ATOM, min_size=0, max_size=8),
)

_BAD_STRING = st.one_of(
    st.builds(
        lambda parts: '"' + "".join(parts),
        st.lists(_STRING_BODY_ATOM, min_size=0, max_size=6),
    ),
    st.just('"'),
    st.builds(
        lambda parts: '"' + "".join(parts) + "\\",
        st.lists(_STRING_BODY_ATOM, min_size=0, max_size=6),
    ),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT = st.one_of(
    st.just("0"),
    st.from_regex(r"[1-9][0-9]*", fullmatch=True),
)
_FRAC = st.from_regex(r"\.[0-9]+", fullmatch=True)
_EXP = st.from_regex(r"[Ee][+-]?[0-9]+", fullmatch=True)

_GOOD_NUMBER = st.builds(
    lambda s, i, f, e: ("-" if s else "") + i + f + e,
    st.booleans(),
    _INT,
    st.one_of(st.just(""), _FRAC),
    st.one_of(st.just(""), _EXP),
)

_EXTREME_NUMBER = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e308",
        "1e-308",
        "1e999999999",
        "1e-999999999",
        "0e0",
        "0e999",
        "-0",
        "-0.0",
        "123456789012345678901234567890",
        "1.7976931348623157e308",
        "2.2250738585072014e-308",
        "5e-324",
        "1.8e308",
        "9" * 40,
        "0." + "0" * 50 + "1",
        "1e+309",
        "1E309",
        "1e01",
        "1e-01",
    ]
)

_BAD_NUMBER = st.sampled_from(
    [
        "+1",
        ".5",
        "1.",
        "01",
        "00",
        "-01",
        "0x1F",
        "1e",
        "1e+",
        "1.2.3",
        "--1",
        "1..2",
        "1e1e1",
        "0b101",
        "0o17",
        "Infinity",
        "NaN",
        "-",
        "+",
        ".",
        "e5",
    ]
)

_NUMBER = st.one_of(_GOOD_NUMBER, _EXTREME_NUMBER, _BAD_NUMBER)

# ---------------------------------------------------------------------------
# Malformed punctuation fragments (near-valid-but-bad)
# ---------------------------------------------------------------------------

_MALFORMED_FRAGMENTS = st.sampled_from(
    [
        ",,",
        "{,}",
        "[,]",
        "[,1]",
        "[1,,2]",
        '{"a" 1}',
        '{"a":}',
        '{"a":,}',
        "{:1}",
        "{a:1}",
        "{'a':1}",
        "[1 2]",
        '{"a":1 "b":2}',
        "//comment\n1",
        "/*c*/1",
        "'single'",
        "truefalse",
        "nullnull",
        "1abc",
        "[]xyz",
        "true false",
        "1 garbage",
        "{} {}",
        "[] []",
        "\x00",
        "\x00{}",
        "{}\x00",
        "[1,2,]\x00",
    ]
)

# ---------------------------------------------------------------------------
# Recursive obj/arr/value construction
# ---------------------------------------------------------------------------

_KEY = st.one_of(
    _STRING,
    st.sampled_from(['"a"', '"a"', '"a"', '"b"', '"key"', '""']),
)

_WS = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\t"),
    st.just("\n"),
    st.just("\r"),
    st.sampled_from(["  ", "\r\n", " \t "]),
)

_value = st.deferred(lambda: _value_strategy)

_pair = st.builds(
    lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
    _KEY,
    _WS,
    _WS,
    _value,
)

_obj = st.one_of(
    st.just("{}"),
    st.builds(
        lambda w1, members, trailing, w2: "{"
        + w1
        + ",".join(members)
        + trailing
        + w2
        + "}",
        _WS,
        st.lists(_pair, min_size=1, max_size=6),
        st.one_of(st.just(""), st.just(",")),
        _WS,
    ),
)

_arr = st.one_of(
    st.just("[]"),
    st.builds(
        lambda w1, items, trailing, w2: "["
        + w1
        + ",".join(items)
        + trailing
        + w2
        + "]",
        _WS,
        st.lists(_value, min_size=1, max_size=6),
        st.one_of(st.just(""), st.just(",")),
        _WS,
    ),
)

def _deep_nesting():
    depth = st.integers(min_value=1, max_value=64)
    return st.builds(
        lambda d, inner: "[" * d + inner + "]" * d,
        depth,
        st.one_of(
            st.just("0"),
            _STRING,
            st.just("null"),
            st.just("true"),
            st.just("false"),
        ),
    )


_deep_obj_nesting = st.builds(
    lambda d: '{"a":' * d + "0" + "}" * d,
    st.integers(min_value=1, max_value=64),
)

_deep_arr_nesting = st.builds(
    lambda d: "[" * d + "0" + "]" * d,
    st.integers(min_value=1, max_value=128),
)

# ---------------------------------------------------------------------------
# Near-crash intensification: structurally mutate around the crashing input.
#
# Observed crash signature is a UBSan "applying-non-zero-offset-to-null-pointer"
# in the parse function, produced by deeply nested arrays whose innermost
# element is a string containing escaped-quote / control-byte sequences
# (e.g. `[[[..."\u83B9\"\x1f\"F\"\"F"]]]`) and by extreme-magnitude numbers
# such as `-1e309`.
#
# We build a family of inputs that preserve the *structure* of those crashing
# cases while mutating the leaves: deep bracket nesting with a stress string
# inside, deep nesting with extreme numbers inside, and vice-versa.
# ---------------------------------------------------------------------------

# Stress strings drawn from the crash neighborhood: escaped quotes, stray
# control bytes, and \uXXXX escapes packed into a quoted string.
_STRESS_STRING_ATOM = st.sampled_from(
    [
        '\\"',
        "\\\\",
        "\\u83B9",
        "\\u83b9",
        "\\uD800",
        "\\uDC00",
        "\x1f",
        "\x00",
        "\x0b",
        "\x7f",
        "F",
        "0F",
        "",
    ]
)

_STRESS_STRING = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_STRESS_STRING_ATOM, min_size=0, max_size=10),
)

# Extreme numbers that triggered the divergence (e.g. "-1e309").
_CRASH_NUMBER = st.sampled_from(
    [
        "-1e309",
        "1e309",
        "-1e308",
        "1e308",
        "-1e999999999",
        "1e999999999",
        "-1e-309",
        "1e-309",
        "-0",
        "-0.0",
        "1.7976931348623157e308",
        "-1.7976931348623157e308",
        "5e-324",
        "-5e-324",
    ]
)

# Innermost payload for the deep-array crash shape.
_CRASH_INNER = st.one_of(
    _STRESS_STRING,
    _CRASH_NUMBER,
    st.just("0"),
    st.just("null"),
    _STRING,
    _NUMBER,
)

# Deep array nesting around the crash inner payload, biased to the depths
# seen in the divergences (long runs of `[`) and to the cap boundary.
_NEAR_CRASH_DEEP_ARR = st.builds(
    lambda d, inner, trail: "[" * d + inner + "]" * d + trail,
    st.one_of(
        st.integers(min_value=40, max_value=64),
        st.integers(min_value=1, max_value=64),
        st.sampled_from([63, 64, 65, 128]),
    ),
    _CRASH_INNER,
    st.one_of(st.just(""), st.just("\x00"), st.just("garbage"), st.just("\x1f")),
)

# Deep object nesting ({"a": ... }) around the crash inner payload.
_NEAR_CRASH_DEEP_OBJ = st.builds(
    lambda d, inner, trail: '{"a":' * d + inner + "}" * d + trail,
    st.one_of(
        st.integers(min_value=40, max_value=64),
        st.integers(min_value=1, max_value=64),
        st.sampled_from([63, 64, 65]),
    ),
    _CRASH_INNER,
    st.one_of(st.just(""), st.just("\x00"), st.just("garbage")),
)

# Mixed nesting: alternate `[` and `{"a":` prefixes, then mirror suffixes.
_NEAR_CRASH_MIXED = st.builds(
    lambda opens, inner, closes: opens + inner + closes,
    st.builds(
        lambda n: "".join("[{\"a\":"[i % 4] for i in range(n)),
        st.integers(min_value=1, max_value=48),
    ),
    _CRASH_INNER,
    st.builds(
        lambda n: "".join("]}"[i % 2] for i in range(n)),
        st.integers(min_value=1, max_value=48),
    ),
)

# Leading whitespace / CR prefix (divergences began with `\r`).
_NEAR_CRASH_PREFIX = st.one_of(
    st.just(""),
    st.just("\r"),
    st.just("\n"),
    st.just(" "),
    st.just("\t"),
    st.just("\r\n"),
)

_NEAR_CRASH = st.one_of(
    _NEAR_CRASH_DEEP_ARR,
    _NEAR_CRASH_DEEP_ARR,
    _NEAR_CRASH_DEEP_ARR,
    _NEAR_CRASH_DEEP_OBJ,
    _NEAR_CRASH_MIXED,
    # Bare extreme numbers, directly at the crash site.
    _CRASH_NUMBER,
    _CRASH_NUMBER,
)

# ---------------------------------------------------------------------------
# Base (non-recursive) values.
# ---------------------------------------------------------------------------

_base_value = st.one_of(
    _STRING,
    _NUMBER,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

# Full recursive value strategy: base leaves + obj + arr.
_value_strategy = st.one_of(
    _base_value,
    _obj,
    _arr,
    _deep_nesting(),
    _deep_obj_nesting,
    _deep_arr_nesting,
    _BAD_STRING,
    _MALFORMED_FRAGMENTS,
)

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

# Bias toward objects with members (the stressed first-pass path) while still
# covering arrays, scalars, and malformed inputs.
_top = st.one_of(
    _obj,
    _obj,
    _obj,
    _arr,
    _value,
    _value,
    _base_value,
    _MALFORMED_FRAGMENTS,
)

# Intensified top-level: heavily weight the near-crash family so Hypothesis
# spends its budget mutating structurally around the observed crashes.
_top_intensified = st.one_of(
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _top,
    _top,
    _top,
)

# Optional surrounding whitespace and trailing junk (parser rejects junk,
# but exercises the "whole input consumed" path). Near-crash inputs carry
# their own \r prefix, so we keep the lead empty for those.
strategy = st.one_of(
    st.builds(
        lambda lead, body, trail: lead + body + trail,
        st.one_of(st.just(""), _WS),
        _top_intensified,
        st.one_of(st.just(""), _WS, st.just("\x00"), st.just("garbage")),
    ),
    st.builds(
        lambda prefix, body, trail: prefix + body + trail,
        _NEAR_CRASH_PREFIX,
        _NEAR_CRASH,
        st.one_of(st.just(""), st.just("\x00"), st.just("garbage")),
    ),
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 14,
    "crash": 217,
    "reject": 6
  },
  "acceptance_rate": 0.059,
  "max_nesting_depth": 64,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "json",
    "value"
  ],
  "productions_gap": [
    "obj",
    "pair",
    "true",
    "false",
    "null"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 3,
  "divergences": 3,
  "divergence_examples": [
    "b'[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[-1e309]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]'",
    "b'\\r\\n[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[\"\"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]'",
    "b'\\r\\n[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[\"\"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]'"
  ],
  "unique_crash_signatures": [
    "ubsan:applying-non-zero-offset-to-null-pointer|the parse function>harness_parse>run_stdin_mode"
  ],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.