```python
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Primitive leaves
# ---------------------------------------------------------------------------

# Characters that are "safe" inside a JSON string per the grammar but that we
# also want to stress with control / NUL bytes (parser accepts them).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates from char gen itself
    blacklist_characters='"\\',
)

_control_chars = st.sampled_from(
    ["\x00", "\x01", "\x08", "\x09", "\x0a", "\x0b", "\x0c", "\x0d", "\x1f", "\x7f"]
)

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")


@st.composite
def _unicode_escape(draw):
    """A \uXXXX escape, sometimes a lone surrogate, sometimes a valid pair."""
    kind = draw(st.integers(min_value=0, max_value=4))
    h = lambda: draw(st.lists(_hex_digit, min_size=4, max_size=4).map("".join))
    if kind == 0:
        # arbitrary code unit (may be a lone surrogate -> rejected)
        return "\\u" + h()
    if kind == 1:
        # explicit high surrogate (lone -> rejected)
        return "\\u" + draw(st.sampled_from(["d800", "dbff", "d83d"]))
    if kind == 2:
        # explicit low surrogate (lone -> rejected)
        return "\\u" + draw(st.sampled_from(["dc00", "dfff", "de00"]))
    if kind == 3:
        # valid surrogate pair
        return "\\u" + draw(st.sampled_from(["d83d", "d800"])) + "\\u" + draw(
            st.sampled_from(["de00", "dc00", "dfff"])
        )
    # plain BMP escape
    return "\\u" + draw(st.sampled_from(["0041", "00e9", "20ac", "0000", "000a"]))


_simple_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_string_body_piece = st.one_of(
    _safe_chars,
    _control_chars,
    _simple_escape,
    _unicode_escape(),
    # invalid escapes (rejected) mixed in
    st.sampled_from(["\\x", "\\u12", "\\uzzzz", "\\", "\\U0001"]),
)


@st.composite
def _json_string(draw):
    """A quoted JSON string, possibly malformed (unterminated)."""
    n = draw(st.integers(min_value=0, max_value=8))
    body = "".join(draw(_string_body_piece) for _ in range(n))
    malformed = draw(st.integers(min_value=0, max_value=9))
    if malformed == 0:
        # unterminated string
        return '"' + body
    return '"' + body + '"'


# ---------------------------------------------------------------------------
# Numbers: valid, extreme, and near-valid-but-malformed
# ---------------------------------------------------------------------------

_int_part = st.one_of(
    st.just("0"),
    st.from_regex(r"[1-9][0-9]{0,5}", fullmatch=True),
    st.from_regex(r"[1-9][0-9]{15,25}", fullmatch=True),  # big ints
)

_frac_part = st.one_of(
    st.just(""),
    st.from_regex(r"\.[0-9]{1,10}", fullmatch=True),
)

_exp_part = st.one_of(
    st.just(""),
    st.sampled_from(["e309", "e308", "e-309", "E+400", "e0", "e01", "E-0", "e999"]),
)

_sign = st.one_of(st.just(""), st.just("-"))


@st.composite
def _json_number(draw):
    style = draw(st.integers(min_value=0, max_value=9))
    if style <= 5:
        return draw(_sign) + draw(_int_part) + draw(_frac_part) + draw(_exp_part)
    if style == 6:
        # hex (accepted by parser)
        return draw(st.one_of(st.just(""), st.just("-"))) + "0x" + draw(
            st.from_regex(r"[0-9a-fA-F]{1,8}", fullmatch=True)
        )
    if style == 7:
        # leading zeros (accepted)
        return "0" + draw(st.from_regex(r"[0-9]{1,5}", fullmatch=True))
    if style == 8:
        # trailing dot (accepted)
        return draw(_sign) + draw(_int_part) + "."
    # malformed numbers (rejected)
    return draw(
        st.sampled_from(
            ["-", "+1", ".5", "-.5", "1e", "1e+", "--1", "1..2", "01.2.3", "1e309e"]
        )
    )


# ---------------------------------------------------------------------------
# Recursive obj / arr
# ---------------------------------------------------------------------------

_literal = st.sampled_from(["true", "false", "null"])

# Non-recursive value leaves
_leaf_value = st.one_of(_json_string(), _json_number(), _literal)

# Malformed fragments used to inject near-valid-but-broken structure
_malformed_fragment = st.sampled_from(
    [
        ",",
        ",,",
        ":",
        "::",
        "{,",
        "[,",
        "{:}",
        "[,]",
        "{,}",
        '"a":',
        ':"b"',
        "{",
        "}",
        "[",
        "]",
        '{"a" 1}',
        "[1 2]",
        '{"a":1,}',
        "[1,]",
        "{,}",
    ]
)


@st.composite
def _json_value(draw, depth):
    """Draw a value, recursing with a controlled depth budget."""
    # Bias toward leaves as we approach the budget.
    if depth <= 0:
        return draw(st.one_of(_leaf_value, _malformed_fragment))
    roll = draw(st.integers(min_value=0, max_value=9))
    if roll <= 4:
        return draw(_leaf_value)
    if roll == 5:
        return draw(_malformed_fragment)
    if roll <= 7:
        return draw(_json_array(depth - 1))
    return draw(_json_object(depth - 1))


@st.composite
def _json_array(draw, depth):
    n = draw(st.integers(min_value=0, max_value=4))
    items = [draw(_json_value(depth)) for _ in range(n)]
    body = ",".join(items)
    # occasionally inject malformed array punctuation
    bad = draw(st.integers(min_value=0, max_value=9))
    if bad == 0:
        return "[" + body + ",]"          # trailing comma (rejected)
    if bad == 1:
        return "[" + body + ",," + "]"    # double comma (rejected)
    if bad == 2:
        return "[" + body              # unterminated (rejected)
    return "[" + body + "]"


@st.composite
def _json_object(draw, depth):
    n = draw(st.integers(min_value=0, max_value=4))
    pairs = []
    for _ in range(n):
        key = draw(_json_string())
        sep_style = draw(st.integers(min_value=0, max_value=9))
        val = draw(_json_value(depth))
        if sep_style == 0:
            pairs.append(key + " " + val)      # missing colon (rejected)
        elif sep_style == 1:
            pairs.append(key + "::" + val)     # double colon (rejected)
        else:
            pairs.append(key + ":" + val)
    body = ",".join(pairs)
    bad = draw(st.integers(min_value=0, max_value=9))
    if bad == 0:
        return "{" + body + ",}"              # trailing comma (rejected)
    if bad == 1:
        return "{" + body + ",," + "}"        # double comma (rejected)
    if bad == 2:
        return "{" + body                     # unterminated (rejected)
    return "{" + body + "}"


# ---------------------------------------------------------------------------
# Depth targeting: concentrate near the ~1000 nesting limit
# ---------------------------------------------------------------------------

@st.composite
def _deep_nesting(draw):
    """Generate deeply nested arrays/objects near the 1000-level limit."""
    target = draw(
        st.one_of(
            st.integers(min_value=0, max_value=50),
            st.integers(min_value=950, max_value=1005),
            st.sampled_from([999, 1000, 1001, 1002]),
        )
    )
    opener = draw(st.sampled_from(["[", "{"]))
    if opener == "[":
        closer = "]"
        inner = draw(st.one_of(_leaf_value, st.just("")))
    else:
        closer = "}"
        # objects need a key:value at the innermost level
        inner = draw(st.one_of(_json_string(), st.just('"k"'))) + ":" + draw(
            _leaf_value
        )
    return opener * target + inner + closer * target


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

@st.composite
def _top_level(draw):
    kind = draw(st.integers(min_value=0, max_value=9))

    if kind == 0:
        # deep nesting near the limit
        return draw(_deep_nesting())

    if kind == 1:
        # empty containers and duplicates
        return draw(
            st.sampled_from(
                [
                    "{}",
                    "[]",
                    '{"a":1,"a":2,"a":3}',
                    '{"":0,"":1}',
                    '{"a":{},"b":[]}',
                    "[[],{},[{}]]",
                    '{"x":{"y":{"z":[1,2,3]}}}',
                ]
            )
        )

    if kind == 2:
        # extreme numeric magnitudes
        return draw(
            st.sampled_from(
                [
                    "1e309",
                    "-1e309",
                    "1e-309",
                    "1e9999",
                    "0e0",
                    "123456789012345678901234567890",
                    "1.7976931348623157e308",
                    "-0.0",
                    "1E+400",
                ]
            )
        )

    if kind == 3:
        # escapes, surrogates, control/NUL bytes
        return draw(
            st.one_of(
                st.just('"\\ud800"'),
                st.just('"\\udc00"'),
                st.just('"\\ud83d\\ude00"'),
                st.just('"\\u0000"'),
                st.just('"\x00"'),
                st.just('"a\x00b"'),
                st.just('"tab\there"'),
                st.just('"new\nline"'),
                st.just('"\\uZZZZ"'),
                st.just('"\\q"'),
                _json_string(),
            )
        )

    if kind == 4:
        # malformed inputs
        return draw(
            st.sampled_from(
                [
                    "{,}",
                    "[,]",
                    '{"a":1,}',
                    "[1,]",
                    '{"a" 1}',
                    "[1 2]",
                    "{",
                    "[",
                    "}",
                    "]",
                    '"unterminated',
                    "-",
                    "+1",
                    ".5",
                    "NaN",
                    "Infinity",
                    "",
                ]
            )
        )

    if kind == 5:
        # leading BOM
        return "\ufeff" + draw(st.one_of(_leaf_value, _json_object(2), _json_array(2)))

    if kind == 6:
        # leading zeros / trailing dot / hex (accepted deviations)
        return draw(
            st.sampled_from(["01", "007", "1.", "-1.", "0x10", "0xFF", "-0x1", "00"])
        )

    if kind == 7:
        # trailing content after a complete value (accepted)
        first = draw(st.one_of(_leaf_value, _json_object(1), _json_array(1)))
        tail = draw(st.sampled_from(["abc", " 1 2", "\x00", "]}]", "garbage", "{" ]))
        return first + tail

    if kind == 8:
        # random objects/arrays
        return draw(st.one_of(_json_object(3), _json_array(3)))

    # general value
    return draw(_json_value(3))


strategy = _top_level()
```