Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters safe to place literally inside a JSON string (no quote, no
# backslash, no raw control bytes).  We deliberately allow a broad unicode
# range but exclude surrogate code points (which can't be encoded) and the
# raw NUL/control bytes.
_SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

# A handful of interesting escape sequences, including surrogates and NUL.
_ESCAPES = st.sampled_from([
    '\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
    '\\u0000', '\\u001f', '\\u0020', '\\u007f',
    '\\u00e9', '\\u20ac', '\\uffff',
    '\\ud800', '\\udc00', '\\ud83d\\ude00',  # lone + paired surrogates
    '\\uD800', '\\uDC00',
    '\\u0000\\u0000',
    '\\u12', '\\uZZZZ',  # malformed hex (for malformed variant)
])

_string_piece = st.one_of(_SAFE_CHARS.map(str), _ESCAPES)


def _quoted(inner):
    return inner.map(lambda s: '"' + s + '"')


# A well-formed JSON string body (contents only, no quotes).
_string_body = st.lists(_string_piece, max_size=8).map("".join)

# A well-formed JSON string (with quotes).
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


# Extreme magnitudes / exponents, including overflow and underflow.
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
# Malformed / near-valid fragments (used at the top level and inside values)
# ---------------------------------------------------------------------------

_malformed = st.sampled_from([
    # leading + / .5 / 01 style
    "+1", "+1.5", ".5", "-.5", "01", "007", "-01", "1.", "-", "-.",
    "1e", "1e+", "1e-", "1.e5", "0x10", "Infinity", "-Infinity", "NaN",
    # broken strings
    '"abc', '"abc\\', '"\\u12"', '"\\uZZZZ"', '"\\x41"',
    # structural
    "{", "}", "[", "]", ",", ":", "{}extra", "[]extra",
    "{,}", "[,]", "[1,]", "[,1]", '{"a":}', '{"a" 1}', '{"a":1,}',
    '{"a":1 "b":2}', '{"a":1,,}', '[1,,2]', '[,]',
    "", " ", "\t\n",
    "tru", "fals", "nul", "truex", "nullx",
    # trailing content (accepted by this parser)
    "1abc", "1 garbage", "[]xyz", "{}xyz", 'true!', 'null?',
])

# ---------------------------------------------------------------------------
# Recursive JSON value strategy
# ---------------------------------------------------------------------------

# Leaf values (non-recursive).
_leaves = st.one_of(
    _json_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
    _malformed,
)

# Keys: mostly well-formed strings; occasionally duplicates are created by
# the object strategy below by repeating a chosen key.
_key = _json_string

# Whitespace fragments (the grammar skips WS, so sprinkle a little).
_ws = st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "])


def _join(parts):
    return "".join(parts)


@st.composite
def _object(draw, value_strategy):
    n = draw(st.integers(min_value=0, max_value=6))
    if n == 0:
        return "{" + draw(_ws) + "}"
    pairs = []
    # Occasionally force a duplicate key to exercise the stricter path.
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
    # Depth is bounded; the recursive strategy handles nesting.  We keep the
    # per-level branching modest so total size stays reasonable while still
    # allowing deep nesting when the driver chooses to recurse.
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
    # Concentrate around the cap: depths near 2048 (both under and slightly
    # over, where the parser cleanly rejects).
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
        # nested single-key objects
        return '{"a":' * d + "null" + "}" * d

    return build()


# ---------------------------------------------------------------------------
# Top-level composition
# ---------------------------------------------------------------------------

@st.composite
def _top_level(draw):
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice <= 4:
        # Ordinary recursive JSON value.
        text = draw(_json_value)
    elif choice == 5:
        # Deep nesting near the cap.
        text = draw(_deep_nesting())
    elif choice == 6:
        # Malformed fragment alone.
        text = draw(_malformed)
    elif choice == 7:
        # Valid value followed by trailing content (accepted by this parser).
        text = draw(_json_value) + draw(st.sampled_from(
            ["garbage", " 1 2 3", "xyz", "!", "//c", "/*x*/", "\n\n"]
        ))
    elif choice == 8:
        # Empty containers and small edge shapes.
        text = draw(st.sampled_from([
            "{}", "[]", "[[[]]]", '{"a":{}}', '{"a":[]}',
            '{"":""}', '{"a":"\\u0000"}', '["\\ud800"]',
            '[1e309]', '{"k":1,"k":2}',
        ]))
    else:
        # Concatenation of a value with a malformed tail.
        text = draw(_json_value) + draw(_malformed)

    # Never emit a raw NUL byte: the harness would skip it.
    return text.replace("\x00", "")


strategy = _top_level()
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 76.9,
  "region_coverage_pct": 86.11
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.