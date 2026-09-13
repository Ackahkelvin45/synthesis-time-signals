```python
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

# Characters that are safe inside a JSON string (no raw control bytes, no raw NUL).
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00',
).filter(lambda c: ord(c) >= 0x20)

# Escape sequences that are always valid.
_SIMPLE_ESCAPES = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_HEX = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    """A \\uXXXX escape, sometimes a lone surrogate (valid syntax, weird value)."""
    kind = draw(st.sampled_from(["plain", "high", "low", "nul", "ffff"]))
    if kind == "high":
        return "\\u" + draw(st.sampled_from("dD")) + draw(
            st.sampled_from("89abAB")
        ) + draw(_HEX) + draw(_HEX)
    if kind == "low":
        return "\\u" + draw(st.sampled_from("dD")) + draw(
            st.sampled_from("cdefCDEF")
        ) + draw(_HEX) + draw(_HEX)
    if kind == "nul":
        return "\\u0000"
    if kind == "ffff":
        return "\\uffff"
    return "\\u" + "".join(draw(_HEX) for _ in range(4))


@st.composite
def _string_body(draw):
    """Content of a JSON string, without the surrounding quotes."""
    n = draw(st.integers(min_value=0, max_value=12))
    parts = []
    for _ in range(n):
        parts.append(
            draw(
                st.one_of(
                    _SAFE_CHARS.map(str),
                    _SIMPLE_ESCAPES,
                    _unicode_escape(),
                )
            )
        )
    return "".join(parts)


@st.composite
def _json_string(draw):
    return '"' + draw(_string_body()) + '"'


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT_DIGITS = st.text(alphabet="0123456789", min_size=1, max_size=18)


@st.composite
def _number(draw):
    kind = draw(
        st.sampled_from(
            [
                "zero",
                "small_int",
                "big_int",
                "huge_int",
                "frac",
                "exp",
                "extreme_exp",
                "neg",
                "tiny",
            ]
        )
    )
    if kind == "zero":
        return "0"
    if kind == "small_int":
        return str(draw(st.integers(min_value=-1000, max_value=1000)))
    if kind == "big_int":
        return "-" * draw(st.booleans()) + str(
            draw(st.integers(min_value=10 ** 15, max_value=10 ** 18))
        )
    if kind == "huge_int":
        return "-" * draw(st.booleans()) + draw(
            st.text(alphabet="123456789", min_size=1, max_size=1)
        ) + draw(st.text(alphabet="0123456789", min_size=300, max_size=400))
    if kind == "frac":
        return (
            "-" * draw(st.booleans())
            + str(draw(st.integers(min_value=0, max_value=10 ** 9)))
            + "."
            + draw(st.text(alphabet="0123456789", min_size=1, max_size=20))
        )
    if kind == "exp":
        return (
            "-" * draw(st.booleans())
            + str(draw(st.integers(min_value=0, max_value=1000)))
            + draw(st.sampled_from("eE"))
            + draw(st.sampled_from(["", "+", "-"]))
            + draw(st.text(alphabet="0123456789", min_size=1, max_size=4))
        )
    if kind == "extreme_exp":
        # Overflow / underflow territory (parser rejects non-finite).
        mant = draw(
            st.sampled_from(["1", "9", "1.5", "0.1", "12345", "1e", "10"])
        )
        sign = draw(st.sampled_from(["", "+", "-"]))
        exp = draw(
            st.sampled_from(
                ["309", "308", "310", "1000", "999999", "400", "324", "325"]
            )
        )
        return mant + draw(st.sampled_from("eE")) + sign + exp
    if kind == "neg":
        return "-" + str(draw(st.integers(min_value=0, max_value=10 ** 6)))
    # tiny
    return "0." + draw(st.text(alphabet="0123456789", min_size=1, max_size=30))


# ---------------------------------------------------------------------------
# Recursive JSON value
# ---------------------------------------------------------------------------

_MAX_DEPTH = 2048


@st.composite
def _key(draw):
    return draw(_json_string())


@st.composite
def _object(draw, values):
    n = draw(st.integers(min_value=0, max_value=8))
    if n == 0:
        return "{}"
    pairs = []
    for _ in range(n):
        k = draw(_key())
        v = draw(values)
        pairs.append(k + ":" + v)
    return "{" + ",".join(pairs) + "}"


@st.composite
def _array(draw, values):
    n = draw(st.integers(min_value=0, max_value=8))
    if n == 0:
        return "[]"
    items = [draw(values) for _ in range(n)]
    return "[" + ",".join(items) + "]"


def _value_strategy():
    return st.recursive(
        st.one_of(
            _json_string(),
            _number(),
            st.sampled_from(["true", "false", "null"]),
        ),
        lambda children: st.one_of(_array(children), _object(children)),
        max_leaves=60,
    )


# ---------------------------------------------------------------------------
# Edge / malformed / structural specials
# ---------------------------------------------------------------------------

def _deep_nesting():
    """Nesting near the parser's MAX_NESTING limit (2048)."""
    def build(depth, opener, closer):
        return opener * depth + closer * depth

    return st.one_of(
        st.integers(min_value=2040, max_value=2048).map(
            lambda d: build(d, "[", "]")
        ),
        st.integers(min_value=2040, max_value=2048).map(
            lambda d: build(d, '{"k":', "}")
        ),
        st.integers(min_value=2046, max_value=2050).map(
            lambda d: build(d, "[", "]")
        ),
        # Deep but well under the cap.
        st.integers(min_value=1, max_value=64).map(lambda d: build(d, "[", "]")),
        st.integers(min_value=1, max_value=64).map(
            lambda d: build(d, '{"k":', "}")
        ),
    )


def _duplicate_keys():
    return st.one_of(
        st.just('{"k":0,"k":1}'),
        st.just('{"a":1,"b":2,"a":3}'),
        st.just('{"x":{"y":1},"x":[2]}'),
        st.tuples(
            _json_string(),
            _number(),
            _number(),
        ).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"),
    )


def _malformed():
    # Near-valid-but-broken variants.
    return st.one_of(
        st.just("{"),
        st.just("["),
        st.just("}"),
        st.just("]"),
        st.just('{"a":}'),
        st.just('{"a" 1}'),
        st.just('{"a":1,}'),
        st.just("[1,2,]"),
        st.just("[1,,2]"),
        st.just("{,}"),
        st.just('{"a":1 "b":2}'),
        st.just('"unterminated'),
        st.just('"unterminated\\'),
        st.just('{"a":"unterminated}'),
        st.just("[1,2"),
        st.just('{"a":1'),
        st.just("+1"),
        st.just(".5"),
        st.just("1."),
        st.just("01"),
        st.just("00"),
        st.just("-"),
        st.just("-."),
        st.just("--1"),
        st.just("1e"),
        st.just("1e+"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-999"),
        st.just("tru"),
        st.just("truee"),
        st.just("nul"),
        st.just("nullx"),
        st.just("fals"),
        st.just("NaN"),
        st.just("Infinity"),
        st.just("-Infinity"),
        st.just("'single'"),
        st.just(""),
        st.just(" "),
        st.just("\t\n"),
        # Trailing content after a complete value (parser accepts).
        st.just("1abc"),
        st.just("[]xyz"),
        st.just('{"a":1} trailing'),
        st.just("null null"),
        st.just("{}[]"),
    )


def _control_chars_in_string():
    # Escaped control chars and NUL escape (six-char, not raw NUL).
    return st.one_of(
        st.just('"\\u0000"'),
        st.just('"a\\u0000b"'),
        st.just('"\\u001f"'),
        st.just('"\\u0001\\u0002\\u0003"'),
        st.just('"\\u007f"'),
        st.just('"\\ud800"'),
        st.just('"\\udfff"'),
        st.just('"\\ud800\\udc00"'),
        st.just('"\\ud83d\\ude00"'),
        st.just('"\\uD834\\uDD1E"'),
    )


def _special_values():
    return st.one_of(
        _deep_nesting(),
        _duplicate_keys(),
        _malformed(),
        _control_chars_in_string(),
        st.just("{}"),
        st.just("[]"),
        st.just("[[[[[]]]]]"),
        st.just('{"a":{}}'),
        st.just('[{}]'),
        st.just('{"":0}'),
        st.just('{"":""}'),
    )


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

def _with_ws(s):
    """Occasionally sprinkle whitespace around a value."""
    return st.one_of(
        st.just(s),
        st.tuples(
            st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
            st.just(s),
            st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )


_value = _value_strategy()

# Broadened accepted-structure generators: wider mixes of scalars, arrays,
# objects, and whitespace, to push beyond the saturated coverage.
_WS_TOKENS = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  ", " \n "])

_SCALARS = st.one_of(
    _json_string(),
    _number(),
    st.sampled_from(["true", "false", "null"]),
    st.sampled_from(["0", "-1", "1e10", '""', "[]", "{}", "0.0", "-0", "1E2"]),
)


def _broad_structures():
    """Diverse accepted structures with varied whitespace and shapes."""
    scalar = _SCALARS
    # Arrays with arbitrary whitespace between tokens and elements.
    arr = st.tuples(
        _WS_TOKENS,
        st.lists(st.tuples(_WS_TOKENS, scalar, _WS_TOKENS), min_size=0, max_size=12),
        _WS_TOKENS,
    ).map(
        lambda t: "["
        + t[0]
        + ",".join(a + v + b for a, v, b in t[1])
        + t[2]
        + "]"
    )
    # Objects with arbitrary whitespace around keys, colons, commas.
    obj = st.tuples(
        _WS_TOKENS,
        st.lists(
            st.tuples(_WS_TOKENS, _json_string(), _WS_TOKENS, scalar, _WS_TOKENS),
            min_size=0,
            max_size=12,
        ),
        _WS_TOKENS,
    ).map(
        lambda t: "{"
        + t[0]
        + ",".join(a + k + b + ":" + c + v + d for a, k, b, v, c, d in [
            (p[0], p[1], p[2], p[3], p[4], "") for p in t[1]
        ])
        + t[2]
        + "}"
    )
    # Nested containers built from scalars and other containers.
    nested = st.recursive(
        scalar,
        lambda children: st.one_of(
            st.lists(children, min_size=0, max_size=10).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(
                st.tuples(_json_string(), children), min_size=0, max_size=10
            ).map(
                lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"
            ),
        ),
        max_leaves=120,
    )
    return st.one_of(arr, obj, nested)


def _diverse_structures():
    """Wider variety of accepted shapes to push beyond saturated coverage.

    Focuses on structural diversity rather than edge cases: mixed nesting,
    heterogeneous arrays, key variety, and varied whitespace placement.
    """
    scalar = _SCALARS

    # Heterogeneous arrays mixing scalars and shallow containers.
    shallow = st.one_of(
        scalar,
        st.lists(scalar, min_size=0, max_size=4).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(
            st.tuples(_json_string(), scalar), min_size=0, max_size=4
        ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
    )
    hetero_arr = st.lists(shallow, min_size=0, max_size=16).map(
        lambda xs: "[" + ",".join(xs) + "]"
    )

    # Objects with diverse key shapes and value shapes.
    keys = st.one_of(
        _json_string(),
        st.sampled_from(['""', '"a"', '"key"', '"k1"', '"\\u0041"', '" "']),
    )
    obj_variety = st.lists(
        st.tuples(keys, shallow), min_size=0, max_size=16
    ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}")

    # Mixed nested structure with random whitespace insertion.
    def _ws_insert(s):
        return s

    mixed = st.recursive(
        st.one_of(scalar, hetero_arr, obj_variety),
        lambda children: st.one_of(
            st.lists(children, min_size=0, max_size=8).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(
                st.tuples(keys, children), min_size=0, max_size=8
            ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
        ),
        max_leaves=200,
    )

    # Whitespace-heavy variants around scalars and containers.
    ws = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  ", " \t "])
    ws_wrapped = st.tuples(ws, st.one_of(scalar, hetero_arr, obj_variety), ws).map(
        lambda t: t[0] + t[1] + t[2]
    )

    return st.one_of(hetero_arr, obj_variety, mixed, ws_wrapped)


# ---------------------------------------------------------------------------
# Broadened exploration: deeper / wider accepted-structure diversity.
# ---------------------------------------------------------------------------

# A pool of scalar leaves with deliberately varied textual shapes.
_LEAF_POOL = st.one_of(
    st.sampled_from(
        [
            "0",
            "-0",
            "0.0",
            "-0.0",
            "1",
            "-1",
            "42",
            "3.14",
            "-2.5e-3",
            "1E2",
            "1e+10",
            "123456789012345",
            "true",
            "false",
            "null",
            '""',
            '"a"',
            '"hello world"',
            '"\\n\\t\\"\\\\"',
            '"\\u00e9"',
            '"\\uD83D\\uDE00"',
            "[]",
            "{}",
            "[0]",
            '{"k":0}',
            "[[],{}]",
            '[{"a":[]}]',
        ]
    ),
    _SCALARS,
)


def _stacked_structures():
    """Structures that vary nesting depth, breadth, and homogeneity."""
    leaf = _LEAF_POOL

    # Depth-focused: linear chains of single-element containers.
    depth_chain = st.integers(min_value=1, max_value=40).map(
        lambda d: "[" * d + "0" + "]" * d
    )
    depth_chain_obj = st.integers(min_value=1, max_value=40).map(
        lambda d: '{"a":' * d + "0" + "}" * d
    )
    depth_chain_mixed = st.integers(min_value=1, max_value=30).map(
        lambda d: "".join(
            ("[" if i % 2 == 0 else '{"a":') for i in range(d)
        )
        + "null"
        + "".join(("]" if i % 2 == 0 else "}") for i in reversed(range(d)))
    )

    # Breadth-focused: many siblings, shallow.
    wide_arr = st.lists(leaf, min_size=0, max_size=64).map(
        lambda xs: "[" + ",".join(xs) + "]"
    )
    wide_obj = st.lists(
        st.tuples(_json_string(), leaf), min_size=0, max_size=64
    ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}")

    # Alternating container kinds at each level.
    def _alt(depth):
        s = "0"
        for i in range(depth):
            if i % 3 == 0:
                s = "[" + s + "]"
            elif i % 3 == 1:
                s = '{"k":' + s + "}"
            else:
                s = "[" + s + "," + s + "]"
        return s

    alternating = st.integers(min_value=1, max_value=14).map(_alt)

    # Ragged nesting: random depth per branch.
    ragged = st.recursive(
        leaf,
        lambda children: st.one_of(
            st.lists(children, min_size=0, max_size=6).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(
                st.tuples(_json_string(), children), min_size=0, max_size=6
            ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
        ),
        max_leaves=250,
    )

    return st.one_of(
        depth_chain,
        depth_chain_obj,
        depth_chain_mixed,
        wide_arr,
        wide_obj,
        alternating,
        ragged,
    )


def _whitespace_matrix():
    """Same logical value rendered with many whitespace permutations."""
    ws = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  ", " \t\n "])
    scalar = _LEAF_POOL

    def _pad(s):
        return s

    return st.one_of(
        # Whitespace inside array brackets and around commas.
        st.tuples(
            ws, ws, st.lists(scalar, min_size=0, max_size=8), ws
        ).map(
            lambda t: "["
            + t[0]
            + (t[1] + "," + t[1]).join(t[2])
            + t[3]
            + "]"
        ),
        # Whitespace around colons and commas in objects.
        st.tuples(
            ws,
            ws,
            ws,
            st.lists(st.tuples(_json_string(), scalar), min_size=0, max_size=8),
            ws,
        ).map(
            lambda t: "{"
            + t[0]
            + (t[1] + "," + t[1]).join(
                k + t[2] + ":" + t[2] + v for k, v in t[3]
            )
            + t[4]
            + "}"
        ),
        # Leading/trailing whitespace around a nested value.
        st.tuples(
            ws, st.one_of(scalar, _stacked_structures()), ws
        ).map(lambda t: t[0] + t[1] + t[2]),
    )


strategy = st.one_of(
    _special_values(),
    _value.flatmap(_with_ws),
    # Arrays/objects wrapping special values, to exercise nesting + edge cases.
    st.tuples(
        st.sampled_from(["[", '{"k":']),
        _special_values(),
        st.sampled_from(["]", "}"]),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # Diversify accepted structures: wider mixes of scalars, arrays, objects,
    # and whitespace, to push beyond the saturated coverage.
    _broad_structures().flatmap(_with_ws),
    # Broadened exploration: more heterogeneous shapes, key/value variety,
    # and deeper mixed nesting to reach unsaturated regions.
    _diverse_structures().flatmap(_with_ws),
    # Broadened exploration: stacked depth/breadth structures, alternating
    # container kinds, ragged nesting, and whitespace permutations.
    _stacked_structures().flatmap(_with_ws),
    _whitespace_matrix().flatmap(_with_ws),
)
```