```python
from hypothesis import strategies as st
import json

# ---------- primitives ----------

_hex = "0123456789abcdefABCDEF"

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_control_bytes = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x0e", "\x1f", "\t", "\n", "\r"]
)

_escapes = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_unicode_esc = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    st.sampled_from(_hex), st.sampled_from(_hex),
    st.sampled_from(_hex), st.sampled_from(_hex),
)

_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udbff", "\\udc00", "\\udfff", "\\uD800", "\\uDFFF",
     "\\ud800\\udc00", "\\ud83d\\ude00"]
)

_esc_or_uni = st.one_of(_escapes, _unicode_esc, _surrogate_esc)

_string_body = st.one_of(
    st.text(_safe_chars, max_size=12),
    st.lists(st.one_of(_esc_or_uni, _control_bytes, st.text(_safe_chars, max_size=3)),
             max_size=6).map("".join),
)

quoted_string = _string_body.map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)

_int = st.one_of(
    st.just("0"),
    st.builds(lambda d, r: d + r, st.sampled_from("123456789"),
              st.text("0123456789", max_size=6)),
)

_frac = st.builds(lambda d: "." + d, _digits)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    _digits,
)

_extreme_num = st.sampled_from([
    "1e309", "-1e309", "1e308", "1e-309", "1e999999", "1E+400", "-0",
    "0.0", "1.7976931348623157e309", "5e-324", "1e-400",
    "123456789012345678901234567890", "-" + "9" * 30,
    "0e0", "0e999", "-0.0e-0",
])

_number = st.one_of(
    st.builds(lambda i, f, e: i + f + e, _int, _frac, _exp),
    st.builds(lambda i, e: i + e, _int, _exp),
    st.builds(lambda i, f: i + f, _int, _frac),
    _int,
    _extreme_num,
)

# ---------- malformed number-ish ----------

_bad_number = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "-", "--1", "1..2",
    "1e", "1e+", "1.2.3", "+", "1e+ 2", "0b1", "1_000",
])

# ---------- recursive structure ----------

json_strategy = st.recursive(
    st.one_of(
        quoted_string,
        _number,
        st.sampled_from(["true", "false", "null"]),
        _bad_number,
    ),
    lambda children: st.one_of(
        _array(children),
        _object(children),
    ),
    max_leaves=60,
)


def _array(children):
    # bias toward non-empty; allow empty and trailing comma and doubles
    elems = st.lists(children, min_size=1, max_size=6)
    return st.one_of(
        st.just("[]"),
        elems.map(lambda xs: "[" + ",".join(xs) + "]"),
        elems.map(lambda xs: "[" + ",".join(xs) + ",]"),
        st.lists(children, min_size=2, max_size=5).map(
            lambda xs: "[" + ",".join(xs[:1] + [""] + xs[1:]) + "]"),
        st.just("[,"),
        st.just("[,]"),
        st.just("[1,,2]"),
        children.map(lambda x: "[" + x),
    )


def _key():
    return st.one_of(
        quoted_string,
        st.sampled_from(['"a"', '"a"', '"b"', '"\\u0000"', '""', '"\\ud800"']),
    )


def _pair(children):
    return st.builds(
        lambda k, v: k + ":" + v,
        _key(),
        children,
    )


def _object(children):
    pairs = st.lists(_pair(children), min_size=1, max_size=6)
    dup_pairs = st.builds(
        lambda p, q: p + "," + q,
        _pair(children),
        st.builds(lambda v: '"a":' + v, children),
    )
    return st.one_of(
        st.just("{}"),
        pairs.map(lambda ps: "{" + ",".join(ps) + "}"),
        pairs.map(lambda ps: "{" + ",".join(ps) + ",}"),
        dup_pairs.map(lambda s: "{" + s + "}"),
        st.builds(lambda v: '{"a":' + v + ',"a":' + v + "}", children),
        st.builds(lambda k, v: "{" + k + v + "}", _key(), children),
        st.builds(lambda k: "{" + k + "}", _key()),
        st.just("{,}"),
        st.just('{"a":1,,}'),
        st.builds(lambda v: "{" + v + "}", children),
    )


# ---------- deep nesting ----------

_deep = st.integers(min_value=1, max_value=400).flatmap(
    lambda n: st.just("[" * n + "0" + "]" * n)
)

_deep_obj = st.integers(min_value=1, max_value=300).flatmap(
    lambda n: st.just('{"a":' * n + "1" + "}" * n)
)

_deep_mixed = st.integers(min_value=1, max_value=200).flatmap(
    lambda n: st.just('{"a":[' * n + "null" + "]}" * n)
)

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    '{"a" 1}',
    '{"a":}',
    '{"a":1 "b":2}',
    '{"a":1,}',
    '{"a":1,,}',
    '[1 2]',
    '[1,2',
    '{"a":1',
    '"unterminated',
    '"unterminated\\',
    "'single'",
    "{a:1}",
    '{"a":1}garbage',
    '1abc',
    '[]xyz',
    'true false',
    '//comment\n1',
    '/*c*/1',
    '\x00',
    '\x00{}',
    '{"a":\x00}',
    '"\x00"',
    '"\x01\x02\x03"',
    '{"\\u0000":1}',
    '{"a":"\\ud800"}',
    '[,1]',
    '[1,,2]',
    '{,}',
    '{"a":1,,"b":2}',
    '',
    ' ',
    '\n\t ',
])

# ---------- combine ----------

strategy = st.one_of(
    json_strategy,
    _deep,
    _deep_obj,
    _deep_mixed,
    _malformed,
)
```