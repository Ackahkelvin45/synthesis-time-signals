```python
from hypothesis import strategies as st
import json

# ---------- low-level building blocks ----------

# Characters that are legal inside a JSON string without escaping.
# SAFECODEPOINT = ~["\\\u0000-\u001F]  -> anything except ", \, and controls.
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in raw text
    blacklist_characters='\\"',
    min_codepoint=0x20,
)

# Raw control bytes, including NUL. Allowed and encouraged.
_control_chars = st.integers(min_value=0x00, max_value=0x1F).map(chr)

# Escape sequences per grammar: \" \\ \/ \b \f \n \r \t \uXXXX
_simple_escapes = st.sampled_from(['\\"', '\\\\', "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.tuples(
    st.just("\\u"),
    _hex_digit,
    _hex_digit,
    _hex_digit,
    _hex_digit,
).map("".join)

# Surrogate escapes (high and low), plus a few interesting literal ones.
_surrogate_escapes = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD83D\\uDE00",  # valid surrogate pair
    "\\uD800\\uD800",  # two highs
    "\\uDC00\\uDC00",  # two lows
])

_string_body_piece = st.one_of(
    _safe_chars.map(str),
    _control_chars,
    _simple_escapes,
    _unicode_escape,
    _surrogate_escapes,
)

# A well-formed JSON string literal.
_string_literal = st.lists(_string_body_piece, max_size=12).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# Broken / unterminated strings (near-valid-but-malformed).
_unterminated_string = st.lists(_string_body_piece, min_size=0, max_size=8).map(
    lambda parts: '"' + "".join(parts)
)
_string_with_quote = st.lists(_string_body_piece, min_size=0, max_size=6).map(
    lambda parts: '"' + "".join(parts) + '"' + "".join(parts)
)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(
        st.sampled_from("123456789"),
        st.text(alphabet="0123456789", min_size=0, max_size=8),
    ).map("".join),
)

_frac_part = st.tuples(st.just("."), _digits).map("".join)

_exp_part = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map("".join)

_sign = st.one_of(st.just(""), st.just("-"))

# Extreme magnitudes / exponents (overflow like 1e309, tiny, huge).
_extreme_numbers = st.sampled_from([
    "1e309", "-1e309", "1e-309", "1e308", "1e999",
    "1e1000000", "-1e-1000000",
    "0.0000000000000000000000001",
    "12345678901234567890123456789012345678901234567890",
    "1.7976931348623157e308",
    "5e-324", "2.2250738585072014e-308",
    "-",  # lone minus: accepted by parser
    "0", "-0", "0.0", "-0.0", "00", "01", "007",
])

_number = st.one_of(
    _extreme_numbers,
    st.tuples(_sign, _int_part, st.one_of(st.just(""), _frac_part), st.one_of(st.just(""), _exp_part)).map("".join),
    # malformed numeric forms (leading +, leading dot, trailing dot, hex)
    st.sampled_from(["+1", ".5", "-.5", "1.", "1.e3", "0x1F", "0X1f", "1e", "1e+", "--1", "-+1"]),
)

# ---------- recursive structure ----------

_json_value = st.deferred(lambda: _value)

# Object member keys: mostly well-formed strings, sometimes duplicates-friendly
_member_key = st.one_of(_string_literal, _unterminated_string)

_pair = st.tuples(
    _member_key,
    st.one_of(st.just(":"), st.just(""), st.just("::")),
    _json_value,
).map("".join)

# Objects biased toward having members (the stressed first-pass path).
_obj = st.one_of(
    st.just("{}"),
    st.tuples(
        st.just("{"),
        st.lists(_pair, min_size=1, max_size=6).map(lambda ps: ",".join(ps)),
        st.one_of(st.just(""), st.just(",")),  # allow single trailing comma
        st.just("}"),
    ).map("".join),
)

_arr = st.one_of(
    st.just("[]"),
    st.tuples(
        st.just("["),
        st.lists(_json_value, min_size=1, max_size=6).map(lambda vs: ",".join(vs)),
        st.one_of(st.just(""), st.just(",")),
        st.just("]"),
    ).map("".join),
)

_scalar = st.one_of(
    _string_literal,
    _number,
    st.sampled_from(["true", "false", "null"]),
)

_value = st.one_of(_scalar, _obj, _arr)

# ---------- deep nesting ----------

_deep_obj = st.integers(min_value=1, max_value=256).map(
    lambda n: '{"a":' * n + "1" + "}" * n
)
_deep_arr = st.integers(min_value=1, max_value=256).map(
    lambda n: "[" * n + "1" + "]" * n
)
_deep_mixed = st.integers(min_value=1, max_value=128).map(
    lambda n: ('{"k":[' * n) + "0" + ("]}" * n)
)

# ---------- malformed inputs ----------

_malformed = st.sampled_from([
    "[1,,2]", "[,]", "[,1]", "[1 2]", "{,}", '{"a":1,,"b":2}',
    '{"a" 1}', '{"a"::1}', '{"a":}', '{:1}', '{"a":1 "b":2}',
    '{"a":1}', '{"a":1,}', '[1,2,]',
    "1abc", "[]xyz", "1 garbage", "true false",
    "+1", ".5", "1.", "01", "0x1F",
    '"unterminated', '"a\\', '"\\u12"', '"\\uZZZZ"', '"\\x41"',
    "tru", "fals", "nul", "True", "NULL",
    "{", "}", "[", "]", ":", ",",
    "", " ", "\t\n\r",
    "{}garbage", "null null", '"a" "b"',
    '{\x00:1}', '["\x00"]', '{"a":\x00}',
    "[1,2,3", '{"a":1', '"x',
])

# ---------- NUL / control-byte injections ----------

_nul_control = st.one_of(
    st.just("\x00"),
    st.integers(min_value=0, max_value=0x1F).map(chr),
    st.sampled_from(["\x00\x00", "\x01\x02\x03", "\x7f", "\x0b", "\x0c"]),
)

_control_injected = st.tuples(
    st.one_of(st.just(""), st.just("[")),
    _nul_control,
    st.one_of(st.just(""), _string_literal, _number),
    st.one_of(st.just(""), st.just("]")),
).map("".join)

# ---------- top-level strategy ----------

_structured = st.recursive(
    _scalar,
    lambda children: st.one_of(
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(_member_key, st.just(":"), children).map("".join),
                min_size=1,
                max_size=6,
            ).map(lambda ps: ",".join(ps)),
            st.one_of(st.just(""), st.just(",")),
            st.just("}"),
        ).map("".join),
        st.tuples(
            st.just("["),
            st.lists(children, min_size=1, max_size=6).map(lambda vs: ",".join(vs)),
            st.one_of(st.just(""), st.just(",")),
            st.just("]"),
        ).map("".join),
    ),
    max_leaves=40,
)

# ---------- whitespace / trivia fuzzing ----------

_ws = st.text(alphabet=" \t\n\r\f\v\x00", min_size=0, max_size=4)

# Inject arbitrary whitespace (including NUL) around structural tokens of a
# valid document to stress the tokenizer's whitespace handling.
_ws_injected = st.tuples(
    _ws,
    st.one_of(_scalar, _obj, _arr),
    _ws,
).map("".join)

# ---------- differential oracle: valid JSON that must round-trip ----------

# Produce a Python object, serialize with json.dumps, and use that string as
# the input. This guarantees well-formed JSON while exercising the parser's
# handling of every value type, unicode escapes, and deep structures.
_jsonable_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**63), max_value=2**63),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=20),
)

_jsonable = st.recursive(
    _jsonable_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=6),
        st.dictionaries(st.text(max_size=8), children, max_size=6),
    ),
    max_leaves=30,
)

_roundtrip_json = _jsonable.map(lambda obj: json.dumps(obj, ensure_ascii=False))
_roundtrip_json_ascii = _jsonable.map(lambda obj: json.dumps(obj, ensure_ascii=True))

# ---------- top-level strategy ----------

strategy = st.one_of(
    _structured,
    _deep_obj,
    _deep_arr,
    _deep_mixed,
    _malformed,
    _control_injected,
    _ws_injected,
    _string_literal,
    _unterminated_string,
    _string_with_quote,
    _number,
    _obj,
    _arr,
    _roundtrip_json,
    _roundtrip_json_ascii,
)
```