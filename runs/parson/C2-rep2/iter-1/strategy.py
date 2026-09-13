from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)


# ---------- string literals ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.tuples(st.just("\\u"), _hex, _hex, _hex, _hex).map(_join)

_simple_escape = st.sampled_from(list('"\\/bfnrt')).map(lambda c: "\\" + c)

_esc = st.one_of(_simple_escape, _unicode_escape)

# SAFECODEPOINT: ~ ["\\\u0000-\u001F]  -- no raw NUL, no control chars, no quote/backslash
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

_string_body = st.lists(st.one_of(_safe_char, _esc), max_size=12).map(_join)

# A well-formed JSON string literal.
valid_string = st.tuples(st.just('"'), _string_body, st.just('"')).map(_join)

# Strings that carry interesting escapes explicitly.
_interesting_strings = st.sampled_from([
    '""',
    '"\\u0000"',
    '"\\uD800"',
    '"\\uDC00"',
    '"\\uD834\\uDD1E"',
    '"\\uFFFF"',
    '"\\u00e9"',
    '"a\\u0000b"',
    '"\\n\\t\\r\\b\\f\\/\\\\\\""',
    '"' + "x" * 100 + '"',
])

string_lit = st.one_of(valid_string, _interesting_strings)

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)
_digits_many = st.text("0123456789", min_size=1, max_size=40)
_nonzero = st.text("123456789", min_size=1, max_size=1)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(_nonzero, st.text("0123456789", max_size=10)).map(_join),
    _digits,
)

_frac = st.tuples(st.just("."), _digits).map(_join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    _digits,
).map(_join)

_sign = st.one_of(st.just(""), st.just("-"))

number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
).map(_join)

# Extreme / edge numerics, including overflow and malformed forms.
_extreme_numbers = st.sampled_from([
    "0", "-0", "1", "-1",
    "1e309", "-1e309", "1e-309", "1e999999999",
    "1e+308", "1.7976931348623157e308", "5e-324",
    "0.0", "-0.0", "1.0",
    "123456789012345678901234567890",
    "-123456789012345678901234567890",
    "1E01", "1e01", "1e+01",
    "01", "-01", ".5", "-.5", "1.", "+1", "-", "-.", "+",
    "1e", "1e+", "1.2.3", "0x10", "Infinity", "-Infinity", "NaN",
    "1e3090", "9" * 40,
])

number_lit = st.one_of(number, _extreme_numbers)

# ---------- structural keywords ----------

_keyword = st.sampled_from(["true", "false", "null"])

# ---------- recursive value / obj / arr ----------

_json_text = st.deferred(lambda: value)

# obj key: prefer valid strings; occasionally duplicate-prone keys.
_key_pool = st.one_of(
    string_lit,
    st.sampled_from(['"k"', '"a"', '"b"', '"x"', '"dup"', '"\\u0000"']),
)

_pair = st.tuples(_key_pool, st.just(":"), _json_text).map(_join)

_obj = st.one_of(
    st.just("{}"),
    st.tuples(
        st.just("{"),
        st.lists(_pair, min_size=1, max_size=6).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map(_join),
)

_arr = st.one_of(
    st.just("[]"),
    st.tuples(
        st.just("["),
        st.lists(_json_text, min_size=1, max_size=6).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(_join),
)

value = st.one_of(
    string_lit,
    number_lit,
    _keyword,
    _obj,
    _arr,
)

# ---------- malformed / near-valid variants ----------

_malformed = st.sampled_from([
    # double commas / trailing commas
    "[1,,2]", "[1,2,]", "{,}", '{"a":1,,}',
    '{"a":1,}', '{"a":1,"b":2,}',
    # missing colons
    '{"a" 1}', '{"a"}', '{a:1}', '{"a":}',
    # missing braces/brackets
    '{"a":1', '[1,2', '{', '[', '}', ']',
    # unterminated strings
    '"abc', '"abc\\', '"\\u12', '"\\uD800',
    # bad escapes
    '"\\x"', '"\\uZZZZ"', '"\\"',
    # bad numbers
    '01', '-01', '.5', '1.', '+1', '1e', '1e+', '1.2.3',
    # trailing content after valid value (parser accepts)
    '1abc', '1 garbage', '[]xyz', '{}extra', 'true false', 'nullx',
    # lone sign (parser accepts as 0)
    '-', '-.',
    # whitespace-only / empty
    '', ' ', '\t\n\r',
    # duplicate keys (parser rejects)
    '{"k":0,"k":1}', '{"a":1,"a":2,"a":3}',
    # non-finite (parser rejects)
    '1e309', '-1e309', '1e999999999',
    # control-ish content inside strings via escapes
    '"\\u0000"', '"a\\u0000b"',
    # surrogate escapes
    '"\\uD800"', '"\\uDC00"', '"\\uD834\\uDD1E"',
    # nested-ish malformed
    '{"a":[1,2,{"b":}]}',
    '[[[[', ']]]]',
    '{"a":1}}', '[[1]]]',
])

# ---------- whitespace ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

# ---------- depth control ----------
# Concentrate depth near the parser's MAX_NESTING = 2048.
# Use mostly shallow trees, with occasional deep-but-legal nesting near the limit.

_depth_choice = st.one_of(
    st.integers(min_value=0, max_value=3),          # shallow
    st.integers(min_value=4, max_value=64),         # moderate
    st.integers(min_value=2000, max_value=2047),    # near cap
    st.sampled_from([2048, 2049, 2050, 2100]),      # at / just past cap
)


def _wrap_depth(d, inner):
    # d levels of array nesting around inner
    return "[" * d + inner + "]" * d


_deep = st.tuples(_depth_choice, value).map(lambda t: _wrap_depth(t[0], t[1]))

_deep_obj = st.tuples(
    _depth_choice,
    st.sampled_from(['"k":0', '"a":1', '"x":null']),
).map(lambda t: '{"k":' * t[0] + t[1] + "}" * t[0])

# ---------- top-level assembly ----------

_composed = st.one_of(
    value,
    _deep,
    _deep_obj,
    _malformed,
)

# Occasionally add surrounding whitespace and/or trailing content.
_lead_ws = st.one_of(st.just(""), _ws)
_trail_ws = st.one_of(st.just(""), _ws)

_trailing_garbage = st.one_of(
    st.just(""),
    st.sampled_from(["abc", "garbage", "xyz", " 1", "[]", "{}", "//", "/* */"]),
)

strategy = st.tuples(_lead_ws, _composed, _trail_ws, _trailing_garbage).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
).filter(lambda s: "\x00" not in s)