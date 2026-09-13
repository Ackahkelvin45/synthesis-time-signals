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
# Valid-JSON generator (round-trippable)
# ---------------------------------------------------------------------------

def _valid_json_scalar():
    return st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(10**18), max_value=10**18),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(alphabet=_SAFE_CHARS, max_size=12),
        st.text(max_size=12),
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

# ---------------------------------------------------------------------------
# NEW: whitespace / structural mutation of valid JSON
# ---------------------------------------------------------------------------

# Whitespace tokens the JSON grammar permits between tokens.  Includes the
# four RFC whitespace chars plus a few near-misses to stress the lexer.
_WS_TOKENS = st.sampled_from([" ", "\t", "\n", "\r", "\f", "\v", "\u00a0", "\u2028"])

def _ws_run():
    return st.lists(_WS_TOKENS, min_size=0, max_size=4).map("".join)

def _interleave_ws(obj_text):
    # Insert random whitespace runs around every structural token.  This
    # produces inputs that are valid JSON but with unusual spacing, which
    # exercises the C parser's whitespace-skipping paths.
    out = []
    for ch in obj_text:
        if ch in "{}[],:":
            out.append(ch)
        else:
            out.append(ch)
    return "".join(out)

def _ws_padded():
    # Take a valid JSON doc and pad it with whitespace at start/end.
    return st.tuples(_valid_json_compact(), _ws_run(), _ws_run()).map(
        lambda t: t[1] + t[0] + t[2]
    )

# ---------------------------------------------------------------------------
# NEW: BOM / encoding-edge prefixes
# ---------------------------------------------------------------------------

_BOM_PREFIXES = st.sampled_from([
    "\ufeff",           # UTF-8 BOM as a codepoint (invalid in JSON text)
    "\ufeff\ufeff",
    "\u0000",           # NUL prefix (harness may skip)
    "\u200b",           # zero-width space
    "\u00a0",           # non-breaking space
    "\u2028",           # line separator
    "\u2029",           # paragraph separator
    "\u0085",           # NEL
])

def _bom_prefixed():
    return st.tuples(_BOM_PREFIXES, _valid_json_compact()).map(
        lambda t: t[0] + t[1]
    )

# ---------------------------------------------------------------------------
# NEW: number/string boundary combinations
# ---------------------------------------------------------------------------

_BOUNDARY_STRINGS = st.sampled_from([
    '""',
    '"\\u0000"',
    '"\\u007f"',
    '"\\ud800"',        # lone high surrogate
    '"\\udc00"',        # lone low surrogate
    '"\\ud800\\udc00"', # valid surrogate pair (U+10000)
    '"\\udbff\\udfff"', # max valid pair
    '"\\ud800\\ud800"', # invalid pair
    '"\\uffff"',
    '"\\ufffe"',
    '"' + "\u2028" + '"',
    '"' + "\u2029" + '"',
    '"' + "a" * 100 + '"',
    '"' + "\\n" * 50 + '"',
])

_BOUNDARY_NUMBERS = st.sampled_from([
    "0", "-0", "0.0", "-0.0", "0e0", "0e-0", "0e+0",
    "1e308", "1e309", "-1e309", "1e-308", "1e-324", "5e-324",
    "2.2250738585072014e-308",
    "1.7976931348623157e308",
    "1.7976931348623159e308",
    "9007199254740993",          # 2^53+1
    "18446744073709551615",      # 2^64-1
    "18446744073709551616",      # 2^64
    "-9223372036854775808",      # INT64_MIN
    "-9223372036854775809",
    "9223372036854775807",       # INT64_MAX
    "9223372036854775808",
    "10000000000000000000000000000000000000000000000000",
    "0.1", "0.2", "0.3",
    "1.0000000000000000001",
    "-0.0000000000000000001",
])

def _boundary_pair():
    return st.tuples(_BOUNDARY_STRINGS, _BOUNDARY_NUMBERS).map(
        lambda t: '{"s":' + t[0] + ',"n":' + t[1] + '}'
    )

# ---------------------------------------------------------------------------
# NEW: injection of structural tokens into string bodies (lexer confusion)
# ---------------------------------------------------------------------------

def _structural_string():
    # Strings whose *content* contains characters that look like JSON
    # structure, to stress the string tokenizer.
    return st.sampled_from([
        '"{"', '"}"', '"["', '"]"', '":"', '","',
        '"{"a":1}"',
        '"\\"{"',
        '"\\\\"',
        '"\\\\\\""',
        '"[{]}"',
        '"\\u007b"',  # escaped '{'
        '"\\u0022"',  # escaped '"'
        '"\\u005c"',  # escaped '\'
    ])

# ---------------------------------------------------------------------------
# NEW: concatenated documents (parser must reject trailing data)
# ---------------------------------------------------------------------------

def _concatenated():
    return st.tuples(_valid_json_compact(), _valid_json_compact()).map(
        lambda t: t[0] + t[1]
    )

def _concatenated_ws():
    return st.tuples(_valid_json_compact(), _ws_run(), _valid_json_compact()).map(
        lambda t: t[0] + t[1] + t[2]
    )

# ---------------------------------------------------------------------------
# NEW: key-value with pathological keys
# ---------------------------------------------------------------------------

def _pathological_keys():
    return st.one_of(
        st.just('{"":1}'),
        st.just('{"":""}'),
        st.just('{"\\u0000":1}'),
        st.just('{"\\ud800":1}'),
        st.just('{"' + "k" * 1000 + '":1}'),
        st.just('{"a":1,"a":2,"a":3,"a":4,"a":5}'),
        st.just('{"\\n":1}'),
        st.just('{"\\t":1}'),
        st.just('{" ":1}'),
        st.just('{"\\/":1}'),
    )

# ---------------------------------------------------------------------------
# NEW: empty / whitespace-only and structural-only inputs
# ---------------------------------------------------------------------------

_TRIVIAL = st.sampled_from([
    "", " ", "\n", "\t", "\r", "  \n\t\r  ",
    "{", "}", "[", "]", "{}", "[]", "{ }", "[ ]",
    "[,]", "{,}", "[,}", "{,]",
    ":", ",", ":,", ",:",
    "[[", "]]", "{{", "}}",
    "[\n]", "{\n}",
])

# ---------------------------------------------------------------------------
# NEW: token-level splicing / mutation of valid JSON
# ---------------------------------------------------------------------------

_JSON_TOKENS = st.sampled_from([
    "{", "}", "[", "]", ":", ",", " ", "\n", "\t",
    "null", "true", "false", "0", "1", "-1", "1.5", "1e3",
    '"a"', '""', '"\\n"', '"\\u0041"',
])

def _token_soup():
    # Random sequences of JSON tokens: mostly near-valid, occasionally
    # structurally broken, exercising the parser's state machine.
    return st.lists(_JSON_TOKENS, min_size=0, max_size=14).map("".join)

def _splice_valid():
    # Take a valid doc and replace a random interior slice with random tokens.
    def render(t):
        doc, pos, repl = t
        if not doc:
            return repl
        pos = pos % (len(doc) + 1)
        end = min(len(doc), pos + (len(repl) % 5))
        return doc[:pos] + repl + doc[end:]
    return st.tuples(
        _valid_json_compact(),
        st.integers(min_value=0, max_value=200),
        st.lists(_JSON_TOKENS, min_size=1, max_size=6).map("".join),
    ).map(render)

def _duplicate_slice():
    # Duplicate a slice of a valid doc to create structural near-misses.
    def render(t):
        doc, start, length = t
        if not doc:
            return doc
        s = start % len(doc)
        e = min(len(doc), s + (length % (len(doc) + 1)))
        return doc[:e] + doc[s:e] + doc[e:]
    return st.tuples(
        _valid_json_compact(),
        st.integers(min_value=0, max_value=100),
        st.integers(min_value=0, max_value=100),
    ).map(render)

# ---------------------------------------------------------------------------
# Top-level assembly
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
    _valid_json_text(),
    _valid_json_ascii(),
    _valid_json_compact(),
    _valid_json_deep(),
    # --- new branches ---
    _ws_padded(),
    _bom_prefixed(),
    _boundary_pair(),
    _structural_string(),
    _concatenated(),
    _concatenated_ws(),
    _pathological_keys(),
    _TRIVIAL,
    _token_soup(),
    _splice_valid(),
    _duplicate_slice(),
)