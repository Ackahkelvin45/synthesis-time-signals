from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFE_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " _-.,:;!?@#$%^&*()[]{}|~`'<>+=/"
)

_RAW_CONTROL = "".join(chr(c) for c in range(1, 0x20) if c != 0x00)

_ESCAPES = ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]

def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

def _unicode_escape():
    return st.one_of(
        _hex4(),
        st.sampled_from(
            ["d800", "dbff", "dc00", "dfff", "D800", "DFFF", "0000", "001f", "007f", "fffd"]
        ),
    ).map(lambda h: "\\u" + h)

def _escaped_piece():
    return st.one_of(
        st.sampled_from(_ESCAPES),
        _unicode_escape(),
    )

def _string_char():
    return st.one_of(
        st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=4),
        st.sampled_from(list(_RAW_CONTROL)),
        _escaped_piece(),
        st.just("\u2028"),
        st.just("\U0001f600"),
    )

def _string_body():
    return st.lists(_string_char(), max_size=8).map("".join)

def _string():
    return _string_body().map(lambda s: '"' + s + '"')

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT_PART = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=9).map(str),
    st.integers(min_value=10, max_value=10**18).map(str),
    st.integers(min_value=-10**18, max_value=-1).map(str),
)

_EXP_PART = st.one_of(
    st.just(""),
    st.integers(min_value=-400, max_value=400).map(lambda e: "e" + str(e)),
    st.sampled_from(["e0", "e01", "E+1", "e-0", "e308", "e309", "e-309", "e999", "e-999"]),
)

_FRAC_PART = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
    st.just(".0"),
    st.just(".000"),
)

def _number():
    return st.tuples(_INT_PART, _FRAC_PART, _EXP_PART).map(lambda t: "".join(t))

# ---------------------------------------------------------------------------
# Malformed snippets
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from([
    "", "{", "}", "[", "]",
    "{,}", "[,]", "[1,]", "{,}",
    "{\"a\"}", "{\"a\":}", "{\"a\":,}", "[1 2]",
    "{\"a\":1 \"b\":2}",
    "\"unterminated", "\"bad\\", "\"bad\\x\"", "\"bad\\u12\"", "\"bad\\uZZZZ\"",
    "01", "-01", "+1", ".5", "-.5", "1.", "1e", "1e+",
    "tru", "fals", "nul", "True", "FALSE", "Null", "nulll",
    "{\"a\":1,}", "[1,2,]", ":", ",", "'single'", "{\"a\"::1}", "[[]", "{{}}",
])

# ---------------------------------------------------------------------------
# Recursive JSON value generator
# ---------------------------------------------------------------------------

_DEPTH_CHOICES = st.sampled_from([
    0, 1, 2, 3, 4, 5, 8, 16, 32, 64, 128, 256,
    512, 1024, 1500, 1800, 2000, 2040, 2046, 2047, 2048, 2049, 2050, 2100, 3000,
])

def _deep_nesting():
    depth = _DEPTH_CHOICES
    return st.tuples(depth, st.booleans(), st.booleans()).map(_render_deep)

def _render_deep(t):
    depth, is_obj, inner_is_str = t
    if depth > 4096:
        depth = 4096
    if is_obj:
        inner = '{"k":"v"}' if inner_is_str else '{}'
        open_c, close_c = '{"k":', '}'
    else:
        inner = '["v"]' if inner_is_str else '[]'
        open_c, close_c = '[', ']'
    return open_c * depth + inner + close_c * depth

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _MALFORMED,
    )

def _value_strategy():
    return st.recursive(
        _leaf(),
        lambda children: st.one_of(_array(children), _object(children)),
        max_leaves=20,
    )

def _array(children):
    return st.one_of(
        st.just("[]"),
        st.lists(children, min_size=1, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]"),
        st.lists(children, min_size=1, max_size=4).map(lambda xs: "[" + ",".join(xs) + ",]"),
        st.lists(children, min_size=2, max_size=4).map(lambda xs: "[" + " ".join(xs) + "]"),
    )

def _pair(children):
    return st.tuples(_string(), children).map(lambda t: t[0] + ":" + t[1])

def _object(children):
    return st.one_of(
        st.just("{}"),
        st.lists(_pair(children), min_size=1, max_size=4).map(
            lambda ps: "{" + ",".join(ps) + "}"
        ),
        st.tuples(_string(), children, children).map(
            lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
        ),
        st.lists(_pair(children), min_size=1, max_size=3).map(
            lambda ps: "{" + ",".join(ps) + ",}"
        ),
        st.tuples(_string(), children).map(lambda t: "{" + t[0] + t[1] + "}"),
    )

# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

_TRAILING = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\n", "\t", "abc", "garbage", "xyz", "]", "}", ",", "1", "null"]),
)

_WHITESPACE_PREFIX = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\n", "\t", "\r", "  \n\t "]),
)

def _assemble(t):
    ws, val, trail = t
    return ws + val + trail

_base_value = _value_strategy()

# ---------------------------------------------------------------------------
# Roundtrip / serialize / equals / deep-copy exercisers
#
# The uncovered functions are all "post-parse" APIs (serialize, equals,
# deep_copy, validate).  They are only reached when the input parses
# successfully into a non-trivial value.  We therefore add a family of
# *strictly valid* JSON documents (no trailing junk, no malformed
# fragments, no duplicate keys, no leading zeros) so the harness will
# actually invoke those code paths.
# ---------------------------------------------------------------------------

def _valid_string_char():
    # Printable ASCII plus a few escapes; no raw control, no lone surrogates.
    return st.one_of(
        st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=6),
        st.sampled_from(_ESCAPES),
        st.sampled_from(["\\u00e9", "\\u2028", "\\ud83d\\ude00", "\\u0000"]),
    )

def _valid_string():
    return st.lists(_valid_string_char(), max_size=6).map(
        lambda xs: '"' + "".join(xs) + '"'
    )

def _valid_number():
    return st.one_of(
        st.integers(min_value=-10**15, max_value=10**15).map(str),
        st.tuples(
            st.integers(min_value=-10**9, max_value=10**9),
            st.integers(min_value=0, max_value=10**9),
            st.integers(min_value=-300, max_value=300),
        ).map(lambda t: "%d.%de%d" % t),
        st.just("0"),
        st.just("-0.0"),
        st.just("1.7976931348623157e308"),
    )

def _valid_leaf():
    return st.one_of(
        _valid_string(),
        _valid_number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _valid_value():
    return st.recursive(
        _valid_leaf(),
        lambda children: st.one_of(
            st.lists(children, max_size=4).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(
                st.tuples(_valid_string(), children), max_size=4
            ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
        ),
        max_leaves=12,
    )

# A valid document, optionally with surrounding whitespace (still valid).
_valid_doc = st.tuples(
    _WHITESPACE_PREFIX, _valid_value(), _WHITESPACE_PREFIX
).map(lambda t: t[0] + t[1] + t[2])

# ---------------------------------------------------------------------------
# NEW: richer valid documents aimed specifically at serialize / equals /
# deep_copy / validate.  These functions only fire on successful parses, so
# we build larger, more heterogeneous, escape-heavy valid documents.
# ---------------------------------------------------------------------------

def _rich_valid_string():
    # Mix printable runs with every escape form, including unicode escapes
    # that decode to multibyte UTF-8 and surrogate pairs.
    pieces = st.one_of(
        st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=12),
        st.sampled_from(_ESCAPES),
        st.sampled_from([
            "\\u0000", "\\u001f", "\\u007f", "\\u00e9", "\\u2028",
            "\\u20ac", "\\ud83d\\ude00", "\\uFFFD", "\\uD834\\uDD1E",
        ]),
    )
    return st.lists(pieces, min_size=0, max_size=10).map(
        lambda xs: '"' + "".join(xs) + '"'
    )

def _rich_valid_number():
    return st.one_of(
        st.integers(min_value=-10**18, max_value=10**18).map(str),
        st.tuples(
            st.integers(min_value=-10**9, max_value=10**9),
            st.integers(min_value=0, max_value=10**12),
            st.integers(min_value=-320, max_value=320),
        ).map(lambda t: "%d.%de%d" % t),
        st.sampled_from([
            "0", "-0", "0.0", "-0.0", "1e0", "1E0", "1e+0", "1e-0",
            "1.7976931348623157e308", "5e-324", "2.2250738585072014e-308",
            "123456789012345678901234567890",
        ]),
    )

def _rich_valid_leaf():
    return st.one_of(
        _rich_valid_string(),
        _rich_valid_number(),
        st.sampled_from(["true", "false", "null"]),
    )

def _rich_valid_value():
    return st.recursive(
        _rich_valid_leaf(),
        lambda children: st.one_of(
            st.lists(children, min_size=0, max_size=6).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(
                st.tuples(_rich_valid_string(), children), min_size=0, max_size=6
            ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
        ),
        max_leaves=25,
    )

_rich_valid_doc = st.tuples(
    _WHITESPACE_PREFIX, _rich_valid_value(), _WHITESPACE_PREFIX
).map(lambda t: t[0] + t[1] + t[2])

# ---------------------------------------------------------------------------
# NEW: targeted valid documents for serialize / deep_copy / equals / validate
#
# These post-parse APIs are only reached on successful parses.  We dedicate a
# large share of the strategy to *strictly valid* documents that are
# guaranteed to parse, so those functions actually get exercised.  We also
# include structural variants (empty containers, single-element containers,
# nested empties) that stress the recursive serialize/deep_copy/equals paths.
# ---------------------------------------------------------------------------

def _serialize_string():
    # Strings that exercise the serialize_string path heavily: control chars
    # via escapes, quotes, backslashes, forward slashes, unicode escapes,
    # surrogate pairs, and long printable runs.
    pieces = st.one_of(
        st.text(alphabet=_SAFE_CHARS, min_size=0, max_size=20),
        st.sampled_from(_ESCAPES),
        st.sampled_from([
            "\\u0000", "\\u0001", "\\u001f", "\\u007f", "\\u0080",
            "\\u00e9", "\\u2028", "\\u2029", "\\u20ac", "\\uFFFD",
            "\\ud83d\\ude00", "\\uD834\\uDD1E", "\\uDBFF\\uDFFF",
            "\\/", "\\\\", '\\"',
        ]),
    )
    return st.lists(pieces, min_size=0, max_size=12).map(
        lambda xs: '"' + "".join(xs) + '"'
    )

def _serialize_value():
    return st.recursive(
        st.one_of(
            _serialize_string(),
            _rich_valid_number(),
            st.sampled_from(["true", "false", "null"]),
        ),
        lambda children: st.one_of(
            # Empty and single-element containers stress serialize loops.
            st.just("[]"),
            st.just("{}"),
            st.lists(children, min_size=1, max_size=8).map(
                lambda xs: "[" + ",".join(xs) + "]"
            ),
            st.lists(
                st.tuples(_serialize_string(), children), min_size=1, max_size=8
            ).map(lambda ps: "{" + ",".join(k + ":" + v for k, v in ps) + "}"),
        ),
        max_leaves=40,
    )

_serialize_doc = st.tuples(
    _WHITESPACE_PREFIX, _serialize_value(), _WHITESPACE_PREFIX
).map(lambda t: t[0] + t[1] + t[2])

# Structural documents: containers-of-containers, empty inner containers,
# mixed types — good for deep_copy / equals recursion.
_structural_doc = st.sampled_from([
    "[]", "{}", "[[]]", "[{}]", "{\"a\":[]}", "{\"a\":{}}",
    "[[],[]]", "[{},{}]", "{\"a\":[],\"b\":{}}",
    "[[[[]]]]", "{\"a\":{\"b\":{\"c\":[]}}}",
    "[null]", "[true]", "[false]", "[0]", "[\"\"]",
    "{\"\":null}", "{\"\":\"\"}", "{\"a\":[null,true,false,0,\"\"]}",
    "[1,2,3,4,5,6,7,8,9,10]",
    "{\"a\":1,\"b\":2,\"c\":3,\"d\":4,\"e\":5}",
    "[[1,2],[3,4],[5,6]]",
    "{\"x\":{\"y\":{\"z\":[1,2,3]}}}",
])

# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    st.tuples(_WHITESPACE_PREFIX, _base_value, _TRAILING).map(_assemble),
    _deep_nesting(),
    _MALFORMED,
    st.tuples(_string(), _base_value, _base_value).map(
        lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
    ),
    st.sampled_from(["-", "-.", "+", "+.", ".", ".5", "1.", "01", "-01", "1e", "1e+"]),
    st.sampled_from([
        "1e309", "-1e309", "1e-400", "1e400", "1e999999", "0e0",
        "1.7976931348623157e308", "1.7976931348623159e308",
        "2.2250738585072014e-308", "5e-324", "1e-324",
        "123456789012345678901234567890",
        "-0", "0.0", "-0.0",
    ]),
    st.lists(_escaped_piece(), min_size=1, max_size=6).map(
        lambda parts: '"' + "".join(parts) + '"'
    ),
    st.sampled_from(["{}", "[]", "  {}  ", "\n[]\n", " \t\r\n ", "{}[]", "[][]"]),
    # Strictly valid documents to exercise serialize/equals/deep_copy/validate.
    _valid_doc,
    # Bias heavily toward valid documents with rich, deeply-nested,
    # heterogeneous structures so serialize/equals/deep_copy/validate get
    # exercised on non-trivial values (strings with escapes, unicode,
    # numbers, nested arrays/objects, booleans, nulls).
    _valid_doc,
    _valid_doc,
    st.tuples(_WHITESPACE_PREFIX, _valid_value(), _WHITESPACE_PREFIX).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    # Richer valid documents targeting the uncovered post-parse APIs.
    _rich_valid_doc,
    _rich_valid_doc,
    _rich_valid_doc,
    # NEW: dedicated serialize/deep_copy/equals/validate exercisers.  These
    # are guaranteed-valid documents so the post-parse APIs always run.
    _serialize_doc,
    _serialize_doc,
    _serialize_doc,
    _serialize_doc,
    _structural_doc,
    _structural_doc,
    _structural_doc,
    _structural_doc,
)