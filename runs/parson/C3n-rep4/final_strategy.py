from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Control/edge characters that are legal *inside* a JSON string (as raw bytes)
# except NUL, which we must never emit raw.
_SAFE_RAW = [chr(c) for c in range(0x09, 0x20)] + ["\x7f"]

_ESCAPES = ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]

# \uXXXX escapes, including surrogates and the (textual) \u0000 escape.
_HEX4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_UNICODE_ESC = st.builds(lambda h: "\\u" + h, _HEX4)
_SURROGATE_ESC = st.builds(
    lambda h: "\\u" + h,
    st.sampled_from(["D800", "DBFF", "DC00", "DFFF", "d800", "dc00"]),
)

_STRING_CHUNK = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_characters='\\"\x00',
            blacklist_categories=("Cs",),
        ),
        max_size=6,
    ),
    st.sampled_from(_ESCAPES),
    _UNICODE_ESC,
    _SURROGATE_ESC,
    st.sampled_from(_SAFE_RAW),
)

# A properly quoted JSON string (may contain escapes / surrogates).
json_string = st.builds(
    lambda chunks: '"' + "".join(chunks) + '"',
    st.lists(_STRING_CHUNK, max_size=6),
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10 ** 18).map(str),
    st.integers(min_value=-(10 ** 18), max_value=-1).map(str),
)

# Extreme magnitudes / exponents, including overflow like 1e309.
_BIG_EXP = st.sampled_from(
    ["309", "310", "1000", "9999", "308", "307", "001", "01", "+5", "-5", "-309"]
)
_FRAC = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10 ** 12).map(str),
)

number = st.one_of(
    _INT,
    st.builds(
        lambda i, f: i + "." + f,
        _INT,
        _FRAC,
    ),
    st.builds(
        lambda i, e: i + "e" + e,
        _INT,
        _BIG_EXP,
    ),
    st.builds(
        lambda i, f, e: i + "." + f + "e" + e,
        _INT,
        _FRAC,
        _BIG_EXP,
    ),
    st.sampled_from(
        ["1e309", "-1e309", "1e-9999", "0e0", "1E+308", "1e308", "-0", "0.0"]
    ),
)

# ---------------------------------------------------------------------------
# Malformed fragments (near-valid-but-broken)
# ---------------------------------------------------------------------------

malformed = st.sampled_from(
    [
        "",
        "{",
        "}",
        "[",
        "]",
        "{,}",
        "[,]",
        "[1,,2]",
        '{"a" 1}',
        '{"a":}',
        '{"a":1,}',
        '{"a":1 "b":2}',
        '{"a"}',
        '"unterminated',
        '"unterminated\\',
        "+1",
        ".5",
        "01",
        "-.5",
        "1.",
        "1..2",
        "tru",
        "fals",
        "nul",
        "tru e",
        "{'a':1}",
        "\\uD800",
        '"\x01"',
        "1e",
        "1e+",
        "--1",
        "NaN",
        "Infinity",
        "-Infinity",
        "0x10",
    ]
)

# ---------------------------------------------------------------------------
# Recursive value strategy (obj / arr through value)
# ---------------------------------------------------------------------------

# Depth budget: concentrate near the parser's MAX_NESTING of 2048.
_DEPTHS = [0, 1, 2, 3, 5, 8, 16, 64, 256, 1024, 2040, 2047, 2048, 2049, 2050, 3000]


def _deep_nest(depth):
    """Build a deeply nested array/object near the parser's nesting cap."""
    if depth <= 0:
        return "null"
    open_ch = "[" if depth % 2 == 0 else "{"
    close_ch = "]" if depth % 2 == 0 else "}"
    inner = "null"
    if open_ch == "{":
        inner = '"k":null'
    return open_ch * depth + inner + close_ch * depth


deep_nesting = st.sampled_from(_DEPTHS).map(_deep_nest)

# Duplicate-key objects (the parser rejects these).
duplicate_keys = st.builds(
    lambda k, v1, v2: '{"' + k + '":' + v1 + ',"' + k + '":' + v2 + "}",
    st.sampled_from(["a", "k", "", "x", "key"]),
    st.sampled_from(["0", "1", "null", "true", '"s"']),
    st.sampled_from(["0", "1", "null", "false", '"t"']),
)

# Empty containers and simple atoms.
_atom = st.one_of(
    json_string,
    number,
    st.sampled_from(["true", "false", "null"]),
    st.just("{}"),
    st.just("[]"),
    duplicate_keys,
    deep_nesting,
)

# Recursive value: obj/arr built via st.recursive.
value = st.recursive(
    _atom,
    lambda children: st.one_of(
        # array
        st.builds(
            lambda vs: "[" + ",".join(vs) + "]",
            st.lists(children, max_size=4),
        ),
        # object with distinct keys (avoid accidental duplicate-key rejection
        # unless we want it; use index-based keys)
        st.builds(
            lambda pairs: "{"
            + ",".join('"' + k + '":' + v for k, v in pairs)
            + "}",
            st.lists(
                st.tuples(
                    st.integers(min_value=0, max_value=10 ** 6).map(
                        lambda i: "k%d" % i
                    ),
                    children,
                ),
                max_size=4,
            ),
        ),
    ),
    max_leaves=20,
)

# ---------------------------------------------------------------------------
# Top-level combinations: valid, malformed, and trailing-content variants
# ---------------------------------------------------------------------------

_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

top_level = st.one_of(
    value,
    # trailing content after a complete value (parser ACCEPTS)
    st.builds(
        lambda v, t: v + t,
        value,
        st.sampled_from(["abc", " garbage", "xyz", "1", "[]", "{}", "//c", "/*c*/"]),
    ),
    # leading whitespace
    st.builds(lambda w, v: w + v, _ws, value),
    # malformed inputs
    malformed,
    # malformed wrapping a valid value
    st.builds(lambda a, v, b: a + v + b, malformed, value, malformed),
    # lone sign (parser parses as 0)
    st.sampled_from(["-", "-.", "+", ".5", "1."]),
    deep_nesting,
)

# ---------------------------------------------------------------------------
# Exercise serialization round-trips (json_serialize_string / _to_buffer_r).
# A full JSON document that the parser accepts, so the harness can parse it
# and then serialize the resulting value back out, driving the serializer.
# ---------------------------------------------------------------------------

# Strings that specifically drive json_serialize_string's escaping branches:
# control characters that must be re-escaped on output, quotes, backslashes,
# forward slashes, and non-ASCII / \u escapes.
_SERIALIZE_STRING = st.builds(
    lambda chunks: '"' + "".join(chunks) + '"',
    st.lists(
        st.one_of(
            # raw control chars (must be escaped on serialize)
            st.sampled_from([chr(c) for c in range(0x00, 0x20)]),
            st.just('"'),
            st.just("\\"),
            st.just("/"),
            # escapes that decode to chars requiring re-escaping
            st.sampled_from(
                [
                    "\\u0000",
                    "\\u0001",
                    "\\u0008",
                    "\\u0009",
                    "\\u000a",
                    "\\u000b",
                    "\\u000c",
                    "\\u000d",
                    "\\u001f",
                    "\\u007f",
                    "\\u0080",
                    "\\u00e9",
                    "\\u4e2d",
                    "\\uD83D\\uDE00",
                    "\\b",
                    "\\f",
                    "\\n",
                    "\\r",
                    "\\t",
                    '\\"',
                    "\\\\",
                    "\\/",
                ]
            ),
            # plain printable ASCII
            st.text(
                alphabet=st.characters(
                    blacklist_characters='\\"\x00',
                    blacklist_categories=("Cs",),
                ),
                max_size=4,
            ),
        ),
        min_size=1,
        max_size=8,
    ),
)

# Keys that drive the serializer's key-escaping branch, including control
# chars, quotes, backslashes and non-ASCII characters.
_SERIALIZE_KEY = st.builds(
    lambda chunks: '"' + "".join(chunks) + '"',
    st.lists(
        st.one_of(
            st.sampled_from([chr(c) for c in range(0x01, 0x20)]),
            st.just('"'),
            st.just("\\"),
            st.just("/"),
            st.sampled_from(
                [
                    "\\u0001",
                    "\\u0008",
                    "\\u000a",
                    "\\u000d",
                    "\\u001f",
                    "\\u007f",
                    "\\u00e9",
                    "\\u4e2d",
                    "\\n",
                    "\\t",
                    '\\"',
                    "\\\\",
                ]
            ),
            st.text(
                alphabet=st.characters(
                    blacklist_characters='\\"\x00',
                    blacklist_categories=("Cs",),
                ),
                max_size=3,
            ),
        ),
        min_size=1,
        max_size=5,
    ),
)

_serialize_doc = st.one_of(
    # String-heavy documents: force the string-escaping serializer path,
    # including control chars, quotes, backslashes and non-ASCII / \u escapes.
    _SERIALIZE_STRING,
    st.builds(
        lambda vs: "[" + ",".join(vs) + "]",
        st.lists(_SERIALIZE_STRING, min_size=1, max_size=6),
    ),
    st.builds(
        lambda pairs: "{"
        + ",".join('"k%d":%s' % (i, v) for i, v in enumerate(pairs))
        + "}",
        st.lists(_SERIALIZE_STRING, min_size=1, max_size=6),
    ),
    # Objects whose KEYS require re-escaping on serialize (drives the
    # key-escaping branch of json_serialize_string).
    st.builds(
        lambda pairs: "{"
        + ",".join(k + ":" + v for k, v in pairs)
        + "}",
        st.lists(
            st.tuples(_SERIALIZE_KEY, _SERIALIZE_STRING),
            min_size=1,
            max_size=6,
        ),
    ),
    # Nested documents with escaping-heavy strings/keys at every level.
    st.builds(
        lambda v: v,
        value,
    ),
)

# ---------------------------------------------------------------------------
# Focused driver for json_serialize_string.
#
# json_serialize_string is only reached when the harness parses a document and
# then re-serializes the resulting value. To guarantee coverage of its branches
# (escaping of control chars, quote, backslash, forward slash, and the
# non-ASCII unescaped path), emit top-level JSON *strings* whose decoded
# content spans every branch, plus arrays/objects containing them so the
# serializer is invoked on nested values too.
# ---------------------------------------------------------------------------

# A decoded string whose characters hit every escaping branch of
# json_serialize_string: control chars (0x00-0x1F), quote, backslash,
# forward slash, DEL, and a range of non-ASCII code points.
_SERIALIZE_DRIVER_CHARS = st.one_of(
    st.sampled_from([chr(c) for c in range(0x00, 0x20)]),  # \u00XX escapes
    st.just('"'),
    st.just("\\"),
    st.just("/"),
    st.just("\x7f"),
    st.sampled_from(["\x80", "\xe9", "\u4e2d", "\u2028", "\u2029", "\U0001F600"]),
    st.text(
        alphabet=st.characters(
            blacklist_characters='\\"\x00',
            blacklist_categories=("Cs",),
        ),
        max_size=3,
    ),
)

# Build a JSON string literal (with \u escapes for control chars) that, once
# parsed and re-serialized, exercises every branch of json_serialize_string.
_SERIALIZE_DRIVER_STRING = st.builds(
    lambda chunks: '"' + "".join(chunks) + '"',
    st.lists(
        st.one_of(
            # raw control chars are illegal in source, so use \uXXXX escapes
            st.builds(
                lambda c: "\\u%04x" % ord(c),
                st.sampled_from([chr(c) for c in range(0x00, 0x20)]),
            ),
            st.just('\\"'),
            st.just("\\\\"),
            st.just("\\/"),
            st.just("\\u007f"),
            st.sampled_from(
                ["\\u0080", "\\u00e9", "\\u4e2d", "\\u2028", "\\u2029",
                 "\\uD83D\\uDE00"]
            ),
            st.text(
                alphabet=st.characters(
                    blacklist_characters='\\"\x00',
                    blacklist_categories=("Cs",),
                ),
                max_size=3,
            ),
        ),
        min_size=1,
        max_size=10,
    ),
)

_serialize_driver = st.one_of(
    # Top-level string: parse -> serialize string directly.
    _SERIALIZE_DRIVER_STRING,
    # Array of driver strings.
    st.builds(
        lambda vs: "[" + ",".join(vs) + "]",
        st.lists(_SERIALIZE_DRIVER_STRING, min_size=1, max_size=8),
    ),
    # Object with driver strings as keys and values.
    st.builds(
        lambda pairs: "{"
        + ",".join('"k%d":%s' % (i, v) for i, v in enumerate(pairs))
        + "}",
        st.lists(_SERIALIZE_DRIVER_STRING, min_size=1, max_size=8),
    ),
    # Object whose keys are driver strings (drives key-escaping branch).
    st.builds(
        lambda pairs: "{"
        + ",".join('"' + k + '":' + v for k, v in pairs)
        + "}",
        st.lists(
            st.tuples(
                st.builds(
                    lambda s: s.strip('"'),
                    _SERIALIZE_DRIVER_STRING,
                ),
                st.sampled_from(["0", "null", "true", '"x"']),
            ),
            min_size=1,
            max_size=6,
        ),
    ),
)

strategy = st.one_of(top_level, _serialize_doc, _serialize_driver)