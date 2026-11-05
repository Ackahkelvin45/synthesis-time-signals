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
    return lead + v + trail + extra


# Exercise the printer / comparison code paths (cJSON_Print*, cJSON_Compare)
# which were entirely uncovered: these operate on parsed values.
@st.composite
def _print_compare_doc(draw):
    v = draw(_value)
    # A second value to compare against (sometimes identical).
    if draw(st.booleans()):
        other = v
    else:
        other = draw(_value)
    mode = draw(st.sampled_from(["print", "compare", "both"]))
    return v + "\n---\n" + other + "\n" + mode


# Directly-targeted documents that exercise the printer and comparison code
# paths (print_value / print_string_ptr / print_number / print_object /
# cJSON_Compare) which were previously 0% covered. These are valid JSON
# documents whose parsed values are then printed / compared by the harness.
_PRINT_COMPARE_VALUES = st.one_of(
    # strings with escapes, unicode, controls -> print_string_ptr paths
    _quoted_string,
    st.sampled_from(
        [
            '"plain"',
            '"with \\"quote\\""',
            '"tab\\there"',
            '"newline\\nhere"',
            '"unicode \\u00e9 \\u4e2d"',
            '"control \x01\x02\x1f"',
            '"backslash \\\\ ok"',
            '""',
        ]
    ),
    # numbers -> print_number paths (int, frac, exp, extremes)
    _number,
    _extreme_number,
    st.sampled_from(
        [
            "0",
            "-0",
            "1",
            "-1",
            "42",
            "3.14159",
            "-2.5",
            "1e10",
            "1E-10",
            "1.5e+3",
            "9007199254740993",
            "1.7976931348623157e308",
        ]
    ),
    # scalars
    st.sampled_from(["true", "false", "null"]),
    # arrays / objects -> print_value / print_object paths
    st.sampled_from(
        [
            "[]",
            "[1]",
            "[1,2,3]",
            "[true,false,null]",
            '["a","b"]',
            "[[1],[2,3]]",
            "[1,[2,[3]]]",
            "{}",
            '{"a":1}',
            '{"a":1,"b":2}',
            '{"a":[1,2],"b":{"c":3}}',
            '{"nested":{"deep":{"deeper":true}}}',
            '{"s":"str","n":1.5,"b":false,"z":null}',
            '{"":"empty key"}',
            '{"k":[]}',
            '{"k":{}}',
        ]
    ),
)


@st.composite
def _print_compare_targeted(draw):
    v = draw(_PRINT_COMPARE_VALUES)
    # Sometimes compare against a structurally similar / identical value.
    if draw(st.booleans()):
        other = v
    else:
        other = draw(_PRINT_COMPARE_VALUES)
    mode = draw(st.sampled_from(["print", "compare", "both"]))
    return v + "\n---\n" + other + "\n" + mode


strategy = st.one_of(_json_doc(), _print_compare_doc(), _print_compare_targeted())
```