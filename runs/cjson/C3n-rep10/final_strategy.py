from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(*parts):
    return lambda t: "".join(t)

# ---------- strings ----------

_safe_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\\',
).filter(lambda c: ord(c) >= 0x20)

_esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_esc_unicode = _hex4.map(lambda h: "\\u" + h)
_esc_surrogate = _hex4.map(lambda h: "\\u" + h)

# raw control / NUL bytes allowed by the parser inside strings
_raw_ctrl = st.sampled_from(["\x00", "\x01", "\x1f", "\t", "\n", "\r", "\x7f"])

_str_body_unit = st.one_of(
    _safe_char,
    _esc_simple,
    _esc_unicode,
    _raw_ctrl,
)

_string = st.lists(_str_body_unit, max_size=8).map(lambda xs: '"' + "".join(xs) + '"')

# ---------- numbers ----------

_int = st.one_of(
    st.integers(min_value=0, max_value=0).map(str),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-10**18, max_value=-1).map(str),
    # leading zeros (accepted deviation)
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),
)

_frac = st.one_of(
    st.integers(min_value=0, max_value=10**18).map(lambda n: "." + str(n)),
    st.just("."),  # trailing dot (accepted deviation)
)

_exp = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.integers(min_value=-400, max_value=400).map(lambda n: "E+" + str(n)),
    st.just("e309"),
    st.just("e-309"),
    st.just("e9999"),
)

_hex_num = st.integers(min_value=0, max_value=2**32).map(lambda n: "0x" + format(n, "x"))

_number = st.one_of(
    _int,
    st.builds(lambda i, f: i + f, _int, _frac),
    st.builds(lambda i, e: i + e, _int, _exp),
    st.builds(lambda i, f, e: i + f + e, _int, _frac, _exp),
    _hex_num,
)

# ---------- recursive values ----------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  "])

def _pair(key, value, ws):
    return key + ws + ":" + ws + value

_pair_st = st.builds(_pair, _string, st.deferred(lambda: _value), _ws)

_obj = st.one_of(
    st.just("{}"),
    st.builds(
        lambda pairs: "{" + ",".join(pairs) + "}",
        st.lists(_pair_st, min_size=1, max_size=4),
    ),
    # duplicate keys
    st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        _string,
        st.deferred(lambda: _value),
        st.deferred(lambda: _value),
    ),
)

_arr = st.one_of(
    st.just("[]"),
    st.builds(
        lambda vals: "[" + ",".join(vals) + "]",
        st.lists(st.deferred(lambda: _value), min_size=1, max_size=4),
    ),
)

_value = st.one_of(
    _string,
    _number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
    _obj,
    _arr,
)

_value_rec = st.recursive(
    st.one_of(_string, _number, st.just("true"), st.just("false"), st.just("null")),
    lambda children: st.one_of(
        st.builds(
            lambda vals: "[" + ",".join(vals) + "]",
            st.lists(children, min_size=1, max_size=4),
        ),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(_pair, _string, children, _ws),
                min_size=1,
                max_size=4,
            ),
        ),
    ),
    max_leaves=12,
)

# ---------- deep nesting near the 1000 limit ----------

def _deep_nest(depth, opener, closer):
    return opener * depth + closer * depth

_deep_array = st.integers(min_value=0, max_value=1000).map(
    lambda d: _deep_nest(d, "[", "]")
)

_deep_obj = st.integers(min_value=0, max_value=1000).map(
    lambda d: _deep_nest(d, '{"a":', "}")
)

# ---------- malformed near-valid inputs ----------

_malformed = st.sampled_from([
    # double commas
    "[1,,2]",
    '{"a":1,,}',
    "[,]",
    '{"a":1,,"b":2}',
    # missing colons
    '{"a" 1}',
    '{"a"}',
    '{"a"::1}',
    # unterminated strings
    '"abc',
    '{"a":"b}',
    '["x]',
    # leading + / .5 / lone -
    "+1",
    ".5",
    "-",
    "-.5",
    "+.5",
    "1+",
    # trailing commas
    "[1,]",
    "[1,2,]",
    '{"a":1,}',
    '{"a":1,"b":2,}',
    # words
    "NaN",
    "Infinity",
    "-Infinity",
    # invalid escapes / quotes
    "'single'",
    "{a:1}",
    '"\\x41"',
    '"\\u12"',
    '"\\ud800"',
    '"\\udfff"',
    # empty / whitespace only
    "",
    "   ",
    "\n\t",
    # lone colon / brackets
    ":",
    ",",
    "[",
    "]",
    "{",
    "}",
])

# ---------- trailing content / BOM / NUL ----------

_trailing = st.builds(
    lambda v, junk: v + junk,
    _value_rec,
    st.sampled_from(["", "x", " 1 2", "\x00", "abc", "]", "}", " junk"]),
)

_bom = st.builds(lambda v: "\ufeff" + v, _value_rec)

_nul_inside = st.builds(
    lambda v: v[:1] + "\x00" + v[1:] if v else "\x00",
    _value_rec,
)

# ---------- cJSON_Compare coverage: paired JSON values ----------

_compare_value = st.recursive(
    st.one_of(
        _string,
        _number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    ),
    lambda children: st.one_of(
        st.builds(
            lambda vals: "[" + ",".join(vals) + "]",
            st.lists(children, min_size=0, max_size=4),
        ),
        st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(
                st.builds(_pair, _string, children, _ws),
                min_size=0,
                max_size=4,
            ),
        ),
    ),
    max_leaves=10,
)

def _compare_inputs(a, b):
    # cJSON_Compare expects two separately parsed JSON values; feed both
    # as a JSON array so a single parse yields two values the harness can compare.
    return "[" + a + "," + b + "]"

# Generate two values that are frequently equal (to hit the "equal" branches)
# and frequently structurally similar (to hit type-mismatch and deep-compare branches).
_compare_pair = st.one_of(
    # identical values -> exercises equality fast paths
    st.builds(lambda v: _compare_inputs(v, v), _compare_value),
    # same value with differing whitespace -> equal after parse
    st.builds(
        lambda v, w1, w2: _compare_inputs(v, v + w1 + w2),
        _compare_value,
        _ws,
        _ws,
    ),
    # two independent values -> exercises mismatch branches
    st.builds(_compare_inputs, _compare_value, _compare_value),
    # arrays with same/different lengths and contents
    st.builds(
        lambda a, b: _compare_inputs(
            "[" + ",".join(a) + "]",
            "[" + ",".join(b) + "]",
        ),
        st.lists(_compare_value, min_size=0, max_size=4),
        st.lists(_compare_value, min_size=0, max_size=4),
    ),
    # objects with same/different keys and values
    st.builds(
        lambda a, b: _compare_inputs(
            "{" + ",".join(a) + "}",
            "{" + ",".join(b) + "}",
        ),
        st.lists(st.builds(_pair, _string, _compare_value, _ws), min_size=0, max_size=4),
        st.lists(st.builds(_pair, _string, _compare_value, _ws), min_size=0, max_size=4),
    ),
    # type mismatches: number vs string vs bool vs null vs container
    st.builds(
        lambda a, b: _compare_inputs(a, b),
        st.one_of(_number, _string, st.just("true"), st.just("false"), st.just("null")),
        st.one_of(_number, _string, st.just("true"), st.just("false"), st.just("null")),
    ),
    # case sensitivity in object keys
    st.builds(
        lambda k1, k2, v: _compare_inputs(
            "{" + k1 + ":" + v + "}",
            "{" + k2 + ":" + v + "}",
        ),
        _string,
        _string,
        _compare_value,
    ),
    # nested deep structures that differ only at the leaves
    st.builds(
        lambda a, b, depth: _compare_inputs(
            "[" * depth + a + "]" * depth,
            "[" * depth + b + "]" * depth,
        ),
        _compare_value,
        _compare_value,
        st.integers(min_value=1, max_value=5),
    ),
    # objects with reordered keys (equal content, different order)
    st.builds(
        lambda k1, k2, v1, v2: _compare_inputs(
            "{" + k1 + ":" + v1 + "," + k2 + ":" + v2 + "}",
            "{" + k2 + ":" + v2 + "," + k1 + ":" + v1 + "}",
        ),
        _string,
        _string,
        _compare_value,
        _compare_value,
    ),
    # same key, differing value types
    st.builds(
        lambda k, a, b: _compare_inputs(
            "{" + k + ":" + a + "}",
            "{" + k + ":" + b + "}",
        ),
        _string,
        _compare_value,
        _compare_value,
    ),
    # numbers that compare equal after parse (e.g. 1 vs 1.0)
    st.builds(
        lambda n: _compare_inputs(str(n), str(n) + ".0"),
        st.integers(min_value=-1000, max_value=1000),
    ),
    # numbers that compare unequal after parse
    st.builds(
        lambda a, b: _compare_inputs(str(a), str(b)),
        st.integers(min_value=-1000, max_value=1000),
        st.integers(min_value=-1000, max_value=1000),
    ),
    # string comparisons: equal, prefix, case-differing
    st.builds(
        lambda s: _compare_inputs(s, s),
        _string,
    ),
    st.builds(
        lambda s1, s2: _compare_inputs(s1, s2),
        _string,
        _string,
    ),
    # boolean/null identity and mismatch
    st.builds(
        lambda a, b: _compare_inputs(a, b),
        st.sampled_from(["true", "false", "null"]),
        st.sampled_from(["true", "false", "null"]),
    ),
    # array length mismatch
    st.builds(
        lambda a, b: _compare_inputs(
            "[" + ",".join(a) + "]",
            "[" + ",".join(b) + "]",
        ),
        st.lists(_compare_value, min_size=0, max_size=3),
        st.lists(_compare_value, min_size=0, max_size=3),
    ),
    # object key-count mismatch
    st.builds(
        lambda a, b: _compare_inputs(
            "{" + ",".join(a) + "}",
            "{" + ",".join(b) + "}",
        ),
        st.lists(st.builds(_pair, _string, _compare_value, _ws), min_size=0, max_size=3),
        st.lists(st.builds(_pair, _string, _compare_value, _ws), min_size=0, max_size=3),
    ),
)

_compare = _compare_pair

# ---------- top-level strategy ----------

strategy = st.one_of(
    _value_rec,
    _deep_array,
    _deep_obj,
    _malformed,
    _trailing,
    _bom,
    _nul_inside,
    # duplicate keys at top level
    st.builds(
        lambda k, v1, v2: "{" + k + ":" + v1 + "," + k + ":" + v2 + "}",
        _string,
        _value_rec,
        _value_rec,
    ),
    # exercise cJSON_Compare
    _compare,
).map(lambda s: s if isinstance(s, str) else str(s))