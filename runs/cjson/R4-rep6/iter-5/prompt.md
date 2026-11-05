Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Whitespace the grammar skips.
_ws = st.sampled_from(["", "", "", " ", "\t", "\n", "\r", " \t", "\n\r"])

# A safe code point for inside strings (no quote, no backslash, no control).
_safe = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
    min_codepoint=0x20,
)

# Raw control / NUL bytes: the parser accepts these inside strings.
_control = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\t", "\n", "\r"]
)

# Valid escape sequences.
_short_esc = st.sampled_from(list('"\\/bfnrt'))
_hex = st.sampled_from("0123456789abcdefABCDEF")
_unicode_esc = st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map("".join)

# Surrogate escapes: lone ones are rejected, pairs are fine-ish. Include both.
_surrogate_esc = st.sampled_from(
    [
        "\\ud800",
        "\\udfff",
        "\\udc00",
        "\\ud83d\\ude00",  # valid pair
        "\\uD834\\uDD1E",
        "\\u0000",
        "\\uffff",
        "\\uFFFF",
    ]
)

_string_piece = st.one_of(
    _safe,
    _control,
    _short_esc.map(lambda e: "\\" + e),
    _unicode_esc,
    _surrogate_esc,
)

_quoted_string = st.lists(_string_piece, max_size=8).map(lambda p: '"' + "".join(p) + '"')

# Malformed-ish strings (unterminated, bad escapes, single quotes).
_bad_string = st.sampled_from(
    [
        '"',
        '"abc',
        '"abc\\',
        '"\\q"',
        '"\\u12"',
        '"\\uZZZZ"',
        "'abc'",
        "'",
        '"a\x00b',
        '"a\tb"',
    ]
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.from_regex(r"[1-9][0-9]{0,20}", fullmatch=True),
)

_frac = st.one_of(
    st.nothing(),
    st.tuples(st.just("."), st.from_regex(r"[0-9]{1,20}", fullmatch=True)).map("".join),
)

_exp = st.one_of(
    st.nothing(),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.from_regex(r"[0-9]{1,6}", fullmatch=True),
    ).map("".join),
)

_number = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part,
    _frac,
    _exp,
).map("".join)

# Extreme magnitudes / exponents.
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e999999",
        "1E+400",
        "1e-400",
        "-0",
        "0.0",
        "1.7976931348623157e308",
        "2.2250738585072014e-308",
        "123456789012345678901234567890",
        "1e01",
        "1.0e+00",
        # deviations the parser accepts
        "01",
        "007",
        "1.",
        "-1.",
        "0x10",
        "0xFF",
        "0x",
        # deviations the parser rejects
        "+1",
        ".5",
        "-.5",
        "-",
        "NaN",
        "Infinity",
        "-Infinity",
        "1e",
        "1e+",
        "1..2",
        "1.2.3",
    ]
)

# ---------------------------------------------------------------------------
# Recursive value strategy with depth control near the 1000 limit.
# ---------------------------------------------------------------------------

# A few fixed-depth "spine" strings used to probe the nesting boundary.
def _nest(depth, opener, closer):
    return opener * depth + closer * depth

_boundary_depth = st.sampled_from(
    [1, 2, 3, 10, 100, 500, 998, 999, 1000, 1001, 1002, 1100]
)

_deep_array = _boundary_depth.map(lambda d: _nest(d, "[", "]"))
_deep_object = _boundary_depth.map(lambda d: _nest(d, '{"k":', "}"))

_scalar = st.one_of(
    _quoted_string,
    _bad_string,
    _number,
    _extreme_number,
    st.sampled_from(["true", "false", "null", "True", "NULL", "nul"]),
)

# Malformed structural fragments to sprinkle in.
_malformed_fragment = st.sampled_from(
    [
        "[,]",
        "[1,,2]",
        "{,}",
        '{"a":1,,}',
        '{"a" 1}',
        '{"a":}',
        '{"a"}',
        '{"a":1,}',
        "[1,2,]",
        "{",
        "[",
        "}",
        "]",
        '{"a":1',
        "[1,2",
        "",
        "   ",
        "\x00",
        "\ufeff",
        "\ufeff1",
        "1\x00",
        '"\x00"',
    ]
)

# Composite strategies: we use st.recursive for the recursive obj/arr.
# Leaves are scalars and malformed fragments.
def _make_value():
    return st.recursive(
        st.one_of(_scalar, _malformed_fragment, _deep_array, _deep_object),
        lambda children: st.one_of(
            # arrays
            st.lists(children, max_size=5).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(children, max_size=5).map(
                lambda xs: "[" + ",".join(xs) + ",]"  # trailing comma (rejected)
            ),
            # objects
            st.lists(
                st.tuples(_quoted_string, children).map(
                    lambda kv: kv[0] + ":" + kv[1]
                ),
                max_size=5,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
            # object with missing colon
            st.lists(
                st.tuples(_quoted_string, children).map(
                    lambda kv: kv[0] + " " + kv[1]
                ),
                max_size=4,
            ).map(lambda ps: "{" + ",".join(ps) + "}"),
        ),
        max_leaves=12,
    )


_value = _make_value()


# Duplicate-key objects: exercise the parser's duplicate handling path and
# the object comparison paths (print_object / cJSON_Compare).
_dup_key_object = st.lists(
    st.tuples(
        st.sampled_from(['"a"', '"b"', '"a"', '"k"', '"a"']),
        _scalar,
    ).map(lambda kv: kv[0] + ":" + kv[1]),
    min_size=2,
    max_size=6,
).map(lambda ps: "{" + ",".join(ps) + "}")


@st.composite
def _json_doc(draw):
    v = draw(_value)
    lead = draw(_ws)
    trail = draw(_ws)
    # Occasionally add trailing content (accepted by the parser).
    extra = draw(
        st.one_of(
            st.nothing(),
            st.just("abc"),
            st.just(" 1 2"),
            st.just("\x00"),
            st.just("]"),
            st.just("garbage"),
        )
    )
    base = lead + v + trail + extra
    # Occasionally emit a duplicate-key object instead, to reach
    # print_object / cJSON_Compare paths.
    if draw(st.booleans()):
        return draw(_dup_key_object)
    return base


strategy = _json_doc()
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 74.72,
  "region_coverage_pct": 93.9,
  "least_covered_functions": [
    "cJSON_Compare (0% of branches)",
    "print_value (0% of branches)",
    "print_string_ptr (0% of branches)",
    "print_number (0% of branches)",
    "print_object (0% of branches)"
  ],
  "least_covered_function_source": "CJSON_PUBLIC(cJSON_bool) cJSON_Compare(const cJSON * const a, const cJSON * const b, const cJSON_bool case_sensitive)\n{\n    if ((a == NULL) || (b == NULL) || ((a->type & 0xFF) != (b->type & 0xFF)))\n    {\n        return false;\n    }\n\n    /* check if type is valid */\n    switch (a->type & 0xFF)\n    {\n        case cJSON_False:\n        case cJSON_True:\n        case cJSON_NULL:\n        case cJSON_Number:\n        case cJSON_String:\n        case cJSON_Raw:\n        case cJSON_Array:\n        case cJSON_Object:\n            break;\n\n        default:\n            return false;\n    }\n\n    /* identical objects are equal */\n    if (a == b)\n    {\n        return true;\n    }\n\n    switch (a->type & 0xFF)\n    {\n        /* in these cases and equal type is enough */\n        case cJSON_False:\n        case cJSON_True:\n        case cJSON_NULL:\n            return true;\n\n        case cJSON_Number:\n            if (compare_double(a->valuedouble, b->valuedouble))\n            {\n                return true;\n            }\n            return false;\n\n        case cJSON_String:\n        case cJSON_Raw:\n            if ((a->valuestring == NULL) || (b->valuestring == NULL))\n            {\n                return false;\n            }\n            if (strcmp(a->valuestring, b->valuestring) == 0)\n            {\n                return true;\n            }\n\n            return false;\n\n        case cJSON_Array:\n        {\n            cJSON *a_element = a->child;\n            cJSON *b_element = b->child;\n\n            for (; (a_element != NULL) && (b_element != NULL);)\n            {\n                if (!cJSON_Compare(a_element, b_element, case_sensitive))\n                {\n                    return false;\n                }\n\n                a_element = a_element->next;\n                b_element = b_element->next;\n            }\n\n            /* one of the arrays is longer than the other */\n            if (a_element != b_element) {\n                return false;\n            }\n\n            return true;\n/* ... truncated ... */"
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.