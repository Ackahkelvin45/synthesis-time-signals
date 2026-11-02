```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
    min_codepoint=0x20,
)

_control_chars = st.sampled_from(
    [chr(i) for i in range(0x00, 0x20)] + ["\x7f"]
)

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        return "\\u%04x" % hi
    if kind == 1:
        lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x" % lo
    if kind == 2:
        hi = draw(st.integers(min_value=0xD800, max_value=0xDBFF))
        lo = draw(st.integers(min_value=0xDC00, max_value=0xDFFF))
        return "\\u%04x\\u%04x" % (hi, lo)
    if kind == 3:
        cu = draw(st.integers(min_value=0, max_value=0xFFFF))
        return "\\u%04X" % cu
    return "\\u" + "".join(draw(st.lists(_hex_digit, min_size=4, max_size=4)))


_simple_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_string_unit = st.one_of(
    _simple_escapes,
    _unicode_escape(),
    _control_chars,
    st.just("\x00"),
    _safe_chars,
)

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
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
    st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda n: "0x%x" % n),
)

_frac_part = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n)),
    st.just("."),
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
        st.lists(children, min_size=0, max_size=6).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(children, min_size=0, max_size=4).map(
            lambda xs: "[ " + " , ".join(xs) + " ]"
        ),
        st.lists(
            st.tuples(_string(), children).map(lambda t: t[0] + ":" + t[1]),
            min_size=0,
            max_size=5,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
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


@st.composite
def _near_cap(draw):
    depth = draw(st.integers(min_value=990, max_value=1010))
    shape = draw(st.integers(min_value=0, max_value=5))
    leaf = draw(_leaf)
    if shape == 0:
        return "[" * depth + leaf + "]" * depth
    if shape == 1:
        return '{"k":' * depth + leaf + "}" * depth
    if shape == 2:
        return "[" * depth + leaf + "," + "]" * depth
    if shape == 3:
        return '{"k":' * depth + leaf + "," + "}" * depth
    if shape == 4:
        opener = draw(st.sampled_from(["[", '{"k":']))
        closer = "]" if opener == "[" else "}"
        return opener * depth + leaf + closer * depth
    return "[" * depth + leaf


# ---------------------------------------------------------------------------
# Cap-distance targeted probes.
# ---------------------------------------------------------------------------

@st.composite
def _cap_probe(draw):
    depth = draw(st.integers(min_value=996, max_value=1006))
    shape = draw(st.integers(min_value=0, max_value=7))
    leaf = draw(_leaf)
    if shape == 0:
        return "[" * depth + leaf + "]" * depth
    if shape == 1:
        return '{"k":' * depth + leaf + "}" * depth
    if shape == 2:
        return "[" * depth + leaf + "]" * (depth - 1)
    if shape == 3:
        return "[" * depth + leaf + "]" * (depth + 1)
    if shape == 4:
        return '{"k":' * depth + leaf + "}" * (depth - 1)
    if shape == 5:
        return "[" * depth + leaf + "}" * depth
    if shape == 6:
        return ('[' * (depth // 2) + '{"k":' * (depth - depth // 2)
                + leaf + "]" * depth)
    return "[" * depth + "[]" + "]" * depth


# ---------------------------------------------------------------------------
# Divergence-focused probes.
# ---------------------------------------------------------------------------

_trailing_bytes = st.one_of(
    st.lists(
        st.integers(min_value=0, max_value=0x10FFFF).filter(
            lambda c: not (0xD800 <= c <= 0xDFFF)
        ),
        min_size=1,
        max_size=8,
    ).map(lambda cs: "".join(chr(c) for c in cs)),
    st.sampled_from(["\x00", " ", "\t", "\n", "\r", "]", "}", "\x7f"]),
)


@st.composite
def _trailing_garbage(draw):
    head = draw(st.one_of(
        _number(),
        _string(),
        st.sampled_from(["true", "false", "null"]),
        st.lists(_leaf, min_size=0, max_size=3).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(_string(), min_size=0, max_size=3).map(
            lambda ks: "{" + ",".join(k + ":1" for k in ks) + "}"
        ),
    ))
    tail = draw(st.lists(_trailing_bytes, min_size=1, max_size=4).map("".join))
    return head + tail


@st.composite
def _unmatched_openers(draw):
    depth = draw(st.one_of(
        st.integers(min_value=1, max_value=10),
        st.integers(min_value=990, max_value=1010),
    ))
    opener = draw(st.sampled_from(["[", '{"k":']))
    return opener * depth


# ---------------------------------------------------------------------------
# IMPROVEMENT: BOM-prefixed *deep* documents and BOM + trailing-garbage.
#
# The run feedback showed divergences dominated by BOM-prefixed arrays whose
# element strings contained multi-byte UTF-8, and by long runs of unmatched
# '['.  The existing _with_bom only wraps shallow _value, so it never
# combines a BOM with deep nesting or with the multi-byte string content that
# appeared in the divergence examples.  These probes directly target that
# intersection: BOM + deep/near-cap nesting, and BOM + string-heavy arrays.
# ---------------------------------------------------------------------------

@st.composite
def _bom_deep(draw):
    depth = draw(st.integers(min_value=990, max_value=1010))
    shape = draw(st.integers(min_value=0, max_value=3))
    leaf = draw(_leaf)
    if shape == 0:
        body = "[" * depth + leaf + "]" * depth
    elif shape == 1:
        body = '{"k":' * depth + leaf + "}" * depth
    elif shape == 2:
        body = "[" * depth + leaf
    else:
        body = "[" * depth + leaf + "]" * (depth - 1)
    return "\ufeff" + body


@st.composite
def _bom_string_array(draw):
    # BOM-prefixed array of multi-byte-heavy strings, matching the divergence
    # examples (BOM + '[' + string elements with non-ASCII content).
    n = draw(st.integers(min_value=1, max_value=4))
    elems = []
    for _ in range(n):
        kind = draw(st.integers(min_value=0, max_value=2))
        if kind == 0:
            elems.append('""')
        elif kind == 1:
            elems.append(draw(st.sampled_from(["false", "true", "null"])))
        else:
            body = draw(st.text(
                alphabet=st.characters(min_codepoint=0x80, blacklist_categories=("Cs",),
                                       blacklist_characters='"\\'),
                min_size=1, max_size=20,
            ))
            elems.append('"' + body + '"')
    return "\ufeff[" + " , ".join(elems) + "]"


strategy = st.one_of(
    _valid_value,
    _with_trailing,
    _with_bom,
    _whitespace_wrapped,
    _deep_array(),
    _deep_object(),
    _near_cap(),
    _cap_probe(),
    _trailing_garbage(),
    _unmatched_openers(),
    _bom_deep(),
    _bom_string_array(),
    _malformed,
    _raw_bytes,
)
```