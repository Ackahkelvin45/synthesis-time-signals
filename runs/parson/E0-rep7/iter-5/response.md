EDIT: fix_feature_encoding

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map("".join)

# A "safe" character for inside strings: printable ASCII excluding quote and backslash,
# plus a few unicode chars. Never a raw NUL or control char (parser is NUL-terminated).
_safe_chars = st.sampled_from(
    [chr(c) for c in range(0x20, 0x7f) if c not in (0x22, 0x5c)]
    + ["\u00e9", "\u00fc", "\u4e2d", "\u6587", "\U0001F600", "\u2028", "\u007f"]
)

_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# A \u escape must be followed by exactly 4 hex digits; build it from a
# 4-tuple of single hex chars so the encoding is always well-formed.
_unicode_esc = st.tuples(
    st.just("\\u"), _hex4()
).map(lambda t: t[0] + t[1])

# Surrogate escapes (lone / paired) - these are interesting edge cases.
_surrogate_esc = st.sampled_from(
    ["\\ud800", "\\udfff", "\\ud83d\\ude00", "\\uD834\\uDD1E", "\\u0000"]
)

_string_char = st.one_of(_escapes, _unicode_esc, _surrogate_esc, _safe_chars)

def _string_body(max_size=12):
    return st.lists(_string_char, max_size=max_size).map("".join)

_string = st.tuples(st.just('"'), _string_body(), st.just('"')).map("".join)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), st.text(alphabet="0123456789", max_size=10)).map("".join),
    st.text(alphabet="0123456789", min_size=1, max_size=18),
)

_frac = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=10)).map("".join)

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map("".join)

_sign = st.sampled_from(["", "-"])

_number = st.one_of(
    # normal numbers
    st.tuples(_sign, _int_part, st.one_of(st.just(""), _frac), st.one_of(st.just(""), _exp)).map("".join),
    # extreme magnitudes / overflow
    st.sampled_from([
        "1e309", "-1e309", "1e400", "-1e400", "1e-400", "1e308", "1.7976931348623157e308",
        "1.8e308", "-1.8e308", "0e0", "0e999999", "1e999999999", "123456789012345678901234567890",
        "-123456789012345678901234567890", "1.0e-999999", "-0", "-0.0", "0.0000000000000000001",
    ]),
    # lone sign (parser quirk: parses as 0)
    st.just("-"),
    # leading + / .5 / 1. / 01 style near-valid
    st.sampled_from(["+1", ".5", "1.", "01", "-01", "+.5", "--1", "1..2", "1e", "1e+", "1e-"]),
)

# ---------- recursive value ----------

_literal = st.sampled_from(["true", "false", "null"])

_json_leaves = st.one_of(_string, _number, _literal)

def _build_value(children):
    return st.one_of(
        _json_leaves,
        st.tuples(st.just("{"), st.just("}")).map("".join),
        st.tuples(st.just("["), st.just("]")).map("".join),
        # object
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_string, st.just(":"), children).map("".join),
                min_size=0, max_size=4,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map("".join),
        # array
        st.tuples(
            st.just("["),
            st.lists(children, min_size=0, max_size=4).map(lambda xs: ",".join(xs)),
            st.just("]"),
        ).map("".join),
    )

# Base values (depth 0) - small, non-recursive-ish
_base = st.one_of(_json_leaves)

_value = st.recursive(_base, _build_value, max_leaves=40)

# ---------- deep nesting near the 2048 cap ----------

def _deep(depth):
    # depth nested arrays around a leaf value; depth chosen near 2048
    return st.tuples(
        st.just("[" * depth),
        _json_leaves,
        st.just("]" * depth),
    ).map("".join)

def _deep_obj(depth):
    return st.tuples(
        st.just('{"k":' * depth),
        _json_leaves,
        st.just("}" * depth),
    ).map("".join)

# Bias depths tightly around the 2048 cap so the parser's depth limit is
# exercised from just below, at, and just above the threshold.
_depth_choice = st.sampled_from([
    0, 1, 2, 100, 1000,
    2040, 2041, 2042, 2043, 2044, 2045, 2046, 2047,
    2048,
    2049, 2050, 2051, 2052, 2055, 2060,
    2100, 4096,
])

_deep_value = st.one_of(
    _depth_choice.flatmap(_deep),
    _depth_choice.flatmap(_deep_obj),
    # mixed nesting: arrays wrapped in objects and vice versa near the cap
    _depth_choice.flatmap(
        lambda d: st.tuples(
            st.just("[" * (d // 2) + '{"k":' * (d - d // 2)),
            _json_leaves,
            st.just("}" * (d - d // 2) + "]" * (d // 2)),
        ).map("".join)
    ),
)

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    "{,}", "[,]", "[1,,2]", '{"a":1,}', "[1,]", '{"a" 1}', '{"a":}', "{:1}",
    '{"a":1 "b":2}', '"unterminated', '"esc\\', "[1 2]", "{", "}", "[", "]",
    '{"a":1', '[1,2', '"', '\\', "tru", "fals", "nul", "True", "NULL",
    '{"a":1}}', "[[[]]", '{"a":{"b":}}', "1,2", "1 2", "[] []", "{} {}",
    '{"a":1}garbage', "1abc", "[]xyz", "1 garbage", "nullx", "truefalse",
])

# ---------- top-level composition ----------

_trailing = st.tuples(_value, st.text(alphabet=" \t\n\rabc{}[]0123", max_size=8)).map("".join)

_whitespace = st.text(alphabet=" \t\n\r", max_size=6)

def _wrap_ws(v):
    return st.tuples(_whitespace, v, _whitespace).map("".join)

# Broadened structural diversity: mixed-type containers, wider key sets,
# varied separators/whitespace, and assorted top-level shapes.
_mixed_key = st.one_of(
    _string,
    st.sampled_from(['"a"', '"b"', '"k"', '"key"', '""', '"0"', '"1"', '"_"']),
)

_mixed_scalar = st.one_of(
    _json_leaves,
    st.sampled_from(["0", "1", "-1", "true", "false", "null", "1.5", "1e10"]),
)

def _mixed_container(children):
    return st.one_of(
        # object with varied keys and values
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_mixed_key, st.just(":"), st.one_of(children, _mixed_scalar)).map("".join),
                min_size=0, max_size=6,
            ).map(lambda ps: ",".join(ps)),
            st.just("}"),
        ).map("".join),
        # array with mixed scalar/structured elements
        st.tuples(
            st.just("["),
            st.lists(st.one_of(children, _mixed_scalar), min_size=0, max_size=6).map(
                lambda xs: ",".join(xs)
            ),
            st.just("]"),
        ).map("".join),
        # whitespace-padded container
        st.tuples(
            st.just("["),
            st.lists(st.one_of(children, _mixed_scalar), min_size=0, max_size=4).map(
                lambda xs: " ,\n ".join(xs)
            ),
            st.just("]"),
        ).map("".join),
    )

_mixed_value = st.recursive(_mixed_scalar, _mixed_container, max_leaves=30)

_diverse = st.one_of(
    _mixed_value,
    # sequences of values separated by whitespace (multiple top-level values)
    st.lists(_mixed_scalar, min_size=1, max_size=5).map(lambda xs: " ".join(xs)),
    # object with many duplicate-ish keys
    st.tuples(
        st.just("{"),
        st.lists(
            st.tuples(_mixed_key, st.just(":"), _mixed_scalar).map("".join),
            min_size=1, max_size=8,
        ).map(lambda ps: ",".join(ps)),
        st.just("}"),
    ).map("".join),
)

strategy = _wrap_ws(
    st.one_of(
        _value,
        _diverse,
        _deep_value,
        _malformed,
        _trailing,
        st.just(""),
        st.just("{}"),
        st.just("[]"),
        st.just('{"a":0,"a":1}'),  # duplicate keys
        st.just('{"k":0,"k":1}'),
        st.just("1e309"),
        st.just("-"),
    )
)
```