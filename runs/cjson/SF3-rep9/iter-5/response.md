```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf-level strategies
# ---------------------------------------------------------------------------

_number_ints = st.one_of(
    st.integers(min_value=0, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
    st.integers(min_value=0, max_value=2**32).map(lambda n: hex(n)),
    st.just("0"),
    st.just("-0"),
)

_number_fracs = st.one_of(
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
    st.just("."),
    st.tuples(
        st.integers(min_value=0, max_value=10**6),
        st.integers(min_value=0, max_value=10**6),
    ).map(lambda t: "." + str(t[0]) + "0" * (t[1] % 5)),
)

_number_exps = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(abs(e))),
    st.integers(min_value=0, max_value=400).map(lambda e: "e-" + str(e)),
    st.sampled_from(["e309", "e1000", "e999999999", "E+308", "e-9999"]),
)

_numbers = st.one_of(
    _number_ints,
    st.tuples(_number_ints, _number_fracs).map(lambda t: t[0] + t[1]),
    st.tuples(_number_ints, _number_fracs, _number_exps).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(_number_ints, _number_exps).map(lambda t: t[0] + t[1]),
)

_hex4 = st.tuples(*[st.sampled_from("0123456789abcdefABCDEF")] * 4).map(
    lambda t: "".join(t)
)

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4.map(lambda h: "\\u" + h),
    st.tuples(
        st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800"]),
        st.sampled_from(["dc00", "dfff", "0000", "ffff"]),
    ).map(lambda t: "\\u" + t[0] + "\\u" + t[1]),
    st.sampled_from(["\\ud800", "\\udfff", "\\uD800", "\\uDC00"]),
)

_safe_chars = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
    st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
)

_string_pieces = st.one_of(_escapes, _safe_chars)

_strings = st.lists(_string_pieces, max_size=8).map(lambda xs: '"' + "".join(xs) + '"')

_malformed_fragments = st.sampled_from(
    [
        '"unterminated',
        '"',
        "\\",
        "\\u12",
        "\\uZZZZ",
        "\\x41",
        "'single'",
        "01",
        "007",
        "1.",
        "-",
        "+1",
        ".5",
        "0x",
        "0xZZ",
        "NaN",
        "Infinity",
        "-Infinity",
        "1e",
        "1e+",
        "1ee5",
        "tru",
        "fals",
        "nul",
        "True",
        "False",
        "None",
        "{}",
        "[]",
        ",",
        ":",
        "\x00",
        "\ufeff",
        "1 2",
        "1abc",
        "nullnull",
    ]
)

# ---------------------------------------------------------------------------
# Recursive obj/arr construction
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])


@st.composite
def _pair(draw):
    key = draw(_strings)
    colon = draw(st.sampled_from([":", ":", ":", ": ", " : "]))
    val = draw(_value_strategy)
    return key + colon + val


_deep_obj = st.integers(min_value=0, max_value=4).map(
    lambda n: "{" + '"k":' * n + "null" + "}" * n
)
_deep_arr = st.integers(min_value=0, max_value=4).map(
    lambda n: "[" * n + "null" + "]" * n
)

_near_limit_arrays = st.integers(min_value=990, max_value=1010).map(
    lambda n: "[" * n + "0" + "]" * n
)
_near_limit_objs = st.integers(min_value=990, max_value=1010).map(
    lambda n: '{"a":' * n + "0" + "}" * n
)

_empty_containers = st.sampled_from(["{}", "[]", "{ }", "[ ]", "{\n}", "[\t]"])

_duplicate_key_obj = st.tuples(
    _strings,
    _strings,
).map(lambda t: "{" + t[0] + ":1," + t[0] + ":2," + t[1] + ":null}")

_obj_atoms = st.one_of(
    _empty_containers,
    _duplicate_key_obj,
    _deep_obj,
    _near_limit_objs,
)

_arr_atoms = st.one_of(
    _empty_containers,
    _deep_arr,
    _near_limit_arrays,
)

_scalar = st.one_of(
    _strings,
    _numbers,
    st.sampled_from(["true", "false", "null"]),
    _malformed_fragments,
)

_value_strategy = st.recursive(
    _scalar,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=5).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(_pair(), min_size=0, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        st.tuples(
            st.lists(children, min_size=1, max_size=3),
            _ws,
        ).map(lambda t: "[" + t[1] + ("," + t[1]).join(t[0]) + t[1] + "]"),
    ),
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Top-level wrappers
# ---------------------------------------------------------------------------

_trailing_junk = st.one_of(
    st.just(""),
    st.just("\x00"),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("}"),
    st.just("]"),
    st.just("garbage"),
    st.just("\n\n"),
    st.just("\x00\x00"),
)

_bom = st.sampled_from(["", "\ufeff"])

_malformed_top = st.one_of(
    st.just(""),
    st.just("   "),
    st.just(","),
    st.just(":"),
    st.just("[1,,2]"),
    st.just('{"a":1,}'),
    st.just("[1,2,]"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just("{:1}"),
    st.just("{a:1}"),
    st.just("[1 2]"),
    st.just('"\\ud800"'),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("01"),
    st.just("0x10"),
    st.just("\x00"),
    st.just("\ufeff"),
)

_valid_top = st.one_of(
    _value_strategy,
    _obj_atoms,
    _arr_atoms,
    _near_limit_arrays,
    _near_limit_objs,
)

# ---------------------------------------------------------------------------
# Printer / Compare coverage.
#
# The driver parses a single document and then prints/compares it. To reach
# print_value / print_string_ptr / print_number / print_object / cJSON_Compare
# we must emit ONE well-formed document (no NUL-joined pairs, no trailing
# junk), so the driver's parse fully succeeds and falls through to the
# print/compare code paths.
# ---------------------------------------------------------------------------

_printable_scalar = st.one_of(
    st.integers(min_value=-10**18, max_value=10**18),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=16),
    st.booleans(),
    st.none(),
)

_printable_value = st.recursive(
    _printable_scalar,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=6),
        st.dictionaries(
            st.text(max_size=8), children, min_size=0, max_size=6
        ),
    ),
    max_leaves=50,
)

# Single well-formed documents. ensure_ascii=True forces \uXXXX escapes so
# print_string_ptr's escape branch is hit; ensure_ascii=False exercises raw
# UTF-8 output. Both are emitted alone so the driver parses cleanly and then
# prints. A whitespace-padded variant is included to be robust to drivers that
# require exact parsing around the value.
_print_docs = st.one_of(
    _printable_value.map(lambda v: json.dumps(v, ensure_ascii=True)),
    _printable_value.map(lambda v: json.dumps(v, ensure_ascii=False)),
    _printable_value.map(
        lambda v: "  " + json.dumps(v, ensure_ascii=True) + "  "
    ),
)

# Strings that force every escape branch in print_string_ptr (control chars,
# quotes, backslashes, and non-ASCII needing \uXXXX).
_escape_heavy_string = st.tuples(
    st.text(
        alphabet=st.characters(
            min_codepoint=0x00,
            max_codepoint=0x10FFFF,
            blacklist_categories=("Cs",),
        ),
        max_size=10,
    ),
    st.sampled_from(['"', "\\", "\n", "\t", "\x00", "\x1f", "\x7f", "é", "€", "𝄞"]),
    st.text(max_size=6),
).map(lambda t: t[0] + t[1] + t[2])

_escape_doc = _escape_heavy_string.map(
    lambda s: json.dumps(s, ensure_ascii=True)
)

# Numbers spanning print_number's branches (integer vs. fractional, negative,
# large exponents, small/large magnitudes).
_print_number_doc = st.one_of(
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    st.floats(allow_nan=False, allow_infinity=False).map(
        lambda f: json.dumps(f)
    ),
    st.sampled_from(
        ["0", "-0", "1", "-1", "1.5", "-1.5", "1e300", "1e-300", "123456789012345678"]
    ),
)

# Objects with many keys (print_object iteration) and nested objects.
_print_object_doc = st.dictionaries(
    st.text(
        alphabet=st.characters(
            min_codepoint=0x20,
            max_codepoint=0x7E,
            blacklist_characters='"\\',
        ),
        max_size=10,
    ),
    _printable_value,
    min_size=0,
    max_size=8,
).map(lambda d: json.dumps(d, ensure_ascii=True))

# Arrays with many elements (print_array iteration).
_print_array_doc = st.lists(
    _printable_value, min_size=0, max_size=10
).map(lambda xs: json.dumps(xs, ensure_ascii=True))

# A document that the driver can parse and then compare against itself
# (cJSON_Compare self-comparison reaches the compare branches).
_compare_doc = _printable_value.map(
    lambda v: json.dumps(v, ensure_ascii=True)
)

strategy = st.one_of(
    st.tuples(_bom, _valid_top, _trailing_junk).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(_bom, _malformed_top).map(lambda t: t[0] + t[1]),
    st.lists(
        st.one_of(
            st.characters(min_codepoint=0, max_codepoint=0x10FFFF),
        ),
        min_size=0,
        max_size=40,
    ).map(lambda cs: "".join(cs)),
    # Printer/compare coverage: single well-formed documents.
    _print_docs,
    _escape_doc,
    _print_number_doc,
    _print_object_doc,
    _print_array_doc,
    _compare_doc,
)
```