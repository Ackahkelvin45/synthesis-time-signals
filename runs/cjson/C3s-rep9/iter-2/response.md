```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# A "safe" code point: not a quote, not a backslash, not a control char.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\u0000\u0001\u0002\u0003\u0004\u0005\u0006\u0007'
    "\u0008\u0009\u000a\u000b\u000c\u000d\u000e\u000f\u0010\u0011\u0012"
    "\u0013\u0014\u0015\u0016\u0017\u0018\u0019\u001a\u001b\u001c\u001d"
    "\u001e\u001f\\',
)

# Control chars / NUL that the parser accepts raw inside strings.
_raw_control = st.sampled_from(
    ["\u0000", "\u0001", "\t", "\n", "\r", "\u001f", "\u000b", "\u000c"]
)

# Valid two-char escapes.
_short_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    _hex_digit, _hex_digit, _hex_digit, _hex_digit,
)

# Lone surrogate escapes (parser rejects these) -- still useful as fuzz input.
_surrogate_escape = st.builds(
    lambda h, l: "\\u" + h + l,
    st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DC00"]),
    st.sampled_from(["0000", "0041", "ffff", "FFFF", "d800", "dc00"]),
)

# Malformed escapes for near-valid inputs.
_bad_escape = st.sampled_from(
    ["\\x", "\\u12", "\\u", "\\", "\\U0041", "\\uZZZZ", "\\q"]
)

_string_piece = st.one_of(
    _safe_chars,
    _raw_control,
    _short_escapes,
    _unicode_escape,
    _surrogate_escape,
    _bad_escape,
)

# A proper JSON string.
_string = st.builds(
    lambda inner: '"' + inner + '"',
    st.lists(_string_piece, max_size=12).map("".join),
)

# Unterminated strings (near-valid-but-malformed).
_unterminated_string = st.builds(
    lambda inner: '"' + inner,
    st.lists(_string_piece, min_size=1, max_size=12).map("".join),
)

# ---------------------------------------------------------------------------
# Numbers: valid, extreme, and near-valid-but-malformed
# ---------------------------------------------------------------------------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=20)

_valid_int = st.one_of(
    st.just("0"),
    st.builds(lambda s: s, st.integers(min_value=-10**18, max_value=10**18).map(str)),
    st.builds(lambda s: s, st.integers().map(str)),
)

# Extreme magnitudes / exponents, including overflow-ish like 1e309.
_extreme_number = st.sampled_from(
    [
        "1e309", "-1e309", "1e-309", "1e308", "1e999", "-1e999",
        "0e0", "0E0", "1e01", "1E+01", "1e-01", "1E-0",
        "123456789012345678901234567890",
        "-123456789012345678901234567890",
        "1.7976931348623157e308",
        "4.9406564584124654e-324",
        "2.2250738585072014e-308",
        "1e2147483647", "1e-2147483648",
        "0.1", "-0.0", "0.00000000000000000001",
        "99999999999999999999999999999999999999999999999999",
    ]
)

# Leading zeros, trailing dots, hex, etc. -- accepted by parser.
_lenient_number = st.sampled_from(
    [
        "01", "007", "-01", "00", "000",
        "1.", "-1.", "0.", "123.",
        "0x10", "0X1f", "-0xff", "0x0",
        "1e309", "-1e309",
    ]
)

# Malformed numbers: leading +, bare dot, lone minus.
_bad_number = st.sampled_from(
    ["+1", "+0", ".5", "-.5", "-", "+", ".", "-.", "+.5", "e5", "1e", "1e+", "1e-"]
)

_number = st.one_of(
    _valid_int,
    _extreme_number,
    _lenient_number,
    _bad_number,
)

# ---------------------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the ~1000 nesting limit.
# We build a depth-controlled recursive strategy.

_DEPTH_LIMIT = 1000


def _scalar():
    return st.one_of(
        _string,
        _unterminated_string,
        _number,
        st.sampled_from(["true", "false", "null", "True", "False", "NULL", "None"]),
    )


# Use st.recursive with a bounded depth via a custom composite that tracks depth.
# st.recursive uses a max_leaves; we instead use a composite with explicit depth.

@st.composite
def _value(draw, depth=0):
    # Near the limit, force scalars to avoid pathological blowup.
    if depth >= _DEPTH_LIMIT:
        return draw(_scalar())

    choice = draw(st.integers(min_value=0, max_value=9))
    if choice < 5:
        return draw(_scalar())
    if choice < 7:
        return draw(_obj(depth + 1))
    if choice < 9:
        return draw(_arr(depth + 1))
    # Occasionally jump depth by a large step toward the limit.
    jump = draw(st.integers(min_value=0, max_value=50))
    return draw(_value(depth + 1 + jump))


@st.composite
def _pair(draw, depth):
    key = draw(st.one_of(_string, _unterminated_string))
    sep = draw(st.sampled_from([":", "", "::", " : "]))
    val = draw(_value(depth))
    return key + sep + val


@st.composite
def _obj(draw, depth=0):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "{}"
    pairs = [draw(_pair(depth)) for _ in range(n)]
    sep = draw(st.sampled_from([",", ", ", ",,"]))
    body = sep.join(pairs)
    trailing = draw(st.sampled_from(["", ",", ", ", " ,"]))
    return "{" + body + trailing + "}"


@st.composite
def _arr(draw, depth=0):
    n = draw(st.integers(min_value=0, max_value=4))
    if n == 0:
        return "[]"
    vals = [draw(_value(depth)) for _ in range(n)]
    sep = draw(st.sampled_from([",", ", ", ",,"]))
    body = sep.join(vals)
    trailing = draw(st.sampled_from(["", ",", ", ", " ,"]))
    return "[" + body + trailing + "]"


# ---------------------------------------------------------------------------
# Deep nesting generators: near the 1000-level boundary
# ---------------------------------------------------------------------------

_deep_array = st.integers(min_value=0, max_value=1100).map(
    lambda n: "[" * n + "]" * n
)
_deep_object = st.integers(min_value=0, max_value=1100).map(
    lambda n: '{"a":' * n + "null" + "}" * n
)
_deep_mixed = st.integers(min_value=0, max_value=1100).map(
    lambda n: "[" * n + "{}" + "]" * n
)

# ---------------------------------------------------------------------------
# Top-level: value, with optional BOM, leading/trailing garbage, NULs
# ---------------------------------------------------------------------------

_bom = st.sampled_from(["", "\ufeff"])
_ws = st.text(alphabet=" \t\n\r", max_size=4)
_nul = st.sampled_from(["", "\u0000", "\u0000\u0000"])

_top_value = st.one_of(
    _value(0),
    _obj(0),
    _arr(0),
    _deep_array,
    _deep_object,
    _deep_mixed,
    _scalar(),
)

# Trailing content is accepted by the parser, so include it often.
_trailing = st.one_of(
    st.just(""),
    st.just("\u0000"),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("{}[]"),
    st.just("\ufeff"),
    st.text(max_size=8),
)

_leading = st.one_of(
    st.just(""),
    _ws,
    st.just("\u0000"),
    st.just("\ufeff"),
)

strategy = st.builds(
    lambda lead, bom, val, trail: lead + bom + val + trail,
    _leading,
    _bom,
    _top_value,
    _trailing,
)
```