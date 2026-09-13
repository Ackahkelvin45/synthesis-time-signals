from hypothesis import strategies as st
import json

# ---------- primitives ----------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)

# Characters that are safe inside a JSON string without escaping.
_string_body = st.text(
    alphabet=_safe_chars,
    min_size=0,
    max_size=12,
)

_hex = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_escapes = st.sampled_from(
    [
        '\\"',
        "\\\\",
        "\\/",
        "\\b",
        "\\f",
        "\\n",
        "\\r",
        "\\t",
    ]
).map(lambda s: s)

_unicode_escapes = _hex.map(lambda h: "\\u" + h)

# Surrogate escapes and other tricky unicode escapes.
_surrogate_escapes = st.sampled_from(
    [
        "\\uD800",
        "\\uDBFF",
        "\\uDC00",
        "\\uDFFF",
        "\\uD83D\\uDE00",
        "\\u0000",
        "\\u001F",
        "\\u007F",
        "\\uFFFF",
        "\\u00e9",
    ]
)

_escape_units = st.one_of(_escapes, _unicode_escapes, _surrogate_escapes)


def _join(parts):
    return "".join(parts)


_string_units = st.one_of(
    _string_body,
    _escape_units,
)

_string_inner = st.lists(_string_units, max_size=6).map(_join)

# A valid JSON string literal.
valid_string = _string_inner.map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=1, max_value=9)
    .flatmap(lambda d: st.text(alphabet="0123456789", min_size=0, max_size=16).map(lambda rest: str(d) + rest)),
)

_frac_part = st.text(alphabet="0123456789", min_size=1, max_size=12).map(lambda d: "." + d)

_exp_part = st.builds(
    lambda sign, digits: "e" + sign + digits,
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

# Extreme magnitudes / overflow exponents.
_extreme_numbers = st.sampled_from(
    [
        "1e309",
        "-1e309",
        "1e308",
        "1e-309",
        "1e-324",
        "1e400",
        "-1e400",
        "0e0",
        "0e999",
        "1E+308",
        "1E-308",
        "9" * 40,
        "-" + "9" * 40,
        "1." + "0" * 30,
        "0.000000000000000000000000000001",
        "123456789012345678901234567890.123456789012345678901234567890",
        "1e+000000000000000000000001",
    ]
)

_number_core = st.builds(
    lambda neg, ip, fp, ep: neg + ip + fp + ep,
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.just(""), _frac_part),
    st.one_of(st.just(""), _exp_part),
)

valid_number = st.one_of(_number_core, _extreme_numbers)

# ---------- literals ----------

valid_literal = st.sampled_from(["true", "false", "null"])

# ---------- keys ----------

_key_units = st.one_of(_string_body, _escape_units)
_key_inner = st.lists(_key_units, max_size=5).map(_join)
valid_key = _key_inner.map(lambda s: '"' + s + '"')

# A small pool of keys, to encourage duplicate-key collisions.
_common_keys = st.sampled_from(['"k"', '"a"', '"b"', '"key"', '""', '"x"', '"id"'])
any_key = st.one_of(valid_key, _common_keys)

# ---------- whitespace ----------

_ws = st.text(alphabet=" \t\n\r", min_size=0, max_size=3)


def ws(x):
    return _ws.flatmap(lambda a: _ws.map(lambda b: a + x + b))


# ---------- recursive values ----------

# We build values with a bounded depth. The parser rejects nesting > ~2048,
# so we concentrate interesting depth near that limit.

_max_depth = 2048

# Depth distribution: mostly shallow, sometimes near the cap.
_depth_choice = st.one_of(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=2000, max_value=_max_depth),
    st.integers(min_value=1000, max_value=1500),
)


def _pad(open_ch, close_ch, n):
    return open_ch * n + close_ch * n


# Deep nesting near the limit, built explicitly (not via recursion).
_deep_obj = _depth_choice.map(lambda n: "{" + ('"k":' * n) + "0" + ("}" * n))
_deep_arr = _depth_choice.map(lambda n: "[" * n + "0" + "]" * n)

# ---------- malformed / near-valid inputs ----------

_malformed = st.sampled_from(
    [
        # double commas
        "[1,,2]",
        '{"a":1,,"b":2}',
        "[,1]",
        "[1,]",
        '{"a":1,}',
        # missing colons
        '{"a" 1}',
        '{"a"}',
        '{"a":}',
        '{"a"::1}',
        # unterminated strings
        '"abc',
        '{"a": "abc}',
        '["abc]',
        '{"a":"b}',
        # leading + / .5 / 01
        "+1",
        ".5",
        "01",
        "00",
        "-01",
        "1.",
        "-",
        "-.",
        "+.5",
        "1e",
        "1e+",
        "1.2.3",
        # trailing content after a value (accepted by parser)
        "1abc",
        "1 garbage",
        "[]xyz",
        "{} trailing",
        "truefalse",
        "nullnull",
        # unbalanced
        "[",
        "]",
        "{",
        "}",
        "[[[]]",
        "{{}}",
        "[[",
        "]]",
        # bad escapes
        '"\\x"',
        '"\\u12"',
        '"\\uZZZZ"',
        '"\\"',
        # stray
        ",",
        ":",
        "\x01",
        "\x1f",
        "\x7f",
        # empty-ish
        "",
        "   ",
        "\t\n",
    ]
)

# ---------- recursive structure ----------

_json_value = st.deferred(lambda: _value)


def _make_obj(pairs):
    return "{" + ",".join(pairs) + "}"


def _make_arr(items):
    return "[" + ",".join(items) + "]"


def _make_pair(k, v):
    return k + ":" + v


# Object with possibly duplicate keys.
_obj_pairs = st.lists(
    st.builds(_make_pair, any_key, _json_value),
    min_size=0,
    max_size=6,
)

# Duplicate-key object: pick a small key pool and repeat.
_dup_keys = st.lists(
    st.builds(_make_pair, _common_keys, _json_value),
    min_size=2,
    max_size=6,
)

_arr_items = st.lists(_json_value, min_size=0, max_size=6)

_obj = _obj_pairs.map(_make_obj)
_arr = _arr_items.map(_make_arr)
_dup_obj = _dup_keys.map(_make_obj)

_empty_obj = st.just("{}")
_empty_arr = st.just("[]")

_value = st.one_of(
    valid_string,
    valid_number,
    valid_literal,
    _empty_obj,
    _empty_arr,
    _obj,
    _arr,
    _dup_obj,
    _deep_obj,
    _deep_arr,
)

# Recursive strategy for nested values with bounded depth.
recursive_value = st.recursive(
    st.one_of(valid_string, valid_number, valid_literal, _empty_obj, _empty_arr),
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=5).map(_make_arr),
        st.lists(
            st.builds(_make_pair, any_key, children),
            min_size=0,
            max_size=5,
        ).map(_make_obj),
    ),
    max_leaves=20,
)

# A top-level value, possibly with surrounding whitespace and trailing content.
_top_value = st.one_of(
    _value,
    recursive_value,
    _deep_obj,
    _deep_arr,
)

_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("garbage"),
    st.just("xyz"),
    st.just("123"),
    st.just("/* comment */"),
    st.just("// comment"),
    st.just("\x00".replace("\x00", "")),  # keep no raw NUL
    st.just("]"),
    st.just("}"),
    st.just(","),
)

_leading_ws = st.text(alphabet=" \t\n\r", min_size=0, max_size=3)

# ---------- assembled candidates ----------

_valid_ish = _top_value

_with_trailing = st.builds(
    lambda w1, v, w2, t: w1 + v + w2 + t,
    _leading_ws,
    _top_value,
    _ws,
    _trailing,
)

# Nested array/object values built from the recursive strategy, wrapped
# with whitespace inside structures.
_recursive_with_ws = st.recursive(
    st.one_of(valid_string, valid_number, valid_literal, _empty_obj, _empty_arr),
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=4)
        .map(lambda xs: "[" + ", ".join(xs) + "]"),
        st.lists(
            st.builds(_make_pair, any_key, children),
            min_size=0,
            max_size=4,
        ).map(_make_obj),
    ),
    max_leaves=15,
)

# Deep nesting with whitespace padding.
_deep_ws = _depth_choice.map(
    lambda n: "[" * n + " " * (n % 3) + "0" + " " * (n % 2) + "]" * n
)

strategy = st.one_of(
    _valid_ish,
    _with_trailing,
    _recursive_with_ws,
    _deep_ws,
    _malformed,
    # Explicit edge cases.
    st.just("{}"),
    st.just("[]"),
    st.just(""),
    st.just('{"k":0,"k":1}'),
    st.just("1e309"),
    st.just("-1e309"),
    st.just('"\\uD800"'),
    st.just('"\\uD83D\\uDE00"'),
    st.just('"\\u0000"'),
    st.just('"a\\u0000b"'),
    st.just('"\\u001F"'),
    st.just("[" * 2048 + "0" + "]" * 2048),
    st.just("[" * 2049 + "0" + "]" * 2049),
    st.just("[" * 2050 + "0" + "]" * 2050),
    st.just("{" * 2048 + '"k":0' + "}" * 2048),
    st.just("{" * 2050 + '"k":0' + "}" * 2050),
    st.just("[1,,2]"),
    st.just('{"a":1,,"b":2}'),
    st.just('{"a" 1}'),
    st.just('"abc'),
    st.just("+1"),
    st.just(".5"),
    st.just("01"),
    st.just("-"),
    st.just("1abc"),
    st.just("[]xyz"),
    # Embedded control bytes (no raw NUL).
    st.just('"\x01\x02\x1f"'),
    st.just('"tab\there"'),
    st.just('"newline\nhere"'),
    st.just("\x01"),
    st.just("\x1f"),
    st.just("\x7f"),
    st.text(alphabet=" \t\n\r", min_size=1, max_size=20),
)

# Ensure output is str.
strategy = strategy.map(lambda s: s if isinstance(s, str) else str(s))