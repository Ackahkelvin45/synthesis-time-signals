```python
from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

# SAFECODEPOINT: ~ ["\\\u0000-\u001F] plus we deliberately include control/NUL bytes
# for the "embedded NUL/control" edge class (parser takes explicit length).
_plain_char = st.characters(
    blacklist_categories=["Cs"],  # keep lone surrogates out of raw text; use escapes instead
    blacklist_characters='"\\',
)
# control bytes / NUL allowed and encouraged
_control_char = st.sampled_from(["\x00", "\x01", "\x02", "\x08", "\x0b", "\x0c", "\x1f", "\x7f"])

_string_body_char = st.one_of(_plain_char, _control_char)

# ESC fragment pieces
_esc_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_esc_unicode = _hex4.map(lambda h: "\\u" + h)

# surrogate escapes (lone + paired) are valuable edge inputs
_esc_surrogate = st.sampled_from(
    ["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uD834\\uDD1E", "\\u0000"]
)

_esc = st.one_of(_esc_simple, _esc_unicode, _esc_surrogate)

_string_inner = st.one_of(_string_body_char, _esc)

# A well-formed JSON string literal
_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_string_inner, min_size=0, max_size=12),
)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
)

_frac = st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n))

_exp = st.builds(
    lambda e, sign, digits: e + sign + digits,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=10**4).map(str),
)

_sign = st.sampled_from(["", "-"])

# valid-ish numbers, including overflow magnitudes
_valid_number = st.builds(
    lambda s, i, f, e: s + i + f + e,
    _sign,
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

# extreme magnitudes / exponents (overflow like 1e309, huge digits)
_extreme_number = st.one_of(
    st.sampled_from(
        [
            "1e309", "-1e309", "1e-309", "1e999999", "-1e999999",
            "0e0", "0e999999", "1E+308", "1E-308",
            "9" * 30, "-" + "9" * 30,
            "1" + "0" * 30, "1." + "0" * 30,
        ]
    ),
    st.builds(
        lambda m: "1e" + str(m),
        st.integers(min_value=300, max_value=10**6),
    ),
)

# malformed / near-valid numbers (parser rejects these: good edge inputs)
_bad_number = st.sampled_from(
    ["+1", ".5", "1.", "01", "00", "-01", "0x1F", "1e", "1e+", "--1", "1..2", "1e1.5"]
)

_number = st.one_of(_valid_number, _extreme_number, _bad_number)

# lone "-" is accepted by the parser; keep as its own edge
_lone_dash = st.just("-")

# ---------- malformed string fragments (near-valid-but-malformed) ----------

_unterminated_string = st.builds(
    lambda s: '"' + s,
    st.text(alphabet="abcXYZ 0123", min_size=0, max_size=8),
)

_bad_escape = st.sampled_from(['"\\x"', '"\\u12"', '"\\uZZZZ"', '"\\"'])

# ---------- whitespace ----------

_ws = st.text(alphabet=" \t\n\r", min_size=0, max_size=3)

# ---------- recursive JSON structure ----------

# We use st.recursive with a base of scalars and a recursive branch building
# obj/arr via @st.composite-style lambdas that return strings.

_json_scalar = st.one_of(
    _string,
    _number,
    _lone_dash,
    st.sampled_from(["true", "false", "null"]),
    _unterminated_string,
    _bad_escape,
)


@st.composite
def _obj(draw, child):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        # empty object, optionally with a single trailing comma variant
        return draw(st.sampled_from(["{}", "{,}"]))
    pairs = []
    for _ in range(n):
        k = draw(_string)
        v = draw(child)
        pairs.append(k + draw(_ws) + ":" + draw(_ws) + v)
    body = ("," + draw(_ws)).join(pairs)
    # sometimes add a single trailing comma (parser accepts exactly one)
    trailing = draw(st.one_of(st.just(""), st.just(",")))
    return "{" + body + trailing + "}"


@st.composite
def _arr(draw, child):
    n = draw(st.integers(min_value=0, max_value=5))
    if n == 0:
        return draw(st.sampled_from(["[]", "[,]"]))
    items = [draw(child) for _ in range(n)]
    body = ("," + draw(_ws)).join(items)
    trailing = draw(st.one_of(st.just(""), st.just(",")))
    return "[" + body + trailing + "]"


# Bias toward objects-with-members (the stressed first-pass path).
def _make_value(child):
    return st.one_of(
        _obj(child),
        _obj(child),
        _arr(child),
        _json_scalar,
    )


_json_value = st.recursive(
    _json_scalar,
    _make_value,
    max_leaves=40,
)

# ---------- explicit deep nesting (no cap in parser) ----------

_deep_nesting = st.builds(
    lambda d, kind: ("{" + '"a":' if kind == "obj" else "[") * d
    + "null"
    + ("}" if kind == "obj" else "]") * d,
    st.integers(min_value=1, max_value=200),
    st.sampled_from(["obj", "arr"]),
)

# ---------- malformed top-level shapes ----------

_malformed_top = st.sampled_from(
    [
        "[1,,2]",
        "[,1]",
        "[,]",
        "{,}",
        '{"a" 1}',
        '{"a":}',
        '{"a":1,,"b":2}',
        "{:1}",
        "{a:1}",
        "'x'",
        "1abc",
        "[]xyz",
        "true false",
        "1 garbage",
        "//x\n1",
        "/* */1",
        '{"a":1}extra',
        '"unterminated',
    ]
)

# ---------- duplicate keys bias: build an object with repeated keys explicitly ----------

_dup_keys = st.builds(
    lambda k, v1, v2: '{"' + k + '":' + v1 + ',"' + k + '":' + v2 + "}",
    st.text(alphabet="abcXY", min_size=1, max_size=4),
    st.one_of(_valid_number, st.just("null"), st.just("true")),
    st.one_of(_valid_number, st.just("null"), st.just("false")),
)

# ---------- top-level strategy ----------

_value_with_ws = st.builds(
    lambda v: v,
    _json_value,
)

strategy = st.one_of(
    _value_with_ws,
    _dup_keys,
    _deep_nesting,
    _malformed_top,
    st.sampled_from(["{}", "[]", "null", "true", "false", "-", "1e309"]),
)
```