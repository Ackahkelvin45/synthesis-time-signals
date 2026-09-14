from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Maximum nesting the parser accepts (deeper is cleanly rejected).
MAX_DEPTH = 2048

# A few interesting depths clustered near the parser's nesting limit.
_DEPTHS = [0, 1, 2, 3, 5, 8, 16, 32, 64, 128, 256, 512, 1024, 1500, 1800,
           2000, 2040, 2044, 2046, 2047, 2048, 2049, 2050, 2052]


def _join(sep):
    """Turn a strategy of tuples of strings into a strategy of joined strings.

    st.tuples(...) yields tuples, so we must .map to a string before joining.
    """
    def _do(tup):
        return sep.join(tup)
    return _do


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

# Ordinary, well-formed JSON numbers.
_plain_int = st.one_of(
    st.just("0"),
    st.just("-0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=10, max_value=10 ** 18).map(str),
    st.integers(min_value=-(10 ** 18), max_value=-10).map(str),
)

_plain_frac = st.builds(
    lambda a, b: a + "." + b,
    st.one_of(st.just("0"), st.integers(min_value=1, max_value=10 ** 9).map(str)),
    st.text(alphabet="0123456789", min_size=1, max_size=12),
)

_plain_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
)

_plain_number = st.one_of(
    _plain_int,
    st.builds(lambda a, b: a + b, _plain_int, _plain_frac),
    st.builds(lambda a, b: a + b, _plain_int, _plain_exp),
    st.builds(lambda a, b, c: a + b + c, _plain_int, _plain_frac, _plain_exp),
)

# Extreme magnitudes / exponents, including overflow (1e309 -> inf -> rejected).
_extreme_number = st.one_of(
    st.sampled_from([
        "1e309", "-1e309", "1e400", "1e9999", "-1e9999",
        "1e308", "1e-308", "1e-400", "1e-9999",
        "0e0", "0e999", "-0e-999",
        "9" * 300, "-" + "9" * 300,
        "0." + "0" * 300 + "1",
        "1" + "0" * 300,
        "1.7976931348623157e308",
        "5e-324",
        "2.2250738585072014e-308",
    ]),
    st.builds(
        lambda d, e: d + "e" + e,
        st.text(alphabet="0123456789", min_size=1, max_size=20),
        st.integers(min_value=-400, max_value=400).map(str),
    ),
)

# Malformed / near-valid numbers (leading +, lone ., leading zeros, lone -).
_malformed_number = st.sampled_from([
    "+1", "+0", "+1.5", "+1e3",
    ".5", "-.5", ".",
    "01", "00", "0123", "-01", "-00",
    "1.", "1.e3", "-1.", "0.",
    "-", "-.",
    "1e", "1e+", "1e-", "1E",
    "0x10", "0b1",
    "1_000",
    "NaN", "Infinity", "-Infinity", "inf", "nan",
    "1.2.3", "1e2e3", "--1", "1-2",
    "1,2",
])

_number = st.one_of(_plain_number, _extreme_number, _malformed_number)


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

# Safe code points (excluding quote, backslash, and control chars).
_safe_char = st.characters(
    blacklist_categories=("Cs",),  # avoid lone surrogates in Python str
    blacklist_characters='"\\\x00\x01\x02\x03\x04\x05\x06\x07\x08'
                         '\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13'
                         '\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_escapes = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
])

_unicode_escape = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
)

# Surrogate escapes (valid as text, may be rejected as unpaired surrogates).
_surrogate_escape = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD800\\uDC00",   # valid surrogate pair
    "\\uD83D\\uDE00",   # U+1F600
    "\\uD800\\uD800",   # two highs
    "\\uDC00\\uDC00",   # two lows
    "\\uD800x",         # lone high then text
    "\\uDC00x",         # lone low then text
])

# NUL and control characters, only as escapes inside strings (never raw).
_nul_escape = st.just("\\u0000")
_control_escape = st.builds(
    lambda h: "\\u00" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=2, max_size=2),
)

_string_body = st.one_of(
    st.text(alphabet=_safe_char, min_size=0, max_size=20),
    st.lists(
        st.one_of(
            st.text(alphabet=_safe_char, min_size=0, max_size=8),
            _escapes,
            _unicode_escape,
            _surrogate_escape,
            _nul_escape,
            _control_escape,
        ),
        min_size=0,
        max_size=8,
    ).map("".join),
)

_string = _string_body.map(lambda s: '"' + s + '"')

# Malformed strings (unterminated, bad escapes, raw control chars).
_malformed_string = st.one_of(
    st.sampled_from([
        '"', '""extra', '"unterminated',
        '"bad\\x"', '"\\u12"', '"\\uZZZZ"', '"\\"',
        '"\\', '"\\u"', '"\\uD8"',
        '"line\nbreak"', '"tab\there"', '"cr\rhere"',
        '"raw\x00nul"',
        '"ok"trailing',
    ]),
    st.builds(
        lambda s: '"' + s,
        st.text(alphabet=_safe_char, min_size=1, max_size=10),
    ),
)

_any_string = st.one_of(_string, _malformed_string)


# ---------------------------------------------------------------------------
# Recursive JSON values (obj / arr)
# ---------------------------------------------------------------------------

# Depth-bounded recursion: concentrate near the parser's 2048 limit.
_depth_choice = st.one_of(
    st.sampled_from(_DEPTHS),
    st.integers(min_value=0, max_value=MAX_DEPTH),
    st.integers(min_value=MAX_DEPTH - 8, max_value=MAX_DEPTH + 4),
)

_json_value = st.deferred(lambda: _value_strategy)

# Leaf values (no recursion).
_leaves = st.one_of(
    _any_string,
    _number,
    st.sampled_from(["true", "false", "null", "True", "False", "NULL", "nil"]),
)

# Object keys: strings, sometimes duplicates, sometimes empty, sometimes malformed.
_keys = st.one_of(
    _any_string,
    st.sampled_from(['"k"', '"a"', '""', '"key"', '"dup"', '"x"']),
)

_pair = st.builds(
    lambda k, v: k + ":" + v,
    _keys,
    _json_value,
)

# Malformed pairs (missing colon, extra colon, empty key, etc.).
_malformed_pair = st.one_of(
    st.builds(lambda k, v: k + v, _keys, _json_value),          # missing colon
    st.builds(lambda k, v: k + "::" + v, _keys, _json_value),    # double colon
    st.builds(lambda k: k + ":", _keys),                          # trailing colon
    st.just(":1"),
    st.just(":"),
)

_obj_items = st.lists(
    st.one_of(_pair, _malformed_pair),
    min_size=0,
    max_size=6,
)

# Duplicate-key objects (parser rejects these — deliberate coverage).
_dup_key_obj = st.builds(
    lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
    st.sampled_from(['"k"', '"a"', '"dup"', '""']),
    _json_value,
    _json_value,
)

_obj = st.one_of(
    st.just("{}"),
    _obj_items.map(lambda items: "{" + ",".join(items) + "}"),
    # malformed separators
    _obj_items.map(lambda items: "{" + ",,".join(items) + "}"),
    _obj_items.map(lambda items: "{" + ",".join(items) + ",}"),
    _obj_items.map(lambda items: "{" + ",".join(items) + "}"),
    _dup_key_obj,
    st.just("{,}"),
    st.just("{:}"),
    st.just("{"),
    st.just("}"),
)

_arr_items = st.lists(_json_value, min_size=0, max_size=6)

_arr = st.one_of(
    st.just("[]"),
    _arr_items.map(lambda items: "[" + ",".join(items) + "]"),
    _arr_items.map(lambda items: "[" + ",,".join(items) + "]"),
    _arr_items.map(lambda items: "[" + ",".join(items) + ",]"),
    st.just("[,]"),
    st.just("["),
    st.just("]"),
)


# ---------------------------------------------------------------------------
# Deep nesting near the parser limit
# ---------------------------------------------------------------------------

def _deep_nesting(depth, open_ch, close_ch):
    return open_ch * depth + close_ch * depth


_deep = st.builds(
    lambda d, kind: (
        _deep_nesting(d, "[", "]") if kind == 0
        else _deep_nesting(d, '{"a":', "}")
    ),
    _depth_choice,
    st.integers(min_value=0, max_value=1),
)

# Deep nesting with a scalar at the innermost level.
_deep_with_value = st.builds(
    lambda d, v: "[" * d + v + "]" * d,
    _depth_choice,
    _leaves,
)


_value_strategy = st.one_of(
    _leaves,
    _obj,
    _arr,
    _deep,
    _deep_with_value,
)


# ---------------------------------------------------------------------------
# Top-level: a value, optionally with trailing junk (accepted by the parser).
# ---------------------------------------------------------------------------

_trailing = st.one_of(
    st.just(""),
    st.just(" "),
    st.just("\n"),
    st.just("garbage"),
    st.just("abc"),
    st.just("xyz"),
    st.just("/* comment */"),
    st.just("// comment"),
    st.just("null"),
    st.just("0123"),
    st.text(alphabet="abc123 \t\n", min_size=1, max_size=10),
)

_top = st.builds(
    lambda v, t: v + t,
    _value_strategy,
    _trailing,
)

# A few purely malformed top-level fragments.
_malformed_top = st.sampled_from([
    "", " ", "\n", "\t",
    ",", ",,", ":", "::",
    "[,]", "{,}", "[1,]", '{"a":1,}',
    '{"a"}', "{a:1}", "{'a':1}",
    "tru", "fals", "nul", "TRUE", "False",
    "[1 2]", '{"a":1 "b":2}',
    "1 2", "[] []", "{} {}",
    "1.2.3", "1e", "1e+",
    "\\", "\\\\", '"\\u"',
    "[}", "{]", "[)", "(]",
    "0x1F", "0o17", "0b101",
    "1,2,3", "a,b,c",
    "{\"a\":}", "[,]", "[,,]",
])

# ---------------------------------------------------------------------------
# Whitespace / comment-heavy inputs (exercises lexer/whitespace branches).
# ---------------------------------------------------------------------------

_ws = st.sampled_from([" ", "\t", "\n", "\r", "\r\n", "\f", "\v"])

_ws_run = st.lists(_ws, min_size=1, max_size=6).map("".join)

# Interleave whitespace around structural tokens to hit skip-whitespace paths.
_ws_wrapped_value = st.builds(
    lambda a, b, c, d, e: a + b + c + d + e,
    _ws_run,
    st.sampled_from(["[", "{"]),
    _ws_run,
    st.sampled_from(["]", "}"]),
    _ws_run,
)

# Whitespace around a simple scalar.
_ws_scalar = st.builds(
    lambda a, b, c: a + b + c,
    _ws_run,
    st.sampled_from(["1", "true", "false", "null", '"x"']),
    _ws_run,
)

# Whitespace between object members / array elements.
_ws_between = st.builds(
    lambda a, b, c, d, e: a + b + c + d + e,
    _ws_run,
    st.sampled_from(['{"a":1', "[1"]),
    _ws_run,
    st.sampled_from([",", ":"]),
    _ws_run,
).map(lambda s: s)  # keep as-is; fragments are combined below

_ws_between_obj = st.builds(
    lambda a, b, c: a + b + c,
    st.just('{"a":1'),
    _ws_run,
    st.just('}'),
)

_ws_between_arr = st.builds(
    lambda a, b, c, d: a + b + c + d,
    st.just("[1"),
    _ws_run,
    st.just(","),
    st.just("2]"),
)

_ws_inputs = st.one_of(
    _ws_wrapped_value,
    _ws_scalar,
    _ws_between_obj,
    _ws_between_arr,
    _ws_run,
)

# ---------------------------------------------------------------------------
# BOM / encoding-prefix edge cases (exercises byte-order-mark handling).
# ---------------------------------------------------------------------------

_bom_inputs = st.one_of(
    st.sampled_from([
        "\ufeff{}", "\ufeff[]", "\ufeff1", "\ufeffnull",
        "\ufeff", "\ufeff\ufeff{}",
        "\ufeff  {}", " \ufeff{}",
    ]),
    st.builds(
        lambda bom, v: bom + v,
        st.just("\ufeff"),
        _value_strategy,
    ),
)

# ---------------------------------------------------------------------------
# Escape / backslash edge cases at the lexer level (outside strings too).
# ---------------------------------------------------------------------------

_backslash_inputs = st.sampled_from([
    "\\", "\\\\", "\\n", "\\t", "\\\"", "\\/",
    "{\\}", "[\\]", "\\u0041",
    "1\\", "true\\", "null\\",
])

strategy = st.one_of(
    _top,
    _malformed_top,
    _value_strategy,
    _deep,
    _ws_inputs,
    _bom_inputs,
    _backslash_inputs,
)