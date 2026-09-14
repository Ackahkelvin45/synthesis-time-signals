```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic scalar productions
# ---------------------------------------------------------------------------

SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\",
)

# Escapes that appear inside JSON strings (the six-char \u0000 form is fine).
_escapes = st.sampled_from(
    [
        '\\"',
        "\\\\",
        "\\/",
        "\\b",
        "\\f",
        "\\n",
        "\\r",
        "\\t",
        "\\u0000",
        "\\u001f",
        "\\u007f",
        "\\u00e9",
        "\\u20ac",
        "\\ud800",
        "\\udfff",
        "\\ud83d\\ude00",
        "\\uD834\\uDD1E",
        "\\uFFFF",
        "\\u000a",
        "\\u000d",
    ]
)

_string_body = st.one_of(
    st.text(alphabet=SAFE_CHARS, min_size=0, max_size=12),
    st.lists(st.one_of(st.text(alphabet=SAFE_CHARS, max_size=6), _escapes), max_size=6).map(
        "".join
    ),
)

_json_string = _string_body.map(lambda s: '"' + s + '"')

# ---------------------------------------------------------------------------
# Numbers: normal, extreme, and malformed-ish (still grammar-shaped)
# ---------------------------------------------------------------------------

_plain_int = st.integers(min_value=0, max_value=10**18).map(str)

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.sampled_from(
        [
            "1",
            "9",
            "10",
            "12345678901234567890",
            "999999999999999999999999999999",
        ]
    ),
)

_frac = st.one_of(
    st.nothing(),
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n).zfill(1)),
    st.sampled_from([".0", ".5", ".000", ".999999999", "." + "9" * 40]),
)

_exp = st.one_of(
    st.nothing(),
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.sampled_from(
        [
            "e0",
            "E0",
            "e+0",
            "e-0",
            "e01",
            "e+308",
            "e-308",
            "e309",
            "e310",
            "e-400",
            "e+999",
            "E+99999999999999999999",
            "e-99999999999999999999",
        ]
    ),
)

_sign = st.one_of(st.nothing(), st.just("-"))

_json_number = st.builds(
    lambda s, i, f, e: s + i + f + e,
    _sign,
    _int_part,
    _frac,
    _exp,
)

# A few "lenient but grammar-adjacent" numeric forms the parser is known/expected
# to be permissive about. These are deliberately outside strict JSON NUMBER.
_weird_number = st.sampled_from(
    [
        "-",
        "-.",
        "-.0",
        ".5",
        "1.",
        "+1",
        "+0",
        "01",
        "00",
        "1e",
        "1e+",
        "1e-",
        "1.e5",
        "-01",
        "0x10",
        "Infinity",
        "-Infinity",
        "NaN",
    ]
)

number_value = st.one_of(_json_number, _weird_number)

# ---------------------------------------------------------------------------
# Recursive structure: obj / arr / value
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the parser's MAX_NESTING = 2048.
# st.recursive keeps things bounded; we also add explicit deep-nesting cases.
_base_value = st.one_of(
    _json_string,
    number_value,
    st.sampled_from(["true", "false", "null"]),
)

# Object keys: mix of ordinary, empty, duplicate-prone, and escape-laden keys.
_key = st.one_of(
    _json_string,
    st.sampled_from(
        [
            '""',
            '"k"',
            '"a"',
            '"\\u0000"',
            '"\\ud800"',
            '"\\n"',
            '"\\""',
            '"\\\\"',
        ]
    ),
)

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \n\t "])

_pair = st.builds(
    lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
    _key,
    _ws,
    _ws,
    _base_value,
)

# Malformed pair fragments: missing colon, empty key, bare tokens.
_bad_pair = st.sampled_from(
    [
        '"a" 1',
        '"a":',
        ':1',
        '""',
        '"a" "b"',
        '"a":,',
        '"a"::1',
        '1:2',
    ]
)


def _join(parts):
    return "".join(parts)


def _obj(inner):
    """Object built from inner value strategy."""
    pair = st.builds(
        lambda k, w1, w2, v: k + w1 + ":" + w2 + v,
        _key,
        _ws,
        _ws,
        inner,
    )
    member = st.one_of(pair, _bad_pair)
    members = st.lists(member, min_size=0, max_size=5).map(lambda xs: (",".join(xs)))
    return st.builds(
        lambda w1, body, w2: "{" + w1 + body + w2 + "}",
        _ws,
        members,
        _ws,
    )


def _arr(inner):
    elems = st.lists(inner, min_size=0, max_size=5).map(lambda xs: ",".join(xs))
    return st.builds(
        lambda w1, body, w2: "[" + w1 + body + w2 + "]",
        _ws,
        elems,
        _ws,
    )


# ---------------------------------------------------------------------------
# Deep nesting near the cap (2048). Builders that produce exactly-N-depth input.
# ---------------------------------------------------------------------------

def _deep_array(depth, leaf):
    return "[" * depth + leaf + "]" * depth


def _deep_object(depth, leaf):
    return '{"a":' * depth + leaf + "}" * depth


def _deep_mixed(depth, leaf):
    # Alternate array/object nesting.
    openers = []
    closers = []
    for i in range(depth):
        if i % 2 == 0:
            openers.append("[")
            closers.append("]")
        else:
            openers.append('{"a":')
            closers.append("}")
    return "".join(openers) + leaf + "".join(reversed(closers))


_depth = st.one_of(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=2000, max_value=2052),
    st.sampled_from([1, 2, 100, 1024, 2046, 2047, 2048, 2049, 2050, 4096, 100000]),
)

_deep_leaf = st.one_of(
    st.sampled_from(["0", "1", "null", "true", "false", '"x"', ""]),
)

deep_value = st.one_of(
    st.builds(_deep_array, _depth, _deep_leaf),
    st.builds(_deep_object, _depth, _deep_leaf),
    st.builds(_deep_mixed, _depth, _deep_leaf),
)

# ---------------------------------------------------------------------------
# Recursive value via st.recursive
# ---------------------------------------------------------------------------

_recursive_value = st.recursive(
    _base_value,
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=20,
)

value = st.one_of(_recursive_value, deep_value)

# ---------------------------------------------------------------------------
# Malformed / near-valid top-level inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        "",
        " ",
        "{",
        "}",
        "[",
        "]",
        "[,]",
        "[1,]",
        "[,1]",
        "[1,,2]",
        "{,}",
        '{"a":1,}',
        '{"a":1,,"b":2}',
        '{"a" 1}',
        '{"a":}',
        '{"a":1 "b":2}',
        '{"a":1,}',
        '"unterminated',
        '"unterminated\\',
        '"\\u12"',
        '"\\uZZZZ"',
        '"\\x41"',
        "'single'",
        "tru",
        "truE",
        "NULL",
        "nul",
        "undefined",
        "1abc",
        "[]xyz",
        "{}trailing",
        '{"a":1}garbage',
        "[1,2,3] extra",
        "/* comment */ 1",
        "// line\n1",
        "\x01",
        "\x1f",
        "\x7f",
        "\u00e9",
        "\u2028",
        "\ufeff{}",
        "{\"a\":1,\"a\":2}",
        '{"a":1,"a":1}',
        '{"a":1,"b":2,"a":3}',
        "1e309",
        "-1e309",
        "1e999999999",
        "[1e309]",
        '{"x":1e309}',
        "9007199254740993",
        "123456789012345678901234567890",
        "-",
        "-.",
        "+1",
        ".5",
        "01",
        "1.",
    ]
)

# ---------------------------------------------------------------------------
# Top-level strategy: complete values (with optional trailing junk / ws),
# deep nesting, and malformed inputs.
# ---------------------------------------------------------------------------

_trailing = st.one_of(
    st.nothing(),
    st.sampled_from(["", " ", "\n", "garbage", "abc", "]", "}", ",", "1", "null"]),
)

complete = st.builds(
    lambda w1, v, w2, t: w1 + v + w2 + t,
    _ws,
    value,
    _ws,
    _trailing,
)

strategy = st.one_of(
    complete,
    deep_value,
    _malformed,
    # Pure whitespace / empty-ish inputs.
    st.text(alphabet=" \t\n\r", max_size=8),
    # A couple of raw JSON dumps of Python objects for realistic seeds.
    st.one_of(
        st.integers(min_value=-10**6, max_value=10**6),
        st.floats(allow_nan=False, allow_infinity=False, width=64),
        st.booleans(),
        st.none(),
        st.text(alphabet=SAFE_CHARS, max_size=8),
        st.lists(st.integers(min_value=-100, max_value=100), max_size=5),
    ).map(lambda o: json.dumps(o, ensure_ascii=True)),
)
```