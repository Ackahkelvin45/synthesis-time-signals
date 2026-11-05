Here is the current Hypothesis strategy:

```python
import json
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

_hex = "0123456789abcdefABCDEF"

def _escape():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    uni = st.tuples(*([st.sampled_from(_hex)] * 4)).map(lambda t: "\\u" + "".join(t))
    # lone surrogates (rejected by parser, but useful fuzz)
    lone = st.sampled_from(["\\ud800", "\\udc00", "\\udfff", "\\uD800"])
    return st.one_of(simple, uni, lone)

def _safe_char():
    # printable-ish chars, plus raw control chars / NUL (accepted by parser)
    printable = st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                              blacklist_categories=("Cs",))
    control = st.sampled_from(["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x7f"])
    return st.one_of(printable, control)

def _string_body():
    return st.lists(st.one_of(_safe_char(), _escape()), max_size=8).map("".join)

def _string():
    return _string_body().map(lambda b: '"' + b + '"')

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _number():
    int_part = st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),  # leading zero (accepted)
    )
    sign = st.sampled_from(["", "-"])
    frac = st.one_of(
        st.just(""),
        st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
        st.just("."),  # trailing dot (accepted)
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(st.sampled_from(["e", "E"]),
                  st.sampled_from(["", "+", "-"]),
                  st.integers(min_value=0, max_value=400).map(str)).map("".join),
        st.sampled_from(["e309", "e999", "e-999", "E+308", "e01"]),
    )
    good = st.tuples(sign, int_part, frac, exp).map(lambda t: "".join(t))
    hexnum = st.tuples(st.sampled_from(["", "-"]),
                       st.sampled_from(["0x", "0X"]),
                       st.integers(min_value=0, max_value=0xFFFFFF).map(lambda n: format(n, "x"))
                       ).map(lambda t: "".join(t))
    bad = st.sampled_from(["-", "+1", ".5", "NaN", "Infinity", "-Infinity", "1e", "1e+", "--1"])
    return st.one_of(good, hexnum, bad)

# ---------------------------------------------------------------------------
# Malformed fragments (near-valid-but-broken)
# ---------------------------------------------------------------------------

def _malformed():
    return st.sampled_from([
        '{"a":1,}', '[1,2,]', '{"a" 1}', '{"a":}', '{:1}', '[1,,2]',
        '"unterminated', "'single'", '{a:1}', '[', '{', '}', ']',
        '[,]', '{,}', '{"a":1 "b":2}', 'tru', 'nul', 'fals', 'TRUE',
        '"\\x41"', '"\\u12"', '{"a":1}}', '[[1,2]', '{"a":[1,2}',
    ])

# ---------------------------------------------------------------------------
# Recursive value strategy
# ---------------------------------------------------------------------------

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _malformed(),
    )

def _pair():
    return st.tuples(_string(), st.just(":"), _leaf()).map(lambda t: "".join(t))

def _obj_flat():
    pairs = st.lists(_pair(), max_size=4).map(lambda ps: ",".join(ps))
    return pairs.map(lambda p: "{" + p + "}")

def _arr_flat():
    vals = st.lists(_leaf(), max_size=4).map(lambda vs: ",".join(vs))
    return vals.map(lambda v: "[" + v + "]")

_value = st.recursive(
    _leaf(),
    lambda children: st.one_of(
        st.tuples(st.just("["), st.lists(children, max_size=3).map(lambda vs: ",".join(vs)), st.just("]")).map("".join),
        st.tuples(st.just("{"),
                  st.lists(st.tuples(_string(), st.just(":"), children).map(lambda t: "".join(t)),
                           max_size=3).map(lambda ps: ",".join(ps)),
                  st.just("}")).map("".join),
    ),
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Depth-focused constructions near the 1000-level limit
# ---------------------------------------------------------------------------

def _depth_strategy():
    depth = st.one_of(
        st.integers(min_value=0, max_value=50),
        st.integers(min_value=990, max_value=1010),
        st.sampled_from([999, 1000, 1001, 1002]),
    )
    opener = st.sampled_from(["[", "{"])
    closer = st.sampled_from(["]", "}"])

    def build(t):
        d, o, c = t
        if o == "{" and c == "}":
            inner = "0"
            return "{" * d + '"a":' + inner + "}" * d
        return o * d + "0" + c * d

    return st.tuples(depth, opener, closer).map(build)

# ---------------------------------------------------------------------------
# Edge-case literals and whitespace/BOM wrappers
# ---------------------------------------------------------------------------

_edges = st.sampled_from([
    '{}', '[]', '{"a":1}', '[1,2,3]', '{"":""}', '{"a":1,"a":2}',
    '1e309', '-1e309', '1e-999', '0x10', '01', '1.', '1abc', '1 2',
    '\ufeff{"a":1}', '\ufeff1', '"a\x00b"', '"\x01"', '"\\ud800"',
    '"\\ud83d\\ude00"', '"\\u0000"', '""', 'true', 'false', 'null',
    '{"a":{"b":{"c":[1,2,{"d":null}]}}}',
])

_ws = st.sampled_from(["", " ", "\t", "\n", "\r\n", " \t\n"])

def _wrapped(v):
    return st.tuples(_ws, v, _ws).map(lambda t: "".join(t))

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _value,
    _obj_flat(),
    _arr_flat(),
    _edges,
    _depth_strategy(),
    _wrapped(_value),
    _wrapped(st.one_of(_edges, _depth_strategy())),
    _malformed(),
    # trailing content after a complete value (accepted by parser)
    st.tuples(_value, st.sampled_from(["abc", " 1 2", "\x00", "}", "]"])).map(lambda t: t[0] + t[1]),
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 76.42,
  "region_coverage_pct": 94.08,
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