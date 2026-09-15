```python
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Primitive pieces
# ---------------------------------------------------------------------------

# Safe characters for string bodies (no quote, no backslash, no raw control).
safe_char = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in Python str
    blacklist_characters='"\\',
).filter(lambda c: ord(c) > 0x1F)

# Escape sequences allowed by the grammar.
simple_esc = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

hex_digit = st.sampled_from("0123456789abcdefABCDEF")


def _hex4():
    return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map("".join)


unicode_esc = _hex4().map(lambda h: "\\u" + h)

# A "raw" byte-ish char: include control chars and NUL, which the parser accepts.
raw_char = st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\')

string_body_piece = st.one_of(
    safe_char.map(str),
    raw_char.map(str),
    simple_esc,
    unicode_esc,
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
nonzero = st.integers(min_value=1, max_value=9).map(str)
int_part = st.one_of(st.just("0"), st.tuples(nonzero, digits).map("".join))

sign = st.sampled_from(["", "-"])

frac = st.one_of(
    st.tuples(st.just("."), digits).map("".join),
    st.just("."),  # trailing dot accepted by this parser
)

exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    digits,
).map("".join)

# Extreme magnitudes / exponents.
extreme_exp = st.sampled_from(
    ["e0", "e1", "e-1", "e308", "e309", "e-309", "e999", "e-999",
     "E+308", "E+309", "e+000", "e-000", "e1000000"]
)

extreme_number = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("0e0"),
    st.just("0.0e0"),
    st.builds(lambda i, e: i + e, int_part, extreme_exp),
    st.builds(lambda s, i, e: s + i + e, sign, int_part, extreme_exp),
)

number = st.one_of(
    st.builds(lambda s, i: s + i, sign, int_part),
    st.builds(lambda s, i, f: s + i + f, sign, int_part, frac),
    st.builds(lambda s, i, e: s + i + e, sign, int_part, exp),
    st.builds(lambda s, i, f, e: s + i + f + e, sign, int_part, frac, exp),
    extreme_number,
)

# ---------------------------------------------------------------------------
# Malformed / near-valid fragments (used as leaves and injections)
# ---------------------------------------------------------------------------

malformed = st.sampled_from([
    "", " ", ",", ",,", ":", "::", "{", "}", "[", "]", "{,}", "[,]",
    "{\"a\":}", "{:1}", "{\"a\" 1}", "[1,,2]", "[1 2]", "[\"a\" \"b\"]",
    "\"unterminated", "\"a\\", "\"\\u12\"", "\"\\uZZZZ\"", "\"\\x41\"",
    "'single'", "{'a':1}", "{a:1}", "+1", ".5", "-", "+", "01", "-01",
    "0x10", "0x", "1.", "1.e5", "NaN", "Infinity", "-Infinity", "nan",
    "tru", "truee", "falsee", "nul", "nullx", "1abc", "1 2",
])

# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

_json_value = st.deferred(lambda: json_value)

# A string token: quoted, with body pieces (may include NUL/control bytes).
string_token = st.one_of(
    st.lists(string_body_piece, max_size=8).map(lambda ps: '"' + "".join(ps) + '"'),
    malformed.filter(lambda s: s.startswith('"')),
)

# Object pair: key string + ':' + value.
pair = st.builds(
    lambda k, v: k + ":" + v,
    string_token,
    _json_value,
)

obj = st.one_of(
    st.just("{}"),
    st.lists(pair, min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}"),
)

arr = st.one_of(
    st.just("[]"),
    st.lists(_json_value, min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
)

leaf = st.one_of(
    string_token,
    number,
    st.sampled_from(["true", "false", "null"]),
)

json_value = st.one_of(
    leaf,
    obj,
    arr,
    malformed.filter(lambda s: not s.startswith('"')),
)

# Use st.recursive to give genuine recursive nesting structure.
recursive_value = st.recursive(
    leaf,
    lambda children: st.one_of(
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ",".join(vs) + "]"
        ),
        st.lists(
            st.builds(lambda k, v: k + ":" + v, string_token, children),
            min_size=1,
            max_size=4,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ),
    max_leaves=12,
)

# ---------------------------------------------------------------------------
# Depth-targeted generators (near the 1000-level limit)
# ---------------------------------------------------------------------------

def _nested_array(depth: int) -> str:
    return "[" * depth + "0" + "]" * depth


def _nested_object(depth: int) -> str:
    return '{"a":' * depth + "0" + "}" * depth


depth_near_limit = st.integers(min_value=900, max_value=1010).map(_nested_array)
depth_obj_near_limit = st.integers(min_value=900, max_value=1010).map(_nested_object)

# ---------------------------------------------------------------------------
# Edge-case explicit values
# ---------------------------------------------------------------------------

edge_cases = st.sampled_from([
    "{}",
    "[]",
    "{\"a\":1,\"a\":2}",
    "{\"a\":1,\"a\":2,\"a\":3}",
    "1e309",
    "-1e309",
    "1e-309",
    "\"\\ud800\"",
    "\"\\udc00\"",
    "\"\\ud800\\udc00\"",
    "\"\\u0000\"",
    "\"\\u0000x\"",
    "\"a\\u0000b\"",
    "\"\\uD83D\\uDE00\"",
    "\"\x00\"",
    "\"\t\n\r\"",
    "\"\x00\x01\x1f\"",
    "\xef\xbb\xbf{}",
    "\xef\xbb\xbf1",
    "1\x00",
    "\"a\"\x00",
    "{\"a\":1}{",
    "[1,2,3,]",
    "{\"a\":1,}",
    "{\"a\":}",
    "{:1}",
    "[,,]",
    "[\"a\",,]",
    "1e",
    "1e+",
    "1e-",
    "-",
    "+1",
    ".5",
    "01",
    "0x10",
    "1.",
    "NaN",
    "Infinity",
    "\"unterminated",
    "\"bad\\x escape\"",
    "\"\\u12g4\"",
    "",
    "   ",
    "\n",
    "\x00",
    "true",
    "false",
    "null",
    "true false",
    "1 2 3",
    "1abc",
    "{} trailing",
    "[] []",
])

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    recursive_value,
    edge_cases,
    depth_near_limit,
    depth_obj_near_limit,
    json_value,
).map(str)
```