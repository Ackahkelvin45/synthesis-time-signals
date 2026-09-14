from hypothesis import strategies as st
import json

# ---------- primitives ----------

_json_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escapes = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    _hex, _hex, _hex, _hex,
)

# surrogate pairs and lone surrogates
_surrogate_escapes = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD800\\uDC00",  # valid pair
    "\\uD83D\\uDE00",  # valid pair
    "\\u0000",         # NUL escape (six chars, fine)
    "\\u001f", "\\u007f", "\\uFFFD",
])

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) > 0x1F)

_string_body = st.one_of(
    st.text(_safe_chars, max_size=8),
    st.lists(
        st.one_of(
            st.text(_safe_chars, max_size=4),
            _simple_escapes,
            _unicode_escapes,
            _surrogate_escapes,
        ),
        max_size=6,
    ).map("".join),
)

# occasionally malformed string (unterminated, stray backslash, etc.)
_malformed_string = st.sampled_from([
    '"', '"abc', '"abc\\', '"\\u12', '"\\uZZZZ"', '"\\x"',
    '"\\uD800"', '"a\nb"', '"\\', '""extra',
])

json_string = st.one_of(
    _string_body.map(lambda s: '"' + s + '"'),
    _malformed_string,
)


# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d: d, st.text("123456789", min_size=1, max_size=1).flatmap(
        lambda first: st.tuples(st.just(first), _digits).map(lambda t: t[0] + t[1])
    )),
)

_frac = st.builds(lambda d: "." + d, _digits)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    _digits,
)

_normal_number = st.builds(
    lambda sign, ip, fr, ex: sign + ip + fr + ex,
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-309", "1e999999", "-1e999999",
    "0e0", "1E+308", "1e-308", "9" * 30, "-" + "9" * 30,
    "1e" + "9" * 20, "0." + "0" * 20 + "1",
    "1e2147483648", "-1e2147483647",
])

_malformed_number = st.sampled_from([
    "+1", ".5", "1.", "01", "00", "-", "-.", "1..2",
    "1e", "1e+", "--1", "1.e5", "0x1", "1_000",
])

json_number = st.one_of(_normal_number, _extreme_number, _malformed_number)


# ---------- recursive structures ----------

_json_simple_value = st.one_of(
    json_string,
    json_number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_key = st.one_of(
    _string_body.map(lambda s: '"' + s + '"'),
    st.sampled_from(['"a"', '"b"', '"key"', '"k"', '"dup"', '""']),
)


def _pair(value_strategy):
    return st.builds(
        lambda k, v: k + ":" + v,
        _key,
        value_strategy,
    )


# malformed object pieces
_bad_obj = st.sampled_from([
    "{}", "{,}", '{"a":}', '{"a" 1}', '{"a":1,}', '{"a":1,,}',
    '{a:1}', '{"a":1', '{"a":1}}', '{:1}', '{"a":1 "b":2}',
    '{"a":1,"a":2}',  # duplicate keys
    '{"a":1, "a":2, "a":3}',
])

_bad_arr = st.sampled_from([
    "[]", "[,]", "[1,]", "[1,,2]", "[1 2]", "[1", "[1]]", "[,1]",
])


def _make_json(depth):
    # depth controls how much recursion budget remains
    value = st.deferred(lambda: _value_strategy(depth))
    pair = _pair(value)
    obj = st.one_of(
        st.just("{}"),
        st.builds(
            lambda parts: "{" + ",".join(parts) + "}",
            st.lists(pair, min_size=1, max_size=4),
        ),
        _bad_obj,
    )
    arr = st.one_of(
        st.just("[]"),
        st.builds(
            lambda parts: "[" + ",".join(parts) + "]",
            st.lists(value, min_size=1, max_size=4),
        ),
        _bad_arr,
    )
    return st.one_of(_json_simple_value, obj, arr)


def _value_strategy(depth):
    if depth <= 0:
        return _json_simple_value
    return st.one_of(
        _json_simple_value,
        _make_json(depth - 1),
    )


# depth-limited recursive value (concentrate near 2048 but bounded for safety)
_deep_value = st.recursive(
    _json_simple_value,
    lambda children: st.one_of(
        st.builds(
            lambda parts: "[" + ",".join(parts) + "]",
            st.lists(children, min_size=1, max_size=3),
        ),
        st.builds(
            lambda parts: "{" + ",".join(parts) + "}",
            st.lists(
                st.builds(lambda k, v: k + ":" + v, _key, children),
                min_size=1,
                max_size=3,
            ),
        ),
    ),
    max_leaves=50,
)


# ---------- explicit deep nesting generators ----------

@st.composite
def _deep_nesting(draw):
    # target depth near 2048 cap (rejected beyond, accepted below)
    depth = draw(st.one_of(
        st.integers(min_value=0, max_value=16),
        st.integers(min_value=2040, max_value=2060),
        st.integers(min_value=1000, max_value=2050),
    ))
    open_c = draw(st.sampled_from(["[", "{"]))
    if open_c == "[":
        close_c = "]"
        inner = draw(st.one_of(st.just("0"), st.just('"x"'), st.just("null")))
    else:
        close_c = "}"
        inner = draw(st.one_of(
            st.just('"k":0'),
            st.just('"k":{"k":1}'),
            st.just('"a":1,"b":2'),
        ))
    return open_c * depth + inner + close_c * depth


# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    "", " ", "\t", "\n",
    "{", "}", "[", "]", ",", ":", '"',
    "tru", "fals", "nul", "TRUE", "Null",
    '"unterminated', "'single'", "\\",
    "1abc", "1 garbage", "[]xyz", "{}trailing", "nullnull",
    "[]", "{}", "0", "-", "-.",
    '{"a":1,"a":1}', '{"x":[1,2,3],"x":[]}',
    "[1,2,3,]", '{"a":1,}',
    '\u0000',  # raw NUL - will be skipped by harness, but harmless here
])

# strip raw NUL from final outputs
def _no_raw_nul(s):
    return s.replace("\x00", "")


# ---------- combine ----------

_base_value = st.one_of(
    json_string,
    json_number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_recursive_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        st.builds(
            lambda parts: "[" + ",".join(parts) + "]",
            st.lists(children, min_size=1, max_size=4),
        ),
        st.builds(
            lambda parts: "{" + ",".join(parts) + "}",
            st.lists(
                st.builds(lambda k, v: k + ":" + v, _key, children),
                min_size=1,
                max_size=4,
            ),
        ),
    ),
    max_leaves=30,
)

_full = st.one_of(
    _recursive_value,
    _deep_value,
    _deep_nesting(),
    _malformed,
    st.builds(
        lambda v, tail: v + tail,
        _recursive_value,
        st.sampled_from(["", " ", "garbage", "xyz", "\n", "[]extra"]),
    ),
)

strategy = _full.map(_no_raw_nul)