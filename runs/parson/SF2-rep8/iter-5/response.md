```python
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
# Structured, valid JSON via json.dumps for broad valid-path coverage
# ---------------------------------------------------------------------------

def _json_value_strategy():
    return st.recursive(
        st.one_of(
            st.none(),
            st.booleans(),
            st.integers(min_value=-10**18, max_value=10**18),
            st.floats(allow_nan=False, allow_infinity=False),
            _string_body(),
        ),
        lambda children: st.one_of(
            st.lists(children, max_size=5),
            st.dictionaries(_string_body(), children, max_size=5),
        ),
        max_leaves=20,
    )

_valid_json = _json_value_strategy().map(json.dumps)

# ---------------------------------------------------------------------------
# Structural fuzzers targeting under-covered parser branches
# ---------------------------------------------------------------------------

# Truncation of a valid document at an arbitrary byte offset exercises the
# "unexpected EOF" branches throughout the recursive-descent parser.
def _truncation():
    return st.tuples(_valid_json, st.floats(min_value=0.0, max_value=1.0)).map(
        lambda t: t[0][: int(len(t[0]) * t[1])]
    )

# Pure punctuation soup stresses the tokenizer's default/reject path for
# structural characters in unexpected positions.
_PUNCT = "{}[],:\"\\ \t\n\r"

def _punct_soup():
    return st.lists(
        st.sampled_from(list(_PUNCT)),
        min_size=1,
        max_size=12,
    ).map("".join)

# Number tokenizer edge cases: signs, dots, exponents in every combination.
_NUM_EDGE = st.one_of(
    st.tuples(
        st.sampled_from(["", "+", "-"]),
        st.sampled_from(["", "0", "1", "12", "12345678901234567890"]),
        st.sampled_from(["", ".", ".0", ".5", ".123"]),
        st.sampled_from(["", "e", "E", "e+", "e-", "e0", "E+1", "e-1", "e999", "e-999"]),
    ).map(lambda t: "".join(t)),
    st.sampled_from([
        "0e", "0e+", "0e-", "0.", "0.e1", "1.e1", "1..2", "1e1e1",
        "-0e0", "+0e0", "00", "000", "-00", "1E", "1E+", "1E-",
        "1ee1", "1e++1", "1e--1", "1e+-1", "1e-+1",
    ]),
)

# Literal keyword edge cases: every prefix of true/false/null plus case
# variants and trailing junk.
_LIT_EDGE = st.one_of(
    st.sampled_from([
        "t", "tr", "tru", "true", "truex", "true ", "True", "TRUE",
        "f", "fa", "fal", "fals", "false", "falsex", "False", "FALSE",
        "n", "nu", "nul", "null", "nullx", "Null", "NULL",
        "truetrue", "nullnull", "falsefalse",
    ]),
)

# Strings with pathological escape sequences and boundary codepoints.
_STR_EDGE = st.one_of(
    st.sampled_from([
        '""', '"\\u0000"', '"\\u001f"', '"\\u0020"', '"\\u007f"',
        '"\\u0080"', '"\\ud7ff"', '"\\ud800"', '"\\udbff"',
        '"\\udc00"', '"\\udfff"', '"\\ue000"', '"\\uffff"',
        '"\\ud800\\udc00"', '"\\udbff\\udfff"',
        '"\\ud800\\ud800"', '"\\udc00\\udc00"',
        '"\\uD800\\uDC00"',
        '"\\"', '"\\\\', '"\\/', '"\\b', '"\\f', '"\\n', '"\\r', '"\\t',
        '"\\x"', '"\\u"', '"\\u0"', '"\\u00"', '"\\u000"',
        '"\\u000g"', '"\\U0041"',
    ]),
)

# Whitespace interleaved between every structural token of a small doc.
def _ws_spaced():
    ws = st.sampled_from(["", " ", "\n", "\t", "\r", "  ", "\n\t"])
    return st.tuples(
        ws, ws, ws, ws, ws, ws, ws, ws,
        st.sampled_from(['"a"', '"b"', "1", "true", "null", "[]", "{}"]),
        st.sampled_from(['"x"', '"y"', "2", "false"]),
    ).map(lambda t: (
        t[0] + "{" + t[1] + t[8] + t[2] + ":" + t[3] + t[9] + t[4] + "," +
        t[5] + '"c"' + t[6] + ":" + t[7] + "1" + t[4] + "}"
    ))

# ---------------------------------------------------------------------------
# NEW: targeted generators for under-covered branches
# ---------------------------------------------------------------------------

# Mutations of a valid document at a single byte position.  Single-point
# mutations are a strong driver of error-path coverage: they hit "unexpected
# character", "expected X" and similar branches that pure random soup misses.
_MUTATION_BYTES = list('{}[],:"\\ \t\n\r0123456789tfn.eE+-') + list(_RAW_CONTROL)

def _mutate():
    return st.tuples(
        _valid_json,
        st.integers(min_value=0, max_value=10**6),
        st.sampled_from(_MUTATION_BYTES),
        st.sampled_from(["insert", "replace", "delete"]),
    ).map(_apply_mutation)

def _apply_mutation(t):
    doc, pos, ch, op = t
    if not doc:
        return ch
    i = pos % (len(doc) + 1)
    if op == "insert":
        return doc[:i] + ch + doc[i:]
    if op == "replace":
        if i >= len(doc):
            i = len(doc) - 1
        return doc[:i] + ch + doc[i + 1:]
    # delete
    if i >= len(doc):
        i = len(doc) - 1
    return doc[:i] + doc[i + 1:]

# Two-point mutation: two independent edits to a valid document.
def _mutate2():
    return st.tuples(
        _valid_json,
        st.integers(min_value=0, max_value=10**6),
        st.sampled_from(_MUTATION_BYTES),
        st.integers(min_value=0, max_value=10**6),
        st.sampled_from(_MUTATION_BYTES),
    ).map(_apply_mutation2)

def _apply_mutation2(t):
    doc, p1, c1, p2, c2 = t
    if not doc:
        return c1 + c2
    i = p1 % (len(doc) + 1)
    doc = doc[:i] + c1 + doc[i:]
    j = p2 % (len(doc) + 1)
    doc = doc[:j] + c2 + doc[j:]
    return doc

# Prefixes of valid documents up to every length, to systematically hit
# every EOF position inside a known-good structure.
def _prefix():
    return st.tuples(_valid_json, st.floats(min_value=0.0, max_value=1.0)).map(
        lambda t: t[0][: int(len(t[0]) * t[1])]
    )

# Suffix / leading garbage around a valid document.
def _garbage_wrap():
    return st.tuples(
        st.sampled_from(["", " ", "\n", "x", "]", "}", ",", ":", "0", "\"", "\\"]),
        _valid_json,
        st.sampled_from(["", " ", "\n", "x", "]", "}", ",", ":", "0", "\"", "\\"]),
    ).map(lambda t: t[0] + t[1] + t[2])

# Deeply nested valid-ish structures at moderate depths (exercises the
# recursion/stack paths without the extreme tail).
def _mid_nesting():
    return st.tuples(
        st.integers(min_value=1, max_value=64),
        st.booleans(),
    ).map(lambda t: (
        ('[' * t[0]) + ('1' if t[1] else '') + (']' * t[0])
    ))

# Object/array with many members (exercises the member-loop and comma paths).
def _wide():
    return st.tuples(
        st.booleans(),
        st.lists(_leaf(), min_size=1, max_size=32),
    ).map(lambda t: (
        ("[" + ",".join(t[1]) + "]") if t[0]
        else ("{" + ",".join('"k%d":%s' % (i, v) for i, v in enumerate(t[1])) + "}")
    ))

# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

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
    # Well-formed JSON via json.dumps for broad valid-path coverage.
    _valid_json,
    # Whitespace-only and control-char inputs to exercise the tokenizer's
    # whitespace skipping and EOF handling paths.
    st.text(
        alphabet=" \t\n\r" + _RAW_CONTROL,
        min_size=0,
        max_size=16,
    ),
    # Bare scalar values at top level (valid JSON) with surrounding whitespace.
    st.tuples(_WHITESPACE_PREFIX, _leaf(), _TRAILING).map(_assemble),
    # Strings with embedded whitespace/control chars to exercise string
    # tokenization and escape handling paths.
    st.lists(
        st.one_of(
            _string_char(),
            st.sampled_from(list(" \t\n\r")),
        ),
        min_size=0,
        max_size=10,
    ).map(lambda parts: '"' + "".join(parts) + '"'),
    # Objects/arrays with whitespace around structural characters.
    st.tuples(_base_value, _base_value).map(
        lambda t: "{\n  \"a\" : " + t[0] + " ,\n  \"b\" : " + t[1] + "\n}"
    ),
    # --- New coverage-targeted generators ---
    # Truncated valid documents (unexpected-EOF branches).
    _truncation(),
    # Structural punctuation soup (tokenizer default/reject paths).
    _punct_soup(),
    # Number-tokenizer edge combinations.
    _NUM_EDGE,
    # Literal keyword edge cases.
    _LIT_EDGE,
    # String escape / codepoint boundary cases.
    _STR_EDGE,
    # Whitespace interleaved between structural tokens.
    _ws_spaced(),
    # --- Newly added targeted generators (improve_strategy) ---
    # Single-point mutations of valid documents.
    _mutate(),
    # Two-point mutations of valid documents.
    _mutate2(),
    # Systematic prefixes of valid documents.
    _prefix(),
    # Valid documents wrapped in leading/trailing garbage.
    _garbage_wrap(),
    # Moderate-depth nesting.
    _mid_nesting(),
    # Wide containers.
    _wide(),
)
```