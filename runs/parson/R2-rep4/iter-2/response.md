```python
from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

# Safe string characters (no raw NUL, no unescaped control chars, no quote/backslash)
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in the source text
    blacklist_characters='"\x00\\',
    min_codepoint=0x20,
    max_codepoint=0x10FFFF,
)

# Escapes that are valid inside a JSON string
_simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex = st.sampled_from("0123456789abcdefABCDEF")
_hex4 = st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_unicode_escapes = st.one_of(
    _hex4.map(lambda h: "\\u" + h),
    # surrogate pairs
    st.tuples(
        st.sampled_from("dD"), st.sampled_from("89abAB"), _hex, _hex
    ).map(lambda t: "\\u" + "".join(t)),
    st.tuples(
        st.sampled_from("dD"), st.sampled_from("cdefCDEF"), _hex, _hex
    ).map(lambda t: "\\u" + "".join(t)),
    # lone low surrogate escapes
    st.tuples(
        st.sampled_from("dD"), st.sampled_from("cdefCDEF"), _hex, _hex
    ).map(lambda t: "\\u" + "".join(t)),
    st.just("\\u0000"),
    st.just("\\u001f"),
    st.just("\\u007f"),
    st.just("\\uffff"),
    st.just("\\ufffe"),
)

_string_piece = st.one_of(
    _safe_chars.map(str),
    _simple_escapes,
    _unicode_escapes,
)

def _mk_string(pieces):
    return '"' + "".join(pieces) + '"'

_json_string = st.lists(_string_piece, max_size=8).map(_mk_string)

# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)
_nonzero_digits = st.text("0123456789", min_size=1, max_size=6).filter(
    lambda s: not s.startswith("0") or len(s) == 1
)

_int_part = st.one_of(
    st.just("0"),
    st.text("123456789", min_size=1, max_size=1).flatmap(
        lambda first: st.text("0123456789", min_size=0, max_size=6).map(
            lambda rest: first + rest
        )
    ),
)

_frac_part = st.one_of(
    st.just(""),
    st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1]),
)

_exp_part = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.text("0123456789", min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # extreme exponents
    st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.sampled_from(["308", "309", "310", "999", "1000", "400"]),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

def _mk_number(sign, ip, fp, ep):
    return sign + ip + fp + ep

_number = st.tuples(
    st.sampled_from(["", "-"]),
    _int_part,
    _frac_part,
    _exp_part,
).map(lambda t: _mk_number(*t))

# Extreme magnitude literals
_extreme_numbers = st.sampled_from([
    "1e309", "-1e309", "1e400", "-1e400", "1e308", "1.7976931348623157e308",
    "1.7976931348623159e308", "5e-324", "1e-400", "0e999", "-0", "0.0",
    "123456789012345678901234567890", "1e1000000", "9" * 30,
])

_literal = st.sampled_from(["true", "false", "null"])

# ---------- recursive structure ----------

# Malformed fragments for near-valid-but-malformed inputs
_malformed_tail = st.sampled_from([
    ",", ",,", ",]", ",}", ":", "::", '"', '""', "]", "}", " ",
    "1abc", "[]xyz", "{}garbage", "1 garbage", "-", "-.", ".5", "+1", "01",
    "tru", "nul", "fals", "\t", "\n", "\r",
])

_ws = st.sampled_from(["", " ", "\n", "\t", "\r", "  ", "\n\t"])

def _join(parts):
    return "".join(parts)

def _mk_obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _mk_arr(items):
    return "[" + ",".join(items) + "]"

def _mk_pair(k, v):
    return k + ":" + v

# We build the strategy recursively. Leaves are strings/numbers/literals.
# The recursion is bounded by Hypothesis' recursion machinery.

value_strategy = st.deferred(lambda: _value)

def _make_value():
    # A leaf or a (recursive) container.
    leaf = st.one_of(
        _json_string,
        _number,
        _extreme_numbers,
        _literal,
    )

    pair = st.tuples(_json_string, value_strategy).map(lambda t: _mk_pair(*t))
    obj = st.one_of(
        st.just("{}"),
        st.lists(pair, min_size=1, max_size=4).map(_mk_obj),
        # duplicate keys deliberately
        st.tuples(_json_string, value_strategy, value_strategy).map(
            lambda t: _mk_pair(t[0], t[1]) + "," + _mk_pair(t[0], t[2])
        ).map(lambda s: "{" + s + "}"),
    )

    arr = st.one_of(
        st.just("[]"),
        st.lists(value_strategy, min_size=1, max_size=4).map(_mk_arr),
    )

    return st.one_of(leaf, obj, arr)

_value = _make_value()

# ---------- top-level assembly ----------

# Deep nesting near the 2048 limit: build a chain of '[' * n + value + ']' * n
def _deep_nest(n, inner):
    return "[" * n + inner + "]" * n

_deep_depth = st.one_of(
    st.integers(min_value=2000, max_value=2048),
    st.integers(min_value=2045, max_value=2050),
    st.integers(min_value=1, max_value=20),
)

_deep = st.tuples(_deep_depth, value_strategy).map(
    lambda t: _deep_nest(t[0], t[1])
)

# Objects nested deeply too
_deep_obj = st.tuples(
    st.integers(min_value=1900, max_value=2048),
    _json_string,
    value_strategy,
).map(lambda t: '{"k":' * t[0] + t[2] + "}" * t[0])

# Near-valid-but-malformed: take a valid value and corrupt it
def _corrupt(v, tail):
    return v + tail

_malformed = st.tuples(value_strategy, _malformed_tail).map(
    lambda t: _corrupt(*t)
)

# Unterminated string
_unterminated = st.lists(_string_piece, max_size=6).map(
    lambda ps: '"' + "".join(ps)
)

# Missing colon / double comma forms
_missing_colon = st.tuples(_json_string, value_strategy).map(
    lambda t: "{" + t[0] + t[1] + "}"
)
_double_comma = st.tuples(value_strategy, value_strategy).map(
    lambda t: "[" + t[0] + ",," + t[1] + "]"
)
_leading_plus = st.tuples(_int_part, _frac_part, _exp_part).map(
    lambda t: "+" + t[0] + t[1] + t[2]
)
_leading_dot = st.tuples(_digits, _exp_part).map(
    lambda t: "." + t[0] + t[1]
)
_leading_zero = st.tuples(st.text("0123456789", min_size=1, max_size=4)).map(
    lambda t: "0" + t[0]
)

# Whitespace-wrapped valid values (WS is skipped by grammar)
_ws_wrapped = st.tuples(_ws, value_strategy, _ws).map(
    lambda t: t[0] + t[1] + t[2]
)

# Trailing content after a complete value (parser accepts)
_trailing = st.tuples(value_strategy, _malformed_tail).map(
    lambda t: t[0] + t[1]
)

# ---------- NEW: targeted error-path generators to raise branch coverage ----------

# Truncated valid values at arbitrary byte positions (exercises EOF handling
# in every state: mid-string, mid-number, mid-literal, mid-structure).
def _truncate(v, frac):
    n = len(v)
    if n == 0:
        return v
    k = int(n * frac)
    if k < 0:
        k = 0
    if k > n:
        k = n
    return v[:k]

_truncated = st.tuples(
    value_strategy,
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
).map(lambda t: _truncate(*t))

# Truncated deep structures (tests depth-limit + EOF interaction)
_truncated_deep = st.tuples(
    st.integers(min_value=1, max_value=2048),
    st.sampled_from(["", "1", '"x"', "true", "null", "[", "{"]),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
).map(lambda t: _truncate("[" * t[0] + t[1] + "]" * t[0], t[2]))

# Bad literals: close-but-wrong spellings of true/false/null
_bad_literal = st.sampled_from([
    "tru", "truE", "tRue", "True", "TRUE", "t", "tr",
    "fals", "falsE", "False", "FALSE", "f", "fa", "fal", "fals",
    "nul", "nulL", "Null", "NULL", "n", "nu",
    "truefalse", "nulltrue", "falsenull",
])

# Bad escapes inside strings
_bad_escape = st.sampled_from([
    '\\x', '\\u', '\\u1', '\\u12', '\\u123', '\\u12g4', '\\uZZZZ',
    '\\U0041', '\\', '"\\q"', '"\\u{41}"', '"a\\', '"\\uD800"',
    '"\\uDC00"', '"\\uD800\\uD800"', '"\\uD800x"',
])

# Bad structural forms
_bad_structure = st.sampled_from([
    "{", "}", "[", "]", "{]", "[}", "{,}", "[,]", "{:}", "[:]",
    '{"a"}', '{"a":}', '{"a":1,}', '[1,]', '[,1]', '[1,,2]',
    '{"a":1 "b":2}', '{"a" 1}', '{"a":1:2}', '[1 2]',
    '{}{}', '[][]', '{"a":1}{"b":2}', '[1][2]',
])

# Bad numbers
_bad_number = st.sampled_from([
    "-", "+", ".", "-.", "+.", ".e1", "1.", "1.e1", "01", "00",
    "-01", "+1", "1e", "1e+", "1e-", "1ee1", "1e1e1", "0x1", "Infinity",
    "NaN", "-Infinity", "1.2.3", "--1", "-+1", "1-", "1+",
])

# Raw control characters in strings (invalid unescaped)
_raw_control = st.sampled_from([
    '"\x01"', '"\x1f"', '"\x7f"', '"a\x01b"', '"\x0b"',
])

# UTF-8 / byte-level edge cases as text
_byte_edge = st.sampled_from([
    "\ufeff{}", "\ufeff[]", "\ufeff1",  # BOM
    "\u2028", "\u2029",                # line separators
    "\ufffd",                          # replacement char
    "\ud7ff", "\ue000",                # boundary around surrogates
])

# Empty-ish / whitespace-only
_ws_only = st.sampled_from(["", " ", "\n", "\t", "\r", "  \n\t ", "\n\n\n"])

_top = st.one_of(
    value_strategy,
    _deep,
    _deep_obj,
    _malformed,
    _unterminated,
    _missing_colon,
    _double_comma,
    _leading_plus,
    _leading_dot,
    _leading_zero,
    _ws_wrapped,
    _trailing,
    # newly added targeted error-path generators
    _truncated,
    _truncated_deep,
    _bad_literal,
    _bad_escape,
    _bad_structure,
    _bad_number,
    _raw_control,
    _byte_edge,
    _ws_only,
    st.just("{}"),
    st.just("[]"),
    st.just("-"),
    st.just(""),
)

# Filter out any raw NUL bytes (harness skips those)
def _no_nul(s):
    return "\x00" not in s

strategy = _top.filter(_no_nul)
```