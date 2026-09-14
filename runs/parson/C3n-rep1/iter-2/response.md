```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Safe string characters (no raw NUL, no unescaped control chars, no quote/backslash)
_SAFE = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\u0000"\\',
)

_ESCAPES = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_HEX = st.sampled_from("0123456789abcdefABCDEF")
_HEX4 = st.tuples(*([_HEX] * 4)).map("".join)


def _unicode_escape():
    return _HEX4.map(lambda h: "\\u" + h)


# Surrogate escapes (lone and paired) — valid text, potentially tricky
_SURROGATE_ESC = st.sampled_from(
    ["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
     "\\uD800\\uDC00", "\\uDBFF\\uDFFF", "\\uD800\\uD800"]
)

# Escapes that produce NUL / control chars as text (six-char escape, not raw byte)
_NUL_ESC = st.just("\\u0000")
_CTRL_ESC = st.sampled_from(
    ["\\u0001", "\\u001F", "\\u0007", "\\u000B", "\\u000C", "\\u001B"]
)


def _string_body():
    """Content between the quotes of a JSON string (no surrounding quotes)."""
    return st.one_of(
        st.lists(
            st.one_of(
                _SAFE,
                _ESCAPES,
                _unicode_escape(),
                _SURROGATE_ESC,
                _NUL_ESC,
                _CTRL_ESC,
            ),
            max_size=12,
        ).map("".join),
    )


def _quoted_string():
    return _string_body().map(lambda s: '"' + s + '"')


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
)

_EXP = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(e)),
)

_FRAC = st.integers(min_value=0, max_value=10**12).map(lambda f: "." + str(f))


def _number():
    return st.one_of(
        # plain ints
        _INT,
        # negative ints
        _INT.map(lambda s: "-" + s),
        # fractional
        st.tuples(_INT, _FRAC).map(lambda t: t[0] + t[1]),
        st.tuples(_INT, _FRAC).map(lambda t: "-" + t[0] + t[1]),
        # exponents
        st.tuples(_INT, _EXP).map(lambda t: t[0] + t[1]),
        st.tuples(_INT, _FRAC, _EXP).map(lambda t: t[0] + t[1] + t[2]),
        # extreme magnitudes / overflow-ish
        st.sampled_from([
            "1e309", "-1e309", "1e-309", "1e308", "1e-308",
            "9" * 30, "-" + "9" * 30,
            "1" + "0" * 300, "1e" + "9" * 5,
            "0.0000000000000000000000000001",
            "123456789012345678901234567890.123456789",
        ]),
        # lenient / near-valid number forms (parser may accept)
        st.sampled_from(["-", "-.", ".5", "1.", "+1", "01", "-01", "007"]),
    )


# ---------------------------------------------------------------------------
# Malformed fragments
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from([
    '{"a":}', '{"a"}', '{:1}', '{,}', '[,]', '[1,,2]', '[1 2]',
    '{"a":1,}', '[1,]', '"unterminated', '{"a":"x', '{',
    '[', '}', ']', ':', ',', 'tru', 'fals', 'nul', 'True', 'NULL',
    '{"a":1"b":2}', '{"a" 1}', '[1,2,3', '{"a":1}}', '[[[]]',
    '"\\x"', '"\\u12"', '"\\uZZZZ"', '{"a":+1}', '{"a":.5}',
    '{"a":01}', "'single'", '{a:1}', '{"a":1,,"b":2}',
])


# ---------------------------------------------------------------------------
# Recursive JSON value
# ---------------------------------------------------------------------------

def _leaf():
    return st.one_of(
        _quoted_string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _MALFORMED,
    )


def _value():
    return st.recursive(
        _leaf(),
        lambda children: st.one_of(
            st.lists(children, max_size=4).map(lambda xs: "[" + ",".join(xs) + "]"),
            st.lists(
                st.tuples(_quoted_string(), children),
                max_size=4,
            ).map(
                lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}"
            ),
        ),
        max_leaves=30,
    )


# ---------------------------------------------------------------------------
# Depth-targeted builders (near the 2048 cap)
# ---------------------------------------------------------------------------

def _deep_array(depth):
    return "[" * depth + "0" + "]" * depth


def _deep_object(depth):
    return '{"a":' * depth + "0" + "}" * depth


def _deep_arrays():
    return st.one_of(
        st.integers(min_value=1, max_value=50),
        st.integers(min_value=2000, max_value=2050),
        st.sampled_from([2047, 2048, 2049, 2050, 2100, 3000]),
    ).map(_deep_array)


def _deep_objects():
    return st.one_of(
        st.integers(min_value=1, max_value=50),
        st.integers(min_value=2000, max_value=2050),
        st.sampled_from([2047, 2048, 2049, 2050, 2100]),
    ).map(_deep_object)


# ---------------------------------------------------------------------------
# Duplicate-key objects
# ---------------------------------------------------------------------------

def _dup_keys():
    return st.tuples(
        _quoted_string(),
        _leaf(),
        _leaf(),
    ).map(lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}")


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

_WHITESPACE = st.sampled_from(["", " ", "\t", "\n", "\r\n", "  "])

_TRAILING = st.sampled_from([
    "", " ", "x", "abc", "garbage", "[]xyz", "1abc", "\n\t", "null",
])


def _with_trailing(base):
    return st.tuples(base, _TRAILING).map(lambda t: t[0] + t[1])


def _with_ws(base):
    return st.tuples(_WHITESPACE, base, _WHITESPACE).map(
        lambda t: t[0] + t[1] + t[2]
    )


def _empty_containers():
    return st.sampled_from(["{}", "[]", "{ }", "[ ]", "{\n}", "[\t]"])


def _build():
    core = st.one_of(
        _value(),
        _empty_containers(),
        _deep_arrays(),
        _deep_objects(),
        _dup_keys(),
    )
    return st.one_of(
        core,
        _with_trailing(core),
        _with_ws(core),
        _with_ws(_with_trailing(core)),
    )


strategy = _build()
```