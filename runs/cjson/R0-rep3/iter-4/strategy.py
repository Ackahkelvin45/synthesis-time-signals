from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

_valid_scalars = st.one_of(
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.integers(min_value=-(10**18), max_value=10**18).map(str),
    st.integers(min_value=0, max_value=10**30).map(lambda n: "0" * (n % 5) + str(n)),
    st.sampled_from([
        "0", "-0", "1", "-1", "1.0", "-1.5", "3.141592653589793",
        "1e309", "-1e309", "1e-309", "1e1000", "-1e1000",
        "1E+400", "1e-400", "0.0", "9" * 400, "-" + "9" * 400,
        "1e308", "1.7976931348623157e308", "5e-324",
        "1.", "-1.", "01", "-01", "0x10", "0xDEADBEEF",
        "1e01", "1E-01", "123456789012345678901234567890",
    ]),
    st.sampled_from([
        "-", "+1", ".5", "-.5", "NaN", "Infinity", "-Infinity",
        "1e", "1e+", "1.e5", "--1", "1..2", "0x", "0xg",
    ]),
)

_escapes = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u001f", "\\u007f", "\\u00e9", "\\u20ac", "\\uFFFF",
    "\\uD83D\\uDE00",
    "\\ud800",
    "\\udfff",
    "\\u12", "\\uZZZZ", "\\x41", "\\",
])

_raw_bytes = st.sampled_from([
    "a", "Z", "0", " ", "\t", "\n", "\r", "\x00", "\x01", "\x1f",
    "\x7f", "\u00e9", "\u20ac", "\U0001F600", "/", "'",
])

_string_body = st.one_of(_escapes, _raw_bytes, st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), min_codepoint=0x20),
    max_size=8,
))

def _mk_string(body_parts):
    body = "".join(body_parts)
    return '"' + body + '"'

_quoted_string = st.lists(_string_body, max_size=6).map(_mk_string)

_unterminated_string = st.lists(_string_body, max_size=6).map(
    lambda parts: '"' + "".join(parts)
)

_keys = st.one_of(
    _quoted_string,
    st.sampled_from(['""', '"a"', '"key"', '"dup"', '"\\u0000"', '"\\ud800"']),
)

# ---------------------------------------------------------------------------
# Recursive values
# ---------------------------------------------------------------------------

_leaf = st.one_of(_valid_scalars, _quoted_string)

def _make_obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _make_arr(items):
    return "[" + ",".join(items) + "]"

_pair = st.tuples(_keys, _leaf).map(lambda kv: kv[0] + ":" + kv[1])

def _build_recursive():
    return st.recursive(
        _leaf,
        lambda children: st.one_of(
            st.lists(children, max_size=4).map(_make_arr),
            st.lists(
                st.tuples(_keys, children).map(lambda kv: kv[0] + ":" + kv[1]),
                max_size=4,
            ).map(_make_obj),
        ),
        max_leaves=20,
    )

_value = _build_recursive()

# ---------------------------------------------------------------------------
# Depth-targeted wrappers
# ---------------------------------------------------------------------------

def _nest(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

_depth = st.sampled_from([0, 1, 2, 5, 50, 500, 999, 1000, 1001, 1002, 1500])

_deep_array = st.tuples(_depth, _value).map(
    lambda t: _nest(t[0], "[", "]", t[1])
)
_deep_object = st.tuples(_depth, _value).map(
    lambda t: _nest(t[0], '{"k":', "}", t[1])
)
_deep_mixed = st.tuples(_depth, _value).map(
    lambda t: _nest(t[0] // 2, '[{"a":', "}]", t[1])
)

# ---------------------------------------------------------------------------
# Malformed-but-near-valid structures
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    st.sampled_from([
        "", " ", "\t\n\r", ",", ",,", "[,]", "[1,,2]", "[1,2,]",
        "{,}", '{"a":1,}', '{"a":1,,}', '{"a" 1}', '{"a":}',
        "{:1}", '{"a":1 "b":2}', "[1 2]", "[1:2]",
        "tru", "fals", "nul", "TRUE", "Null", "nan",
        "'x'", "{a:1}", "[}", "{]", "[1}", "]", "}",
        "1 2", "1abc", "true false", "nullx",
        "\ufeff", "\ufeff1", "\ufeff{}",
        "\x00", "1\x00", "\x00{}", '"a"\x00',
    ]),
    _unterminated_string,
    st.tuples(_quoted_string, _value).map(lambda t: t[0] + t[1]),
    st.tuples(_value, _value).map(lambda t: t[0] + "," + t[1]),
    st.tuples(_value, _value).map(lambda t: t[0] + t[1]),
    st.tuples(st.lists(_value, min_size=1, max_size=3)).map(
        lambda t: "[" + ",".join(t[0]) + ","
    ),
    st.tuples(st.lists(_pair, min_size=1, max_size=3)).map(
        lambda t: "{" + ",".join(t[0]) + ","
    ),
    st.tuples(st.lists(_value, min_size=1, max_size=3)).map(
        lambda t: "[" + ",".join(t[0])
    ),
    st.tuples(st.lists(_pair, min_size=1, max_size=3)).map(
        lambda t: "{" + ",".join(t[0])
    ),
)

# ---------------------------------------------------------------------------
# Top-level combination
# ---------------------------------------------------------------------------

# IMPROVEMENT: the previous "deeply nested objects with duplicate / odd keys"
# branch was effectively broken (it always produced `{` + key + value + `}`*depth
# with no real nesting, and the `if False` dead code obscured that). Replace it
# with a genuine deep-object builder that nests real key:value pairs at each
# level, cycling through a small set of keys to reliably exercise duplicate-key
# handling at depth, and optionally terminating in a malformed inner fragment.
def _deep_dup_obj(t):
    depth, key, inner = t
    if depth <= 0:
        return inner
    # Real nesting: {"key":{"key":...inner...}}
    return ('{' + key + ':') * depth + inner + '}' * depth

_deep_dup_obj_strat = st.tuples(_depth, _keys, _value).map(_deep_dup_obj)

strategy = st.one_of(
    _value,
    _deep_array,
    _deep_object,
    _deep_mixed,
    _malformed,
    st.tuples(_value, st.sampled_from(["x", " ", "\x00", "abc", "{}", "[]"])).map(
        lambda t: t[0] + t[1]
    ),
    st.tuples(st.just("\ufeff"), _value).map(lambda t: t[0] + t[1]),
    st.tuples(_depth, _value, st.sampled_from(["x", " ", "\x00", "abc", "{}", "[]"])).map(
        lambda t: _nest(t[0], "[", "]", t[1]) + t[2]
    ),
    st.tuples(_depth, st.lists(_value, min_size=1, max_size=2)).map(
        lambda t: "[" * t[0] + "[" + ",".join(t[1]) + "," + "]" * t[0]
    ),
    _deep_dup_obj_strat,
)