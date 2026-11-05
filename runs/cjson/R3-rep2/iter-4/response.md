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

# simpler object builder avoiding helper complexity
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

_documents = st.one_of(
    st.tuples(_bom, _ws, _value_strategy, _ws, _trailing).map(lambda t: "".join(t)),
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

# ---------- coverage-boosting: round-trip / print / compare exercises ----------

# Build valid JSON via json.dumps from rich Python values so that the parser's
# print_* and compare code paths (currently uncovered) get exercised when the
# harness round-trips parsed values back to text.
_py_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=12),
)

_py_value = st.recursive(
    _py_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(max_size=8), children, max_size=4),
    ),
    max_leaves=20,
)

# Pretty-printed variants also hit print_string_ptr / print_number formatting.
_valid_json_doc = st.one_of(
    _py_value.map(json.dumps),
    _py_value.map(lambda v: json.dumps(v, indent=2)),
    _py_value.map(lambda v: json.dumps(v, separators=(",", ":"))),
    _py_value.map(lambda v: json.dumps(v, ensure_ascii=False)),
)

# Duplicate-key and key-order objects exercise cJSON_Compare.
_compare_doc = st.tuples(_py_value, _py_value).map(
    lambda t: json.dumps(t[0]) + "\n" + json.dumps(t[1])
)

# Single-document forms that the harness will parse, print, and compare against
# themselves (or a structurally-equivalent re-serialization). These are the most
# direct way to reach print_value / print_string_ptr / print_number /
# print_object / cJSON_Compare, which the current run left at 0%.
_roundtrip_doc = st.tuples(_py_value, _py_value).map(
    lambda t: json.dumps(t[0]) + "\n" + json.dumps(t[1])
)

_self_compare_doc = _py_value.map(lambda v: json.dumps(v) + "\n" + json.dumps(v))

# Objects with keys in different insertion orders but same content -> exercises
# cJSON_Compare's key-lookup path (not just value equality).
_reordered_obj_doc = st.lists(
    st.tuples(st.text(min_size=1, max_size=6), _py_scalar), min_size=1, max_size=6
).map(lambda items: json.dumps(dict(items)) + "\n" + json.dumps(dict(reversed(items))))

# IMPORTANT: The parser's print_* and cJSON_Compare functions are only reached
# when the harness receives a *single* well-formed JSON document (it parses,
# prints, and compares). The multi-document "\n"-separated forms above never
# trigger those paths (the parser stops at the first document). So we add
# dedicated single-document valid-JSON strategies that are heavily weighted
# toward the uncovered functions.
_single_valid_doc = st.one_of(
    _py_value.map(json.dumps),
    _py_value.map(lambda v: json.dumps(v, indent=2)),
    _py_value.map(lambda v: json.dumps(v, separators=(",", ":"))),
    _py_value.map(lambda v: json.dumps(v, ensure_ascii=False)),
    # Numeric edge cases for print_number: large/small magnitudes, fractions,
    # negative zero, exponents.
    st.sampled_from([
        "0", "-0", "1", "-1", "123456789", "-123456789",
        "1.5", "-1.5", "0.1", "1e10", "1e-10", "1E+300", "1e-300",
        "9007199254740993", "1.7976931348623157e308",
        "5e-324", "2.2250738585072014e-308",
        "3.141592653589793", "-2.718281828459045",
        "100000000000000000000", "0.000000000000000000001",
    ]),
    # String-heavy docs to drive print_string_ptr: escapes, unicode, control,
    # all the escape sequences the printer must emit.
    st.lists(
        st.text(
            alphabet=st.characters(min_codepoint=0x00, max_codepoint=0x2FFF),
            max_size=20,
        ),
        max_size=6,
    ).map(json.dumps),
    # Objects with varied key/value types to drive print_object.
    st.dictionaries(
        st.text(min_size=1, max_size=8),
        _py_scalar,
        min_size=1,
        max_size=8,
    ).map(json.dumps),
    # Nested structures to drive print_value recursion.
    _py_value.map(json.dumps),
)

_documents = st.one_of(
    _documents,
    _valid_json_doc,
    _compare_doc,
    _roundtrip_doc,
    _self_compare_doc,
    _reordered_obj_doc,
    _single_valid_doc,
)

strategy = _documents
```