from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf-level strategies
# ---------------------------------------------------------------------------

# Numbers: keep the valid core, then sprinkle in the parser's lenient
# deviations (leading zeros, trailing dot, hex, huge exponents).
_number_ints = st.one_of(
    st.integers(min_value=0, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    # leading zeros (accepted by parser)
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
    # hex (accepted by parser)
    st.integers(min_value=0, max_value=2**32).map(lambda n: hex(n)),
    st.just("0"),
    st.just("-0"),
)

_number_fracs = st.one_of(
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
    st.just("."),  # trailing dot, accepted by parser
    st.tuples(
        st.integers(min_value=0, max_value=10**6),
        st.integers(min_value=0, max_value=10**6),
    ).map(lambda t: "." + str(t[0]) + "0" * (t[1] % 5)),
)

_number_exps = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(abs(e))),
    st.integers(min_value=0, max_value=400).map(lambda e: "e-" + str(e)),
    # huge magnitudes -> inf when parsed
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

# Strings: valid escapes, \uXXXX, surrogate escapes, raw control/NUL bytes.
_hex4 = st.tuples(*[st.sampled_from("0123456789abcdefABCDEF")] * 4).map(
    lambda t: "".join(t)
)

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4.map(lambda h: "\\u" + h),
    # surrogate pairs (valid) and lone surrogates (rejected by parser)
    st.tuples(
        st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800"]),
        st.sampled_from(["dc00", "dfff", "0000", "ffff"]),
    ).map(lambda t: "\\u" + t[0] + "\\u" + t[1]),
    st.sampled_from(["\\ud800", "\\udfff", "\\uD800", "\\uDC00"]),
)

# Raw code points allowed inside a string: printable ASCII plus control/NUL.
_safe_chars = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF),
    # raw control bytes and NUL, accepted by the parser
    st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"]),
)

_string_pieces = st.one_of(_escapes, _safe_chars)

_strings = st.lists(_string_pieces, max_size=8).map(lambda xs: '"' + "".join(xs) + '"')

# Malformed / near-valid leaf fragments (used for fuzzing mutations).
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


# Build the recursive value strategy with a depth budget.
# Depth limit of the parser is 1000; concentrate near it.
_deep_obj = st.integers(min_value=0, max_value=4).map(
    lambda n: "{" + '"k":' * n + "null" + "}" * n
)
_deep_arr = st.integers(min_value=0, max_value=4).map(
    lambda n: "[" * n + "null" + "]" * n
)

# Near-limit depth generators (careful: keep counts modest for speed).
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

# Recursive core; use st.recursive for obj/arr nesting.
_scalar = st.one_of(
    _strings,
    _numbers,
    st.sampled_from(["true", "false", "null"]),
    _malformed_fragments,
)

_value_strategy = st.recursive(
    _scalar,
    lambda children: st.one_of(
        # arrays
        st.lists(children, min_size=0, max_size=5).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        # objects with pairs
        st.lists(_pair(), min_size=0, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        # whitespace-padded containers
        st.tuples(
            st.lists(children, min_size=1, max_size=3),
            _ws,
        ).map(lambda t: "[" + t[1] + ("," + t[1]).join(t[0]) + t[1] + "]"),
    ),
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Top-level wrappers: valid, near-valid, malformed, BOM, trailing junk
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

strategy = st.one_of(
    # valid values with optional BOM and trailing content
    st.tuples(_bom, _valid_top, _trailing_junk).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    # malformed top-level inputs
    st.tuples(_bom, _malformed_top).map(lambda t: t[0] + t[1]),
    # raw NUL / control-heavy fuzz: bias toward structural/control bytes
    st.lists(
        st.one_of(
            st.sampled_from(
                [
                    "{", "}", "[", "]", ",", ":", '"', "\\", "0", "1", "-",
                    "+", ".", "e", "E", "t", "f", "n", "u", " ", "\t", "\n",
                    "\r", "\x00", "\x01", "\x1f", "\x7f", "\ufeff",
                ]
            ),
            st.characters(min_codepoint=0, max_codepoint=0x10FFFF),
        ),
        min_size=0,
        max_size=40,
    ).map(lambda cs: "".join(cs)),
)