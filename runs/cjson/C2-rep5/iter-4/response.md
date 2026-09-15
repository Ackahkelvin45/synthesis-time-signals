```python
import json
from hypothesis import strategies as st

# ---------- leaf fragments ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.text(alphabet=_hex, min_size=4, max_size=4)

# escapes that are valid per grammar
_simple_esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

# \uXXXX plus a few surrogate-ish escapes (some lone surrogates -> rejected)
_unicode_esc = st.builds(lambda h: "\\u" + h, _hex4())

# Surrogate pair escapes (valid in many parsers) and lone surrogates
_high_surrogate = st.integers(min_value=0xD800, max_value=0xDBFF).map(lambda n: "\\u%04x" % n)
_low_surrogate = st.integers(min_value=0xDC00, max_value=0xDFFF).map(lambda n: "\\u%04x" % n)
_surrogate_pair = st.builds(lambda a, b: a + b, _high_surrogate, _low_surrogate)
_lone_surrogate = st.one_of(_high_surrogate, _low_surrogate)

# Raw control / NUL bytes and other safe-ish code points inside strings
_control_char = st.integers(min_value=0, max_value=0x1F).map(chr)
_raw_nul = st.just("\x00")

# SAFECODEPOINT: anything except '"', '\\', and control chars (0x00-0x1F)
# We allow a broad range of unicode to exercise the parser.
_safe_cp = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates as raw code points
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
                         '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

# A string body piece: safe code point, escape, unicode escape, surrogate pair,
# lone surrogate (rejected), raw control, or raw NUL (accepted by this parser).
_string_piece = st.one_of(
    _safe_cp,
    _simple_esc,
    _unicode_esc,
    _surrogate_pair,
    _lone_surrogate,
    _control_char,
    _raw_nul,
)

# Build string bodies. Keep mostly small, occasionally long.
_string_body_small = st.lists(_string_piece, min_size=0, max_size=8).map("".join)
_string_body_long = st.lists(_string_piece, min_size=0, max_size=200).map("".join)
_string_body = st.one_of(_string_body_small, _string_body_long)

# A well-formed JSON string (grammar-valid, except we also allow raw controls/NUL)
_string = st.builds(lambda b: '"' + b + '"', _string_body)

# Also produce deliberately unterminated strings (missing closing quote)
_unterminated_string = st.builds(lambda b: '"' + b, _string_body_small)

# ---------- numbers ----------

# Valid per grammar: -? INT ('.' [0-9]+)? EXP?
_digits = st.text(alphabet="0123456789", min_size=1, max_size=25)
_nonzero_digits = st.text(alphabet="0123456789", min_size=1, max_size=25).filter(
    lambda s: s[0] != "0"
) if False else st.text(alphabet="0123456789", min_size=1, max_size=25)

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d: d, _nonzero_digits),
)

# Deviations the parser accepts:
_leading_zero_int = st.builds(lambda d: "0" + d, _digits)
_trailing_dot = st.builds(lambda i: i + ".", _int_part)
_hex_number = st.builds(lambda h: "0x" + h, st.text(alphabet=_hex, min_size=1, max_size=16))

# Rejected numeric forms (should be rejected by the parser)
_rejected_numbers = st.sampled_from([
    "-", "+1", ".5", "-.5", "+.5", "NaN", "Infinity", "-Infinity", "nan", "inf",
])

_frac = st.builds(lambda d: "." + d, _digits)
_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    _digits,
)

# Extreme exponents/magnitudes (some overflow to inf, accepted)
_extreme_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=400),
)

_plain_number = st.builds(
    lambda sign, i, f, e: sign + i + f + e,
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

_big_number = st.builds(
    lambda sign, i, f, e: sign + i + f + e,
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.just(""), _frac),
    _extreme_exp,
)

_number = st.one_of(
    _plain_number,
    _big_number,
    _leading_zero_int,
    _trailing_dot,
    _hex_number,
    _rejected_numbers,
)

# ---------- whitespace ----------

_ws = st.text(alphabet=" \t\n\r", min_size=0, max_size=4)
_ws_required = st.text(alphabet=" \t\n\r", min_size=1, max_size=4)

# ---------- literals ----------

# Upweight true/false to close the productions_gap.
_literal = st.one_of(
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.sampled_from(["true", "false"]),
    st.just("null"),
)

# ---------- malformed structural fragments ----------

_double_comma = st.just(",")
_missing_colon = st.just(" ")
_trailing_comma_arr = st.just(",]")
_trailing_comma_obj = st.just(",}")

# ---------- recursive JSON values ----------

def _make_strategy():
    # Base (non-recursive) values
    base = st.one_of(
        _string,
        _unterminated_string,
        _number,
        _literal,
    )

    # Composite helpers must be defined before use in recursive.
    @st.composite
    def _pair(draw):
        key = draw(_string)
        colon = draw(st.sampled_from([":", " :", ": ", " : "]))
        val = draw(value)
        return key + colon + val

    @st.composite
    def _obj(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        if n == 0:
            return "{}"
        parts = draw(st.lists(_pair(), min_size=n, max_size=n))
        sep = draw(st.sampled_from([",", ", ", " ,"]))
        inner = sep.join(parts)
        # occasionally inject malformed bits
        malformed = draw(st.one_of(
            st.just(""),
            _double_comma.map(lambda s: s),
            _missing_colon.map(lambda s: s),
            _trailing_comma_obj.map(lambda s: s),
        ))
        return "{" + inner + malformed + "}"

    @st.composite
    def _arr(draw):
        n = draw(st.integers(min_value=0, max_value=6))
        if n == 0:
            return "[]"
        parts = draw(st.lists(value, min_size=n, max_size=n))
        sep = draw(st.sampled_from([",", ", ", " ,"]))
        inner = sep.join(parts)
        malformed = draw(st.one_of(
            st.just(""),
            _double_comma.map(lambda s: s),
            _trailing_comma_arr.map(lambda s: s),
        ))
        return "[" + inner + malformed + "]"

    # Recursive value: leaves plus obj/arr
    value = st.recursive(
        base,
        lambda children: st.one_of(_obj(), _arr()),
        max_leaves=20,
    )
    return value

_value = _make_strategy()

# ---------- deep nesting near the 1000-level limit ----------

def _nested_array(depth):
    return "[" * depth + "]" * depth

def _nested_object(depth):
    return "{" + '"a":' * depth + "null" + "}" * depth

# Depths near the limit: 999, 1000, 1001, and a few around them.
_near_limit_depth = st.sampled_from([
    0, 1, 2, 10, 100, 500, 900, 998, 999, 1000, 1001, 1002, 1200,
])

_deep_array = _near_limit_depth.map(_nested_array)
_deep_object = _near_limit_depth.map(_nested_object)

# Mixed deep nesting: arrays inside objects, etc.
@st.composite
def _deep_mixed(draw):
    depth = draw(_near_limit_depth)
    kind = draw(st.sampled_from(["arr", "obj", "alt"]))
    if kind == "arr":
        return _nested_array(depth)
    if kind == "obj":
        return _nested_object(depth)
    # alternating
    out = []
    for i in range(depth):
        out.append("[" if i % 2 == 0 else '{"k":')
    # close in reverse
    for i in reversed(range(depth)):
        out.append("]" if i % 2 == 0 else "}")
    # Need a value at the innermost point; for alternating we must ensure
    # the innermost is a valid value position.
    return "".join(out)

_deep = st.one_of(_deep_array, _deep_object, _deep_mixed())

# ---------- top-level value with optional whitespace, BOM, trailing junk ----------

_bom = st.sampled_from(["", "\ufeff"])

# Trailing content is accepted by the parser; include it sometimes.
_trailing = st.one_of(
    st.just(""),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("\x00"),
    st.just(" garbage"),
    st.just("}"),
    st.just("]"),
    st.just(","),
)

@st.composite
def _top(draw):
    lead = draw(_ws)
    bom = draw(_bom)
    val = draw(st.one_of(_value, _deep))
    trail = draw(_trailing)
    return bom + lead + val + trail

# ---------- extra malformed top-level inputs ----------

_malformed_top = st.sampled_from([
    "",
    " ",
    "\n",
    "{",
    "}",
    "[",
    "]",
    "{,}",
    "[,]",
    '{"a"}',
    '{"a":}',
    '{"a":1,}',
    "[1,]",
    "[1,,2]",
    '"unterminated',
    "'single'",
    "{'a':1}",
    "{a:1}",
    "+1",
    "-",
    ".5",
    "NaN",
    "Infinity",
    "-Infinity",
    "01",
    "1.",
    "0x10",
    "1e309",
    "1e-400",
    "\x00",
    '"\\ud800"',
    '"\\udc00"',
    '"\\ud800\\udc00"',
    '"\\uD83D\\uDE00"',
    '"\\uZZZZ"',
    '"\\x41"',
    '"\\u12"',
    "true",
])

strategy = st.one_of(
    _top(),
    _malformed_top,
    _deep,
)
```