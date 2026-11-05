from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_ESCAPES = st.sampled_from([
    '\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
    '\\u0000', '\\u001f', '\\u0020', '\\u007f',
    '\\u00e9', '\\u20ac', '\\uffff',
    '\\ud800', '\\udc00', '\\ud83d\\ude00',
    '\\uD800', '\\uDC00',
    '\\u0000\\u0000',
    '\\u12', '\\uZZZZ',
])

_string_piece = st.one_of(_SAFE_CHARS.map(str), _ESCAPES)


def _quoted(inner):
    return inner.map(lambda s: '"' + s + '"')


_string_body = st.lists(_string_piece, max_size=8).map("".join)

_json_string = _quoted(_string_body)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _digits(min_size=1, max_size=12):
    return st.text("0123456789", min_size=min_size, max_size=max_size)


def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), _digits(0, 15)).map(lambda t: t[0] + t[1]),
    )


def _frac_part():
    return st.tuples(st.just("."), _digits(1, 12)).map(lambda t: t[0] + t[1])


def _exp_part():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits(1, 4),
    ).map(lambda t: t[0] + t[1] + t[2])


def _number_parts():
    return st.tuples(
        st.sampled_from(["", "-"]),
        _int_part(),
        st.one_of(st.just(""), _frac_part()),
        st.one_of(st.just(""), _exp_part()),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3])


_extreme_numbers = st.sampled_from([
    "0", "-0", "1", "-1",
    "1e308", "1e309", "-1e309", "1e-308", "1e-999", "1e999",
    "1.7976931348623157e308", "1.7976931348623159e308",
    "5e-324", "4.9e-324", "2.2250738585072014e-308",
    "123456789012345678901234567890",
    "-123456789012345678901234567890",
    "0.000000000000000000000000000001",
    "1E+308", "1E-308", "1e0000000000000000001",
    "9007199254740993",
])

_number = st.one_of(_number_parts(), _extreme_numbers)


# ---------------------------------------------------------------------------
# Malformed / near-valid fragments
# ---------------------------------------------------------------------------

_malformed = st.sampled_from([
    "+1", "+1.5", ".5", "-.5", "01", "007", "-01", "1.", "-", "-.",
    "1e", "1e+", "1e-", "1.e5", "0x10", "Infinity", "-Infinity", "NaN",
    '"abc', '"abc\\', '"\\u12"', '"\\uZZZZ"', '"\\x41"',
    "{", "}", "[", "]", ",", ":", "{}extra", "[]extra",
    "{,}", "[,]", "[1,]", "[,1]", '{"a":}', '{"a" 1}', '{"a":1,}',
    '{"a":1 "b":2}', '{"a":1,,}', '[1,,2]', '[,]',
    "", " ", "\t\n",
    "tru", "fals", "nul", "truex", "nullx",
    "1abc", "1 garbage", "[]xyz", "{}xyz", 'true!', 'null?',
])

# ---------------------------------------------------------------------------
# Recursive JSON value strategy
# ---------------------------------------------------------------------------

_leaves = st.one_of(
    _json_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
    _malformed,
)

_key = _json_string

_ws = st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "])


def _join(parts):
    return "".join(parts)


@st.composite
def _object(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=6))
    if n == 0:
        return "{" + draw(_ws) + "}"
    pairs = []
    duplicate = draw(st.booleans())
    forced_key = draw(_key)
    for i in range(n):
        if duplicate and i >= 1 and draw(st.booleans()):
            key = forced_key
        else:
            key = draw(_key)
        val = draw(value_strategy)
        pairs.append(key + draw(_ws) + ":" + draw(_ws) + val)
    sep = "," + draw(_ws)
    return "{" + draw(_ws) + sep.join(pairs) + draw(_ws) + "}"


@st.composite
def _array(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=6))
    if n == 0:
        return "[" + draw(_ws) + "]"
    items = [draw(value_strategy) for _ in range(n)]
    sep = "," + draw(_ws)
    return "[" + draw(_ws) + sep.join(items) + draw(_ws) + "]"


def _value_strategy():
    return st.recursive(
        _leaves,
        lambda children: st.one_of(
            _object(children),
            _array(children),
        ),
        max_leaves=40,
    )


_json_value = _value_strategy()

# ---------------------------------------------------------------------------
# Deep nesting near the parser's 2048 limit
# ---------------------------------------------------------------------------

def _deep_nesting():
    depth = st.one_of(
        st.integers(min_value=1, max_value=64),
        st.integers(min_value=2000, max_value=2050),
        st.integers(min_value=2040, max_value=2060),
        st.sampled_from([2047, 2048, 2049, 2050, 4096]),
    )
    kind = st.sampled_from(["arr", "obj"])

    @st.composite
    def build(draw):
        d = draw(depth)
        k = draw(kind)
        if k == "arr":
            return "[" * d + "]" * d
        return '{"a":' * d + "null" + "}" * d

    return build()


# ---------------------------------------------------------------------------
# Top-level composition
# ---------------------------------------------------------------------------

@st.composite
def _top_level(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice <= 4:
        text = draw(_json_value)
    elif choice == 5:
        text = draw(_deep_nesting())
    elif choice == 6:
        text = draw(_malformed)
    elif choice == 7:
        text = draw(_json_value) + draw(st.sampled_from(
            ["garbage", " 1 2 3", "xyz", "!", "//c", "/*x*/", "\n\n"]
        ))
    elif choice == 8:
        text = draw(st.sampled_from([
            "{}", "[]", "[[[]]]", '{"a":{}}', '{"a":[]}',
            '{"":""}', '{"a":"\\u0000"}', '["\\ud800"]',
            '[1e309]', '{"k":1,"k":2}',
        ]))
    else:
        text = draw(_json_value) + draw(_malformed)

    return text.replace("\x00", "")


strategy = _top_level()