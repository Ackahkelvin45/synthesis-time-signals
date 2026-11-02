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

# Structured "near-valid" mutations: take a valid value and inject a single
# grammar-breaking defect at the top level so the parser's error-recovery
# branches get exercised (branch coverage).
@st.composite
def _mutated_valid(draw):
    body = draw(_value_strategy)
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind == 0:
        return body + ","
    if kind == 1:
        return body + "}"
    if kind == 2:
        return body + "]"
    if kind == 3:
        return "[" + body
    if kind == 4:
        return "{" + body
    if kind == 5:
        return body + " " + draw(_trailing_junk)
    return body + draw(_malformed_fragments)

# ---------------------------------------------------------------------------
# Grammar-aware nested mutations: inject a single defect *inside* a container
# so the parser's inner error-recovery branches (not just top-level) get
# exercised. This targets branch coverage inside array/object parsing.
# ---------------------------------------------------------------------------

_inner_defects = st.sampled_from(
    [
        ",",       # double comma
        ":",       # stray colon
        "}",       # stray close brace
        "]",       # stray close bracket
        "{",       # stray open brace
        "[",       # stray open bracket
        " ",       # whitespace only
        "\x00",    # NUL
        '"',       # unterminated quote
        "\\",      # lone backslash
        "1e",      # truncated number
        "01",      # leading zero
        "-",       # lone minus
        "tru",     # truncated literal
        "nul",     # truncated literal
        "fals",    # truncated literal
        "NaN",
        "Infinity",
    ]
)


@st.composite
def _nested_mutation(draw):
    # Build a shallow container with a few slots, then replace one slot with
    # a defect so the parser must recover mid-stream.
    n = draw(st.integers(min_value=1, max_value=4))
    items = [draw(_scalar) for _ in range(n)]
    idx = draw(st.integers(min_value=0, max_value=n - 1))
    items[idx] = draw(_inner_defects)
    if draw(st.booleans()):
        # array form
        sep = draw(st.sampled_from([",", ", ", " ,"]))
        return "[" + sep.join(items) + "]"
    # object form: pair each item with a key
    pairs = []
    for i, it in enumerate(items):
        key = draw(_strings)
        pairs.append(key + ":" + it)
    sep = draw(st.sampled_from([",", ", ", " ,"]))
    return "{" + sep.join(pairs) + "}"


# ---------------------------------------------------------------------------
# NEW: multi-defect and deeper-structure mutations to push branch coverage
# past the current 75% by exercising error-recovery paths that only trigger
# on combinations of defects (e.g. missing value + missing comma, or a
# defect nested inside a container inside a container).
# ---------------------------------------------------------------------------

@st.composite
def _multi_defect(draw):
    # Inject 2-3 independent defects across an array/object's slots.
    n = draw(st.integers(min_value=2, max_value=5))
    items = [draw(_scalar) for _ in range(n)]
    k = draw(st.integers(min_value=2, max_value=min(3, n)))
    for _ in range(k):
        idx = draw(st.integers(min_value=0, max_value=n - 1))
        items[idx] = draw(_inner_defects)
    if draw(st.booleans()):
        sep = draw(st.sampled_from([",", ", ", " ,", ",,"]))
        return "[" + sep.join(items) + "]"
    pairs = []
    for it in items:
        key = draw(_strings)
        pairs.append(key + ":" + it)
    sep = draw(st.sampled_from([",", ", ", " ,", ",,"]))
    return "{" + sep.join(pairs) + "}"


@st.composite
def _deep_nested_defect(draw):
    # Wrap a nested mutation inside one or two more containers so the parser
    # must recover at multiple nesting depths.
    inner = draw(_nested_mutation())
    depth = draw(st.integers(min_value=1, max_value=3))
    for _ in range(depth):
        if draw(st.booleans()):
            inner = "[" + inner + "]"
        else:
            inner = '{"k":' + inner + "}"
    return inner


# ---------------------------------------------------------------------------
# NEW: whitespace / comment / separator edge cases that often sit on
# distinct branches (tabs, CR, form feed, vertical tab, unusual spacing
# around ':' and ',').
# ---------------------------------------------------------------------------

_odd_ws = st.sampled_from(
    ["", " ", "\t", "\n", "\r", "\f", "\v", "\x00", "\u00a0", "\u2028", "\u2029"]
)


@st.composite
def _ws_heavy(draw):
    a = draw(_odd_ws)
    b = draw(_odd_ws)
    c = draw(_odd_ws)
    d = draw(_odd_ws)
    if draw(st.booleans()):
        return a + "[" + b + "1" + c + "," + d + "2" + a + "]"
    return (
        a
        + "{"
        + b
        + '"a"'
        + c
        + ":"
        + d
        + "1"
        + a
        + ","
        + b
        + '"b"'
        + c
        + ":"
        + d
        + "2"
        + a
        + "}"
    )


strategy = st.one_of(
    st.tuples(_bom, _valid_top, _trailing_junk).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.tuples(_bom, _malformed_top).map(lambda t: t[0] + t[1]),
    st.tuples(_bom, _mutated_valid()).map(lambda t: t[0] + t[1]),
    st.tuples(_bom, _nested_mutation()).map(lambda t: t[0] + t[1]),
    st.tuples(_bom, _multi_defect()).map(lambda t: t[0] + t[1]),
    st.tuples(_bom, _deep_nested_defect()).map(lambda t: t[0] + t[1]),
    st.tuples(_bom, _ws_heavy()).map(lambda t: t[0] + t[1]),
    st.lists(
        st.one_of(
            st.characters(min_codepoint=0, max_codepoint=0x10FFFF),
        ),
        min_size=0,
        max_size=40,
    ).map(lambda cs: "".join(cs)),
)
```