from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

# Strings that exercise escapes, unicode, control chars (no raw NUL), etc.
_escapes = st.sampled_from([
    '\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
    '\\u0000', '\\u001F', '\\u007F', '\\u00e9', '\\u20ac',
    '\\uD800', '\\uDC00', '\\uD83D\\uDE00', '\\uFFFF', '\\uABCD',
    '\\u0000\\u0000', '\\uD834\\uDD1E',
])

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) > 0x1F or c in "\t\n\r")

# A "string body" piece: either a safe char or an escape sequence
_str_piece = st.one_of(_safe_chars, _escapes)

_string_body = st.lists(_str_piece, min_size=0, max_size=12).map("".join)

_json_string = _string_body.map(lambda s: '"' + s + '"')


# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=400).map(str),
    ).map("".join),
    # extreme exponents including overflow
    st.sampled_from(["e309", "E309", "e-309", "e999", "e-999",
                     "e+308", "e-308", "e1000", "e-1000"]),
)

_number = st.tuples(_int_part, _frac, _exp).map("".join)

# malformed-ish numbers (leading +, .5, 1., 01, lone -)
_bad_number = st.sampled_from([
    "+1", "+0", "+1.5", ".5", "-.5", "1.", "01", "007", "-", "-.",
    "1e", "1e+", "1E-", "--1", "1..2", "0x1", "1_000", "Infinity", "NaN",
])


# ---------- recursive values ----------

_leaf = st.one_of(
    _json_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
)

# depth near the parser cap (2048). Concentrate interesting depth near limit.
_deep_depth = st.one_of(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=2000, max_value=2048),
    st.integers(min_value=2049, max_value=2100),
)


def _wrap(value_strategy, depth):
    """Wrap a value in `depth` nested arrays (or objects)."""
    def build(s):
        return "[" * depth + s + "]" * depth
    return st.tuples(value_strategy, st.just(depth)).map(lambda t: build(t[0]))


# We'll use st.recursive for obj/arr productions.
def _obj_like(children):
    # children: strategy producing value strings
    pair = st.tuples(_json_string, children).map(lambda t: t[0] + ":" + t[1])
    pairs = st.lists(pair, min_size=0, max_size=5).map(lambda ps: ",".join(ps))
    return pairs.map(lambda body: "{" + body + "}")


def _arr_like(children):
    elems = st.lists(children, min_size=0, max_size=5).map(lambda es: ",".join(es))
    return elems.map(lambda body: "[" + body + "]")


def _make_value():
    return st.recursive(
        _leaf,
        lambda children: st.one_of(_obj_like(children), _arr_like(children)),
        max_leaves=40,
    )


_value = _make_value()


# Deep-but-legal nesting near the cap, wrapping a simple value.
_deep = st.builds(
    lambda d, inner: "[" * d + inner + "]" * d,
    _deep_depth,
    st.one_of(_leaf, st.just("{}"), st.just("[]")),
)

_deep_obj = st.builds(
    lambda d, inner: '{"k":' * d + inner + "}" * d,
    _deep_depth,
    st.one_of(_leaf, st.just("null")),
)


# ---------- malformed near-valid inputs ----------

_malformed = st.sampled_from([
    # double commas / trailing commas
    "[1,,2]", "[1,2,]", "[,]", "{,}", '{"a":1,,"b":2}', '{"a":1,}',
    # missing colons
    '{"a" 1}', '{"a" 1, "b":2}', '{"a"}', '{"a":}',
    # unterminated strings
    '"abc', '{"a":"b', '["x', '"\\', '"\\u12',
    # unterminated containers
    '[', '{', '[1,2', '{"a":1',
    # stray tokens
    ']', '}', ':', ',', '[,]', '{:}',
    # leading + / .5 / 01 style numbers in context
    '[+1]', '[.5]', '[1.]', '[01]', '[-]', '[-.]', '[+0]',
    # trailing content (accepted by target)
    '1abc', '1 garbage', '[]xyz', '{}extra', 'nullnull', 'truefalse',
    '1 2 3', '"a""b"', '[1] [2]',
    # duplicate keys (target rejects)
    '{"k":0,"k":1}', '{"a":1,"a":2,"b":3}', '{"x":{"y":1},"x":2}',
    # non-finite (target rejects)
    '1e309', '-1e309', '1e9999', '[1e309]', '{"a":1e309}',
    # control chars in strings (escaped)
    '"\\u0000"', '"a\\u0000b"', '"\\u001F"',
    # surrogate escapes
    '"\\uD800"', '"\\uDC00"', '"\\uD83D\\uDE00"', '"\\uD834\\uDD1E"',
    # whitespace variants
    '  {  "a"  :  1  }  ', '\t[\n1,\r2]\n', ' { } ', ' [ ] ',
    # empty
    '{}', '[]', '', ' ', '\n',
    # keys that are not strings (exercises key-parsing branches)
    '{1:2}', '{true:1}', '{null:0}', '{[]:1}', '{{}:1}', '{:1}',
    # unexpected value tokens in arrays/objects (exercises value dispatch)
    '[true,]', '{,}', '[:]', '[null null]', '{"a"::1}', '{"a":,}',
    # bare tokens / partial keywords (keyword-matching branches)
    't', 'tr', 'tru', 'truex', 'f', 'fa', 'fals', 'falsey',
    'n', 'nu', 'nul', 'nullx', 'TRUE', 'False', 'NULL',
    # unterminated escapes/keywords at EOF
    '"\\u', '"\\uD8', '"\\uD800', 'tru', 'fals', 'nul',
    # numbers with partial exponent/frac at EOF
    '1e', '1e+', '1e-', '1.', '-', '-0.', '0e', '0e+',
    # nested malformed
    '[[1,],2]', '{"a":{"b":}}', '[{"a":1},]', '{"a":[1,2,]}',
    # extra closing brackets
    ']', ']]', '}', '}}', '[1]]', '{"a":1}}',
    # deep-ish malformed
    '[[[[', '{"a":{"a":', '[1,[2,[3,',
])


# ---------- top-level combination ----------

_valid = st.one_of(
    _value,
    _deep,
    _deep_obj,
    st.sampled_from(["{}", "[]", "true", "false", "null", "0", "-0",
                     '""', '{"":""}', '[[],{}]', '[{},[]]']),
)

strategy = st.one_of(_valid, _malformed).map(lambda s: s if isinstance(s, str) else str(s))