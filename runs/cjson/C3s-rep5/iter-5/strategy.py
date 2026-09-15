from hypothesis import strategies as st
import json

# ---------- helpers ----------

_safe_cp = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"',
    min_codepoint=0x20,
    max_codepoint=0x10FFFF,
)

_control = st.sampled_from(["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x7f"])

_esc_short = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_esc_unicode = _hex4.map(lambda h: "\\u" + h)

# lone surrogate escapes: parser REJECTS these (interesting near-valid input)
_lone_surrogate = st.sampled_from(["\\ud800", "\\udfff", "\\uD800", "\\uDC00"])

# valid surrogate pair
_surrogate_pair = st.tuples(
    st.sampled_from(["d800", "d801", "dbff", "D800", "DBFF"]),
    st.sampled_from(["dc00", "dc01", "dfff", "DC00", "DFFF"]),
).map(lambda t: "\\u" + t[0] + "\\u" + t[1])

# a high surrogate escape NOT followed by a low surrogate (parser must reject)
_bad_surrogate_escape = st.tuples(
    st.sampled_from(["d800", "dbff", "D800"]),
    st.sampled_from(["\\u0041", "\\uZZZZ", "x", "", "\\", "\\u12"]),
).map(lambda t: "\\u" + t[0] + t[1])

_esc = st.one_of(
    _esc_short, _esc_unicode, _lone_surrogate, _surrogate_pair,
    _bad_surrogate_escape,
)

_str_char = st.one_of(_safe_cp, _control, _esc)

_string = st.lists(_str_char, max_size=8).map(lambda cs: '"' + "".join(cs) + '"')

# unterminated string: near-valid-but-malformed
_unterminated_string = st.lists(_str_char, min_size=0, max_size=6).map(
    lambda cs: '"' + "".join(cs)
)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)
_nonzero = st.text(alphabet="123456789", min_size=1, max_size=1)

# grammar-valid int
_int_ok = st.one_of(
    st.just("0"),
    st.tuples(_nonzero, _digits).map(lambda t: t[0] + t[1]),
)

# leading zero (accepted by parser, rejected by strict)
_leading_zero = st.tuples(st.just("0"), _digits).map(lambda t: t[0] + t[1])

# extreme exponents incl. overflow
_exp = st.one_of(
    st.just("e309"),
    st.just("E309"),
    st.just("e-309"),
    st.just("e308"),
    st.just("e+308"),
    st.just("e999999999"),
    st.just("e-999999999"),
    st.tuples(st.sampled_from(["e", "E"]),
              st.sampled_from(["", "+", "-"]),
              _digits).map(lambda t: t[0] + t[1] + t[2]),
)

_frac = st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1])

_number_ok = st.one_of(
    _int_ok,
    st.tuples(st.just("-"), _int_ok).map(lambda t: t[0] + t[1]),
    st.tuples(_int_ok, _frac).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("-"), _int_ok, _frac).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_int_ok, _exp).map(lambda t: t[0] + t[1]),
    st.tuples(_int_ok, _frac, _exp).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(st.just("-"), _int_ok, _exp).map(lambda t: t[0] + t[1] + t[2]),
)

# malformed / lenient numbers
_number_bad = st.one_of(
    st.just("-"),
    st.just("+1"),
    st.just(".5"),
    st.just("1."),
    st.just("-01"),
    _leading_zero,
    st.just("0x10"),
    st.just("0X1f"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.tuples(_int_ok, _exp).map(lambda t: t[0] + t[1] + "."),
)

_number = st.one_of(_number_ok, _number_bad)

# ---------- recursive obj/arr ----------

_ws = st.text(alphabet=" \t\n\r", max_size=3)

def _join(parts):
    return "".join(parts)

# key: mostly valid strings, sometimes malformed (unquoted / single-quoted)
_key = st.one_of(
    _string,
    st.text(alphabet="abcXYZ_0123", min_size=1, max_size=5),
    st.tuples(st.just("'"), st.text(alphabet="abcXYZ", min_size=1, max_size=4),
              st.just("'")).map(_join),
)

# a "pair" as a list of string pieces; may be malformed
_pair = st.one_of(
    st.tuples(_key, st.just(":"), st.deferred(lambda: _value)).map(_join),
    st.tuples(_key, st.deferred(lambda: _value)).map(_join),          # missing colon
    st.tuples(_key, st.just(":"), st.just(":")).map(_join),           # extra colon
)

# separators: valid comma, or malformed double/trailing commas
_sep = st.one_of(
    st.just(","),
    st.just(",,"),
    st.just(" , "),
)

_obj_inner = st.one_of(
    st.just(""),
    st.lists(_pair, min_size=1, max_size=4).map(lambda ps: ",".join(ps)),
    # trailing comma (rejected by parser)
    st.lists(_pair, min_size=1, max_size=3).map(lambda ps: ",".join(ps) + ","),
    # double commas between pairs
    st.lists(_pair, min_size=2, max_size=3).map(lambda ps: ",,".join(ps)),
    st.lists(_pair, min_size=1, max_size=3).map(
        lambda ps: "".join(p + s for p, s in zip(ps, [","] * len(ps)))
    ),
)

_arr_inner = st.one_of(
    st.just(""),
    st.lists(st.deferred(lambda: _value), min_size=1, max_size=4).map(
        lambda vs: ",".join(vs)
    ),
    # trailing comma (rejected by parser)
    st.lists(st.deferred(lambda: _value), min_size=1, max_size=3).map(
        lambda vs: ",".join(vs) + ","
    ),
    # double commas
    st.lists(st.deferred(lambda: _value), min_size=2, max_size=3).map(
        lambda vs: ",,".join(vs)
    ),
)

_obj = _obj_inner.map(lambda inner: "{" + inner + "}")

# unterminated containers: exercise EOF-inside-container error branches
_unterminated_obj = _obj_inner.map(lambda inner: "{" + inner)
_unterminated_arr = _arr_inner.map(lambda inner: "[" + inner)

# missing colon variants with whitespace and EOF
_obj_missing_colon = st.tuples(
    _key, st.just(" "), st.deferred(lambda: _value)
).map(_join)

# colon but no value (EOF after colon)
_obj_colon_eof = st.tuples(_key, st.just(":")).map(_join)

_arr = _arr_inner.map(lambda inner: "[" + inner + "]")

_literal = st.sampled_from(["true", "false", "null"])

_value = st.deferred(
    lambda: st.one_of(
        _string,
        _unterminated_string,
        _number,
        _literal,
        _obj,
        _arr,
    )
)

# ---------- depth control ----------

def _nest(depth, inner):
    """Wrap `inner` in `depth` levels of arrays/objects, alternating."""
    s = inner
    for i in range(depth):
        if i % 2 == 0:
            s = "[" + s + "]"
        else:
            s = '{"k":' + s + "}"
    return s

# depth values concentrated near the 1000 limit
_depth = st.one_of(
    st.integers(min_value=0, max_value=5),
    st.sampled_from([10, 50, 100, 500, 900, 998, 999, 1000, 1001, 1002, 1100]),
    st.integers(min_value=990, max_value=1010),
)

_deep_value = st.tuples(_depth, _value).map(lambda t: _nest(t[0], t[1]))

# ---------- top-level assembly ----------

_bom = st.just("\ufeff")

def _prepend_bom(s):
    return "\ufeff" + s

# inputs with raw (unescaped) multi-byte / non-ASCII characters inside strings,
# exercising the parser's UTF-8 decode and multibyte-copy branches
_raw_utf8 = st.sampled_from([
    "\u00e9", "\u00ff", "\u0100", "\u07ff", "\u0800", "\u4e2d", "\u20ac",
    "\U0001f600", "\U00010000", "\U0010ffff", "\u0080",
])

_raw_string = st.lists(
    st.one_of(_safe_cp, _raw_utf8), max_size=6
).map(lambda cs: '"' + "".join(cs) + '"')

_raw_key = st.lists(
    st.one_of(st.characters(min_codepoint=0x21, max_codepoint=0x10FFFF,
                            blacklist_characters='"\\'),
              _raw_utf8),
    min_size=1, max_size=4,
).map(lambda cs: '"' + "".join(cs) + '"')

_raw_pair = st.tuples(_raw_key, st.just(":"), st.deferred(lambda: _value)).map(_join)

_raw_obj = st.lists(_raw_pair, min_size=1, max_size=3).map(
    lambda ps: "{" + ",".join(ps) + "}"
)

# raw bytes that are not valid UTF-8 (parser must handle decode failure branch)
_invalid_utf8 = st.sampled_from([
    "\x80", "\xbf", "\xc0", "\xc1", "\xf5", "\xfe", "\xff",
    "\xc0\x80", "\xed\xa0\x80", "\xf4\x90\x80\x80", "\xe0\x80\x80",
])

_invalid_utf8_value = st.lists(
    st.one_of(_safe_cp, _invalid_utf8), max_size=4
).map(lambda cs: '"' + "".join(cs) + '"')

# malformed container inputs that exercise error/EOF branches
_malformed_container = st.one_of(
    _unterminated_obj,
    _unterminated_arr,
    _obj_missing_colon,
    _obj_colon_eof,
    st.just("{"),
    st.just("["),
    st.just("}"),
    st.just("]"),
    st.just('{"a"'),
    st.just('{"a":'),
    st.just("[1"),
    st.just("[1,"),
    st.just('{"a":1'),
    st.just('{"a":1,'),
    st.just('["'),
    st.just('{"'),
)

# whitespace-only and separator-heavy inputs to reach skip-ws / separator branches
_ws_only = st.text(alphabet=" \t\n\r", min_size=1, max_size=6)

# inputs that mix valid values with all separator/whitespace/EOF edge cases
_sep_edge = st.one_of(
    st.just("[,]"),
    st.just("[,1]"),
    st.just("[1,,2]"),
    st.just('{,}'),
    st.just('{"a":1,,}'),
    st.just('{"a",}'),
    st.just('{"a":}'),
    st.just('{"a"1}'),
    st.just('{1:2}'),
    st.just('{"a":1 "b":2}'),
    st.just("[1 2]"),
    st.just("[1;2]"),
    st.just('{"a";"b"}'),
    st.just('true false'),
    st.just('null null'),
    st.just('"a" "b"'),
    st.just('123 456'),
    st.just('123abc'),
    st.just('truex'),
    st.just('nullx'),
    st.just('nul'),
    st.just('tru'),
    st.just('fals'),
    st.just('t'),
    st.just('f'),
    st.just('n'),
    st.just('[true,]'),
    st.just('{"a":true,}'),
    st.just('{"a":null}'),
    st.just('{"a":false}'),
)

# ---------- NEW: branch-coverage boosters ----------

# whitespace between structural tokens, including exotic ws bytes
_ws_any = st.text(alphabet=" \t\n\r\f\v", max_size=3)

# containers with whitespace around every structural token (colon, comma, braces)
_ws_obj = st.lists(
    st.tuples(
        _ws_any, _key, _ws_any, st.just(":"), _ws_any,
        st.deferred(lambda: _value), _ws_any,
    ).map(_join),
    min_size=1, max_size=3,
).map(lambda ps: "{" + ",".join(ps) + "}")

_ws_arr = st.lists(
    st.tuples(_ws_any, st.deferred(lambda: _value), _ws_any).map(_join),
    min_size=1, max_size=3,
).map(lambda vs: "[" + ",".join(vs) + "]")

# nested combination of valid ws-wrapped containers
_ws_nested = st.one_of(
    _ws_obj,
    _ws_arr,
    st.tuples(_ws_arr, _ws_any, _ws_obj).map(_join),
    st.tuples(_ws_obj, _ws_any, _ws_arr).map(_join),
)

# strings with escapes at the very end / start (copy-loop boundary branches)
_esc_boundary_string = st.one_of(
    st.tuples(st.just('"'), _esc).map(_join),                       # just an escape
    st.tuples(st.just('"'), _esc_short, st.just('"')).map(_join),
    st.tuples(st.just('"'), _esc_unicode, st.just('"')).map(_join),
    st.tuples(st.just('"'), _safe_cp, _esc, st.just('"')).map(_join),
    st.tuples(st.just('"'), _esc, _safe_cp, st.just('"')).map(_join),
    st.tuples(st.just('"'), _esc_unicode, _esc_unicode, st.just('"')).map(_join),
    st.tuples(st.just('"'), _esc_short, _esc_short, _esc_short, st.just('"')).map(_join),
)

# escape sequences with malformed hex (parser hex-decode error branch)
_bad_hex_escape = st.tuples(
    st.just("\\u"),
    st.text(alphabet="0123456789abcdefABCDEF", min_size=0, max_size=3),
).map(_join)

_bad_escape_string = st.one_of(
    st.tuples(st.just('"'), _bad_hex_escape, st.just('"')).map(_join),
    st.tuples(st.just('"'), st.just("\\"), st.just('"')).map(_join),   # trailing backslash
    st.tuples(st.just('"'), st.just("\\x"), st.just('"')).map(_join),
    st.tuples(st.just('"'), st.just("\\u"), st.just('"')).map(_join),
    st.tuples(st.just('"'), st.just("\\"), _safe_cp).map(_join),       # unterminated w/ backslash
)

# literals with trailing garbage / partial matches at various prefixes
_literal_prefix = st.sampled_from([
    "t", "tr", "tru", "true", "f", "fa", "fal", "fals", "false",
    "n", "nu", "nul", "null", "truee", "falsee", "nullx", "True", "NULL",
    "tRue", "FALSE", "Null",
])

# numbers with weird internal structures to hit digit/exp state branches
_number_edge = st.one_of(
    st.tuples(st.just("-"), st.just("0")).map(_join),
    st.tuples(st.just("-"), st.just("0"), _frac).map(_join),
    st.tuples(st.just("0"), _frac, _exp).map(_join),
    st.tuples(st.just("0"), _exp).map(_join),
    st.tuples(st.just("0"), st.just("e")).map(_join),
    st.tuples(st.just("0"), st.just("e+")).map(_join),
    st.tuples(st.just("0"), st.just("e-")).map(_join),
    st.tuples(st.just("1"), st.just("e+"), st.just("")).map(_join),
    st.tuples(st.just("1"), st.just("E-")).map(_join),
    st.tuples(st.just("."), st.just("")).map(_join),
    st.tuples(st.just("-"), st.just(".")).map(_join),
    st.tuples(st.just("1"), st.just("."), st.just("e")).map(_join),
    st.tuples(st.just("1"), st.just("."), st.just("e+")).map(_join),
    st.tuples(st.just("00"), _digits).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("-"), st.just("0"), _digits).map(_join),
)

# empty-ish and structural-only inputs that stress top-level dispatch
_structural = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\t"),
    st.just("\n"),
    st.just("\r"),
    st.just("\f"),
    st.just("\v"),
    st.just("  \t\n\r"),
    st.just(":"),
    st.just(","),
    st.just("{}"),
    st.just("[]"),
    st.just("[]{}"),
    st.just("{}[]"),
    st.just("[{}]"),
    st.just("{[[]]}"),
    st.just("[[[[[]]]]]"),
    st.just('{"a":{}}'),
    st.just('{"a":[]}'),
    st.just('[{"a":1}]'),
    st.just('{"a":[1,2,3]}'),
)

# deeply nested with ws at every level to hit recursion + ws branches together
_deep_ws_value = st.tuples(_depth, _value).map(
    lambda t: _nest(t[0], t[1]) + " " * (t[0] % 3)
)

_top = st.one_of(
    _value,
    _deep_value,
    _raw_string,
    _raw_obj,
    _invalid_utf8_value,
    _malformed_container,
    _ws_only,
    _sep_edge,
    _ws_nested,                 # NEW
    _esc_boundary_string,       # NEW
    _bad_escape_string,         # NEW
    _literal_prefix,            # NEW
    _number_edge,               # NEW
    _structural,                # NEW
    _deep_ws_value,             # NEW
    st.tuples(_value, st.text(alphabet="abc012 \t", max_size=4)).map(_join),  # trailing content
    st.tuples(_value, st.just("\x00")).map(_join),                            # NUL after value
    st.tuples(_value, st.just(" 2")).map(_join),                              # two top-level values
    st.tuples(_value, _value).map(lambda t: t[0] + " " + t[1]),
    _value.map(_prepend_bom),                                                 # BOM prefix
    st.tuples(_ws, _value, _ws).map(_join),                                   # surrounding whitespace
    st.just(""),
    st.just("   "),
    st.just(","),
    st.just(":"),
    st.just("{},"),
    st.just("[1,2,]"),
    st.just('{"a":1,}'),
)

strategy = _top