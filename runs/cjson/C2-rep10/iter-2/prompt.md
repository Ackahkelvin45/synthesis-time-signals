Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

# SAFECODEPOINT: everything except " \ and control chars 0x00-0x1F
_safe_char = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in raw text
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

# raw control / NUL bytes allowed by the parser inside strings (deviation)
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x0b", "\x0c", "\x7f"]
)

_escape_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# \uXXXX escapes: include lone surrogates (parser rejects) and paired surrogates
_u_escape = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet=_hex, min_size=4, max_size=4),
)

_high_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF).map(
    lambda n: "\\u%04x" % n
)
_low_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF).map(
    lambda n: "\\u%04x" % n
)
_surrogate_pair = st.tuples(_high_surrogate, _low_surrogate).map(lambda t: t[0] + t[1])
_lone_surrogate = st.one_of(_high_surrogate, _low_surrogate)

_string_body = st.one_of(
    _safe_char,
    _raw_control,
    _escape_simple,
    _u_escape,
    _surrogate_pair,
    _lone_surrogate,
)

_string = st.lists(_string_body, max_size=12).map(lambda cs: '"' + "".join(cs) + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text(alphabet="123456789", min_size=1, max_size=1).flatmap(
    lambda first: st.tuples(
        st.just(first), st.text(alphabet="0123456789", min_size=0, max_size=6)
    ).map(lambda t: t[0] + t[1])
)

_int_part = st.one_of(
    st.just("0"),
    _nonzero_digits,
    # leading zeros: accepted by parser, rejected by strict
    st.text(alphabet="0123456789", min_size=2, max_size=5).filter(
        lambda s: s[0] == "0"
    ),
)

_frac = st.one_of(
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
    st.just("."),  # trailing dot, accepted by parser
)

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    _digits,
).map(lambda t: t[0] + t[1] + t[2])

# extreme exponents / magnitudes
_extreme_exp = st.sampled_from(
    [
        "e309", "E309", "e-309", "e999", "e-999", "e2147483647",
        "e-2147483648", "e308", "e400", "E+400", "e-400",
        "e0000000000000000001", "e999999999999999999999",
    ]
)

_hex_number = st.tuples(
    st.sampled_from(["0x", "0X", "-0x", "-0X"]),
    st.text(alphabet=_hex, min_size=1, max_size=8),
).map(lambda t: t[0] + t[1])

_sign = st.sampled_from(["", "-"])

_plain_number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.none(), _frac),
    st.one_of(st.none(), _exp),
).map(
    lambda t: t[0]
    + t[1]
    + (t[2] if t[2] is not None else "")
    + (t[3] if t[3] is not None else "")
)

_magnitude_number = st.tuples(
    st.one_of(st.just("1"), st.just("0"), _digits),
    _extreme_exp,
).map(lambda t: t[0] + t[1])

# malformed numbers the parser rejects
_malformed_number = st.sampled_from(
    ["-", "+1", ".5", "-.5", "01", "0x", "1e", "1e+", "--1", "1..2", "+", "."]
)

_number = st.one_of(
    _plain_number,
    _magnitude_number,
    _hex_number,
    _malformed_number,
)

# ---------- malformed string fragments ----------

_unterminated_string = st.lists(_string_body, max_size=8).map(
    lambda cs: '"' + "".join(cs)
)

_malformed_string = st.one_of(
    _unterminated_string,
    st.just("'single'"),
    st.just('"bad\\x"'),
    st.just('"\\u12"'),
    st.just('"unclosed'),
)

# ---------- malformed structural fragments ----------

_malformed_frag = st.sampled_from(
    [
        "{,}",
        "[,]",
        "{,}",
        "[1,]",
        '{"a":1,}',
        "[1 2]",
        '{"a" 1}',
        "{a:1}",
        "{'a':1}",
        "[",
        "]",
        "{",
        "}",
        '{"a":}',
        "[,]",
        "{:1}",
        "[1,,2]",
        '{"a":1 "b":2}',
    ]
)

# ---------- recursive value ----------

_json_value = st.deferred(lambda: _value)

# leaf values
_leaf = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# pair: STRING ':' value
_pair = st.tuples(_string, _json_value).map(lambda t: t[0] + ":" + t[1])

_obj = st.one_of(
    st.just("{}"),
    st.lists(_pair, min_size=1, max_size=5).map(lambda ps: "{" + ",".join(ps) + "}"),
)

_arr = st.one_of(
    st.just("[]"),
    st.lists(_json_value, min_size=1, max_size=5).map(
        lambda vs: "[" + ",".join(vs) + "]"
    ),
)

# base for recursion: leaves + malformed fragments (as "values")
_base_value = st.one_of(_leaf, _malformed_string, _malformed_frag, _malformed_number)

_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        st.lists(children, min_size=1, max_size=5).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(
            st.tuples(_string, children).map(lambda t: t[0] + ":" + t[1]),
            min_size=1,
            max_size=5,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ),
)

# ---------- deep nesting near the 1000-level limit ----------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth


_depth_choice = st.one_of(
    st.integers(min_value=0, max_value=5),
    st.integers(min_value=990, max_value=1010),
    st.integers(min_value=999, max_value=1002),
    st.sampled_from([999, 1000, 1001, 1002, 500, 950, 1000]),
)


@st.composite
def _deeply_nested(draw):
    depth = draw(_depth_choice)
    kind = draw(st.sampled_from(["arr", "obj", "mixed"]))
    inner = draw(st.one_of(_leaf, st.just("1"), st.just('"x"'), st.just("null")))
    if kind == "arr":
        return _deep(depth, "[", "]", inner)
    if kind == "obj":
        return _deep(depth, '{"k":', "}", inner)
    # mixed
    out = inner
    for i in range(depth):
        if i % 2 == 0:
            out = "[" + out + "]"
        else:
            out = '{"k":' + out + "}"
    return out


# ---------- duplicate keys ----------

@st.composite
def _dup_keys(draw):
    n = draw(st.integers(min_value=2, max_value=8))
    key = draw(_string)
    vals = draw(st.lists(_leaf, min_size=n, max_size=n))
    pairs = [key + ":" + v for v in vals]
    return "{" + ",".join(pairs) + "}"


# ---------- BOM, trailing content, NUL placement ----------

_bom = st.just("\ufeff")

_trailing = st.sampled_from(
    ["", "1abc", " \n\t", "\x00", " 1 2", "xyz", "]", "}", ",", "null"]
)


@st.composite
def _with_bom_and_trailing(draw):
    bom = draw(st.one_of(st.just(""), _bom))
    v = draw(_value)
    tr = draw(_trailing)
    return bom + v + tr


# ---------- top-level strategy ----------

strategy = st.one_of(
    _value,
    _deeply_nested(),
    _dup_keys(),
    _with_bom_and_trailing(),
    # ensure some pure edge cases appear
    st.sampled_from(
        [
            "{}",
            "[]",
            "1e309",
            "1e-309",
            "0x10",
            "01",
            "1.",
            "\ufeff{}",
            "\x00",
            '"\\ud800"',
            '"\\udc00"',
            '"\\ud83d\\ude00"',
            '"a\x00b"',
            '"a\tb"',
            "NaN",
            "Infinity",
            "-",
            "+1",
            ".5",
            "[1,]",
            '{"a":1,}',
            "[1 2]",
            '{"a" 1}',
        ]
    ),
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 60,
    "reject": 290
  },
  "acceptance_rate": 0.171,
  "max_nesting_depth": 1010,
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
  "cap_distance_mass": 0.0,
  "novelty": 19,
  "divergences": 55,
  "divergence_examples": [
    "b'{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"k\":[{\"'",
    "b'\\xef\\xbb\\xbf\"\"'",
    "b'1.'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **generate_nesting_toward_cap** — target depth 700-950.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.