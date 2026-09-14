from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# Strings that are safe as JSON string *contents* (no raw NUL, no raw control).
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters=("\x00",),
).filter(lambda c: ord(c) >= 0x20 or c in "\t\n\r")

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_escape = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.builds(lambda h: "\\u" + h, _hex4),
    # surrogate escapes (lone and paired) and other interesting code units
    st.sampled_from([
        "\\u0000", "\\u001f", "\\u007f", "\\u0080", "\\u07ff", "\\u0800",
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\uFFFD", "\\uFFFF",
    ]),
)

_string_body = st.one_of(
    st.text(alphabet=_safe_char, max_size=12),
    st.lists(st.one_of(_safe_char, _escape), max_size=8).map(_join),
)

_json_string = st.builds(
    lambda body: '"' + body + '"',
    _string_body,
)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d, rest: d + rest,
              st.integers(min_value=1, max_value=9).map(str),
              st.text(alphabet="0123456789", max_size=10)),
)

_frac = st.builds(lambda ds: "." + ds,
                  st.text(alphabet="0123456789", min_size=1, max_size=8))

_exp = st.builds(lambda e, s, ds: e + s + ds,
                 st.sampled_from(["e", "E"]),
                 st.sampled_from(["", "+", "-"]),
                 st.text(alphabet="0123456789", min_size=1, max_size=4))

_extreme_numbers = st.sampled_from([
    "0", "-0", "1e309", "-1e309", "1e-309", "1e308", "1.7976931348623157e308",
    "1.7976931348623159e308", "5e-324", "1e400", "-1e400", "1e999999",
    "123456789012345678901234567890", "-123456789012345678901234567890",
    "0.0000000000000000000001", "1e01", "1E+01", "1e-0",
])

_number = st.one_of(
    _extreme_numbers,
    st.builds(lambda sign, i: sign + i, st.sampled_from(["", "-"]), _int_part),
    st.builds(lambda sign, i, f: sign + i + f, st.sampled_from(["", "-"]), _int_part, _frac),
    st.builds(lambda sign, i, e: sign + i + e, st.sampled_from(["", "-"]), _int_part, _exp),
    st.builds(lambda sign, i, f, e: sign + i + f + e,
              st.sampled_from(["", "-"]), _int_part, _frac, _exp),
)

# ---------- malformed fragments (near-valid) ----------

_bad_number = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "-01", "+.5", "1e", "1e+", "1e-",
    "--1", "1..2", "0x1f", "Infinity", "-Infinity", "NaN", "1_000",
])

_unterminated_string = st.builds(
    lambda body: '"' + body,
    st.text(alphabet=_safe_char, min_size=1, max_size=10),
)

_bad_key_token = st.one_of(
    st.just("k"),          # unquoted key
    st.just("'k'"),        # single-quoted key
    st.just(""),           # missing key
)

# ---------- recursive JSON values ----------

_json_value = st.recursive(
    st.one_of(
        _json_string,
        _number,
        st.sampled_from(["true", "false", "null"]),
    ),
    lambda children: st.one_of(
        # arrays
        st.just("[]"),
        st.builds(lambda xs: "[" + ",".join(xs) + "]",
                  st.lists(children, min_size=1, max_size=5)),
        # objects
        st.just("{}"),
        st.builds(lambda pairs: "{" + ",".join(pairs) + "}",
                  st.lists(
                      st.builds(lambda k, v: k + ":" + v, _json_string, children),
                      min_size=1, max_size=5)),
    ),
    max_leaves=40,
)

# ---------- edge cases ----------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

_deep_nesting = st.one_of(
    st.integers(min_value=1, max_value=64),
    st.integers(min_value=2000, max_value=2048),
    st.integers(min_value=2049, max_value=2100),
).flatmap(lambda d: st.one_of(
    st.just(_deep(d, "[", "]", "0")),
    st.just(_deep(d, "[", "]", "")),
    st.just(_deep(d, "[", "]", "null")),
))

_dup_keys = st.builds(
    lambda key, v1, v2: "{" + key + ":" + v1 + "," + key + ":" + v2 + "}",
    _json_string,
    _json_value,
    _json_value,
)

_trailing = st.builds(
    lambda v, t: v + t,
    _json_value,
    st.sampled_from(["", " ", "\n", "abc", "garbage", "xyz", "]", "}", ",", "1"]),
)

_malformed = st.one_of(
    # double commas / leading commas
    st.sampled_from([
        "[1,,2]", "[,]", "[1,]", "{,}", '{"a":1,,}', '{"a":1,}',
        '{"a":1 "b":2}', '{"a" 1}', '{"a":}', '{:"1"}', '{"a":1,}',
        "[1 2]", "[1,2", "{\"a\":1", "[", "{", "]", "}", ":", ",",
    ]),
    st.builds(lambda n: "[" + n + "," + n + "]", _number),
    st.builds(lambda k, v: "{" + k + ":" + v + ",}", _json_string, _json_value),
    st.builds(lambda k, v: "{" + k + " " + v + "}", _json_string, _json_value),
    st.builds(lambda k, v: "{" + k + ":" + v, _json_string, _json_value),
    st.builds(lambda v: "{" + v + "}", _json_value),
    st.builds(lambda v: "[" + v, _json_value),
    st.builds(lambda v: v + "]", _json_value),
    _unterminated_string,
    _bad_number,
    st.builds(lambda k, v: "{" + k + ":" + v + "}", _bad_key_token, _json_value),
)

_lone_sign = st.sampled_from(["-", "-.", "+", ".", "+.", "1.", ".5"])

# ---------- whitespace / structural variants to reach unexercised branches ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "\r\n", "  "])

_ws_variants = st.builds(
    lambda a, b, c, v: a + v + b + c,
    _ws, _ws, _ws, _json_value,
)

_ws_inside = st.builds(
    lambda a, b, c, d, e, k, v1, v2: (
        "{" + a + k + b + ":" + c + v1 + d + "," + e + k + ":" + v2 + "}"
    ),
    _ws, _ws, _ws, _ws, _ws, _json_string, _json_value, _json_value,
)

_ws_array = st.builds(
    lambda a, b, c, d, e, xs: (
        "[" + a + (b + "," + c).join(xs) + d + e + "]"
    ),
    _ws, _ws, _ws, _ws, _ws,
    st.lists(_json_value, min_size=1, max_size=4),
)

_bom_and_unicode = st.sampled_from([
    "\ufeff{}", "\ufeff[]", "\ufeff1", "\ufeff\"a\"",
    "\u00a0{}", "\u2028{}", "\u2029{}", "\u000b{}", "\u000c{}",
    "{} \ufeff", "[1]\ufeff",
])

_nested_structures = st.one_of(
    st.builds(lambda v: "[" + v + "]", _json_value),
    st.builds(lambda k, v: "{" + k + ":" + v + "}", _json_string, _json_value),
    st.builds(lambda v: "[" + v + "]", _json_value),
)

# ---------- top-level ----------

strategy = st.one_of(
    _json_value,
    _deep_nesting,
    _dup_keys,
    _trailing,
    _malformed,
    _lone_sign,
    _ws_variants,
    _ws_inside,
    _ws_array,
    _bom_and_unicode,
    _nested_structures,
    st.just(""),
    st.just(" "),
    st.just("{}"),
    st.just("[]"),
    # Exercise parser branches for literal keywords in non-standalone
    # positions and structurally-nested partial keywords.
    st.sampled_from([
        "[true]", "[false]", "[null]", '{"a":true}', '{"a":false}',
        '{"a":null}', "[true,false,null]", "truex", "nul", "fals",
        "tru", "tr", "fa", "nu", "n", "t", "f",
        "{\"a\":tru}", "{\"a\":fals}", "{\"a\":nul}",
        "[tru]", "[fals]", "[nul]",
        "{\"a\":true,\"b\":false,\"c\":null}",
    ]),
)