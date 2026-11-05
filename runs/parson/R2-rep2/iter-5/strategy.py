import json
from hypothesis import strategies as st

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

def _join_comma(parts):
    return ",".join(parts)

# ---------- scalars ----------

_hex = "0123456789abcdefABCDEF"

def _hex4():
    return st.tuples(*([st.sampled_from(_hex)] * 4)).map(lambda t: "".join(t))

# \uXXXX escapes including surrogates
_unicode_escape = _hex4().map(lambda h: "\\u" + h)

# simple escapes
_simple_escape = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

# safe code points (excluding quote, backslash, control chars)
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00',
).filter(lambda c: ord(c) >= 0x20)

_string_body_piece = st.one_of(
    _safe_char,
    _simple_escape,
    _unicode_escape,
)

_json_string = st.lists(_string_body_piece, max_size=8).map(_join).map(lambda s: '"' + s + '"')

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

def _int_part():
    return st.one_of(
        st.just("0"),
        st.tuples(st.sampled_from("123456789"), _digits.map(lambda d: d)).map(_join),
    )

def _frac_part():
    return _digits.map(lambda d: "." + d)

def _exp_part():
    return st.tuples(
        st.sampled_from("eE"),
        st.sampled_from(["", "+", "-"]),
        st.text(alphabet="0123456789", min_size=1, max_size=4),
    ).map(_join)

def _number():
    sign = st.sampled_from(["", "-"])
    frac = st.one_of(st.just(""), _frac_part())
    exp = st.one_of(st.just(""), _exp_part())
    return st.tuples(sign, _int_part(), frac, exp).map(_join)

# extreme magnitudes
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "-1e308", "1e400", "1e-400",
    "123456789012345678901234567890",
    "-123456789012345678901234567890",
    "1.7976931348623157e308",
    "2.2250738585072014e-308",
    "0e0", "0.0", "-0", "1E+10", "1e-10",
])

_number_strategy = st.one_of(_number(), _extreme_number)

# ---------- recursive values ----------

_key = _json_string

# forward reference via deferred strategy
_value_ref = st.deferred(lambda: _value)

def _pair():
    return st.tuples(_key, st.just(":"), _value_ref).map(_join)

def _obj():
    return st.one_of(
        st.just("{}"),
        st.lists(_pair(), min_size=1, max_size=4).map(lambda ps: "{" + ",".join(ps) + "}"),
    )

def _arr():
    return st.one_of(
        st.just("[]"),
        st.lists(_value_ref, min_size=1, max_size=4).map(lambda vs: "[" + ",".join(vs) + "]"),
    )

_leaf = st.one_of(
    _json_string,
    _number_strategy,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_value = st.recursive(
    _leaf,
    lambda children: st.one_of(_obj(), _arr()),
    max_leaves=12,
)

# ---------- deep nesting near the 2048 limit ----------

def _deep_nesting():
    # depth concentrated near 2048
    depth = st.integers(min_value=1, max_value=2048)
    open_ch = st.sampled_from(["[", "{"])
    return st.tuples(depth, open_ch).map(lambda t: _build_deep(t[0], t[1]))

def _build_deep(depth, ch):
    if ch == "[":
        return "[" * depth + "]" * depth
    else:
        return ('{"k":' * depth) + "0" + ("}" * depth)

_deep = _deep_nesting()

# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    '{"a":1,,}',
    '{"a":1,}',
    "[1,,2]",
    "[1,]",
    '{"a" 1}',
    '{"a":}',
    '{"a":1 "b":2}',
    '{"a":1,,"b":2}',
    '[,]',
    '{,}',
    '{"a":1',
    '[1,2',
    '"unterminated',
    '"unterminated\\',
    '{"a":"unterminated}',
    '+1',
    '.5',
    '-.5',
    '01',
    '-01',
    '1.',
    '00',
    '1e',
    '1e+',
    '-',
    '-.',
    'tru',
    'nul',
    'fals',
    '{"a":1}garbage',
    '[]xyz',
    '1abc',
    '1 garbage',
    'null extra',
    'true false',
    '{"a":1} {"b":2}',
    '"\\uD800"',
    '"\\uDFFF"',
    '"\\uD800\\uDC00"',
    '"\\u0000"',
    '"\\u00"',
    '"\\uZZZZ"',
    '"\\x"',
    '"\\"',
    '{"a":1,"a":2}',
    '{"k":0,"k":1}',
    '{"a":{"b":1},"a":2}',
])

# ---------- top-level combination ----------

def _with_trailing(v):
    return st.tuples(v, st.sampled_from(["", " ", "x", " garbage", "\n", "[]"])).map(_join)

# Generate whitespace-heavy variants to hit whitespace-skipping branches.
_ws = st.sampled_from([" ", "\t", "\n", "\r"])

def _ws_list():
    return st.lists(_ws, min_size=0, max_size=4).map(_join)

def _ws_wrap_value():
    return st.tuples(_ws_list(), _value, _ws_list()).map(_join)

def _ws_obj():
    # object with whitespace around tokens
    return st.tuples(
        _ws_list(), st.just("{"), _ws_list(),
        st.lists(_ws_pair(), min_size=0, max_size=4).map(_join_comma),
        _ws_list(), st.just("}"), _ws_list(),
    ).map(_join)

def _ws_pair():
    return st.tuples(_ws_list(), _json_string, _ws_list(), st.just(":"),
                     _ws_list(), _value, _ws_list()).map(_join)

def _ws_arr():
    return st.tuples(
        _ws_list(), st.just("["), _ws_list(),
        st.lists(_ws_wrap_value(), min_size=0, max_size=4).map(_join_comma),
        _ws_list(), st.just("]"), _ws_list(),
    ).map(_join)

_ws_value = st.recursive(
    st.one_of(_leaf, _ws_wrap_value()),
    lambda children: st.one_of(_ws_obj(), _ws_arr()),
    max_leaves=8,
)

# Empty containers with whitespace inside
_empty_ws = st.one_of(
    st.tuples(_ws_list(), st.just("["), _ws_list(), st.just("]")).map(_join),
    st.tuples(_ws_list(), st.just("{"), _ws_list(), st.just("}")).map(_join),
)

# ---------- error-path / truncated inputs ----------

# Truncate a valid value at a random position to exercise EOF/error branches.
def _truncated(v):
    return st.tuples(v, st.integers(min_value=0, max_value=64)).map(
        lambda t: t[0][:max(0, len(t[0]) - t[1])] if t[0] else t[0]
    )

# Random byte-soup-ish mutations from a small alphabet to hit lexer errors.
_mutate_alphabet = st.sampled_from(list('{}[],:"\\0123456789.eE+-truefalsnul \t\n\rxyz'))

def _mutated(v):
    def _apply(t):
        s, ops = t
        s = list(s)
        for op in ops:
            kind = op[0]
            if kind == 0 and s:
                i = op[1] % len(s)
                s[i] = op[2]
            elif kind == 1 and s:
                i = op[1] % len(s)
                del s[i]
            elif kind == 2:
                i = op[1] % (len(s) + 1)
                s.insert(i, op[2])
        return "".join(s)
    return st.tuples(
        v,
        st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=2),
                st.integers(min_value=0, max_value=4096),
                _mutate_alphabet,
            ),
            min_size=1, max_size=4,
        ),
    ).map(_apply)

# Prefix/suffix garbage to exercise trailing-byte and leading-byte handling.
_garbage = st.sampled_from(["", " ", "x", "\x00", "\xff", "[]", "{}", "null", "0"])

def _surround(v):
    return st.tuples(_garbage, v, _garbage).map(_join)

_value_top = st.one_of(
    _value,
    _deep,
    _malformed,
    _ws_value,
    _empty_ws,
    _truncated(_value),
    _truncated(_ws_value),
    _mutated(_value),
    _mutated(_ws_value),
    _surround(_value),
    _surround(_ws_value),
)

# avoid raw NUL bytes in final output
_final = _value_top.map(lambda s: s.replace("\x00", ""))
_final = st.one_of(_final, _with_trailing(_value), _with_trailing(_ws_value))

# ---------- targeted coverage boosters (improve_strategy) ----------

# Exercise deep-ish nesting with mixed brackets and whitespace, plus truncated
# deep inputs to hit recursion-depth and EOF error branches simultaneously.
def _mixed_deep():
    return st.tuples(
        st.integers(min_value=2, max_value=64),
        st.lists(st.sampled_from(["[", "{", "]", "}", " ", "\t", "\n", "\r"]),
                 min_size=1, max_size=8).map(_join),
    ).map(lambda t: t[1] * t[0])

_deep_truncated = st.tuples(_deep, st.integers(min_value=0, max_value=4096)).map(
    lambda t: t[0][:max(0, len(t[0]) - t[1])] if t[0] else t[0]
)

# Whitespace-only and empty inputs to hit skip-whitespace then EOF branches.
_ws_only = st.lists(_ws, min_size=0, max_size=8).map(_join)

# Boundary lengths around typical buffer sizes.
_boundary_len = st.sampled_from([0, 1, 2, 3, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 255, 256, 511, 512, 1023, 1024])
_boundary_input = st.tuples(
    st.sampled_from(["[", "{", '"', "1", "-", "t", "n", "f"]),
    _boundary_len,
).map(lambda t: t[0] * t[1])

# Structural near-misses: valid prefix followed by truncation at bracket boundaries.
def _balanced_prefix():
    return st.tuples(
        st.integers(min_value=1, max_value=32),
        st.sampled_from(["[", "{"]),
    ).map(lambda t: t[1] * t[0])

_struct_trunc = st.tuples(_balanced_prefix(), st.integers(min_value=0, max_value=32)).map(
    lambda t: t[0][:max(0, len(t[0]) - t[1])]
)

# NEW: targeted boosters for string-escape, number, and literal error branches.
# String escapes with lone/invalid escapes and unterminated variants.
_string_escape_fuzz = st.tuples(
    st.lists(
        st.one_of(
            st.sampled_from(['\\u', '\\uD', '\\uD8', '\\uD800', '\\uDC00', '\\uZZZZ',
                             '\\x', '\\', '"', '\\n', '\\t', '\\/', '\\b', '\\f', '\\r',
                             'a', ' ', '\t', '\n']),
        ),
        min_size=0, max_size=6,
    ).map(_join),
    st.sampled_from(['"', '', '"']),
).map(lambda t: '"' + t[0] + t[1])

# Number lexer edge cases: leading zeros, lone signs, exponents, dots.
_number_edge = st.sampled_from([
    "0", "-0", "0.0", "-0.0", "0e0", "0E0", "0e+0", "0e-0",
    "00", "01", "-01", "007", "0.1", "-0.1", ".1", "-.1", "1.", "-1.",
    "1e", "1e+", "1e-", "1E", "1E+", "1E-", "e1", "E1", "+1", "+0",
    "-", "+", ".", "1.2.3", "1e1e1", "1e+-1", "1e--1", "1e+1.5",
    "0x1", "0b1", "0o1", "Infinity", "NaN", "inf", "nan",
    "1e999999", "-1e999999", "1e-999999", "123456789012345678901234567890.0e10",
])

# Literal near-misses: partial keywords and case variants.
_literal_edge = st.sampled_from([
    "t", "tr", "tru", "true", "True", "TRUE", "truex",
    "f", "fa", "fal", "fals", "false", "False", "FALSE", "falsex",
    "n", "nu", "nul", "null", "Null", "NULL", "nullx",
])

# Whitespace edge cases: comments, BOM, vertical tab, form feed.
_ws_edge = st.sampled_from([
    "\xef\xbb\xbf",  # BOM
    "\x0b", "\x0c",  # vertical tab, form feed
    "//", "/", "/*", "*/", "#",
    "\u00a0", "\u2028", "\u2029",  # unicode whitespace
])

# Trailing-comma and separator edge cases in structures.
_struct_edge = st.sampled_from([
    "[,]", "[,,]", "[1,,]", "[,1]", "{,}", "{,,}",
    '{"a":,}', '{"a":1,,}', '{:1}', '{"a"::1}', '{"a":1:2}',
    '{"a":1 "b":2}', '{"a":1,,"b":2}', '[1 2]', '[1,2 3]',
    '{"a":1}x', '{"a":1},', '[1,2],', '{,}', '[]]', '{}}',
    '[[[]]]]', '{"a":{"b":{}}}', '{"a":[1,{"b":2}]}',
])

_extra = st.one_of(
    _mixed_deep(),
    _deep_truncated,
    _ws_only,
    _boundary_input,
    _struct_trunc,
    _string_escape_fuzz,
    _number_edge,
    _literal_edge,
    _ws_edge,
    _struct_edge,
)

_final = st.one_of(_final, _extra)

strategy = _final