Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic leaf generators
# ---------------------------------------------------------------------------

# SAFECODEPOINT: ~ ["\\\u0000-\u001F]  (no raw control chars, no quote, no backslash)
_safe_chars = (
    st.characters(
        blacklist_categories=("Cc", "Cs"),
        blacklist_characters='\\"',
    )
    .filter(lambda c: c not in ('\x00',))
)

# Escape sequences allowed by the grammar: \" \\ \/ \b \f \n \r \t \uXXXX
_simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex = st.sampled_from('0123456789abcdefABCDEF')

_unicode_escape = st.tuples(*([_hex] * 4)).map(lambda t: "\\u" + "".join(t))

# Surrogate-style escapes explicitly
_surrogate_escapes = st.sampled_from(
    ["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uD83D", "\\uDE00",
     "\\u0000", "\\u001F", "\\u007F", "\\uFFFF"]
)

_escape = st.one_of(_simple_escapes, _unicode_escape, _surrogate_escapes)

# String body: mix of safe chars and escapes
_string_body = st.one_of(_safe_chars, _escape)

# A JSON string literal
json_string = st.lists(_string_body, max_size=20).map(lambda cs: '"' + "".join(cs) + '"')

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

# Grammar NUMBER: '-'? INT ('.' [0-9]+)? EXP?
# INT: '0' | [1-9][0-9]*
_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.integers(min_value=1, max_value=9),
              st.lists(st.integers(min_value=0, max_value=9), max_size=15))
      .map(lambda t: str(t[0]) + "".join(str(d) for d in t[1])),
)

_frac_part = st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=15).map(
    lambda ds: "." + "".join(str(d) for d in ds)
)

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + "".join(str(d) for d in t[2]))

# Extreme magnitudes / exponents
_extreme_numbers = st.sampled_from([
    "1e309", "-1e309", "1e-309", "1e1000", "-1e1000",
    "1E309", "1.7976931348623157e308", "1.7976931348623159e308",
    "5e-324", "4.9e-324", "2.2250738585072014e-308",
    "1e2147483647", "1e-2147483647", "0e0", "0e999",
    "-0", "-0.0", "0.0", "0",
    "123456789012345678901234567890",
    "-123456789012345678901234567890",
])

json_number = st.one_of(
    _extreme_numbers,
    st.tuples(
        st.booleans(),  # negative?
        _int_part,
        st.one_of(st.none(), _frac_part),
        st.one_of(st.none(), _exp_part),
    ).map(lambda t: ("-" if t[0] else "") + t[1] + (t[2] or "") + (t[3] or "")),
)

# ---------------------------------------------------------------------------
# Malformed / near-valid fragments
# ---------------------------------------------------------------------------

_malformed_tokens = st.sampled_from([
    # numbers
    "+1", ".5", "1.", "01", "007", "-", "-.", "-.5", "1e", "1e+", "1e-",
    "0x1", "1_000", "Infinity", "-Infinity", "NaN", "1e309",
    # literals
    "True", "FALSE", "nul", "None", "undefined",
    # structural
    "{", "}", "[", "]", ",", ":", "{}", "[]", "{,}", "[,]",
    '{"a":}', '{"a" "b"}', '{"a"::1}', '[1,,2]', '[1 2]',
    '{"a":1,}', '[1,2,]', '{"a":1 "b":2}', '[,]',
    # strings
    '"unterminated', "'single'", '"bad\\x"', '"\\u12"', '"\\uZZZZ"',
    '"\\"', '"\\\\"', '""',
    # trailing content
    "1abc", "1 garbage", "[]xyz", "nullnull", "truefalse",
])

# ---------------------------------------------------------------------------
# Recursive JSON value strategy
# ---------------------------------------------------------------------------

# We build the recursive strategy with st.recursive over a bounded depth.
# Nesting depth target: concentrate near ~2048 where the parser rejects.

_MAX_DEPTH = 2048


def _depth_bias():
    """Integer depth that concentrates near the parser limit."""
    return st.one_of(
        st.integers(min_value=0, max_value=8),
        st.integers(min_value=16, max_value=64),
        st.integers(min_value=256, max_value=1024),
        st.integers(min_value=1500, max_value=_MAX_DEPTH),
        st.integers(min_value=_MAX_DEPTH - 8, max_value=_MAX_DEPTH + 8),
        st.just(_MAX_DEPTH),
    )


# Leaf values (non-recursive)
_leaf = st.one_of(
    json_string,
    json_number,
    st.sampled_from(["true", "false", "null"]),
    _malformed_tokens,
)

# Whitespace
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])


@st.composite
def _json_value(draw, max_leaves=6):
    # Choose whether to produce a leaf or a container.
    kind = draw(st.sampled_from(["leaf", "leaf", "leaf", "obj", "arr"]))
    if kind == "leaf":
        return draw(_leaf)

    if kind == "obj":
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return draw(st.sampled_from(["{}", "{ }", "{\n}", "{\t}"]))
        pairs = []
        for _ in range(n):
            k = draw(json_string)
            v = draw(_json_value(max_leaves=max_leaves))
            pairs.append(k + ":" + v)
        inner = draw(st.sampled_from([",", ", ", ",\n", " , "])).join(pairs)
        return "{" + inner + "}"

    # arr
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return draw(st.sampled_from(["[]", "[ ]", "[\n]", "[\t]"]))
    elems = [draw(_json_value(max_leaves=max_leaves)) for _ in range(n)]
    inner = draw(st.sampled_from([",", ", ", ",\n", " , "])).join(elems)
    return "[" + inner + "]"


# Base recursive strategy
_recursive_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        # obj
        st.tuples(
            st.lists(
                st.tuples(json_string, children),
                min_size=1,
                max_size=4,
            )
        ).map(lambda t: "{" + ",".join(k + ":" + v for k, v in t[0]) + "}"),
        st.just("{}"),
        # arr
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.just("[]"),
    ),
    max_leaves=40,
)


def _deep_nesting():
    """Generate deeply nested arrays/objects near the parser limit."""
    depth = _depth_bias()
    opener = st.sampled_from(["[", "{\"a\":"])
    return st.tuples(depth, opener, _leaf).map(
        lambda t: _build_deep(t[0], t[1], t[2])
    )


def _build_deep(depth, opener, leaf):
    # Cap actual construction to avoid huge strings; use compact nesting.
    depth = min(depth, _MAX_DEPTH + 16)
    if opener == "[":
        return "[" * depth + leaf + "]" * depth
    else:
        return "{\"a\":" * depth + leaf + "}" * depth


# Near-valid malformed full inputs
_near_valid = st.sampled_from([
    # double commas
    '[1,,2]', '{"a":1,, "b":2}', '{,}', '[,]', '[1,2,,]',
    # missing colons
    '{"a" 1}', '{"a" "b"}', '{"a"}', '{"a":1 "b":2}',
    # unterminated strings
    '"abc', '{"a":"abc}', '[ "abc ]',
    # leading + / .5 / 01
    '+1', '.5', '01', '007', '-01', '+.5',
    # trailing commas
    '[1,2,]', '{"a":1,}',
    # lone dash
    '-', '-.', '-e1',
    # trailing content
    '1abc', '1 garbage', '[]xyz', '{}extra', 'null null',
    # non-finite
    '1e309', '-1e309', '1e1000',
    # duplicate keys
    '{"k":0,"k":1}', '{"a":1,"a":2,"a":3}',
    # empty / whitespace
    '', ' ', '\n', '\t\r\n',
    # surrogate escapes
    '"\\uD800"', '"\\uDC00"', '"\\uD800\\uDC00"',
    # embedded NUL escape (six chars, fine)
    '"\\u0000"', '"a\\u0000b"',
    # control escapes
    '"\\u001F"', '"\\u007F"',
])


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    # Well-formed recursive values
    _recursive_value,
    # Composite JSON values with varied whitespace
    _json_value(),
    # Deep nesting near the limit
    _deep_nesting(),
    # Near-valid malformed inputs
    _near_valid,
    # Bare leaves
    _leaf,
    # Numbers with surrounding whitespace
    st.tuples(_ws, json_number, _ws).map(lambda t: t[0] + t[1] + t[2]),
    # Strings with surrounding whitespace
    st.tuples(_ws, json_string, _ws).map(lambda t: t[0] + t[1] + t[2]),
    # Trailing content after a complete value
    st.tuples(_json_value(), st.sampled_from(["garbage", "xyz", "1abc", " ", "\n", "null"]))
      .map(lambda t: t[0] + t[1]),
    # Duplicate keys explicitly
    st.tuples(json_string, _leaf, _leaf).map(
        lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
    ),
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 163,
    "reject": 187
  },
  "acceptance_rate": 0.466,
  "max_nesting_depth": 2048,
  "productions_accepted": [
    "NUMBER",
    "STRING",
    "arr",
    "false",
    "json",
    "null",
    "obj",
    "pair",
    "true",
    "value"
  ],
  "productions_gap": [],
  "cap_distance_mass": 0.025,
  "novelty": 20,
  "divergences": 125,
  "divergence_examples": [
    "b'{\"\":\"\",\"\":\"\"}'",
    "b'{\"\\xc2\\xad\\\\f\\\\u0000\\\\f\\\\f\":null,\"\\xc2\\xad\\\\f\\\\u0000\\\\f\\\\f\":\"\"}'",
    "b'{\"\\\\\"\":\"\",\"\\\\\"\":\"\"}'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **revert_last_edit** — score 62.8 < best 70.5.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.