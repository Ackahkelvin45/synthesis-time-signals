```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Characters that may appear raw inside a JSON string per the grammar.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
    min_codepoint=0x20,
)

# Raw control characters (allowed by this parser inside strings).
_control_chars = st.sampled_from(
    [chr(i) for i in range(0x00, 0x20)] + ["\x7f"]
)

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    # \uXXXX, sometimes a surrogate (lone or paired).
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        # lone high surrogate
        hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        return "\\u%04x" % hi
    if kind == 1:
        # lone low surrogate
        lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x" % lo
    if kind == 2:
        # valid surrogate pair
        hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x\\u%04x" % (hi, lo)
    if kind == 3:
        # uppercase hex, arbitrary code unit
        cu = draw(st.integers(min_value=0, max_value=0xFFFF))
        return "\\u%04X" % cu
    # arbitrary \uXXXX
    return "\\u" + "".join(draw(st.lists(_hex_digit, min_size=4, max_size=4)))


_simple_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

# A single "unit" inside a string body.
_string_unit = st.one_of(
    _simple_escapes,
    _unicode_escape(),
    _control_chars,
    st.just("\x00"),
    _safe_chars,
)

# String body: possibly empty, possibly long, possibly containing NULs.
_string_body = st.one_of(
    st.just(""),
    st.lists(_string_unit, min_size=1, max_size=12).map("".join),
    st.text(
        alphabet=st.characters(min_codepoint=0x20, blacklist_characters='"\\'),
        min_size=0,
        max_size=40,
    ),
)


@st.composite
def _string(draw):
    body = draw(_string_body)
    # Occasionally emit an unterminated string.
    if draw(st.integers(min_value=0, max_value=11)) == 0:
        return '"' + body
    return '"' + body + '"'


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    # leading zeros (accepted by this parser)
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
    # hex (accepted by this parser)
    st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda n: "0x%x" % n),
)

_frac_part = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
    st.just("."),  # trailing dot (accepted)
)

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=400).map(str),
    ).map("".join),
    st.just("e309"),
    st.just("e-309"),
    st.just("e999"),
)


@st.composite
def _number(draw):
    sign = draw(st.sampled_from(["", "-"]))
    intp = draw(_int_part)
    frac = draw(_frac_part)
    exp = draw(_exp_part)
    return sign + intp + frac + exp


# ---------------------------------------------------------------------------
# Malformed fragments (near-valid but broken)
# ---------------------------------------------------------------------------

_malformed = st.sampled_from(
    [
        "+1",
        "-",
        ".5",
        ".",
        "NaN",
        "Infinity",
        "-Infinity",
        "01",
        "1.",
        "1e",
        "1e+",
        "--1",
        "0x",
        "0xg",
        "'single'",
        "{'a': 1}",
        "{a: 1}",
        "[1,2,]",
        '{"a":1,}',
        '{"a" 1}',
        "{,}",
        "[,]",
        "[1,,2]",
        '{"a":}',
        '{"a"}',
        "{:1}",
        "tru",
        "fals",
        "nul",
        "True",
        "NULL",
        "\\u",
        '"\\u12"',
        '"\\x41"',
        '"unterminated',
        "{",
        "[",
        "}",
        "]",
        ":",
        ",",
        "",
        " ",
        "\x00",
    ]
)


# ---------------------------------------------------------------------------
# Recursive JSON values
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the ~1000 nesting limit.
_depth_choices = st.one_of(
    st.integers(min_value=0, max_value=4),
    st.integers(min_value=5, max_value=50),
    st.integers(min_value=900, max_value=1002),
    st.integers(min_value=999, max_value=1001),
)


@st.composite
def _depth(draw):
    return draw(_depth_choices)


def _deep_wrap(inner, depth, opener, closer):
    """Wrap `inner` in `depth` nested openers/closers."""
    return opener * depth + inner + closer * depth


@st.composite
def _deep_array(draw):
    depth = draw(st.integers(min_value=900, max_value=1002))
    leaf = draw(st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])))
    return "[" * depth + leaf + "]" * depth


@st.composite
def _deep_object(draw):
    depth = draw(st.integers(min_value=900, max_value=1002))
    leaf = draw(st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])))
    return '{"k":' * depth + leaf + "}" * depth


# ---------------------------------------------------------------------------
# Non-recursive value productions (leaves).
# ---------------------------------------------------------------------------

_leaf = st.one_of(
    _string(),
    _number(),
    st.sampled_from(["true", "false", "null"]),
)


@st.composite
def _pair(draw):
    key = draw(_string())
    colon = draw(st.sampled_from([":", ": ", " :", " ", ""]))
    val = draw(_value())
    return key + colon + val


# ---------------------------------------------------------------------------
# Recursive value
# ---------------------------------------------------------------------------

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        # arrays
        st.lists(children, min_size=0, max_size=6).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        # arrays with whitespace
        st.lists(children, min_size=0, max_size=4).map(
            lambda xs: "[ " + " , ".join(xs) + " ]"
        ),
        # objects
        st.lists(
            st.tuples(_string(), children).map(lambda t: t[0] + ":" + t[1]),
            min_size=0,
            max_size=5,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
        # objects with duplicate keys
        st.tuples(
            _string(),
            children,
            _string(),
            children,
        ).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[2] + ":" + t[3] + "}"),
    ),
    max_leaves=40,
)


# ---------------------------------------------------------------------------
# Top-level strategy: valid-ish, deep, malformed, and combinations.
# ---------------------------------------------------------------------------

_valid_value = _value

_with_trailing = st.tuples(_value, st.sampled_from(["", " ", "\x00", "abc", " 1 2"])).map(
    lambda t: t[0] + t[1]
)

_with_bom = st.tuples(st.just("\ufeff"), _value).map(lambda t: t[0] + t[1])

_whitespace_wrapped = st.tuples(
    st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
    _value,
    st.sampled_from(["", " ", "\t", "\n", "\r\n"]),
).map(lambda t: t[0] + t[1] + t[2])

_raw_bytes = st.one_of(
    st.text(min_size=0, max_size=30),
    st.lists(
        st.integers(min_value=0, max_value=0x10FFFF).filter(
            lambda c: not (0xD800 <= c <= 0xDFFF)
        ),
        min_size=0,
        max_size=20,
    ).map(lambda cs: "".join(chr(c) for c in cs)),
)

# NEW: valid value with a JSON-looking suffix, to exercise parsers that
# accept a single value and then must handle trailing garbage that itself
# looks like a valid document (streaming / multi-document behavior).
_value_with_json_suffix = st.tuples(
    _value,
    st.sampled_from(
        [
            "{}",
            "[]",
            "null",
            "true",
            "0",
            '""',
            "\n{}",
            "\n[]",
            " \n null",
        ]
    ),
).map(lambda t: t[0] + t[1])


# NEW: deep nesting with a mismatched closer, to stress the parser's
# recursion-limit handling while its error-recovery paths are active.
@st.composite
def _deep_mismatch(draw):
    depth = draw(st.integers(min_value=900, max_value=1002))
    opener = draw(st.sampled_from(["[", "{", '{"k":']))
    closer = draw(st.sampled_from(["]", "}", "] }", "} ]", "]", "}", ""]))
    leaf = draw(st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])))
    return opener * depth + leaf + closer


# NEW: deep nesting interleaved with whitespace and separators, to exercise
# the parser's whitespace handling deep in its recursion.
@st.composite
def _deep_whitespace(draw):
    depth = draw(st.integers(min_value=900, max_value=1002))
    sep = draw(st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "]))
    close_sep = draw(st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "]))
    leaf = draw(st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])))
    return ("[" + sep) * depth + leaf + (close_sep + "]") * depth


# NEW: deeply nested objects with distinct keys, to exercise key handling
# and duplicate-key detection at depth.
@st.composite
def _deep_distinct_keys(draw):
    depth = draw(st.integers(min_value=900, max_value=1002))
    leaf = draw(st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])))
    parts = []
    for i in range(depth):
        parts.append('{"k%d":' % i)
    return "".join(parts) + leaf + "}" * depth


strategy = st.one_of(
    _valid_value,
    _with_trailing,
    _with_bom,
    _whitespace_wrapped,
    _deep_array(),
    _deep_object(),
    _malformed,
    _raw_bytes,
    _value_with_json_suffix,
    _deep_mismatch(),
    _deep_whitespace(),
    _deep_distinct_keys(),
    # valid values embedded in malformed wrappers, to exercise parser
    # error-recovery paths and to combine deep nesting with broken syntax.
    st.tuples(
        st.sampled_from(["[", "{", '"', "[1,", '{"a":', "  "]),
        _value,
        st.sampled_from(["", "}", "]", ",", ":", "\x00", "extra"]),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # deep nesting combined with malformed wrappers, to stress the
    # parser's recursion limit handling together with its error recovery.
    st.tuples(
        st.sampled_from(["[" * 1000, "{" * 1000, '{"k":' * 1000]),
        _value,
        st.sampled_from(["", "]", "}", "]", "}", "extra", "\x00"]),
    ).map(lambda t: t[0] + t[1] + t[2]),
)
```