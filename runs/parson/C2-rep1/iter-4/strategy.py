from hypothesis import strategies as st
import json

# ---------- primitives ----------

def _hex_digits(n):
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=n, max_size=n)

# safe code points: exclude quote, backslash, control chars, and NUL
_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f",
)

_esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_esc_unicode = st.builds(
    lambda h: "\\u" + h,
    _hex_digits(4),
)

# surrogate escapes (lone and paired) - these are text, fine for the parser
_surrogate_esc = st.builds(
    lambda h: "\\u" + h,
    st.sampled_from(["d800", "dbff", "dc00", "dfff", "D800", "DC00", "d83d", "de00"]),
)

_esc = st.one_of(_esc_simple, _esc_unicode, _surrogate_esc)

# string body pieces
_str_piece = st.one_of(
    _safe_char.map(lambda c: c),
    _esc,
    st.just("\\u0000"),  # embedded NUL escape - text, not raw NUL
    st.just("\\u001f"),
)

# a STRING token: quoted, possibly empty; allow longer strings for more variety
_string_token = st.lists(_str_piece, min_size=0, max_size=16).map(lambda ps: '"' + "".join(ps) + '"')

# ---------- numbers ----------

_int_small = st.integers(min_value=-1000, max_value=1000)
_int_big = st.integers(min_value=-(2**70), max_value=2**70)

_exp = st.one_of(
    st.nothing(),
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.integers(min_value=-400, max_value=400).map(lambda e: "E+" + str(e)),
    st.just("e309"),
    st.just("e-309"),
    st.just("e999"),
    st.just("E+999"),
    st.just("e01"),
    st.just("e0"),
)

_frac = st.one_of(
    st.nothing(),
    st.integers(min_value=0, max_value=10**6).map(lambda f: "." + str(f)),
    st.just(".0"),
    st.just(".000000"),
)

def _make_number(i, f, e):
    return ("" if i >= 0 else "-") + str(abs(i)) + f + e

_number = st.one_of(
    st.builds(_make_number, _int_small, _frac, _exp),
    st.builds(_make_number, _int_big, _frac, _exp),
    # extremes
    st.just("0"),
    st.just("-0"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e308"),
    st.just("1e-308"),
    st.just("1.7976931348623157e308"),
    st.just("1.8e308"),
    st.just("123456789012345678901234567890"),
    st.just("-123456789012345678901234567890"),
)

# ---------- malformed / near-valid fragments ----------

_malformed_fragments = st.sampled_from([
    ",",
    ",,",
    "{,}",
    "[,]",
    "[1,]",
    "[,1]",
    '{"a":}',
    '{"a" 1}',
    '{"a"::1}',
    '{"a":1,}',
    '{"a":1,,"b":2}',
    '{"a"}',
    '{:1}',
    '"unterminated',
    "'single'",
    "tru",
    "fals",
    "nul",
    "True",
    "FALSE",
    "NULL",
    "01",
    "007",
    "+1",
    ".5",
    "-.5",
    "1.",
    "1.e5",
    "-",
    "-.",
    "0x10",
    "1e",
    "1e+",
    "1e-",
    "--1",
    "1..2",
    "NaN",
    "Infinity",
    "-Infinity",
    "undefined",
    "\\u",
    "\\x41",
    "\x01",
    "\x1f",
    "\x7f",
])

# ---------- recursive JSON values ----------

json_value = st.deferred(lambda: _json_value)

_key = _string_token

_pair = st.builds(
    lambda k, v: k + ":" + v,
    _key,
    json_value,
)

# broaden accepted structures: larger objects/arrays, deeper mixes
_obj = st.one_of(
    st.just("{}"),
    st.lists(_pair, min_size=1, max_size=10).map(lambda ps: "{" + ",".join(ps) + "}"),
    # duplicate keys
    st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        _key,
        json_value,
        json_value,
    ),
    # trailing comma etc
    st.builds(lambda p: "{" + p + ",}", _pair),
    # many duplicate keys
    st.builds(
        lambda k, vs: "{" + ",".join(k + ":" + v for v in vs) + "}",
        _key,
        st.lists(json_value, min_size=2, max_size=6),
    ),
)

_arr = st.one_of(
    st.just("[]"),
    st.lists(json_value, min_size=1, max_size=10).map(lambda vs: "[" + ",".join(vs) + "]"),
    st.builds(lambda v: "[" + v + ",]", json_value),
    # nested homogeneous arrays
    st.builds(
        lambda vs: "[" + ",".join("[" + v + "]" for v in vs) + "]",
        st.lists(json_value, min_size=1, max_size=5),
    ),
)

_json_value = st.one_of(
    _string_token,
    _number,
    _obj,
    _arr,
    st.sampled_from(["true", "false", "null"]),
    _malformed_fragments,
)

# ---------- depth control near 2048 ----------

def _deep(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

# concentrate near the limit: 2000..2060
_depth_near = st.integers(min_value=2000, max_value=2060)

_deep_arr = st.builds(
    lambda d: "[" * d + "0" + "]" * d,
    _depth_near,
)

_deep_obj = st.builds(
    lambda d: '{"k":' * d + "0" + "}" * d,
    _depth_near,
)

# moderate nesting via recursive
_deep_structured = st.recursive(
    json_value,
    lambda children: st.one_of(
        st.builds(lambda c: "[" + c + "]", children),
        st.builds(lambda c: '{"k":' + c + "}", children),
    ),
    max_leaves=80,
)

# broader structured combinations: mixed nesting of objects and arrays
_mixed_structure = st.recursive(
    st.one_of(_number, _string_token, st.sampled_from(["true", "false", "null"])),
    lambda children: st.one_of(
        st.builds(lambda cs: "[" + ",".join(cs) + "]", st.lists(children, min_size=1, max_size=5)),
        st.builds(lambda cs: "{" + ",".join('"k' + str(i) + '":' + c for i, c in enumerate(cs)) + "}",
                   st.lists(children, min_size=1, max_size=5)),
    ),
    max_leaves=30,
)

# ---------- broader exploration: alternative valid structures ----------

# arrays with whitespace between elements / around brackets
_ws = st.sampled_from(["", " ", "\n", "\t", " \n ", "\r\n"])
_ws_arr = st.builds(
    lambda w1, vs, w2: "[" + w1 + ("," + w1).join(vs) + w2 + "]",
    _ws,
    st.lists(json_value, min_size=0, max_size=6),
    _ws,
)

_ws_obj = st.builds(
    lambda w1, ps, w2: "{" + w1 + ("," + w1).join(ps) + w2 + "}",
    _ws,
    st.lists(_pair, min_size=0, max_size=6),
    _ws,
)

# empty/whitespace-only top-level around values
_padded = st.builds(
    lambda a, v, b: a + v + b,
    _ws,
    json_value,
    _ws,
)

# objects with varied key shapes
_varied_keys = st.one_of(
    st.just('""'),
    _string_token,
    st.just('"\\u0000"'),
    st.just('"\\n"'),
    st.just('"a b"'),
    st.just('"\\u0041"'),
)

_varied_obj = st.builds(
    lambda ks, vs: "{" + ",".join(k + ":" + v for k, v in zip(ks, vs)) + "}",
    st.lists(_varied_keys, min_size=1, max_size=5),
    st.lists(json_value, min_size=1, max_size=5),
)

# arrays of arrays / objects of objects (structural diversity)
_nested_homogeneous = st.one_of(
    st.builds(
        lambda vs: "[" + ",".join("[" + v + "]" for v in vs) + "]",
        st.lists(json_value, min_size=1, max_size=4),
    ),
    st.builds(
        lambda ps: "{" + ",".join('"k' + str(i) + '":{' + '"x":' + v + "}" for i, v in enumerate(ps)) + "}",
        st.lists(json_value, min_size=1, max_size=4),
    ),
)

# ---------- broadened exploration: new structural diversity ----------

# arrays with mixed types at each position (heterogeneous, depth 2-3)
_hetero_arr = st.builds(
    lambda vs: "[" + ",".join(vs) + "]",
    st.lists(
        st.one_of(
            _number,
            _string_token,
            st.sampled_from(["true", "false", "null"]),
            st.builds(lambda v: "[" + v + "]", json_value),
            st.builds(lambda k, v: "{" + k + ":" + v + "}", _key, json_value),
        ),
        min_size=1,
        max_size=8,
    ),
)

# objects with heterogeneous value types
_hetero_obj = st.builds(
    lambda ps: "{" + ",".join(ps) + "}",
    st.lists(
        st.builds(
            lambda k, v: k + ":" + v,
            _key,
            st.one_of(
                _number,
                _string_token,
                st.sampled_from(["true", "false", "null"]),
                st.builds(lambda v: "[" + v + "]", json_value),
                st.builds(lambda k2, v2: "{" + k2 + ":" + v2 + "}", _key, json_value),
            ),
        ),
        min_size=1,
        max_size=8,
    ),
)

# deeply mixed: alternating array/object nesting
_alternating = st.builds(
    lambda d, v: ("[{" * d) + v + ("}]" * d),
    st.integers(min_value=1, max_value=12),
    json_value,
)

# arrays of objects with consistent schema (typical real-world data)
_array_of_objects = st.builds(
    lambda keys, rows: "[" + ",".join(
        "{" + ",".join(k + ":" + v for k, v in zip(keys, row)) + "}"
        for row in rows
    ) + "]",
    st.lists(_varied_keys, min_size=1, max_size=4),
    st.lists(st.lists(json_value, min_size=1, max_size=4), min_size=1, max_size=4),
)

# objects of arrays (typical real-world data)
_object_of_arrays = st.builds(
    lambda ks, arrs: "{" + ",".join(
        k + ":" + "[" + ",".join(a) + "]" for k, a in zip(ks, arrs)
    ) + "}",
    st.lists(_varied_keys, min_size=1, max_size=4),
    st.lists(st.lists(json_value, min_size=0, max_size=4), min_size=1, max_size=4),
)

# top-level scalars wrapped in whitespace and comments-like padding
# (parser may accept surrounding whitespace)
_scalar_top = st.builds(
    lambda w1, v, w2: w1 + v + w2,
    _ws,
    st.one_of(_number, _string_token, st.sampled_from(["true", "false", "null"])),
    _ws,
)

# numbers with leading zeros in exponent / unusual but valid forms
_unusual_numbers = st.sampled_from([
    "0e0", "0E0", "0e+0", "0e-0", "0.0e0", "-0.0", "1E0", "1E+0",
    "1.0e+10", "1.0E-10", "1000000000000000000000000000000000000000000",
    "-0.0000000000000000000000000000000000000000001",
    "0.1", "0.10", "0.100", "1e-1", "1E-1",
])

# strings with all escape types mixed
_mixed_escapes = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(
        st.one_of(
            _safe_char.map(lambda c: c),
            _esc_simple,
            _esc_unicode,
            _surrogate_esc,
            st.just("\\u0000"),
            st.just("\\u001f"),
            st.just("\\u007f"),
            st.just("\\u00ff"),
            st.just("\\uffff"),
        ),
        min_size=0,
        max_size=24,
    ),
)

# ---------- top-level ----------

_trailing = st.one_of(
    st.nothing(),
    st.sampled_from(["", " ", "\n", "abc", " garbage", "xyz", "\t\n", "//c", "/*c*/"]),
)

_top = st.one_of(
    json_value,
    _deep_arr,
    _deep_obj,
    _deep_structured,
    _mixed_structure,
    # broader exploration additions
    _ws_arr,
    _ws_obj,
    _padded,
    _varied_obj,
    _nested_homogeneous,
    # NEW broadened structures
    _hetero_arr,
    _hetero_obj,
    _alternating,
    _array_of_objects,
    _object_of_arrays,
    _scalar_top,
    _unusual_numbers,
    _mixed_escapes,
    # empty containers
    st.sampled_from(["{}", "[]", " \t\n{} \r\n", "[] ", "{}"]),
    # lone sign leniency
    st.sampled_from(["-", "-.", "-e5", "-.e5"]),
    # trailing content after complete value (accepted by parser)
    st.builds(lambda v, t: v + t, json_value, _trailing),
    # malformed
    _malformed_fragments,
)

strategy = _top