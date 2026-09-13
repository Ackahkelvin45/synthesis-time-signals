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

# Raw control characters ARE allowed by the grammar inside strings except the
# ones explicitly excluded (quote, backslash, 0x00-0x1F).  We avoid raw NUL
# (harness skips) but allow other raw control bytes to exercise the tokenizer.
_RAW_CONTROL = "".join(chr(c) for c in range(1, 0x20) if c != 0x00)

_ESCAPES = ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]

def _hex4():
    return st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

def _unicode_escape():
    # Normal \uXXXX plus surrogate range (lone surrogates are interesting).
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
        st.just("\u2028"),  # line separator, valid SAFECODEPOINT
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
# Malformed snippets (near-valid but broken)
# ---------------------------------------------------------------------------

_MALFORMED = st.sampled_from([
    "",                     # empty
    "{", "}", "[", "]",
    "{,}", "[,]", "[1,]", "{,}",
    "{\"a\"}",              # missing colon
    "{\"a\":}",             # missing value
    "{\"a\":,}",            # missing value with comma
    "[1 2]",                # missing comma
    "{\"a\":1 \"b\":2}",    # missing comma in obj
    "\"unterminated",       # unterminated string
    "\"bad\\",              # trailing backslash
    "\"bad\\x\"",           # invalid escape
    "\"bad\\u12\"",         # short unicode escape
    "\"bad\\uZZZZ\"",       # non-hex unicode escape
    "01",                   # leading zero
    "-01",
    "+1",                   # leading plus
    ".5",                   # leading dot
    "-.5",
    "1.",                   # trailing dot
    "1e",                   # missing exponent
    "1e+",
    "tru", "fals", "nul",   # truncated literals
    "True", "FALSE", "Null",
    "nulll",
    "{\"a\":1,}",           # trailing comma
    "[1,2,]",
    ":", ",",               # bare punctuation
    "'single'",             # single quotes
    "{\"a\"::1}",
    "[[]",
    "{{}}",
])

# ---------------------------------------------------------------------------
# Recursive JSON value generator
# ---------------------------------------------------------------------------

# Depth budget concentrated near the parser's MAX_NESTING = 2048.
# We generate a "depth hint" that biases toward the interesting neighbourhood.
_DEPTH_CHOICES = st.sampled_from([
    0, 1, 2, 3, 4, 5, 8, 16, 32, 64, 128, 256,
    512, 1024, 1500, 1800, 2000, 2040, 2046, 2047, 2048, 2049, 2050, 2100, 3000,
])

def _deep_nesting():
    # A deeply nested array or object, near the parser's cap.
    depth = _DEPTH_CHOICES
    return st.tuples(depth, st.booleans(), st.booleans()).map(_render_deep)

def _render_deep(t):
    depth, is_obj, inner_is_str = t
    # Guard against pathological memory on the extreme tail.
    if depth > 4096:
        depth = 4096
    if is_obj:
        if inner_is_str:
            inner = '{"k":"v"}'
        else:
            inner = '{}'
        open_c, close_c = '{"k":', '}'
    else:
        if inner_is_str:
            inner = '["v"]'
        else:
            inner = '[]'
        open_c, close_c = '[', ']'
    return open_c * depth + inner + close_c * depth

def _value(draw):
    return draw(_value_strategy())

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
        lambda children: st.one_of(
            _array(children),
            _object(children),
        ),
        max_leaves=20,
    )

def _array(children):
    return st.one_of(
        st.just("[]"),
        st.lists(children, min_size=1, max_size=5).map(lambda xs: "[" + ",".join(xs) + "]"),
        # Trailing comma variant
        st.lists(children, min_size=1, max_size=4).map(lambda xs: "[" + ",".join(xs) + ",]"),
        # Missing comma variant
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
        # Duplicate keys (parser rejects; still interesting)
        st.tuples(_string(), children, children).map(
            lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
        ),
        # Trailing comma
        st.lists(_pair(children), min_size=1, max_size=3).map(
            lambda ps: "{" + ",".join(ps) + ",}"
        ),
        # Missing colon
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
# Valid-JSON generator (round-trippable): build a Python object and json.dumps
# it.  This yields large, well-formed inputs that exercise the C parser's
# happy path and deep-recursion handling far better than hand-assembled
# strings, and json.dumps guarantees the escaping is exactly right.
# ---------------------------------------------------------------------------

def _valid_json_scalar():
    return st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(10**18), max_value=10**18),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(alphabet=_SAFE_CHARS, max_size=12),
        st.text(max_size=12),  # arbitrary unicode, exercised via json.dumps
    )

def _valid_json_value():
    return st.recursive(
        _valid_json_scalar(),
        lambda children: st.one_of(
            st.lists(children, max_size=6),
            st.dictionaries(
                st.text(alphabet=_SAFE_CHARS, max_size=8),
                children,
                max_size=6,
            ),
        ),
        max_leaves=25,
    )

def _valid_json_text():
    return _valid_json_value().map(lambda obj: json.dumps(obj, ensure_ascii=False))

def _valid_json_ascii():
    return _valid_json_value().map(lambda obj: json.dumps(obj, ensure_ascii=True))

def _valid_json_compact():
    return _valid_json_value().map(
        lambda obj: json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    )

def _valid_json_deep():
    # Valid JSON nested exactly to a target depth, built via json.dumps so it
    # is guaranteed well-formed.  Stresses the parser's recursion cap.
    def render(t):
        depth, is_obj = t
        if depth > 4096:
            depth = 4096
        if is_obj:
            obj = {}
            for _ in range(depth):
                obj = {"k": obj}
        else:
            obj = []
            for _ in range(depth):
                obj = [obj]
        return json.dumps(obj, separators=(",", ":"))
    return st.tuples(_DEPTH_CHOICES, st.booleans()).map(render)

strategy = st.one_of(
    # Normal recursive values, with optional leading/trailing junk.
    st.tuples(_WHITESPACE_PREFIX, _base_value, _TRAILING).map(_assemble),
    # Explicit deep nesting near the parser's cap.
    _deep_nesting(),
    # Pure malformed inputs.
    _MALFORMED,
    # Duplicate keys at top level.
    st.tuples(_string(), _base_value, _base_value).map(
        lambda t: "{" + t[0] + ":" + t[1] + "," + t[0] + ":" + t[2] + "}"
    ),
    # Lone sign / partial-number leniencies.
    st.sampled_from(["-", "-.", "+", "+.", ".", ".5", "1.", "01", "-01", "1e", "1e+"]),
    # Extreme magnitudes.
    st.sampled_from([
        "1e309", "-1e309", "1e-400", "1e400", "1e999999", "0e0",
        "1.7976931348623157e308", "1.7976931348623159e308",
        "2.2250738585072014e-308", "5e-324", "1e-324",
        "123456789012345678901234567890",
        "-0", "0.0", "-0.0",
    ]),
    # Surrogate / unicode escape soup inside strings.
    st.lists(_escaped_piece(), min_size=1, max_size=6).map(
        lambda parts: '"' + "".join(parts) + '"'
    ),
    # Empty containers and trivial whitespace.
    st.sampled_from(["{}", "[]", "  {}  ", "\n[]\n", " \t\r\n ", "{}[]", "[][]"]),
    # Well-formed JSON generated via json.dumps — exercises the happy path
    # with realistic, deeply structured documents and correct escaping.
    _valid_json_text(),
    _valid_json_ascii(),
    _valid_json_compact(),
    _valid_json_deep(),
)