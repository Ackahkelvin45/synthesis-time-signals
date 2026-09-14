Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Leaf strategies
# ---------------------------------------------------------------------------

# Safe JSON string characters (no quote, no backslash, no control chars).
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

# Raw control / NUL bytes that the parser must handle faithfully.
_control_char = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\x7f"]
)

# Escape sequences valid inside a JSON string.
_esc_char = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_unicode_esc = _hex4.map(lambda h: "\\u" + h)

# Surrogate escapes are explicitly requested.
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udfff", "\\ud83d", "\\ude00", "\\ud83d\\ude00", "\\uD800", "\\uDFFF"]
)

_string_body_piece = st.one_of(
    _safe_char.map(str),
    _esc_char,
    _unicode_esc,
    _surrogate_esc,
    _control_char,  # raw control bytes inside strings
)

_string_body = st.lists(_string_body_piece, max_size=12).map("".join)

# A valid JSON string literal.
json_string = _string_body.map(lambda b: '"' + b + '"')

# Unterminated / malformed string variants.
unterminated_string = _string_body.map(lambda b: '"' + b)
bad_string = st.sampled_from(
    ['"', '"abc', '"\\', '"\\u', '"\\u12', '"\\x41"', '"unterminated\\']
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=20)

# Canonical ints (no leading zeros unless single 0).
_canon_int = st.one_of(
    st.just("0"),
    st.builds(
        lambda d, rest: d + rest,
        st.sampled_from("123456789"),
        st.text(alphabet="0123456789", max_size=18),
    ),
)

# Leading-zero ints (invalid per grammar but interesting).
_leading_zero_int = st.builds(
    lambda z, rest: z + rest,
    st.sampled_from("123456789"),
    st.text(alphabet="0123456789", min_size=1, max_size=18),
)

# Extreme magnitudes / exponents.
_extreme_number = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1E999",
        "-1E999",
        "1e+308",
        "1e-999",
        "9" * 40,
        "-" + "9" * 40,
        "0.00000000000000000001",
        "1" + "0" * 300,
        "1e308",
        "1e-308",
        "1.7976931348623157e309",
        "1.7976931348623157e-309",
        "0e0",
        "0E-0",
        "0.0e0",
        "-0",
        "-0.0",
        "-0e0",
        "1e01",
        "1E+00",
    ]
)

_frac = st.builds(
    lambda a, b: a + "." + b,
    _canon_int,
    st.text(alphabet="0123456789", min_size=1, max_size=10),
)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
)

_decimal_number = st.one_of(
    _canon_int,
    _frac,
    st.builds(lambda m, e: m + e, _canon_int, _exp),
    st.builds(lambda m, e: m + e, _frac, _exp),
)

# Malformed numbers the parser is known to reject / accept interestingly.
_bad_number = st.sampled_from(
    [
        "-",
        "+1",
        ".5",
        "1.",
        "01",
        "00",
        "0x1F",
        "1e",
        "1e+",
        "1e-",
        "--1",
        "1..2",
        "1.2.3",
        "+.5",
        "-.5",
        "1e309",
        "1e999999999999999999999",
    ]
)

number = st.one_of(
    _decimal_number,
    _extreme_number,
    _bad_number,
    _leading_zero_int,
)

# ---------------------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------------------

# Whitespace sometimes sprinkled in to exercise the WS-skipping path.
_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])
_ws_opt = st.one_of(st.just(""), _ws)

# Non-recursive leaves.
_leaf = st.one_of(
    json_string,
    number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    bad_string,
)

# A "key" is a JSON string; sometimes duplicate-friendly, sometimes weird.
_key = st.one_of(json_string, bad_string)

# pair: STRING ':' value  (value filled in via recursive composition below).
# We build pairs as (key, value) tuples and join later, never joining tuples
# directly with ",".join.

def _join_pair(kv):
    key, value = kv
    return key + ":" + value

def _join_obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _join_arr(values):
    return "[" + ",".join(values) + "]"

# We use st.recursive with a composite-style builder.
# The base is a leaf; the extension builds objects/arrays from already-built
# value strings.

def _extend(children):
    # children is a strategy producing value strings.
    # Build a pair (key, value) then map to joined string.
    pair = st.tuples(_key, children).map(_join_pair)

    # Object with at least one member (bias toward members), plus empty obj.
    obj_members = st.lists(pair, min_size=1, max_size=6).map(_join_obj)
    obj_empty = st.just("{}")
    obj = st.one_of(obj_members, obj_empty)

    # Sometimes a trailing comma (accepted once).
    obj_trailing = st.lists(pair, min_size=1, max_size=6).map(
        lambda ps: "{" + ",".join(ps) + ",}"
    )

    # Duplicate keys: repeat a single key with different values.
    dup_obj = st.builds(
        lambda k, vals: "{" + ",".join(k + ":" + v for v in vals) + "}",
        _key,
        st.lists(children, min_size=2, max_size=5),
    )

    # Array with members or empty.
    arr_members = st.lists(children, min_size=1, max_size=6).map(_join_arr)
    arr_empty = st.just("[]")
    arr = st.one_of(arr_members, arr_empty)

    # Array with trailing comma.
    arr_trailing = st.lists(children, min_size=1, max_size=6).map(
        lambda vs: "[" + ",".join(vs) + ",]"
    )

    # Malformed variants: double commas, missing colons, missing commas.
    malformed_obj = st.one_of(
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + ",,".join(ps) + "}"
        ),
        st.lists(pair, min_size=1, max_size=4).map(
            lambda ps: "{" + " ".join(ps) + "}"
        ),
        st.tuples(_key, children).map(lambda kv: "{" + kv[0] + kv[1] + "}"),
        st.tuples(_key, children).map(lambda kv: "{" + kv[0] + ":" + kv[1]),
    )

    malformed_arr = st.one_of(
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ",,".join(vs) + "]"
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + " ".join(vs) + "]"
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs)
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: ",".join(vs) + "]"
        ),
    )

    return st.one_of(
        obj,
        obj_trailing,
        dup_obj,
        arr,
        arr_trailing,
        malformed_obj,
        malformed_arr,
    )


_value = st.recursive(_leaf, _extend, max_leaves=30)

# ---------------------------------------------------------------------------
# Top-level: json := value EOF
# ---------------------------------------------------------------------------

# Deep nesting: build a chain of '[' ... ']' and '{...}' around a value.
def _deep_nesting(depth, inner):
    # depth is an int; wrap inner with '[' * depth + inner + ']' * depth
    return "[" * depth + inner + "]" * depth

_deep = st.builds(
    _deep_nesting,
    st.integers(min_value=0, max_value=200),
    st.one_of(_leaf, st.just("")),
)

# Deep object nesting (stresses first-pass memory measurement).
def _deep_obj(depth, leaf):
    return "{" + '"k":' * depth + leaf + "}" * depth

_deep_obj_strat = st.builds(
    _deep_obj,
    st.integers(min_value=0, max_value=100),
    st.one_of(_leaf, st.just("1")),
)

# Trailing content after a complete value (should be rejected, still useful).
_trailing_garbage = st.builds(
    lambda v, g: v + g,
    _value,
    st.sampled_from(["abc", "xyz", " garbage", "false", "1", "]", "}", "\x00"]),
)

# Lone NUL / control bytes at top level.
_raw_bytes = st.lists(
    st.one_of(
        _control_char,
        st.sampled_from(["{", "}", "[", "]", ",", ":", '"', "\\", " ", "1", "a"]),
    ),
    max_size=20,
).map("".join)

# Whitespace-wrapped values.
_ws_wrapped = st.builds(
    lambda pre, v, post: pre + v + post,
    _ws_opt,
    _value,
    _ws_opt,
)

strategy = st.one_of(
    _value,
    _ws_wrapped,
    _deep,
    _deep_obj_strat,
    _trailing_garbage,
    _raw_bytes,
    st.just(""),
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("true"),
    st.just("false"),
    st.just("-"),
    st.just("1e309"),
    st.just('{"a":1,"a":2}'),
    st.just("[1,2,]"),
    st.just('{"a":1,}'),
    st.just('[1,,2]'),
    st.just('{"a"1}'),
    st.just('{"a":}'),
    st.just('"unterminated'),
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 51.27,
  "region_coverage_pct": 51.27
}

Make EXACTLY ONE change to the strategy: **intensify_near_crash** — mutate structurally around the crashing input.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.