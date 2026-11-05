```python
from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

_hex = "0123456789abcdefABCDEF"

_esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_esc_unicode = st.tuples(
    st.just("\\u"),
    st.text(alphabet=_hex, min_size=4, max_size=4),
).map(lambda t: "".join(t))

# lone surrogate escapes (parser rejects, but interesting)
_esc_surrogate = st.tuples(
    st.just("\\u"),
    st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DFFF"]),
).map(lambda t: "".join(t))

# surrogate pair (valid)
_esc_surrogate_pair = st.tuples(
    st.just("\\u"),
    st.sampled_from(["d800", "d83d", "dbff"]),
    st.just("\\u"),
    st.sampled_from(["dc00", "de00", "dfff"]),
).map(lambda t: "".join(t))

_esc = st.one_of(_esc_simple, _esc_unicode, _esc_surrogate, _esc_surrogate_pair)

# safe code points: printable ASCII minus quote and backslash, plus some unicode
_safe_ascii = st.characters(
    min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'
)
_safe_unicode = st.characters(
    min_codepoint=0x80, max_codepoint=0x2FFF, blacklist_categories=("Cs",)
)
_safe = st.one_of(_safe_ascii, _safe_unicode)

# raw control / NUL bytes (parser accepts raw control in strings)
_raw_control = st.characters(min_codepoint=0x00, max_codepoint=0x1F)

_str_piece = st.one_of(_esc, _safe, _raw_control)

_string_body = st.lists(_str_piece, max_size=8).map("".join)

_string = _string_body.map(lambda b: '"' + b + '"')

# malformed strings
_unterminated_string = st.tuples(
    st.just('"'), _string_body
).map(lambda t: t[0] + t[1])

_bad_escape = st.tuples(
    st.just('"'), st.sampled_from(["\\x", "\\q", "\\", "\\u12", "\\uZZZZ"]), st.just('"')
).map(lambda t: "".join(t))

_single_quoted = _string_body.map(lambda b: "'" + b + "'")

# ---------- numbers ----------

_int = st.one_of(
    st.just("0"),
    st.tuples(
        st.sampled_from("123456789"),
        st.text(alphabet="0123456789", max_size=20),
    ).map(lambda t: t[0] + t[1]),
)

_leading_zero = st.tuples(
    st.just("0"), st.text(alphabet="0123456789", min_size=1, max_size=10)
).map(lambda t: t[0] + t[1])

_frac = st.tuples(
    st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=20)
).map(lambda t: t[0] + t[1])

_trailing_dot = st.just(".")

_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map(lambda t: t[0] + t[1] + t[2])

_big_exp = st.tuples(
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.sampled_from(["308", "309", "310", "400", "1000", "99999"]),
).map(lambda t: t[0] + t[1] + t[2])

_opt_neg = st.one_of(st.just(""), st.just("-"))

_number = st.one_of(
    st.tuples(_opt_neg, _int).map(lambda t: t[0] + t[1]),
    st.tuples(_opt_neg, _int, _frac).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_opt_neg, _int, _exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_opt_neg, _int, _frac, _exp).map(lambda t: "".join(t)),
    st.tuples(_opt_neg, _int, _big_exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_opt_neg, _int, _frac, _big_exp).map(lambda t: "".join(t)),
    # deviations accepted by parser
    st.tuples(_opt_neg, _leading_zero).map(lambda t: t[0] + t[1]),
    st.tuples(_opt_neg, _int, _trailing_dot).map(lambda t: "".join(t)),
    st.tuples(_opt_neg, st.just("0x"), st.text(alphabet=_hex, min_size=1, max_size=8))
        .map(lambda t: "".join(t)),
    # malformed numbers (rejected)
    st.just("-"),
    st.tuples(st.just("+"), _int).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=6))
        .map(lambda t: t[0] + t[1]),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# ---------- recursive values ----------

_json_null = st.just("null")
_json_true = st.just("true")
_json_false = st.just("false")

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

_key = st.one_of(_string, _unterminated_string, _single_quoted)

_pair = st.tuples(_key, _ws, st.just(":"), _ws, st.deferred(lambda: _value)).map(
    lambda t: "".join(t)
)

# malformed pair pieces
_bad_pair = st.one_of(
    st.tuples(_key, _ws, _ws, st.deferred(lambda: _value)).map(lambda t: "".join(t)),  # missing colon
    st.tuples(_key, _ws, st.just(":"), _ws).map(lambda t: "".join(t)),  # missing value
)

_value = st.deferred(lambda: _value_strategy)

# simpler object builder
_obj_members = st.lists(_pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps))
_obj = st.one_of(
    st.just("{}"),
    st.tuples(st.just("{"), _ws, _obj_members, _ws, st.just("}"))
        .map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
)

_arr_items = st.lists(_value, min_size=1, max_size=5).map(lambda vs: ",".join(vs))
_arr = st.one_of(
    st.just("[]"),
    st.tuples(st.just("["), _ws, _arr_items, _ws, st.just("]"))
        .map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
)

# malformed containers
_bad_obj = st.one_of(
    st.tuples(st.just("{"), _pair, st.just(","), st.just("}")).map(lambda t: "".join(t)),  # trailing comma
    st.tuples(st.just("{"), st.just(","), st.just("}")).map(lambda t: "".join(t)),
    st.tuples(st.just("{"), _pair, st.just(","), _pair).map(lambda t: "".join(t)),  # unterminated
    st.tuples(st.just("{"), _bad_pair, st.just("}")).map(lambda t: "".join(t)),
    st.just("{"),
    st.just("}"),
)

_bad_arr = st.one_of(
    st.tuples(st.just("["), _value, st.just(","), st.just("]")).map(lambda t: "".join(t)),  # trailing comma
    st.tuples(st.just("["), st.just(","), st.just("]")).map(lambda t: "".join(t)),
    st.tuples(st.just("["), st.just(","), _value).map(lambda t: "".join(t)),
    st.tuples(st.just("["), _value, st.just(","), _value).map(lambda t: "".join(t)),  # unterminated
    st.just("["),
    st.just("]"),
)

# deep nesting near the 1000-level limit
def _deep(depth, opener, closer):
    return opener * depth + closer * depth

_deep_arr = st.sampled_from([999, 1000, 1001, 1002, 1050]).map(
    lambda d: _deep(d, "[", "]")
)
_deep_obj = st.sampled_from([999, 1000, 1001, 1002]).map(
    lambda d: _deep(d, '{"a":', "}")
)
_deep_mixed = st.sampled_from([998, 999, 1000, 1001]).map(
    lambda d: ("[{" * d) + ("}]" * d)
)

_value_strategy = st.one_of(
    _string,
    _number,
    _json_null,
    _json_true,
    _json_false,
    _obj,
    _arr,
    _unterminated_string,
    _bad_escape,
    _single_quoted,
    _bad_obj,
    _bad_arr,
    _deep_arr,
    _deep_obj,
    _deep_mixed,
)

# ---------- top-level assembly ----------

_bom = st.one_of(st.just(""), st.just("\ufeff"))

_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\x00"),
    st.just("abc"),
    st.just(" 1 2"),
    st.just("\x00\x00"),
    st.tuples(st.just(" "), _value).map(lambda t: t[0] + t[1]),
)

# Structured documents that exercise print_* / Compare paths:
# - duplicate keys (Compare on objects)
# - arrays of identical values (Compare on arrays/strings/numbers)
# - objects/arrays with many members to drive print_object/print_value
_dup_key_obj = st.tuples(
    _string, st.just(":"), _value, st.just(","), _string, st.just(":"), _value
).map(lambda t: "{" + "".join(t) + "}")

_identical_arr = st.tuples(
    st.just("["), _value, st.just(","), _value, st.just(","), _value, st.just("]")
).map(lambda t: "".join(t))

_wide_obj = st.lists(
    st.tuples(_string, st.just(":"), _value).map(lambda t: "".join(t)),
    min_size=3, max_size=8,
).map(lambda ps: "{" + ",".join(ps) + "}")

_wide_arr = st.lists(_value, min_size=3, max_size=8).map(
    lambda vs: "[" + ",".join(vs) + "]"
)

_roundtrip_probe = st.one_of(_dup_key_obj, _identical_arr, _wide_obj, _wide_arr)

_documents = st.one_of(
    st.tuples(_bom, _ws, _value_strategy, _ws, _trailing).map(lambda t: "".join(t)),
    _roundtrip_probe,
    # empty input (rejected)
    st.just(""),
    st.just(" "),
    st.just("\x00"),
    # top-level junk
    st.just("{"),
    st.just("["),
    st.just(":"),
    st.just(","),
)

strategy = _documents
```