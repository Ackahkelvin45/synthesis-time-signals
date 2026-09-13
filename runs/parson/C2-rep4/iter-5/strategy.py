from hypothesis import strategies as st
import json

# ---------- primitives ----------

SAFE_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " _-!@#$%^&*()+=;:,.<>?/|~`'"
)

# Characters that are legal inside a JSON string body (already escaped-safe).
string_body_chars = st.one_of(
    st.sampled_from(SAFE_CHARS),
    st.integers(min_value=0x20, max_value=0x7E).map(chr),
    st.integers(min_value=0xA0, max_value=0xD7FF).map(chr),
    st.integers(min_value=0xE000, max_value=0xFFFD).map(chr),
)

escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

hex_digits = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

# \uXXXX including surrogate halves and \u0000 (the six-char escape, not raw NUL).
unicode_escape = st.one_of(
    hex_digits.map(lambda h: "\\u" + h),
    st.sampled_from(
        ["\\u0000", "\\u001f", "\\u007f", "\\uD800", "\\uDBFF",
         "\\uDC00", "\\uDFFF", "\\uFFFD", "\\uFFFF"]
    ),
)

string_piece = st.one_of(string_body_chars, escapes, unicode_escape)

json_string = (
    st.lists(string_piece, min_size=0, max_size=12)
    .map(lambda parts: '"' + "".join(parts) + '"')
)

# ---------- numbers ----------

zero = st.just("0")
nonzero_int = st.integers(min_value=1, max_value=10**18).map(str)
int_part = st.one_of(zero, nonzero_int)

frac = st.text(alphabet="0123456789", min_size=1, max_size=10).map(lambda d: "." + d)
exp = st.one_of(
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(lambda t: "".join(t)),
    st.sampled_from(["e309", "E309", "e+309", "e-309", "e999", "e-999",
                     "e308", "e-308", "e400", "e-400"]),
)

json_number = st.one_of(
    st.tuples(st.sampled_from(["", "-"]), int_part).map(lambda t: t[0] + t[1]),
    st.tuples(st.sampled_from(["", "-"]), int_part, frac).map(lambda t: "".join(t)),
    st.tuples(st.sampled_from(["", "-"]), int_part, exp).map(lambda t: "".join(t)),
    st.tuples(st.sampled_from(["", "-"]), int_part, frac, exp).map(lambda t: "".join(t)),
    # extreme magnitudes
    st.sampled_from([
        "1e309", "-1e309", "1e308", "-1e308", "1e-308", "1e-400",
        "123456789012345678901234567890",
        "0.0000000000000000000001",
        "1" + "0" * 300,
    ]),
    # lone sign / leniency probes
    st.sampled_from(["-", "-.", ".5", "+1", "01", "1.", "-01", "0.0", "-0"]),
)

# ---------- malformed fragments ----------

malformed_string = st.sampled_from([
    '"unterminated',
    '"bad\\xescape"',
    '"\\u12"',
    '"\\uZZZZ"',
    '""extra"',
    '"tab\there"',
    '"newline\nhere"',
])

malformed_number = st.sampled_from([
    "01", "-01", "+1", ".5", "1.", "1..2", "1e", "1e+", "--1", "0x1f", "1e1e1",
])

# ---------- recursive value ----------

json_scalar = st.one_of(
    json_string,
    json_number,
    st.sampled_from(["true", "false", "null"]),
    malformed_string,
    malformed_number,
)

def _join(parts):
    return "".join(parts)

# Build recursive structure with bounded depth.
value = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        # array: empty, singleton, or comma-separated (possibly with trailing comma)
        st.just("[]"),
        st.lists(children, min_size=1, max_size=5).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(children, min_size=1, max_size=4).map(
            lambda xs: "[" + ",".join(xs) + ",]"
        ),
        st.lists(children, min_size=2, max_size=4).map(
            lambda xs: "[" + ",".join(xs[:1]) + ",," + ",".join(xs[1:]) + "]"
        ),
        # object: empty, pairs, duplicate keys, missing colon
        st.just("{}"),
        st.lists(
            st.tuples(json_string, children), min_size=1, max_size=5
        ).map(
            lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"
        ),
        st.lists(
            st.tuples(json_string, children), min_size=1, max_size=4
        ).map(
            lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + ",}"
        ),
        # duplicate keys
        st.tuples(json_string, children, children).map(
            lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
        ),
        # missing colon
        st.tuples(json_string, children).map(
            lambda t: "{" + t[0] + " " + t[1] + "}"
        ),
    ),
    max_leaves=40,
)

# ---------- depth-focused wrappers ----------

def _wrap_depth(depth, inner):
    # depth around the 2048 cap: near-limit interesting
    return "[" * depth + inner + "]" * depth

depth_choice = st.one_of(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=2040, max_value=2048),
    st.integers(min_value=2049, max_value=2055),
    st.sampled_from([1, 2, 3, 100, 1000, 2047, 2048, 2049, 4096]),
)

deep_value = st.tuples(depth_choice, value).map(
    lambda t: _wrap_depth(t[0], t[1])
)

# ---------- top-level with optional trailing content ----------

trailing = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\n", "\t", "\r\n"]),
    st.sampled_from(["garbage", "1abc", "xyz", "[]xyz", "null extra", "/*c*/",
                     "//comment", "  trailing  "]),
)

top = st.tuples(value, trailing).map(lambda t: t[0] + t[1])

# ---------- broadened diverse accepted structures ----------

def _interleave(parts, sep):
    return sep.join(parts)

# Diverse but valid containers that exercise more accepted shapes.
diverse_value = st.one_of(
    # arrays of arrays / arrays of objects
    st.lists(value, min_size=1, max_size=6).map(
        lambda xs: "[" + ",".join(xs) + "]"
    ),
    # objects with varied key styles and multiple pairs
    st.lists(
        st.tuples(json_string, value), min_size=1, max_size=6
    ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
    # nested objects inside arrays
    st.lists(
        st.tuples(json_string, value), min_size=1, max_size=3
    ).map(lambda ps: "[" + ",".join("{" + k + ":" + v + "}" for k, v in ps) + "]"),
    # arrays inside objects
    st.lists(
        st.tuples(json_string, st.lists(value, min_size=0, max_size=3).map(
            lambda xs: "[" + ",".join(xs) + "]"
        )), min_size=1, max_size=3
    ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
    # mixed scalar arrays
    st.lists(
        st.one_of(json_number, json_string, st.sampled_from(["true", "false", "null"])),
        min_size=1, max_size=8
    ).map(lambda xs: "[" + ",".join(xs) + "]"),
    # flat objects with many scalar pairs
    st.lists(
        st.tuples(json_string, st.one_of(json_number, json_string,
                                         st.sampled_from(["true", "false", "null"]))),
        min_size=1, max_size=8
    ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
    # whitespace-padded valid documents
    st.tuples(
        st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "]),
        value,
        st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "]),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # deeply nested small structures
    st.integers(min_value=1, max_value=12).map(
        lambda d: "[" * d + "1" + "]" * d
    ),
    st.integers(min_value=1, max_value=8).map(
        lambda d: '{"a":' * d + "1" + "}" * d
    ),
)

strategy = st.one_of(
    value,
    deep_value,
    top,
    diverse_value,
    st.sampled_from([
        "{}", "[]", "null", "true", "false", "0", "-", "-.",
        '{"a":1,"a":2}',
        '{"":0}',
        '{"k"}',
        '{"k":}',
        '[1,]',
        '[1,,2]',
        '[,]',
        '["\\u0000"]',
        '["\\uD800"]',
        '["\\uDC00\\uD800"]',
        '"\\uD800\\uD800"',
        '1e309',
        '{"a":1e309}',
        '[' * 2048 + ']' * 2048,
        '[' * 2049 + ']' * 2049,
        '{"a":' * 100 + '1' + '}' * 100,
        '1 garbage',
        '[]xyz',
    ]),
)