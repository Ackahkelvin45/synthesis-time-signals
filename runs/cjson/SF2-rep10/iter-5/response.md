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
# Malformed fragments
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


def _mutate(s):
    if not s:
        return s
    n = len(s)
    if n > 1:
        s = s[: max(1, n - 1)]
    return s


@st.composite
def _mutated(draw):
    base = draw(_value)
    kind = draw(st.integers(min_value=0, max_value=9))
    if kind == 0:
        cut = draw(st.integers(min_value=0, max_value=len(base)))
        return base[:cut]
    if kind == 1:
        idxs = [i for i, c in enumerate(base) if c in "{}[],:"]
        if idxs:
            i = draw(st.sampled_from(idxs))
            return base[:i] + base[i + 1:]
        return base
    if kind == 2:
        idxs = [i for i, c in enumerate(base) if c in "{}[],:"]
        if idxs:
            i = draw(st.sampled_from(idxs))
            return base[:i] + base[i] + base[i:]
        return base
    if kind == 3:
        i = draw(st.integers(min_value=0, max_value=len(base)))
        ch = draw(st.sampled_from("{}[],:"))
        return base[:i] + ch + base[i:]
    if kind == 4:
        idxs = [i for i, c in enumerate(base) if c in "{}[],:"]
        if idxs:
            i = draw(st.sampled_from(idxs))
            ch = draw(st.sampled_from("{}[],:"))
            return base[:i] + ch + base[i + 1:]
        return base
    if kind == 5:
        return "[[" + base + "]]"
    if kind == 6:
        other = draw(_leaf)
        return base + other
    if kind == 7:
        return '{"a":' + base + "}"
    if kind == 8:
        return '"' + base.replace('"', "") + '\\u'
    return base


@st.composite
def _truncated_container(draw):
    base = draw(st.one_of(
        st.lists(_leaf, min_size=1, max_size=5).map(
            lambda xs: "[" + ",".join(xs) + "]"
        ),
        st.lists(
            st.tuples(_string(), _leaf).map(lambda t: t[0] + ":" + t[1]),
            min_size=1,
            max_size=4,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ))
    cut = draw(st.integers(min_value=0, max_value=len(base)))
    return base[:cut]


_incomplete = st.sampled_from(
    [
        "[",
        "[1",
        "[1,",
        "[1,2",
        '{"a"',
        '{"a":',
        '{"a":1',
        '{"a":1,',
        '{"a":1,"b"',
        '{"a":1,"b":',
        "[[[[",
        "{{{{",
        '"',
        '"abc',
        "\\",
        "\\u12",
        "-",
        "0x",
        "t",
        "tr",
        "tru",
        "f",
        "fa",
        "fal",
        "fals",
        "n",
        "nu",
        "nul",
    ]
)


_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "\r\n", "  ", "\n\t "])

_ws_value = st.tuples(_ws, _value, _ws).map(lambda t: t[0] + t[1] + t[2])


@st.composite
def _interleaved(draw):
    kind = draw(st.integers(min_value=0, max_value=1))
    ws = lambda: draw(_ws)
    if kind == 0:
        n = draw(st.integers(min_value=0, max_value=4))
        parts = [draw(_leaf) for _ in range(n)]
        body = ""
        for i, p in enumerate(parts):
            if i:
                body += draw(_ws) + "," + draw(_ws)
            body += p
        return "[" + draw(_ws) + body + draw(_ws) + "]"
    n = draw(st.integers(min_value=0, max_value=3))
    parts = []
    for _ in range(n):
        k = draw(_string())
        v = draw(_leaf)
        parts.append(k + draw(_ws) + ":" + draw(_ws) + v)
    body = ""
    for i, p in enumerate(parts):
        if i:
            body += draw(_ws) + "," + draw(_ws)
        body += p
    return "{" + draw(_ws) + body + draw(_ws) + "}"


@st.composite
def _mixed_deep(draw):
    depth = draw(st.integers(min_value=50, max_value=1002))
    leaf = draw(st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])))
    openers = []
    closers = []
    for _ in range(depth):
        if draw(st.integers(min_value=0, max_value=1)) == 0:
            openers.append("[")
            closers.append("]")
        else:
            openers.append('{"k":')
            closers.append("}")
    return "".join(openers) + leaf + "".join(reversed(closers))


_noise = st.sampled_from(
    [
        "//c\n",
        "/*c*/",
        "#c\n",
        "\ufeff",
        "\x00",
        "\x00\x00",
        "\x1b",
    ]
)

_noisy = st.tuples(
    st.one_of(st.just(""), _noise),
    _value,
    st.one_of(st.just(""), _noise),
).map(lambda t: t[0] + t[1] + t[2])


# ---------------------------------------------------------------------------
# NEW: targeted structural-error recovery fuzzers.
#   - _struct_error: valid container with a single injected structural
#     fault (missing/extra/mismatched delimiter, bad separator, missing
#     value/key, wrong token type) to steer the parser's resync branches.
#   - _deep_truncated: deep nesting truncated at many points to reach
#     depth-limit + EOF recovery branches.
# ---------------------------------------------------------------------------

@st.composite
def _struct_error(draw):
    kind = draw(st.integers(min_value=0, max_value=11))
    k = draw(_string())
    v = draw(_leaf)
    if kind == 0:
        # missing closing bracket
        return "[" + v
    if kind == 1:
        # missing closing brace
        return "{" + k + ":" + v
    if kind == 2:
        # mismatched delimiters
        return draw(st.sampled_from([
            "[" + v + "}",
            "{" + k + ":" + v + "]",
            "[" + v + "]]",
            "{" + k + ":" + v + "}}",
        ]))
    if kind == 3:
        # missing comma between elements
        return "[" + v + " " + draw(_leaf) + "]"
    if kind == 4:
        # missing colon in object
        return "{" + k + " " + v + "}"
    if kind == 5:
        # missing value after colon
        return "{" + k + ":}"
    if kind == 6:
        # missing key
        return "{:" + v + "}"
    if kind == 7:
        # leading comma
        return "[," + v + "]"
    if kind == 8:
        # trailing comma
        return "[" + v + ",]"
    if kind == 9:
        # object trailing comma
        return "{" + k + ":" + v + ",}"
    if kind == 10:
        # extra colon / separator
        return "{" + k + "::" + v + "}"
    # kind 11: bare structural noise surrounded by brackets
    return "[" + draw(st.sampled_from([":", ",", "]", "}", "{", "["])) + "]"


@st.composite
def _deep_truncated(draw):
    depth = draw(st.integers(min_value=100, max_value=1002))
    opener = draw(st.sampled_from(["[", '{"k":']))
    s = opener * depth
    cut = draw(st.integers(min_value=0, max_value=len(s)))
    return s[:cut]


strategy = st.one_of(
    _valid_value,
    _with_trailing,
    _with_bom,
    _whitespace_wrapped,
    _deep_array(),
    _deep_object(),
    _malformed,
    _raw_bytes,
    _mutated(),
    _truncated_container(),
    _incomplete,
    _ws_value,
    _interleaved(),
    _mixed_deep(),
    _noisy,
    _struct_error(),
    _deep_truncated(),
)
```