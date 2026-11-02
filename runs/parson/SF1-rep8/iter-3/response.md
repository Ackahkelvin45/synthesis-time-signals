```python
from hypothesis import strategies as st

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

def _literal():
    return st.sampled_from(["true", "false", "null"])

def _leaf():
    return st.one_of(
        _literal(),
        _literal(),
        _literal(),
        _string(),
        _number(),
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

# A single complete, well-formed document (no trailing junk, no leading junk
# beyond optional whitespace).  This boosts the acceptance rate and gives the
# parser clean inputs to exercise the full grammar.
def _clean_document():
    return st.tuples(_WHITESPACE_PREFIX, _base_value, _WHITESPACE_PREFIX).map(
        lambda t: t[0] + t[1] + t[2]
    )

strategy = st.one_of(
    # Clean, complete documents (higher acceptance; exercises full grammar).
    _clean_document(),
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
    # Bare literals and small structures built from them.
    st.sampled_from([
        "true", "false", "null",
        "[true]", "[false]", "[null]",
        "[true,false]", "[true,false,null]",
        '{"a":true}', '{"a":false}', '{"a":null}',
        '{"t":true,"f":false,"n":null}',
        "[true,false,null,true,false,null]",
        '{"a":true,"b":false,"c":null}',
        " true ", " false ", " null ",
        "[ true , false , null ]",
    ]),
)
```