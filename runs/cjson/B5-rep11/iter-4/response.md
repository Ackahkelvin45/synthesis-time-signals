```python
from hypothesis import strategies as st
import json

# ---------- scalar building blocks ----------

_hex = "0123456789abcdefABCDEF"

def _esc():
    simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    uni = st.tuples(st.just("\\u"),
                    st.lists(st.sampled_from(_hex), min_size=4, max_size=4)).map(lambda t: t[0] + "".join(t[1]))
    return st.one_of(simple, uni)

def _safe_char():
    # printable ASCII minus quote and backslash
    return st.characters(min_codepoint=0x20, max_codepoint=0x7e).filter(
        lambda c: c not in '"\\'
    )

def _raw_control():
    # raw control bytes / NUL allowed by the parser inside strings
    return st.sampled_from(['\x00', '\x01', '\x07', '\x08', '\x09', '\x0a', '\x0b',
                            '\x0c', '\x0d', '\x1f', '\x7f'])

def _unicode_raw():
    # non-ASCII raw chars, including astral plane
    return st.characters(min_codepoint=0x80, max_codepoint=0x10ffff,
                         blacklist_categories=('Cs',))

def _string_body_piece():
    return st.one_of(
        _safe_char(),
        _esc(),
        _raw_control(),
        _unicode_raw(),
        st.just(""),  # allows empty
    )

def _string():
    inner = st.lists(_string_body_piece(), max_size=12).map("".join)
    return inner.map(lambda s: '"' + s + '"')

# Malformed / edge strings (unterminated, bad escapes, lone surrogate)
def _bad_string():
    return st.one_of(
        # unterminated
        st.lists(_string_body_piece(), max_size=8).map(lambda p: '"' + "".join(p)),
        # lone surrogate escape
        st.tuples(st.just('"\\u'), st.sampled_from(['d800', 'dfff', 'DC00', 'dbff']),
                  st.just('"')).map(lambda t: t[0] + t[1] + t[2]),
        # invalid escape
        st.tuples(st.just('"\\'), st.sampled_from(['x', 'q', 'z', 'U1234', '']),
                  st.just('"')).map(lambda t: t[0] + t[1] + t[2]),
        st.just('"'),
        st.just(''),
    )

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.from_regex(r"[1-9][0-9]{0,20}", fullmatch=True),
        # leading zeros (accepted by parser)
        st.from_regex(r"0[0-9]{1,10}", fullmatch=True),
    )

def _frac():
    return st.one_of(
        st.from_regex(r"\.[0-9]{1,20}", fullmatch=True),
        st.just("."),  # trailing dot accepted
    )

def _exp():
    return st.tuples(
        st.sampled_from(['e', 'E']),
        st.sampled_from(['', '+', '-']),
        st.from_regex(r"[0-9]{1,4}", fullmatch=True),
    ).map(lambda t: t[0] + t[1] + t[2])

def _number():
    base = st.tuples(
        st.sampled_from(['', '-']),
        _int_part(),
        st.one_of(st.just(""), _frac()),
        st.one_of(st.just(""), _exp()),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3])
    extremes = st.sampled_from([
        "0", "-0", "1e309", "-1e309", "1e-400", "1e400",
        "1.7976931348623157e308", "5e-324", "123456789012345678901234567890",
        "0x10", "0XFF", "0xdeadBEEF", "1.", "-1.", "1e01", "1E+01",
        "01", "-007", "1e999999999",
    ])
    bad = st.sampled_from(["+1", ".5", "-", "NaN", "Infinity", "-Infinity", "--1", "1..2"])
    return st.one_of(base, extremes, bad)

# ---------- malformed structural bits ----------

def _malformed_fragment():
    return st.sampled_from([
        ",", ",,", ":", "::", ",]", ",}", "{}", "[]", "{\"a\"}", "[,]", "{,}",
        "'x'", "a", "truex", "nul", "tru", "fals", "  ", "\n", "\t",
    ])

# ---------- recursive value ----------

def _leaf():
    return st.one_of(
        _string(),
        _number(),
        st.sampled_from(["true", "false", "null"]),
        _bad_string(),
        _malformed_fragment(),
    )

def _ws():
    return st.sampled_from(["", "", "", " ", "\t", "\n", "\r\n", "  "])

def _pair(value_strategy):
    key = st.one_of(_string(), _bad_string())
    colon = st.sampled_from([":", ":", ":", "", "::", " "])
    ws1 = _ws()
    ws2 = _ws()
    return st.tuples(key, ws1, colon, ws2, value_strategy).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

def _obj(value_strategy):
    ws = _ws()
    pairs = st.lists(_pair(value_strategy), max_size=4)
    comma = st.sampled_from([",", ",", ",", ",,", "", " ,"])
    def build(t):
        ws1, ps, ws2, cm = t
        if not ps:
            return "{" + ws1 + ws2 + "}"
        joined = ""
        for i, p in enumerate(ps):
            if i:
                joined += cm
            joined += p
        return "{" + ws1 + joined + ws2 + "}"
    return st.tuples(ws, pairs, ws, comma).map(build)

def _arr(value_strategy):
    ws = _ws()
    vals = st.lists(value_strategy, max_size=4)
    comma = st.sampled_from([",", ",", ",", ",,", "", " ,"])
    def build(t):
        ws1, vs, ws2, cm = t
        if not vs:
            return "[" + ws1 + ws2 + "]"
        joined = ""
        for i, v in enumerate(vs):
            if i:
                joined += cm
            joined += v
        return "[" + ws1 + joined + ws2 + "]"
    return st.tuples(ws, vals, ws, comma).map(build)

_value = st.recursive(
    _leaf(),
    lambda children: st.one_of(_obj(children), _arr(children)),
    max_leaves=20,
)

# ---------- deep nesting near the 1000 limit ----------

def _deep(depth, opener, closer):
    # produce exactly `depth` nested arrays or objects
    def gen(d):
        if d <= 0:
            return "0"
        return opener + gen(d - 1) + closer
    return gen(depth)

def _deep_arrays():
    return st.integers(min_value=1, max_value=1001).map(lambda d: _deep(d, "[", "]"))

def _deep_objects():
    return st.integers(min_value=1, max_value=1001).map(lambda d: _deep(d, '{"a":', "}"))

# ---------- top-level assembly ----------

def _bom():
    return st.sampled_from(["", "", "", "\ufeff"])

def _trailing():
    return st.sampled_from(["", "", "", "x", " ", "\x00", "1 2", "abc", "//"])

def _assemble(t):
    bom, val, trail = t
    return bom + val + trail

def _top():
    val = st.one_of(
        _value,
        _deep_arrays(),
        _deep_objects(),
        _leaf(),
    )
    return st.tuples(_bom(), val, _trailing()).map(_assemble)

# ---------- improved strategy ----------

# Boundary depths around any internal nesting limit (e.g. 1000/1001/1024/2048),
# plus randomized large depths to probe stack overflow / recursion limits.
def _boundary_depths():
    return st.sampled_from([1, 2, 10, 100, 127, 128, 129, 255, 256, 257,
                            511, 512, 513, 999, 1000, 1001, 1002, 1023, 1024,
                            1025, 2047, 2048, 2049, 4096])

def _deep_arrays_boundary():
    return _boundary_depths().map(lambda d: _deep(d, "[", "]"))

def _deep_objects_boundary():
    return _boundary_depths().map(lambda d: _deep(d, '{"a":', "}"))

def _deep_mixed():
    # alternate array/object nesting to stress mixed-depth handling
    def gen(d):
        if d <= 0:
            return "0"
        if d % 2:
            return "[" + gen(d - 1) + "]"
        return '{"a":' + gen(d - 1) + "}"
    return _boundary_depths().map(gen)

# Whitespace-flooded valid documents (stress whitespace skipping / lookahead)
def _ws_flood():
    return st.tuples(
        st.lists(_ws(), min_size=1, max_size=200).map("".join),
        st.sampled_from(["0", "null", "true", "[]", "{}", '"x"']),
        st.lists(_ws(), min_size=1, max_size=200).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2])

# Long strings with many escapes (stress escape buffer handling)
def _escape_heavy_string():
    return st.tuples(
        st.just('"'),
        st.lists(st.one_of(_esc(), _safe_char()), min_size=1, max_size=500).map("".join),
        st.just('"'),
    ).map(lambda t: t[0] + t[1] + t[2])

# Long flat arrays/objects (stress list capacity growth)
def _wide_array():
    return st.lists(_leaf(), min_size=1, max_size=500).map(lambda vs: "[" + ",".join(vs) + "]")

def _wide_object():
    return st.lists(_pair(_leaf()), min_size=1, max_size=500).map(
        lambda ps: "{" + ",".join(ps) + "}"
    )

# Truncated valid documents (cut at arbitrary byte offset)
def _truncated(t):
    s = t[0]
    n = t[1]
    if not s:
        return s
    return s[: n % (len(s) + 1)]

def _truncation():
    return st.tuples(_value, st.integers(min_value=0, max_value=10**6)).map(_truncated)

# Numeric boundary values (int/float overflow, underflow, precision)
def _numeric_boundaries():
    return st.sampled_from([
        "9223372036854775807", "9223372036854775808", "-9223372036854775808",
        "-9223372036854775809", "18446744073709551615", "18446744073709551616",
        "2147483647", "2147483648", "-2147483648", "-2147483649",
        "4294967295", "4294967296",
        "1e-308", "1e-309", "1e-323", "1e-324", "1e-325",
        "1.7976931348623157e308", "1.7976931348623159e308",
        "2.2250738585072014e-308", "4.9406564584124654e-324",
        "0.1", "0.30000000000000004", "3.141592653589793",
        "1e2147483647", "1e-2147483648", "-0.0",
    ])

# Duplicate keys (parser should keep last or first consistently)
def _duplicate_keys():
    return st.sampled_from([
        '{"a":1,"a":2}', '{"a":1,"a":2,"a":3}',
        '{"a":1,"b":2,"a":3}', '{"":1,"":2}',
    ])

# Unicode escape edge cases: surrogate pairs, out-of-range, truncated, uppercase
def _unicode_escape_edges():
    return st.sampled_from([
        '"\\u0000"', '"\\uFFFF"', '"\\uffff"', '"\\uD834\\uDD1E"',
        '"\\ud834\\udd1e"', '"\\ud834"', '"\\udd1e"',
        '"\\uD834\\u0041"', '"\\uD834\\uD834"',
        '"\\u12"', '"\\u"', '"\\u123"', '"\\u12345"',
        '"\\u{1F600}"', '"\\U0001F600"', '"\\uDBFF\\uDFFF"',
        '"\\uDBFF\\uDFFF"', '"\\uDC00\\uD800"',
    ])

# Strings containing every escape kind in sequence
def _escape_sequence_string():
    return st.tuples(
        st.just('"'),
        st.lists(st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f',
                                  '\\n', '\\r', '\\t']), min_size=1, max_size=50).map("".join),
        st.just('"'),
    ).map(lambda t: t[0] + t[1] + t[2])

# Concatenated / multiple top-level values (must be rejected, only first parsed)
def _multi_top_level():
    return st.tuples(_value, _value).map(lambda t: t[0] + t[1])

# JSON with comments (not valid JSON but some parsers accept)
def _with_comments():
    return st.sampled_from([
        '// c\n1', '1 // c', '/* c */1', '1 /* c */',
        '/* unterminated', '// unterminated',
        '{"a":1 /* x */}', '[1, // y\n 2]',
    ])

# Numbers adjacent to structural chars (lexer boundary tests)
def _number_adjacency():
    return st.sampled_from([
        '[1-2]', '[1e]', '[1e+]', '[1.2.3]', '{"a":1e}',
        '[0x]', '[-]', '[+1]', '[1.e5]', '[.5e5]',
        '[01.5]', '[-0.0e-0]', '[1E-]', '[1E+]',
    ])

# Very long single tokens (stress token buffer)
def _long_token():
    return st.one_of(
        st.integers(min_value=1, max_value=10000).map(lambda n: '"' + "a" * n + '"'),
        st.integers(min_value=1, max_value=10000).map(lambda n: "9" * n),
        st.integers(min_value=1, max_value=10000).map(lambda n: " " * n + "1"),
    )

# Invalid UTF-8-like byte sequences embedded in strings (via lone surrogates)
def _invalid_utf8_like():
    return st.sampled_from([
        '"\ud800"', '"\udfff"', '"\udc00\ud800"',
        '"\ufffe"', '"\uffff"', '"\u0000\u0001"',
    ])

# Structural whitespace edge cases
def _ws_edges():
    return st.sampled_from([
        "\x0b", "\x0c", "\x00", "\u00a0", "\u2028", "\u2029",
        "\ufeff", " \t\r\n", "\r", "\n",
    ])

# Empty and near-empty structures
def _empty_structures():
    return st.sampled_from([
        "{}", "[]", "{ }", "[ ]", "{\n}", "[\t]", "{,}", "[,]",
        "[[[[[]]]]]", "{{{{}}}}", '{"a":{}}', '[[],[]]',
    ])

# Keys with special characters
def _special_keys():
    return st.sampled_from([
        '{"":1}', '{" ":1}', '{"\\n":1}', '{"\\u0000":1}',
        '{"a b":1}', '{"a\\tb":1}', '{"\\uD834\\uDD1E":1}',
        '{"\\/":1}', '{"\\\\":1}',
    ])

# Boolean/null-ish near-misses
def _literal_near_misses():
    return st.sampled_from([
        "True", "FALSE", "Null", "NULL", "None",
        "tru", "truE", "fals", "falsE", "nul", "nulL",
        "truefalse", "nullnull", "true1", "nullx",
    ])

strategy = st.one_of(
    _top(),
    st.just(""),
    st.just(" "),
    st.just("\ufeff"),
    st.just("{}"),
    st.just("[]"),
    st.just("null"),
    st.just("01"),
    st.just("1."),
    st.just("0x10"),
    st.just("1e309"),
    st.just('"\\ud800"'),
    st.just("[1,]"),
    st.just('{"a":1,}'),
    st.just("[1 2]"),
    st.just('{"a" 1}'),
    st.just('"abc'),
    st.just("+1"),
    st.just(".5"),
    st.just("-"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just('"\x00"'),
    st.just('"\x01\x1f"'),
    _deep_arrays(),
    _deep_objects(),
    # --- improved coverage ---
    _deep_arrays_boundary(),
    _deep_objects_boundary(),
    _deep_mixed(),
    _ws_flood(),
    _escape_heavy_string(),
    _wide_array(),
    _wide_object(),
    _truncation(),
    _numeric_boundaries(),
    _duplicate_keys(),
    # --- additional targeted constructs ---
    _unicode_escape_edges(),
    _escape_sequence_string(),
    _multi_top_level(),
    _with_comments(),
    _number_adjacency(),
    _long_token(),
    _invalid_utf8_like(),
    _ws_edges(),
    _empty_structures(),
    _special_keys(),
    _literal_near_misses(),
)
```