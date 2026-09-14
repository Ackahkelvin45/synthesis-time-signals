```python
from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

# Safe string bodies (no quotes/backslash/control) for keys
_key_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

_keys = st.one_of(
    st.just(""),
    st.text(_key_chars, min_size=1, max_size=12),
    # duplicate-key bait: small alphabet
    st.text(alphabet="ab", min_size=1, max_size=4),
)

# String content pieces, including escapes, unicode escapes, surrogates,
# control bytes and NUL, all wrapped so they form valid JSON strings.
_escape_pieces = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u0001", "\\u001f", "\\u007f", "\\u00e9", "\\u20ac",
    "\\uD800", "\\uDC00", "\\uDBFF", "\\uDFFF", "\\uD83D\\uDE00",
    "\\uFFFF", "\\uFFFE", "\\u0000\\u0000",
])

_control_pieces = st.sampled_from([
    "\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\x7f",
])

_safe_pieces = st.text(_key_chars, min_size=0, max_size=8)

_string_piece = st.one_of(_safe_pieces, _escape_pieces, _control_pieces)


@st.composite
def _json_string(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    body = "".join(draw(_string_piece) for _ in range(n))
    return '"' + body + '"'


# ---------- number strategies ----------

_int_part = st.one_of(
    st.just("0"),
    st.from_regex(r"[1-9][0-9]{0,18}", fullmatch=True),
)

_frac_part = st.one_of(
    st.just(""),
    st.from_regex(r"\.[0-9]{1,18}", fullmatch=True),
)

_exp_part = st.one_of(
    st.just(""),
    st.from_regex(r"[eE][+-]?[0-9]{1,4}", fullmatch=True),
    # extreme exponents / overflow
    st.sampled_from(["e309", "e-309", "E308", "e999999", "e-999999",
                     "e+308", "e+309", "E-400"]),
)

_number = st.builds(
    lambda sign, ip, fp, ep: sign + ip + fp + ep,
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    _frac_part,
    _exp_part,
)

# non-finite / extreme magnitudes
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "-1e308", "1e-309", "1e-324", "1e400",
    "0e0", "-0", "-0.0", "0.0", "1234567890123456789",
    "-123456789012345678901234567890", "1e+999999", "1e-999999",
    "9" * 40, "0." + "0" * 30 + "1",
])

# malformed number forms (parser rejects, but valuable)
_bad_number = st.sampled_from([
    "+1", "+0", ".5", "-.5", "1.", "01", "007", "-01", "0x1F",
    "1_000", "1e", "1e+", "1e-", "--1", "1..2", "1e1.5",
    "-",  # lone minus: accepted by parser, still edge
    "00", "0e", "Infinity", "NaN", "-Infinity",
])

_number_all = st.one_of(_number, _extreme_number, _bad_number)


# ---------- recursive value ----------

_json_value = st.recursive(
    st.one_of(
        _json_string(),
        _number_all,
        st.sampled_from(["true", "false", "null"]),
    ),
    lambda children: st.one_of(
        # arrays
        st.builds(
            lambda items: "[" + ",".join(items) + "]",
            st.lists(children, min_size=0, max_size=6),
        ),
        # trailing comma array
        st.builds(
            lambda items: "[" + ",".join(items) + ",]" if items else "[,]",
            st.lists(children, min_size=0, max_size=5),
        ),
        # objects (biased: usually non-empty)
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(
                    lambda k, v: k + ":" + v,
                    _json_string(),
                    children,
                ),
                min_size=1,
                max_size=6,
            ),
        ),
        # empty object
        st.just("{}"),
        # trailing comma object
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + ",}",
            st.lists(
                st.builds(
                    lambda k, v: k + ":" + v,
                    _json_string(),
                    children,
                ),
                min_size=1,
                max_size=5,
            ),
        ),
    ),
    max_leaves=40,
)


# ---------- deep nesting ----------

@st.composite
def _deep_nesting(draw):
    depth = draw(st.integers(min_value=1, max_value=200))
    kind = draw(st.sampled_from(["arr", "obj", "mixed"]))
    if kind == "arr":
        return "[" * depth + "]" * depth
    if kind == "obj":
        return '{"a":' * depth + "null" + "}" * depth
    # mixed: alternate
    out = []
    for i in range(depth):
        if i % 2 == 0:
            out.append('{"a":')
        else:
            out.append("[")
    close = []
    for i in reversed(range(depth)):
        if i % 2 == 0:
            close.append("}")
        else:
            close.append("]")
    return "".join(out) + "null" + "".join(close)


# ---------- malformed near-valid ----------

_malformed = st.sampled_from([
    # double commas
    "[1,,2]", "[,]", "[,1]", "[1,]", "[1,2,,]",
    # missing colons
    '{"a" 1}', '{"a"}', '{"a":}', '{:1}', '{"a":1 "b":2}',
    # unterminated strings
    '"abc', '{"a":"abc}', '["abc]', '"\\', '"\\u12', '"\\uZZZZ"',
    # trailing content
    "1abc", "[]xyz", "1 garbage", "true false", "{} {}", "nullx",
    # bad structure
    "}", "]", "{", "[", '{"a":1', "[1,2", "{{}}", "[[[]",
    # stray tokens
    ",", ":", "::", "{{", "]]", "}{", "][",
    # comments (disabled)
    "//x", "/* */1", "1 //c", "/* unterminated",
    # single quotes / bare keys
    "'x'", "{a:1}", "{'a':1}", "['a']",
    # whitespace-only / empty
    "", " ", "\t\n\r", "\x00",
    # NUL and control bytes embedded
    '"\x00"', "[\x00]", "{\x00:1}", "1\x00", "\x00{}",
    # duplicate keys
    '{"a":1,"a":2}', '{"a":1,"a":2,"a":3}',
    # lone minus / nonfinite
    "-", "1e309", "-1e309",
    # trailing comma variants
    "[1,2,]", '{"a":1,}', "[,]", "{,}",
    # unicode surrogates
    '"\\uD800"', '"\\uDC00"', '"\\uD800\\uD800"', '"\\uD800x"',
])


# ---------- top-level strategy ----------

strategy = st.one_of(
    # heavily weighted toward objects with members
    st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(
            st.builds(
                lambda k, v: k + ":" + v,
                _json_string(),
                _json_value,
            ),
            min_size=1,
            max_size=8,
        ),
    ),
    _json_value,
    _deep_nesting(),
    _malformed,
)
```