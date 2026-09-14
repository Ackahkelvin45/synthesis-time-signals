```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Safe code points: printable-ish chars excluding " \ and control chars.
_safe = st.characters(
    blacklist_categories=("Cs", "Cc"),
    blacklist_characters='"\\',
)
# Allow some control chars via escapes only (we encode them as \uXXXX below).
_esc_short = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])


def _u_escape():
    hexd = "0123456789abcdefABCDEF"
    return st.text(alphabet=hexd, min_size=4, max_size=4).map(lambda h: "\\u" + h)


# Surrogate / high-plane escapes
_surrogate = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD83D", "\\uDE00",
    "\\uD83D\\uDE00",  # valid pair
    "\\uD800\\uD800",  # lone high + lone high
    "\\uDC00\\uDC00",  # lone lows
    "\\u0000",         # escaped NUL (allowed; raw NUL forbidden)
    "\\u001F", "\\u007F", "\\uFFFD", "\\u0041",
])

# Control chars encoded as escapes (raw control bytes inside strings are
# technically allowed by SAFECODEPOINT except \u0000-\u001F... so we escape
# them to stay in the grammar and avoid raw control bytes in output).
_escaped_control = st.integers(min_value=0x00, max_value=0x1F).map(
    lambda n: "\\u%04X" % n
)

_string_piece = st.one_of(
    _safe,
    _esc_short,
    _u_escape(),
    _surrogate,
    _escaped_control,
)

_string_body = st.lists(_string_piece, min_size=0, max_size=12).map("".join)

# A well-formed JSON string literal.
string_lit = _string_body.map(lambda s: '"' + s + '"')

# ---------- numbers ----------
_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map(lambda t: t[0] + t[1]),
    _digits,
)

_frac = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        _digits,
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_sign = st.one_of(st.just(""), st.just("-"))

number = st.tuples(_sign, _int_part, _frac, _exp).map(lambda t: "".join(t))

# Extreme numeric magnitudes / exponents (including overflow like 1e309)
_extreme_number = st.one_of(
    st.sampled_from([
        "1e309", "-1e309", "1e308", "1e-309", "1e9999", "-1e9999",
        "1E+400", "1e-400", "0e0", "0e999", "-0", "-0.0", "0.0",
        "1" + "0" * 308, "1" + "0" * 309,
        "1." + "0" * 5, "." + "5",
        "1e01", "1e000001", "-1e-0001",
        "123456789012345678901234567890",
        "0.000000000000000000001",
    ]),
)

# Malformed / lenient numbers (parser is a superset here)
_malformed_number = st.sampled_from([
    "-", "-.", "+1", "+", ".5", "1.", "01", "00", "007",
    "1e", "1e+", "1e-", "--1", "- 1", "1..2", "1.2.3",
    "0x10", "1_000", " 1", "1 ", "Infinity", "NaN", "inf", "nan",
    "1e309", "-1e309",
])

number_lit = st.one_of(number, _extreme_number, _malformed_number)

# ---------- structural pieces ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", " \n\t "])

# Malformed string literals (unterminated, bad escapes, raw control char)
_malformed_string = st.one_of(
    st.just('"'),
    st.just('"abc'),
    st.just('"abc\\'),
    st.just('"\\x"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just('"unterminated'),
    st.just('"'),
)

# ---------- recursive value / obj / arr ----------

# Leaf values (non-recursive)
_leaf = st.one_of(
    string_lit,
    number_lit,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _malformed_string,
)

# Depth control: concentrate near MAX_NESTING = 2048.
# We build depth via explicit repetition on a "deep" branch, not via recursive
# depth (recursive depth is bounded by Hypothesis recursion limits anyway).
_depth_near_cap = st.integers(min_value=1, max_value=2048)

def _deep_arr(n):
    return "[" * n + "]" * n

def _deep_obj(n):
    return '{"a":' * n + "null" + "}" * n

_deep = st.one_of(
    _depth_near_cap.map(_deep_arr),
    _depth_near_cap.map(_deep_obj),
    st.integers(min_value=2000, max_value=2060).map(_deep_arr),
    st.integers(min_value=2000, max_value=2060).map(_deep_obj),
)


def _pair(key, value):
    return key + ":" + value


# Malformed pairs / separators
_bad_pair_sep = st.sampled_from([
    ":", "::", "", " : ", ": :",
])

_bad_comma = st.sampled_from([",", ",,", " , ", ", "])

value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        # arrays
        st.lists(children, min_size=0, max_size=4).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[" + ", ".join(xs) + ",]"
        ),
        # objects
        st.lists(
            st.tuples(string_lit, children).map(lambda t: t[0] + ":" + t[1]),
            min_size=0, max_size=4,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
        st.lists(
            st.tuples(string_lit, children).map(lambda t: t[0] + ":" + t[1]),
            min_size=1, max_size=3,
        ).map(lambda ps: "{" + ",".join(ps) + ",}"),
    ),
    max_leaves=20,
)

# ---------- malformed / near-valid structural variants ----------

_malformed_structural = st.one_of(
    # double commas
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just("[,1]"),
    st.just("[1,]"),
    st.just('{"a":1,,"b":2}'),
    st.just('{,}'),
    # missing colons
    st.just('{"a" 1}'),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just('{:1}'),
    # unterminated
    st.just("[1,2"),
    st.just('{"a":1'),
    st.just("[["),
    st.just('{"a":'),
    # trailing content (parser ACCEPTS)
    st.just("1abc"),
    st.just("1 garbage"),
    st.just("[]xyz"),
    st.just("{} trailing"),
    st.just("null null null"),
    st.just("truex"),
    st.just('"s" more'),
    # mismatched brackets
    st.just("[}"),
    st.just("{]"),
    st.just("[1}"),
    st.just('{"a":1]'),
    # empty / whitespace
    st.just(""),
    st.just("   "),
    st.just("\n\t\r"),
    # duplicate keys (parser REJECTS)
    st.just('{"k":0,"k":1}'),
    st.just('{"a":1,"a":2,"a":3}'),
    st.just('{"x":{"y":1},"x":2}'),
    # lone sign (parser ACCEPTS as 0)
    st.just("-"),
    st.just("-."),
    # top-level scalars
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("0"),
)


# ---------- top-level value with surrounding whitespace ----------
def _wrap(v):
    return v


value_ws = st.tuples(_ws, value, _ws).map(lambda t: t[0] + t[1] + t[2])

# ---------- final strategy ----------

strategy = st.one_of(
    value_ws,
    _malformed_structural,
    _deep,
    # explicit empty containers and edge scalars
    st.sampled_from([
        "{}", "[]", "[[[]]]", "{\"\":{}}",
        '{"a":[]}', '[[],{}]', '[{}]',
        "0", "-0", "1", "-1",
        '"\\u0000"', '"\\uD83D\\uDE00"',
        '"\\uD800"', '"\\uDFFF"',
    ]),
)
```