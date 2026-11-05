```python
from hypothesis import strategies as st
import json

# ---------- leaf building blocks ----------

def _hex_digits(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)

# escapes that are valid inside a JSON string
_escapes = st.one_of(
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    st.builds(lambda h: "\\u" + h, _hex_digits(4)),
    # surrogate escapes (lone and paired)
    st.builds(lambda h: "\\u" + h, st.sampled_from(
        ["D800", "DBFF", "DC00", "DFFF", "d800", "dc00", "D834", "DD1E"])),
    st.builds(lambda a, b: "\\u" + a + "\\u" + b,
              _hex_digits(4), _hex_digits(4)),
    # embedded NUL escape (six chars, safe)
    st.just("\\u0000"),
)

# safe code points (no raw control chars, no raw NUL, no quote/backslash)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) >= 0x20 or c in "\t\n\r")

_string_body = st.lists(
    st.one_of(_escapes, _safe_char), max_size=12
).map("".join)

_json_string = _string_body.map(lambda b: '"' + b + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d, r: d + r,
              st.sampled_from("123456789"),
              st.text(alphabet="0123456789", max_size=6)),
)

_frac = st.builds(lambda d: "." + d, _digits)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.one_of(st.just(""), st.sampled_from("+-")),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

_number = st.builds(
    lambda sign, ip, fr, ex: sign + ip + fr + ex,
    st.one_of(st.just(""), st.just("-")),
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

# extreme magnitudes / exponents
_extreme_number = st.one_of(
    st.just("1e309"), st.just("-1e309"), st.just("1e-309"),
    st.just("1e999999"), st.just("-1e999999"),
    st.just("1" + "0" * 400),
    st.just("0." + "0" * 300 + "1"),
    st.just("1e308"), st.just("1.7976931348623157e308"),
    st.just("-1.7976931348623157e308"), st.just("1e-400"),
    st.builds(lambda d: "1e" + d, st.text(alphabet="0123456789", min_size=1, max_size=10)),
    st.builds(lambda d: "-1e-" + d, st.text(alphabet="0123456789", min_size=1, max_size=10)),
)

# malformed numeric-ish tokens
_bad_number = st.one_of(
    st.just("+1"), st.just(".5"), st.just("1."), st.just("01"),
    st.just("-01"), st.just("00"), st.just("-"), st.just("-."),
    st.just("1e"), st.just("1e+"), st.just("--1"), st.just("1..2"),
    st.builds(lambda d: "0" + d, _digits),
)

# ---------- malformed fragments ----------

_unterminated_string = st.builds(
    lambda b: '"' + b,
    _string_body,
)

_malformed = st.one_of(
    _unterminated_string,
    st.just("{"),
    st.just("["),
    st.just("}"),
    st.just("]"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just('{"a":1,}'),
    st.just('[1,]'),
    st.just('[,]'),
    st.just('[1,,2]'),
    st.just('{,}'),
    st.just('{"a":1 "b":2}'),
    st.just('{"a" 1}'),
    st.just('{"a":1,,"b":2}'),
    st.just('"\\u12"'),
    st.just('"\\u"'),
    st.just('"\\q"'),
    st.just('tru'),
    st.just('nul'),
    st.just('fals'),
    st.just('True'),
)

# ---------- recursive values ----------

_leaf = st.one_of(
    _json_string,
    _number,
    _extreme_number,
    st.sampled_from(["true", "false", "null"]),
    _bad_number,
    _malformed,
)

_key = st.one_of(
    _json_string,
    st.just('""'),
    st.just('"k"'),
    st.just('"key"'),
    st.just('"\\u0000"'),
    st.just('"\\uD800"'),
)

def _pair(key, value):
    return key + ":" + value

def _obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _arr(items):
    return "[" + ",".join(items) + "]"

# value strategy (recursive)
_value = st.recursive(
    _leaf,
    lambda children: st.one_of(
        st.lists(st.tuples(_key, children), max_size=4)
        .map(lambda ps: _obj([_pair(k, v) for k, v in ps])),
        st.lists(children, max_size=5).map(_arr),
    ),
    max_leaves=40,
)

# ---------- deep nesting near the 2048 cap ----------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

_deep_near_cap = st.builds(
    lambda depth, kind, inner: _deep(depth, kind[0], kind[1], inner),
    st.integers(min_value=2000, max_value=2060),
    st.sampled_from([("[", "]"), ("{", "}")]).map(
        lambda k: k if k[0] == "[" else ('{"a":', "}")
    ) if False else st.sampled_from([("[", "]"), ("[", "]")]),
    st.one_of(st.just(""), st.just("0"), st.just('"x"')),
)

_deep_arr = st.builds(
    lambda depth, inner: "[" * depth + inner + "]" * depth,
    st.integers(min_value=0, max_value=2060),
    st.one_of(st.just(""), st.just("0"), st.just("null")),
)

_deep_obj = st.builds(
    lambda depth: '{"a":' * depth + "0" + "}" * depth,
    st.integers(min_value=0, max_value=2060),
)

_deep = st.one_of(_deep_arr, _deep_obj)

# ---------- top-level: value, with optional trailing content ----------

_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("garbage"),
    st.just("abc"),
    st.just("[]xyz"),
    st.just(" /* c */"),
    st.just("//c"),
    st.just("\t\r\n"),
    st.just("1"),
)

_top_value = st.one_of(_value, _deep, _leaf, _malformed)

# whitespace toggle: sprinkle JSON whitespace between structural tokens
_ws = st.sampled_from(["", "", "", " ", "\n", "\t", "\r\n", "  "])

def _wsify(parts):
    # parts is a list of (text) fragments; interleave random whitespace
    return "".join(parts)

def _obj_ws(ps):
    # build object with whitespace around braces/colon/comma
    return "{" + ",".join(_pair(k, v) for k, v in ps) + "}"

_ws_object = st.builds(
    lambda ps, w1, w2, w3, w4: (
        "{" + w1 + ",".join(
            k + w2 + ":" + w3 + v for k, v in ps
        ) + w4 + "}"
    ),
    st.lists(st.tuples(_key, _value), max_size=4),
    _ws, _ws, _ws, _ws,
)

_ws_array = st.builds(
    lambda xs, w1, w2, w3: "[" + w1 + ("," + w2).join(xs) + w3 + "]",
    st.lists(_value, max_size=5),
    _ws, _ws, _ws,
)

_ws_top = st.one_of(_ws_object, _ws_array)

_top_value = st.one_of(_value, _deep, _leaf, _malformed, _ws_top)

# ---------- improve_strategy: broaden structural coverage ----------

# leading/trailing whitespace variants around the whole document
_lead_ws = st.sampled_from(["", " ", "\n", "\t", "\r\n", "  ", "\ufeff"])
_trail_ws = st.sampled_from(["", " ", "\n", "\t", "\r\n", "  ", "\x00"])

# empty containers and whitespace-only documents
_empty_doc = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("\t\r\n"),
    st.just("{}"),
    st.just("[]"),
    st.just("{ }"),
    st.just("[ ]"),
    st.just("{ } "),
    st.just("[]\n"),
)

# top-level scalars (common parser entry points)
_top_scalar = st.one_of(
    _number,
    _extreme_number,
    _bad_number,
    _json_string,
    _unterminated_string,
    st.sampled_from(["true", "false", "null", "tru", "nul", "fals"]),
)

# duplicate / unusual keys and mixed value types in objects
_dup_key_obj = st.builds(
    lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
    _key,
    _value,
    _value,
)

_mixed_obj = st.builds(
    lambda ps: "{" + ",".join(_pair(k, v) for k, v in ps) + "}",
    st.lists(
        st.tuples(_key, st.one_of(_value, _top_scalar)),
        min_size=1, max_size=6,
    ),
)

_mixed_arr = st.builds(
    lambda xs: "[" + ",".join(xs) + "]",
    st.lists(st.one_of(_value, _top_scalar), min_size=1, max_size=8),
)

# nested empty containers
_nested_empty = st.builds(
    lambda depth: "[" * depth + "]" * depth,
    st.integers(min_value=1, max_value=8),
)

# comments and BOM-ish noise at edges
_noise = st.sampled_from([
    "", " ", "\n", "\r\n", "\t",
    " /* c */", " //c\n", "\ufeff", "\x00", "\x1b",
])

# structural variety at top level
_structural = st.one_of(
    _empty_doc,
    _top_scalar,
    _dup_key_obj,
    _mixed_obj,
    _mixed_arr,
    _nested_empty,
)

# assemble the improved top-level document
_improved_top = st.builds(
    lambda lead, body, trail: lead + body + trail,
    _lead_ws,
    st.one_of(_structural, _top_value),
    _trail_ws,
)

# ---------- improve_strategy: additional coverage-oriented generators ----------

# whitespace-heavy documents (exercise whitespace-skipping branches)
_ws_only = st.builds(
    lambda a, b, c: a + b + c,
    st.sampled_from(["", " ", "\n", "\t", "\r\n", "\x0b", "\x0c"]),
    st.sampled_from(["", " ", "\n", "\t", "\r\n"]),
    st.sampled_from(["", " ", "\n", "\t", "\r\n"]),
)

# strings with heavy escape density and long valid strings
_dense_escape_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(
        st.one_of(_escapes, _safe_char),
        min_size=0, max_size=40,
    ),
)

# very long plain strings (buffer-boundary exercise)
_long_string = st.builds(
    lambda n, c: '"' + c * n + '"',
    st.integers(min_value=0, max_value=5000),
    st.sampled_from(["a", "z", "0", " ", "\u00e9", "\u4e2d"]),
)

# numeric boundary values that hit parse branches
_num_boundary = st.sampled_from([
    "0", "-0", "0.0", "-0.0", "1", "-1", "1e0", "1E0", "1e+0", "1e-0",
    "123456789012345678901234567890",
    "-123456789012345678901234567890",
    "0.0000000000000000001",
    "1.0000000000000000001",
    "9.9999999999999999999e307",
    "1.0000000000000002e308",
    "1e-323", "5e-324", "2.2250738585072014e-308",
    "1.7976931348623157e+308",
    "1e2147483647", "1e-2147483648",
    "0e0", "0e999", "-0e-999",
])

# literal-prefix near misses to exercise keyword matching
_literal_near = st.sampled_from([
    "true", "false", "null",
    "True", "False", "NULL", "Null",
    "tru", "tr", "t", "truex", "true1",
    "fals", "fal", "fa", "f", "falsex",
    "nul", "nu", "n", "nullx", "nulll",
    "tRue", "fALSE", "nULL",
])

# invalid escape sequences in strings (exercise escape error paths)
_bad_escape_string = st.builds(
    lambda pre, bad, post: '"' + pre + bad + post + '"',
    st.text(alphabet="abc", max_size=3),
    st.sampled_from([
        "\\", "\\x", "\\u", "\\u1", "\\u12", "\\u123",
        "\\uZZZZ", "\\U1234", "\\q", "\\'", "\\ ",
        "\\uD800", "\\uDC00", "\\uD800\\uD800", "\\uDC00\\uDC00",
    ]),
    st.text(alphabet="abc", max_size=3),
)

# raw control characters inside strings (should be rejected)
_raw_ctrl_string = st.builds(
    lambda pre, c, post: '"' + pre + c + post + '"',
    st.text(alphabet="abc", max_size=3),
    st.sampled_from(["\x00", "\x01", "\x1f", "\x7f", "\x08", "\x0c"]),
    st.text(alphabet="abc", max_size=3),
)

# truncated documents (exercise EOF handling in every state)
_truncated = st.builds(
    lambda prefix, cut: prefix[:cut] if cut <= len(prefix) else prefix,
    st.one_of(
        st.just('{"a":1,"b":[1,2,3]}'),
        st.just('{"a":{"b":{"c":[1,2,{"d":"e"}]}}}'),
        st.just('[1,2,3,{"a":[true,false,null]}]'),
        st.just('{"key":"value\\u0041\\n","n":-1.5e10}'),
        st.just('[{"a":1},{"b":2},{"c":3}]'),
    ),
    st.integers(min_value=0, max_value=40),
)

# trailing-garbage after a valid value (exercise post-value state)
_trailing_garbage = st.builds(
    lambda v, g: v + g,
    st.one_of(
        st.just('{"a":1}'),
        st.just('[1,2,3]'),
        st.just('"x"'),
        st.just('null'),
        st.just('true'),
        st.just('123'),
        _mixed_obj,
        _mixed_arr,
    ),
    st.sampled_from([
        "", " ", "\n", "\t", "x", "1", "{}", "[]", ",", ":",
        " /* c */", " // c\n", "\x00", "null", "true", "garbage",
    ]),
)

# multiple top-level values (parser should reject trailing)
_multi_value = st.builds(
    lambda a, sep, b: a + sep + b,
    st.one_of(_top_scalar, _mixed_obj, _mixed_arr, st.just("null")),
    st.sampled_from(["", " ", "\n", "\t", "\r\n"]),
    st.one_of(_top_scalar, _mixed_obj, _mixed_arr, st.just("null")),
)

# documents with only structural delimiters / noise
_delim_noise = st.builds(
    lambda parts: "".join(parts),
    st.lists(
        st.sampled_from([
            "{", "}", "[", "]", ",", ":", " ", "\n", "\t",
            '"', "\\", "0", "a",
        ]),
        min_size=0, max_size=20,
    ),
)

# combine into a richer top-level
_extra = st.one_of(
    _ws_only,
    _dense_escape_string,
    _long_string,
    _num_boundary,
    _literal_near,
    _bad_escape_string,
    _raw_ctrl_string,
    _truncated,
    _trailing_garbage,
    _multi_value,
    _delim_noise,
)

strategy = st.one_of(
    _improved_top,
    _extra,
    st.builds(
        lambda v, t: v + t,
        _top_value,
        _trailing,
    ),
)
```