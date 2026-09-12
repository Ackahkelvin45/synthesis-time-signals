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
# ---------------------------------------------------------------------------

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

_EMPTY_STRING = st.sampled_from(['""', '"\\""', '"\\\\"', '"\\u83B9"'])

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

_CRASH_INNER = st.one_of(
    _EMPTY_STRING,
    _EMPTY_STRING,
    _STRESS_STRING,
    _CRASH_NUMBER,
    st.just("0"),
    st.just("null"),
    _STRING,
    _NUMBER,
)

_CRASH_DEPTH = st.one_of(
    st.integers(min_value=38, max_value=42),
    st.integers(min_value=38, max_value=42),
    st.just(40),
    st.just(40),
    st.just(40),
    st.integers(min_value=1, max_value=64),
    st.sampled_from([39, 40, 41, 63, 64, 65, 128]),
)

_NEAR_CRASH_DEEP_ARR = st.builds(
    lambda d, inner, trail: "[" * d + inner + "]" * d + trail,
    _CRASH_DEPTH,
    _CRASH_INNER,
    st.one_of(st.just(""), st.just("\x00"), st.just("garbage"), st.just("\x1f")),
)

_NEAR_CRASH_DEEP_OBJ = st.builds(
    lambda d, inner, trail: '{"a":' * d + inner + "}" * d + trail,
    _CRASH_DEPTH,
    _CRASH_INNER,
    st.one_of(st.just(""), st.just("\x00"), st.just("garbage")),
)

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

_NEAR_CRASH_PREFIX = st.one_of(
    st.just(""),
    st.just(""),
    st.just("\r"),
    st.just("\r\n"),
    st.just("\n"),
    st.just(" "),
    st.just("\t"),
    st.just("\r\n"),
)

_NEAR_CRASH_TRAIL = st.one_of(
    st.just(""),
    st.just(""),
    st.just("\x00"),
    st.just("garbage"),
    st.just("\x1f"),
    st.just("]"),
    st.just("}"),
)

_NEAR_CRASH_EXACT = st.builds(
    lambda pre, d, inner, trail: pre + "[" * d + inner + "]" * d + trail,
    _NEAR_CRASH_PREFIX,
    st.one_of(st.just(40), st.just(40), st.just(40), _CRASH_DEPTH),
    _EMPTY_STRING,
    _NEAR_CRASH_TRAIL,
)

_NEAR_CRASH_EXACT_MUTATED = st.builds(
    lambda pre, d, inner, trail: pre + "[" * d + inner + "]" * d + trail,
    _NEAR_CRASH_PREFIX,
    st.one_of(
        st.just(40),
        st.just(40),
        st.just(40),
        st.just(40),
        st.integers(min_value=39, max_value=41),
        st.integers(min_value=38, max_value=42),
    ),
    st.one_of(
        _EMPTY_STRING,
        _EMPTY_STRING,
        _STRESS_STRING,
        _CRASH_NUMBER,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        st.just("0"),
        _STRING,
    ),
    st.one_of(
        st.just(""),
        st.just(""),
        st.just("\x00"),
        st.just("garbage"),
        st.just("\x1f"),
        st.just("]"),
        st.just("}"),
    ),
)

_NEAR_CRASH_DIVERGENCE = st.builds(
    lambda pre, d, inner, trail: pre + "[" * d + inner + "]" * d + trail,
    st.one_of(st.just("\n"), st.just("\r\n"), st.just("\r"), st.just("")),
    st.one_of(st.just(40), st.just(40), st.just(40), st.just(40),
              st.integers(min_value=39, max_value=41)),
    st.one_of(st.just("true"), st.just("false"), st.just("null"),
              st.just("0"), _EMPTY_STRING),
    st.one_of(st.just("\x00"), st.just("\x00"), st.just(""), st.just("garbage")),
)

_CENTER_STACK = st.builds(
    lambda layers: "".join("[" + inner + "]" for inner in layers),
    st.lists(
        st.one_of(
            _EMPTY_STRING,
            _STRESS_STRING,
            _CRASH_NUMBER,
            st.just("0"),
            st.just("null"),
            st.just("\x1f"),
        ),
        min_size=0,
        max_size=4,
    ),
)

_NEAR_CRASH_CENTER_MUTATED = st.builds(
    lambda pre, d, center, splice, trail: (
        pre + "[" * d + splice + center + "]" * d + trail
    ),
    _NEAR_CRASH_PREFIX,
    st.one_of(
        st.just(40),
        st.just(40),
        st.just(40),
        st.integers(min_value=38, max_value=42),
        st.integers(min_value=1, max_value=64),
    ),
    _CENTER_STACK,
    st.one_of(st.just(""), st.just(""), st.just("\x00"), st.just("\x1f"),
              st.just("\\"), st.just('"')),
    _NEAR_CRASH_TRAIL,
)

_NEAR_CRASH_ASYMMETRIC = st.builds(
    lambda pre, d_open, inner, d_close, trail: (
        pre + "[" * d_open + inner + "]" * d_close + trail
    ),
    _NEAR_CRASH_PREFIX,
    st.one_of(st.just(40), st.just(40), st.integers(min_value=38, max_value=64)),
    st.one_of(_EMPTY_STRING, _STRESS_STRING, _CRASH_NUMBER, st.just("0")),
    st.one_of(
        st.just(0),
        st.just(1),
        st.integers(min_value=0, max_value=40),
        st.integers(min_value=38, max_value=42),
    ),
    _NEAR_CRASH_TRAIL,
)


def _stress_leaf_value():
    return st.one_of(
        st.just('"\\u83B9\\"\\x1f\\"F\\"\\"F"'),
        st.just('"\\u83B9"'),
        st.just('"\\"\\x1f\\"F\\"\\"F"'),
        _STRESS_STRING,
        _EMPTY_STRING,
    )


_NEAR_CRASH_STRESS_LEAF = st.builds(
    lambda pre, d, leaf, trail: pre + "[" * d + leaf + "]" * d + trail,
    _NEAR_CRASH_PREFIX,
    st.one_of(st.just(40), st.just(40), st.just(40),
              st.integers(min_value=38, max_value=42)),
    _stress_leaf_value(),
    _NEAR_CRASH_TRAIL,
)


_NEAR_CRASH = st.one_of(
    _NEAR_CRASH_EXACT,
    _NEAR_CRASH_EXACT,
    _NEAR_CRASH_EXACT,
    _NEAR_CRASH_EXACT_MUTATED,
    _NEAR_CRASH_EXACT_MUTATED,
    _NEAR_CRASH_EXACT_MUTATED,
    _NEAR_CRASH_DIVERGENCE,
    _NEAR_CRASH_DIVERGENCE,
    _NEAR_CRASH_DIVERGENCE,
    _NEAR_CRASH_DEEP_ARR,
    _NEAR_CRASH_DEEP_ARR,
    _NEAR_CRASH_DEEP_ARR,
    _NEAR_CRASH_DEEP_ARR,
    _NEAR_CRASH_DEEP_OBJ,
    _NEAR_CRASH_MIXED,
    _CRASH_NUMBER,
    _CRASH_NUMBER,
    _NEAR_CRASH_CENTER_MUTATED,
    _NEAR_CRASH_CENTER_MUTATED,
    _NEAR_CRASH_CENTER_MUTATED,
    _NEAR_CRASH_ASYMMETRIC,
    _NEAR_CRASH_ASYMMETRIC,
    _NEAR_CRASH_STRESS_LEAF,
    _NEAR_CRASH_STRESS_LEAF,
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

_top_intensified = st.one_of(
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
    _NEAR_CRASH,
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