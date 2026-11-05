from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map(lambda t: "".join(t))

def _escaped_char():
    simple = st.sampled_from(['"', "\\", "/", "b", "f", "n", "r", "t"])
    return st.one_of(
        simple.map(lambda c: "\\" + c),
        _hex4().map(lambda h: "\\u" + h),
    )

# Characters that may appear raw inside a string.  Include control chars and NUL
# because the parser accepts them; also include interesting escapes.
_raw_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    st.sampled_from(["\x00", "\t", "\n", "\r", "\x01", "\x1f", "\x7f"]),
    st.characters(min_codepoint=0x80, max_codepoint=0x2000),
    st.sampled_from(['"', "\\"]).map(lambda c: c),  # will be escaped below
)

def _string_body_piece():
    return st.one_of(
        st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
            lambda c: c not in '"\\'
        ),
        st.sampled_from(["\x00", "\t", "\n", "\r", "\x01", "\x1f", "\x7f"]),
        st.characters(min_codepoint=0x80, max_codepoint=0x2000),
        _escaped_char(),
    )

_string_body = st.lists(_string_body_piece(), max_size=12).map(lambda xs: "".join(xs))

def _string():
    return _string_body.map(lambda b: '"' + b + '"')

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=8)

def _number():
    int_part = st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), _digits).map(lambda t: t[0] + t[1]),
        # leading zeros (accepted by parser)
        st.tuples(st.sampled_from("0123456789"), _digits).map(lambda t: t[0] + t[1]),
        _digits,
    )
    sign = st.one_of(st.just(""), st.just("-"))
    frac = st.one_of(
        st.just(""),
        st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
        st.just("."),  # trailing dot
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from("eE"),
            st.one_of(st.just(""), st.just("+"), st.just("-")),
            _digits,
        ).map(lambda t: t[0] + t[1] + t[2]),
        # extreme exponents
        st.sampled_from(["e309", "e9999", "e-9999", "E+400", "e308", "e-400"]),
    )
    return st.tuples(sign, int_part, frac, exp).map(lambda t: "".join(t))

# ---------------------------------------------------------------------------
# Recursive values
# ---------------------------------------------------------------------------

_ws = st.one_of(st.just(""), st.sampled_from([" ", "\t", "\n", "\r", "  "]))

def _ws_between():
    return _ws

def _make_value(children):
    base = st.one_of(
        _string(),
        _number(),
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )
    if children is None:
        return base
    return st.one_of(base, children)

def _pair(children):
    return st.tuples(
        _string(), _ws, st.just(":"), _ws, children
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])

def _obj(children):
    pair = _pair(children)
    empty = st.just("{}")
    nonempty = st.tuples(
        st.just("{"),
        _ws,
        st.lists(pair, min_size=1, max_size=4),
        _ws,
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + (("," + "").join(t[2])) + t[3] + t[4])
    return st.one_of(empty, nonempty)

def _arr(children):
    empty = st.just("[]")
    nonempty = st.tuples(
        st.just("["),
        _ws,
        st.lists(children, min_size=1, max_size=5),
        _ws,
        st.just("]"),
    ).map(lambda t: t[0] + t[1] + ",".join(t[2]) + t[3] + t[4])
    return st.one_of(empty, nonempty)

_value = st.recursive(
    _make_value(None),
    lambda children: _make_value(st.one_of(_obj(children), _arr(children))),
    max_leaves=40,
)

# ---------------------------------------------------------------------------
# Deep nesting near the 1000-level limit
# ---------------------------------------------------------------------------

def _deep(depth):
    return st.tuples(
        st.just("[" * depth + "]" * depth),
        st.just("[" * depth + "1" + "]" * depth),
        st.just('{"a":' * depth + "0" + "}" * depth),
    )

_deep_strategy = st.one_of(
    st.integers(min_value=990, max_value=1010).flatmap(_deep),
    _deep(1000),
    _deep(1001),
    _deep(999),
)

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_malformed = st.sampled_from([
    "",
    " ",
    "[,]",
    "[1,]",
    '{"a":1,}',
    '{"a"}',
    '{"a" 1}',
    '{"a":}',
    "{:1}",
    "[1,,2]",
    '{"a":1 "b":2}',
    '"unterminated',
    '["unterminated]',
    "-",
    "+1",
    ".5",
    "01",
    "1.",
    "0x10",
    "NaN",
    "Infinity",
    "-Infinity",
    '"\\ud800"',
    '"\\udfff"',
    '"\\uD800\\uDC00"',
    '"\\u12"',
    '"\\q"',
    "'single'",
    "{a:1}",
    "tru",
    "nul",
    "fals",
    "[",
    "{",
    "]",
    "}",
    ",",
    ":",
    "\x00",
    "\ufeff",
    "\ufeff1",
    "1\x00",
    '"a\x00b"',
    '"a\tb"',
    '"a\nb"',
    "1abc",
    "1 2",
    "{}[]",
])

# ---------------------------------------------------------------------------
# Combine
# ---------------------------------------------------------------------------

_value_with_ws = st.tuples(_ws, _value, _ws).map(lambda t: t[0] + t[1] + t[2])

strategy = st.one_of(
    _value_with_ws,
    _deep_strategy,
    _malformed,
    # trailing content after a valid value (accepted)
    st.tuples(_value, st.sampled_from(["abc", " 1", "\x00", "{}", "[]"])).map(
        lambda t: t[0] + t[1]
    ),
    # BOM prefix
    st.tuples(st.just("\ufeff"), _value).map(lambda t: t[0] + t[1]),
).map(lambda s: s if isinstance(s, str) else str(s))