```python
from hypothesis import strategies as st
import json

# --- leaf primitives ---

# SAFECODEPOINT: any char except '"', '\\', and control chars U+0000-U+001F.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"',
    min_codepoint=0x20,
)

# Allow some raw control/NUL bytes inside strings too (parser is length-aware,
# but raw control chars make the string technically malformed -> good fuzzing).
_raw_control = st.sampled_from(["\x00", "\x01", "\x1f", "\x0b", "\x0c", "\x7f"])

_plain_char = st.one_of(_safe_chars, _raw_control)

# Escape sequences per grammar.
_short_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)
_hex_digit = st.sampled_from("0123456789abcdefABCDEF")
_unicode_escape = st.tuples(
    st.just("\\u"), _hex_digit, _hex_digit, _hex_digit, _hex_digit
).map("".join)
# Surrogate escapes (high and low) explicitly.
_surrogate_escape = st.sampled_from(
    ["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uD83D\\uDE00", "\\uD800\\uD800"]
)
_escape = st.one_of(_short_escapes, _unicode_escape, _surrogate_escape)

# A string body piece: either a plain char or an escape.
_string_piece = st.one_of(_plain_char, _escape)

# A valid-ish JSON string (quoted). Sometimes unterminated for malformed cases.
_quoted_string = st.lists(_string_piece, max_size=12).map(
    lambda parts: '"' + "".join(parts) + '"'
)
_unterminated_string = st.lists(_string_piece, max_size=12).map(
    lambda parts: '"' + "".join(parts)
)

# --- numbers ---

_digits = st.text("0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _digits).map("".join),
)

_frac_part = st.tuples(st.just("."), _digits).map("".join)

_exp_part = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    _digits,
).map("".join)

_sign = st.one_of(st.just(""), st.just("-"))

_valid_number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.just(""), _frac_part),
    st.one_of(st.just(""), _exp_part),
).map("".join)

# Extreme magnitudes / exponents, including overflow like 1e309.
_extreme_number = st.one_of(
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("1e308"),
    st.just("1e99999"),
    st.just("-1e99999"),
    st.just("0e0"),
    st.just("1e+0000000000000000000001"),
    st.just("123456789012345678901234567890"),
    st.just("-0"),
    st.just("1.7976931348623157e308"),
    st.just("4.9e-324"),
    st.just("1e-9999"),
)

# Malformed number forms the parser rejects (still valuable).
_bad_number = st.sampled_from(
    ["+1", ".5", "1.", "01", "0x1F", "1..2", "1e", "1e+", "--1", "1.2.3", "-", "1e1e1"]
)

_number = st.one_of(_valid_number, _extreme_number, _bad_number)

# --- whitespace ---

_ws = st.text(" \t\n\r", max_size=4)

# --- recursive value/obj/arr ---

# We use st.recursive with a deferred strategy so obj/arr can reference value.
_value = st.deferred(lambda: _value_strategy)

_primitive = st.one_of(
    _quoted_string,
    _unterminated_string,
    _number,
    st.sampled_from(["true", "false", "null", "TRUE", "True", "nul", "tru"]),
)

# key: mostly valid quoted strings, sometimes duplicate-friendly short keys.
_key = st.one_of(
    _quoted_string,
    st.sampled_from(['"a"', '"a"', '"a"', '"key"', '"0"', '""']),
)

_pair = st.tuples(_key, _ws, st.just(":"), _ws, _value).map("".join)

# malformed pair fragments
_bad_pair = st.sampled_from(
    ['"a" 1', '"a":', ':"a"', '"a"::1', 'a:1', "'a':1", '"a" : }
']
)

_obj_member = st.one_of(_pair, _bad_pair)

_obj = st.one_of(
    st.just("{}"),
    st.tuples(
        st.just("{"),
        _ws,
        st.lists(_obj_member, min_size=1, max_size=6).map(lambda ps: ("," + _ws_dummy).join(ps) if False else ",".join(ps)),
        _ws,
        st.just("}"),
    ).map("".join),
    # single trailing comma variant
    st.tuples(
        st.just("{"),
        st.lists(_pair, min_size=1, max_size=4).map(",".join),
        st.just(",}"),
    ).map("".join),
    # double comma / empty element malformed
    st.sampled_from(['{,}', '{"a":1,,}', '{,1}', '{"a":1 "b":2}', '{"a" 1}']),
)

_arr = st.one_of(
    st.just("[]"),
    st.tuples(
        st.just("["),
        _ws,
        st.lists(_value, min_size=1, max_size=6).map(",".join),
        _ws,
        st.just("]"),
    ).map("".join),
    # single trailing comma
    st.tuples(
        st.just("["),
        st.lists(_value, min_size=1, max_size=4).map(",".join),
        st.just(",]"),
    ).map("".join),
    # malformed
    st.sampled_from(["[1,,2]", "[,]", "[,1]", "[1 2]", "[1,2", "[1;2]"]),
)

_value_strategy = st.recursive(
    st.one_of(_primitive, _obj, _arr),
    lambda children: st.one_of(
        st.tuples(
            st.just("["), _ws, children, _ws, st.just("]")
        ).map("".join),
        st.tuples(
            st.just("{"),
            _ws,
            _key,
            _ws,
            st.just(":"),
            _ws,
            children,
            _ws,
            st.just("}"),
        ).map("".join),
    ),
    max_leaves=30,
)

# helper used above (kept simple)
_ws_dummy = ""

# --- top-level strategy ---

# Deep nesting: build nested objects/arrays by hand (no recursion cap in parser).
_deep_depth = st.integers(min_value=1, max_value=200)

_deep_arr = _deep_depth.map(lambda n: "[" * n + "]" * n)
_deep_obj = _deep_depth.map(lambda n: '{"a":' * n + "0" + "}" * n)

# Top-level JSON: value optionally surrounded by whitespace, sometimes with
# trailing garbage (rejected by parser but good near-valid input).
_trailing_garbage = st.sampled_from(
    ["", "x", " garbage", "abc", "[]xyz", "true false", "1abc", "\x00", "\x00\x00"]
)

_top = st.one_of(
    st.tuples(_ws, _value, _ws).map("".join),
    st.tuples(_value, _trailing_garbage).map("".join),
    _deep_arr,
    _deep_obj,
    # lone things
    st.sampled_from(
        [
            "",
            " ",
            "\n",
            "-",
            "1e309",
            "{}",
            "[]",
            "\x00",
            '"\\uD800"',
            '"\\uDBFF\\uDFFF"',
            '{"a":1,"a":2}',
            "[1,2,]",
            '{"a":1,}',
        ]
    ),
)

strategy = _top
```