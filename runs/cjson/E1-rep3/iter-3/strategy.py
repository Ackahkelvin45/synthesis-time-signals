from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

# Scalar fragments that are valid JSON values.
_valid_scalars = st.one_of(
    st.just("true"),
    st.just("false"),
    st.just("null"),
    # ordinary numbers
    st.integers(min_value=-(10**18), max_value=10**18).map(str),
    st.integers(min_value=0, max_value=10**30).map(lambda n: "0" * (n % 5) + str(n)),
    # floats with extreme exponents / magnitudes
    st.sampled_from([
        "0", "-0", "1", "-1", "1.0", "-1.5", "3.141592653589793",
        "1e309", "-1e309", "1e-309", "1e1000", "-1e1000",
        "1E+400", "1e-400", "0.0", "9" * 400, "-" + "9" * 400,
        "1e308", "1.7976931348623157e308", "5e-324",
        "1.", "-1.", "01", "-01", "0x10", "0xDEADBEEF",
        "1e01", "1E-01", "123456789012345678901234567890",
    ]),
    # malformed numeric-ish junk that should be rejected as a first value
    st.sampled_from([
        "-", "+1", ".5", "-.5", "NaN", "Infinity", "-Infinity",
        "1e", "1e+", "1.e5", "--1", "1..2", "0x", "0xg",
    ]),
)

# Strings: many flavours of escaping / raw bytes.
_escapes = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u001f", "\\u007f", "\\u00e9", "\\u20ac", "\\uFFFF",
    "\\uD83D\\uDE00",          # valid surrogate pair
    "\\ud800",                 # lone surrogate -> rejected
    "\\udfff",                 # lone low surrogate -> rejected
    "\\u12", "\\uZZZZ", "\\x41", "\\",  # bad escapes
])

_raw_bytes = st.sampled_from([
    "a", "Z", "0", " ", "\t", "\n", "\r", "\x00", "\x01", "\x1f",
    "\x7f", "\u00e9", "\u20ac", "\U0001F600", "/", "'",
])

_string_body = st.one_of(_escapes, _raw_bytes, st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), min_codepoint=0x20),
    max_size=8,
))

# Build a quoted string; sometimes unterminated or with stray quotes.
def _mk_string(body_parts):
    body = "".join(body_parts)
    return '"' + body + '"'

_quoted_string = st.lists(_string_body, max_size=6).map(_mk_string)

_unterminated_string = st.lists(_string_body, max_size=6).map(
    lambda parts: '"' + "".join(parts)
)

# Keys for pairs (valid strings and some odd ones)
_keys = st.one_of(
    _quoted_string,
    st.sampled_from(['""', '"a"', '"key"', '"dup"', '"\\u0000"', '"\\ud800"']),
)

# ---------------------------------------------------------------------------
# Recursive values
# ---------------------------------------------------------------------------

# Dedicated NUMBER production: well-formed JSON numbers, used as a leaf so the
# parser's NUMBER production gets exercised directly.
_number = st.one_of(
    st.integers(min_value=-(10**18), max_value=10**18).map(str),
    st.sampled_from([
        "0", "-0", "1", "-1", "42", "-42", "1234567890",
        "1.0", "-1.5", "3.141592653589793", "0.0",
        "1e308", "1.7976931348623157e308", "5e-324",
        "1e309", "-1e309", "1e-309", "1e1000", "-1e1000",
        "1E+400", "1e-400", "1e01", "1E-01",
        "123456789012345678901234567890",
    ]),
)

_leaf = st.one_of(_valid_scalars, _quoted_string, _number)

def _make_obj(pairs):
    return "{" + ",".join(pairs) + "}"

def _make_arr(items):
    return "[" + ",".join(items) + "]"

# A pair strategy: key ":" value
_pair = st.tuples(_keys, _leaf).map(lambda kv: kv[0] + ":" + kv[1])

def _build_recursive():
    return st.recursive(
        _leaf,
        lambda children: st.one_of(
            # arrays
            st.lists(children, max_size=4).map(_make_arr),
            # objects
            st.lists(
                st.tuples(_keys, children).map(lambda kv: kv[0] + ":" + kv[1]),
                max_size=4,
            ).map(_make_obj),
        ),
        max_leaves=20,
    )

_value = _build_recursive()

# ---------------------------------------------------------------------------
# Depth-targeted wrappers (near the 1000-level limit)
# ---------------------------------------------------------------------------

def _nest(depth, opener, closer, inner):
    return opener * depth + inner + closer * depth

# Concentrate depth generation tightly around the parser's ~1000-level cap so
# that cap_distance_mass is meaningful, rather than spreading across a wide
# range that mostly lands far from the limit.
_depth = st.one_of(
    st.sampled_from([0, 1, 2, 5, 50]),
    st.integers(min_value=990, max_value=1010),
    st.sampled_from([999, 1000, 1001, 1002, 1500]),
)

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
    # unterminated strings / arrays / objects
    _unterminated_string,
    st.tuples(_quoted_string, _value).map(lambda t: t[0] + t[1]),  # missing colon
    st.tuples(_value, _value).map(lambda t: t[0] + "," + t[1]),     # top-level pair
    st.tuples(_value, _value).map(lambda t: t[0] + t[1]),           # trailing content
    st.tuples(st.lists(_value, min_size=1, max_size=3)).map(
        lambda t: "[" + ",".join(t[0]) + ","          # trailing comma
    ),
    st.tuples(st.lists(_pair, min_size=1, max_size=3)).map(
        lambda t: "{" + ",".join(t[0]) + ","          # trailing comma
    ),
    st.tuples(st.lists(_value, min_size=1, max_size=3)).map(
        lambda t: "[" + ",".join(t[0])                 # unterminated array
    ),
    st.tuples(st.lists(_pair, min_size=1, max_size=3)).map(
        lambda t: "{" + ",".join(t[0])                 # unterminated object
    ),
)

# ---------------------------------------------------------------------------
# Top-level combination
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _value,
    _number,
    _deep_array,
    _deep_object,
    _deep_mixed,
    _malformed,
    # valid value followed by trailing junk (accepted by parser)
    st.tuples(_value, st.sampled_from(["x", " ", "\x00", "abc", "{}", "[]"])).map(
        lambda t: t[0] + t[1]
    ),
    # BOM-prefixed values
    st.tuples(st.just("\ufeff"), _value).map(lambda t: t[0] + t[1]),
)