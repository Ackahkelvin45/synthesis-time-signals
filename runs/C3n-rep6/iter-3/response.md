```python
from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

unicode_escapes = st.one_of(
    hex4.map(lambda h: "\\u" + h),
    # surrogate pairs and lone surrogates
    hex4.map(lambda h: "\\u" + h),  # can be surrogate range
    st.tuples(
        st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DC00"]),
        hex4,
    ).map(lambda t: "\\u" + t[0] + "\\u" + t[1]),
)

# characters safe for JSON strings, including raw NUL/control bytes
control_chars = st.sampled_from(["\x00", "\x01", "\x1f", "\x0b", "\x0c", "\x7f"])
safe_ascii = st.characters(min_codepoint=0x20, max_codepoint=0x7e, blacklist_characters='"\\')
unicode_chars = st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF)
raw_chars = st.one_of(control_chars, safe_ascii, unicode_chars)

string_body = st.one_of(raw_chars, simple_escapes, unicode_escapes)

json_string = st.lists(string_body, min_size=0, max_size=8).map("".join).map(lambda s: '"' + s + '"')

# malformed strings (unterminated, bad escapes)
malformed_string = st.one_of(
    st.lists(raw_chars, min_size=0, max_size=5).map("".join).map(lambda s: '"' + s),
    st.just('"\\x"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('"'),
    st.just('"abc'),
)

# ---------- numbers ----------

digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
nonzero_digits = st.text(alphabet="0123456789", min_size=1, max_size=6).filter(
    lambda s: s[0] != "0"
)

int_part = st.one_of(st.just("0"), nonzero_digits, st.just("-0"), st.just("-"), st.just(""))

frac_part = st.one_of(
    st.just(""),
    digits.map(lambda d: "." + d),
    st.just("."),
)

exp_part = st.one_of(
    st.just(""),
    st.tuples(st.sampled_from(["e", "E"]), st.sampled_from(["", "+", "-"]), digits).map(
        lambda t: t[0] + t[1] + t[2]
    ),
)

valid_number = st.tuples(int_part, frac_part, exp_part).map(lambda t: t[0] + t[1] + t[2])

extreme_numbers = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e-309",
        "1e308",
        "1e999999",
        "0e0",
        "1E+308",
        "1E-308",
        "-0",
        "0",
        "123456789012345678901234567890",
        "1e1000000",
        "9" * 40,
    ]
)

malformed_number = st.sampled_from(
    ["+1", ".5", "1.", "01", "0x1F", "-.5", "1e", "1e+", "--1", "1..2", "00", "+", "e5"]
)

number = st.one_of(valid_number, extreme_numbers, malformed_number)

# ---------- literals ----------

literal = st.sampled_from(["true", "false", "null", "True", "NULL", "nul", "tru"])

# ---------- recursive structure ----------

# key: prefer strings, sometimes duplicates come for free via random choice
key = json_string

# We build values recursively. Bias toward objects with members.
def _obj_from_pairs(pairs):
    return "{" + ",".join(pairs) + "}"

def _obj_trailing(pairs):
    return "{" + ",".join(pairs) + ",}"

def _arr_from_items(items):
    return "[" + ",".join(items) + "]"

def _arr_trailing(items):
    return "[" + ",".join(items) + ",]"

pair_strategy = st.tuples(key, st.deferred(lambda: value)).map(lambda t: t[0] + ":" + t[1])

def obj_strategy():
    return st.one_of(
        st.just("{}"),
        # objects with members, sometimes duplicate keys, sometimes trailing comma
        st.lists(pair_strategy, min_size=1, max_size=5).map(_obj_from_pairs),
        st.lists(pair_strategy, min_size=1, max_size=5).map(_obj_trailing),
        # duplicate keys explicitly
        st.tuples(key, st.deferred(lambda: value), st.deferred(lambda: value)).map(
            lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
        ),
        # malformed
        st.just("{,}"),
        st.just("{a:1}"),
        st.just('{"a" 1}'),
        st.just('{"a":}'),
        st.just('{"a":1,,}'),
        st.just('{"a":1'),
        st.just("{"),
    )

def arr_strategy():
    return st.one_of(
        st.just("[]"),
        st.lists(st.deferred(lambda: value), min_size=1, max_size=5).map(_arr_from_items),
        st.lists(st.deferred(lambda: value), min_size=1, max_size=5).map(_arr_trailing),
        # malformed
        st.just("[,]"),
        st.just("[1,,2]"),
        st.just("[,1]"),
        st.just("[1,2"),
        st.just("["),
    )

value = st.recursive(
    st.one_of(json_string, number, literal, malformed_string, st.just(""), st.just("-")),
    lambda children: st.one_of(
        obj_strategy(),
        arr_strategy(),
        # deep nesting bias
        children.map(lambda v: "[" + v + "]"),
        children.map(lambda v: '{"k":' + v + "}"),
    ),
    max_leaves=40,
)

# top-level: a value, sometimes with trailing garbage / whitespace / NUL
trailing_garbage = st.sampled_from(["", " ", "\n", "\t", "\x00", "x", "garbage", "[]", "1", "true false", "//comment"])

top = st.tuples(value, trailing_garbage).map(lambda t: t[0] + t[1])

# occasionally generate a bare deep nesting to stress the first-pass measurement
def deep_obj(n):
    return '{"a":' * n + "1" + "}" * n

def deep_arr(n):
    return "[" * n + "]" * n

deep = st.one_of(
    st.integers(min_value=1, max_value=200).map(deep_obj),
    st.integers(min_value=1, max_value=500).map(deep_arr),
)

# ---------- intensify_near_crash: mutate structurally around the crashing input ----------
# The crashing input is a deeply nested JSON array (e.g. "[[[...]]]") that overflows
# the parser's recursion/stack. We mutate structurally around that shape: vary the
# nesting depth in a tight band around typical crash depths, vary the innermost
# leaf, and vary the closing/bracket structure to explore near-crash boundaries.

# Depth is sampled from a distribution that concentrates mass right around the
# observed crash boundary, while still occasionally probing deeper/shallower.
crash_depth = st.one_of(
    st.integers(min_value=50, max_value=600),
    st.integers(min_value=200, max_value=400),
    st.integers(min_value=250, max_value=350),
    st.integers(min_value=280, max_value=320),
    st.integers(min_value=300, max_value=300),
)

crash_leaf = st.one_of(
    st.just(""),
    st.just("1"),
    st.just("null"),
    st.just("true"),
    st.just('"x"'),
    st.just("[]"),
    st.just("{}"),
)

# pure nested arrays around a leaf
near_crash_arr = st.tuples(crash_depth, crash_leaf).map(
    lambda t: "[" * t[0] + t[1] + "]" * t[0]
)

# nested arrays with a slightly mismatched closer (one bracket short / extra)
near_crash_arr_unbalanced = st.tuples(
    crash_depth, crash_leaf, st.integers(min_value=-3, max_value=3)
).map(
    lambda t: "[" * t[0] + t[1] + "]" * max(0, t[0] + t[2])
)

# nested objects around a leaf
near_crash_obj = st.tuples(crash_depth, crash_leaf).map(
    lambda t: '{"a":' * t[0] + t[1] + "}" * t[0]
)

# alternating array/object nesting around a leaf
near_crash_mixed = st.tuples(crash_depth, crash_leaf).map(
    lambda t: ('[{"a":' * (t[0] // 2)) + t[1] + ('}]' * (t[0] // 2))
)

# deeply nested arrays with trailing garbage / NUL / partial close
near_crash_trailing = st.tuples(crash_depth, crash_leaf, trailing_garbage).map(
    lambda t: "[" * t[0] + t[1] + "]" * t[0] + t[2]
)

# deeply nested arrays with a comma and one more element near the crash depth
near_crash_comma = st.tuples(crash_depth, crash_leaf).map(
    lambda t: "[" * t[0] + t[1] + "," + t[1] + "]" * t[0]
)

# nested arrays with an interleaved comma-separated sibling at every level,
# stressing the parser's per-level element loop near the crash depth
near_crash_sibling = st.tuples(crash_depth, crash_leaf).map(
    lambda t: "".join("[" + t[1] + "," for _ in range(t[0])) + t[1] + "]" * t[0]
)

# nested arrays with an unterminated innermost level (missing one closer),
# exercising the parser's error/cleanup path at depth
near_crash_unterminated = st.tuples(crash_depth, crash_leaf).map(
    lambda t: "[" * t[0] + t[1]
)

# nested arrays with whitespace/NUL injected between brackets at depth
near_crash_ws = st.tuples(
    crash_depth, crash_leaf, st.sampled_from(["", " ", "\n", "\t", "\x00"])
).map(
    lambda t: t[2].join("[" for _ in range(t[0])) + t[1] + "]" * t[0]
)

# nested arrays with a deep object leaf at the bottom
near_crash_deep_leaf = st.tuples(crash_depth, crash_depth).map(
    lambda t: "[" * t[0] + '{"a":' * t[1] + "1" + "}" * t[1] + "]" * t[0]
)

intensify_near_crash = st.one_of(
    near_crash_arr,
    near_crash_arr_unbalanced,
    near_crash_obj,
    near_crash_mixed,
    near_crash_trailing,
    near_crash_comma,
    near_crash_sibling,
    near_crash_unterminated,
    near_crash_ws,
    near_crash_deep_leaf,
)

strategy = st.one_of(top, deep, intensify_near_crash)
```