from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

# Numbers: valid per grammar, plus edge magnitudes/exponents and lenient forms.
_valid_numbers = st.one_of(
    st.just("0"),
    st.just("-0"),
    st.integers(min_value=-10**18, max_value=10**18).map(str),
    st.integers(min_value=-(2**63), max_value=2**63).map(str),
    st.builds(
        lambda i, f, e: i + "." + f + e,
        st.integers(min_value=0, max_value=10**6).map(str),
        st.integers(min_value=0, max_value=10**9).map(str),
        st.sampled_from(["", "e0", "e1", "e-1", "e+5", "E10", "e01", "e-07"]),
    ),
    st.sampled_from([
        "1e309", "-1e309", "1e308", "-1e308", "1e999999",
        "1e-999999", "1e-324", "5e-324", "1.7976931348623157e308",
        "1.7976931348623159e308", "0e0", "-0.0", "0.0", "123456789012345678901234567890",
        "1E+400", "1e+0000000000001", "2.2250738585072014e-308",
    ]),
    # lenient / malformed numeric forms (parser may accept some)
    st.sampled_from([
        "-", "-.", "+1", "+0", ".5", "-.5", "1.", "01", "-01", "00",
        "1.2.3", "1e", "1e+", "1e-", "--1", "1..2", "0x10", "1_000",
    ]),
)

# Strings: valid escapes, unicode escapes, surrogates, control chars, unterminated.
_plain_chars = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='"\x00',
    ),
    max_size=12,
)

_escapes = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u0001", "\\u001f", "\\u0020", "\\u007f",
    "\\uD800", "\\uDC00", "\\uDFFF", "\\uDBFF", "\\uFFFF", "\\uabcd", "\\uABCD",
    "\\u12", "\\uZZZZ", "\\x41", "\\u{1F600}", "\\",
])

_string_body = st.one_of(
    _plain_chars,
    st.lists(st.one_of(_plain_chars, _escapes), max_size=8).map("".join),
)

_valid_strings = st.builds(lambda b: '"' + b + '"', _string_body)

# Unterminated / malformed strings (still no raw NUL).
_malformed_strings = st.one_of(
    st.builds(lambda b: '"' + b, _string_body),
    st.sampled_from([
        '"', '"abc', '"a\\"', '"\\u12', '"line\nbreak"',
        '"\x01\x02"', '"\x1f"', '"unterminated\\',
    ]),
)

_constants = st.sampled_from(["true", "false", "null", "TRUE", "True", "nul", "tru"])

_leaf = st.one_of(
    _valid_strings,
    _malformed_strings,
    _valid_numbers,
    _constants,
)

# ---------- recursive structure ----------

# Depth concentrated near the parser cap (2048). We don't generate 2048-deep
# in the recursive strategy itself (too slow / stack heavy); instead we allow
# moderate recursion plus dedicated deep-nesting strings appended separately.

_json_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        # arrays
        st.builds(
            lambda xs: "[" + ",".join(xs) + "]",
            st.lists(children, max_size=5),
        ),
        # objects with unique-ish keys
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(
                    lambda k, v: k + ":" + v,
                    _valid_strings,
                    children,
                ),
                max_size=4,
            ),
        ),
    ),
    max_leaves=30,
)

# ---------- near-valid-but-malformed whole documents ----------

_malformed_docs = st.one_of(
    st.sampled_from([
        "[,]", "[1,,2]", "[1,]", "{,}", '{"a":1,}', '{"a":}', '{"a" 1}',
        '{"a":1 "b":2}', "{:", "[:]", "[1 2]", '{"a":1,,"b":2}',
        "[", "]", "{", "}", "[[]", "{{}}", "[}", "{]",
        "", " ", "\t\n\r", "abc", "1abc", "[]xyz", "{}extra",
        "-", "-.", "truefalse", "nullx",
    ]),
    st.builds(lambda v: v + st.sampled_from(["garbage", "1", "]", "}", "x"]).example(),
               _json_value) if False else st.builds(
        lambda v, t: v + t,
        _json_value,
        st.sampled_from(["", "garbage", "1", "]", "}", "x", "  trailing"]),
    ),
)

# ---------- deep nesting near the cap ----------

def _deep(depth, opener, closer, inner="0"):
    return opener * depth + inner + closer * depth

_deep_nesting = st.one_of(
    st.integers(min_value=1, max_value=64).map(
        lambda d: _deep(d, "[", "]")
    ),
    st.integers(min_value=1, max_value=64).map(
        lambda d: _deep(d, '{"k":', "}")
    ),
    # concentrated near the 2048 cap
    st.sampled_from([
        _deep(2047, "[", "]"),
        _deep(2048, "[", "]"),
        _deep(2049, "[", "]"),
        _deep(2050, "[", "]"),
        _deep(2047, '{"k":', "}"),
        _deep(2048, '{"k":', "}"),
        _deep(2049, '{"k":', "}"),
        _deep(2000, "[", "]"),
        _deep(2100, "[", "]"),
    ]),
)

# ---------- combine ----------

_documents = st.one_of(
    _json_value,
    _malformed_docs,
    _deep_nesting,
)

strategy = _documents