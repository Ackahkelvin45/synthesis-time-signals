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

# ---------- improved structural fuzzing ----------

# Mixed deep nesting: alternate arrays and objects with malformed inner content.
def _deep_mixed():
    def gen(d, acc):
        if d <= 0:
            return acc
        # choose an opener/closer and recurse
        return None
    # build via integers + a strategy choice
    def build(t):
        depth, kind = t
        s = "0"
        for i in range(depth):
            if (i + kind) % 2 == 0:
                s = "[" + s + "]"
            else:
                s = '{"a":' + s + "}"
        return s
    return st.tuples(
        st.integers(min_value=1, max_value=1001),
        st.integers(min_value=0, max_value=1),
    ).map(build)

# Deep nesting with malformed tail (missing closer) to hit error paths at depth.
def _deep_truncated():
    def build(t):
        depth, opener = t
        return opener * depth
    return st.tuples(
        st.integers(min_value=1, max_value=1001),
        st.sampled_from(["[", '{"a":', '{"', "[[", "{[", '{"a":[', '{"a":{"b":']),
    ).map(build)

# Wide structures with many elements to stress list/object handling.
def _wide_array():
    elem = st.one_of(_leaf(), st.just("0"), st.just("null"), st.just('"x"'))
    return st.lists(elem, min_size=0, max_size=200).map(
        lambda xs: "[" + ",".join(xs) + "]"
    )

def _wide_object():
    pair = st.tuples(
        st.one_of(_string(), st.just('"k"')),
        st.just(":"),
        st.one_of(_leaf(), st.just("0"), st.just("null")),
    ).map(lambda t: t[0] + t[1] + t[2])
    return st.lists(pair, min_size=0, max_size=200).map(
        lambda xs: "{" + ",".join(xs) + "}"
    )

# Whitespace-heavy documents to stress the lexer.
def _ws_heavy():
    ws = st.sampled_from([" ", "\t", "\n", "\r\n", "\r", "\x0b", "\x0c", "  "])
    return st.tuples(
        st.lists(ws, min_size=1, max_size=8).map("".join),
        st.one_of(_value, st.just("0"), st.just("{}"), st.just("[]")),
        st.lists(ws, min_size=1, max_size=8).map("".join),
    ).map(lambda t: t[0] + t[1] + t[2])

# String-heavy documents with escapes and raw bytes.
def _string_heavy():
    return st.tuples(
        st.just("["),
        st.lists(_string(), min_size=1, max_size=20),
        st.just("]"),
    ).map(lambda t: t[0] + ",".join(t[1]) + t[2])

# Number-heavy documents.
def _number_heavy():
    return st.lists(_number(), min_size=1, max_size=50).map(
        lambda xs: "[" + ",".join(xs) + "]"
    )

# Random byte-ish strings (valid Python str, may contain control chars).
def _byte_soup():
    return st.lists(
        st.one_of(
            _safe_char(),
            _raw_control(),
            st.sampled_from(['{', '}', '[', ']', ':', ',', '"', '\\', '0', '1', 'e', '-', '.']),
        ),
        min_size=0,
        max_size=40,
    ).map("".join)

# ---------- new: bare-whitespace and lexer-stress documents ----------

# Documents that are entirely whitespace (and possibly BOM) to stress top-level skip.
def _ws_only():
    ws = st.sampled_from([" ", "\t", "\n", "\r", "\r\n", "\x0b", "\x0c", "\u00a0", "\ufeff"])
    return st.lists(ws, min_size=1, max_size=16).map("".join)

# Documents with interleaved whitespace inside brackets and around commas/colons.
def _ws_interleaved():
    ws = st.sampled_from(["", " ", "\t", "\n", "\r\n"])
    def build(t):
        w0, w1, w2, w3, w4, w5 = t
        return (w0 + "[" + w1 + "1" + w2 + "," + w3 + "2" + w4 + "]" + w5)
    return st.tuples(*([ws] * 6)).map(build)

# Deeply nested arrays with a truncation at random depth (missing closers).
def _deep_arrays_truncated():
    def build(t):
        depth, keep = t
        s = "0"
        for _ in range(depth):
            s = "[" + s
        return s
    return st.tuples(
        st.integers(min_value=1, max_value=1001),
        st.integers(min_value=0, max_value=1),
    ).map(build)

# Deeply nested with stray closer at the end.
def _deep_stray_closer():
    def build(t):
        depth, closer = t
        return "[" * depth + closer
    return st.tuples(
        st.integers(min_value=1, max_value=1001),
        st.sampled_from(["]", "]]", "}", "]", "]", "]"]),
    ).map(build)

# Long string with many escapes to stress string scanning.
def _long_escaped_string():
    piece = st.one_of(_esc(), _safe_char(), _raw_control())
    return st.lists(piece, min_size=1, max_size=300).map(
        lambda xs: '"' + "".join(xs) + '"'
    )

# Deep nesting of objects where keys repeat (duplicate keys).
def _deep_dup_keys():
    def build(depth):
        s = "0"
        for _ in range(depth):
            s = '{"a":' + s + ',"a":1}'
        return s
    return st.integers(min_value=1, max_value=200).map(build)

# ---------- new: targeted grammar-boundary and parser-edge cases ----------

# Numbers with extreme exponent digit counts and signs, to stress exponent parsing.
def _number_edge():
    return st.one_of(
        st.tuples(
            st.sampled_from(['', '-']),
            st.sampled_from(["1", "9", "0", "12345678901234567890"]),
            st.sampled_from(["e", "E"]),
            st.sampled_from(['', '+', '-']),
            st.from_regex(r"[0-9]{1,30}", fullmatch=True),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
        st.tuples(
            st.sampled_from(['', '-']),
            st.from_regex(r"[0-9]{1,10}", fullmatch=True),
            st.just("."),
            st.from_regex(r"[0-9]{0,10}", fullmatch=True),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
        st.just("-0.0"),
        st.just("-0e0"),
        st.just("1e-999999999999"),
        st.just("1e+999999999999"),
    )

# Strings containing every escape form together with raw bytes and quotes.
def _string_escape_mix():
    return st.lists(
        st.one_of(
            _esc(),
            _raw_control(),
            _safe_char(),
            st.just('\\'),  # lone backslash inside body
            st.just('"'),   # stray quote inside body
        ),
        min_size=0,
        max_size=40,
    ).map(lambda xs: '"' + "".join(xs) + '"')

# Objects with unquoted / malformed keys and missing separators.
def _bad_object():
    key = st.one_of(
        _string(),
        st.sampled_from(['a', 'abc', '1', 'null', 'true', '', '"', '\\', "'k'"]),
    )
    sep = st.sampled_from([":", "", "::", " ", "=>"])
    val = st.one_of(_leaf(), st.just(""))
    return st.tuples(key, sep, val).map(lambda t: "{" + t[0] + t[1] + t[2] + "}")

# Arrays with missing commas and stray tokens.
def _bad_array():
    return st.lists(
        st.one_of(_leaf(), st.just(""), st.just(","), st.just(":"), st.just(" ")),
        min_size=0,
        max_size=12,
    ).map(lambda xs: "[" + "".join(xs) + "]")

# Nested structure containing a lone surrogate escape deep inside.
def _surrogate_nested():
    def build(t):
        depth, which = t
        s = '"\\u' + which + '"'
        for i in range(depth):
            s = "[" + s + "]" if i % 2 == 0 else '{"k":' + s + "}"
        return s
    return st.tuples(
        st.integers(min_value=0, max_value=20),
        st.sampled_from(['d800', 'dbff', 'dc00', 'dfff', 'D800', 'DFFF']),
    ).map(build)

# Concatenated top-level values (multiple documents) to stress top-level parsing.
def _multi_top():
    return st.lists(
        st.one_of(_leaf(), st.just("{}"), st.just("[]"), st.just("null")),
        min_size=2,
        max_size=5,
    ).map(lambda xs: "".join(xs))

# BOM in unusual positions and repeated BOMs.
def _bom_placement():
    return st.tuples(
        st.sampled_from(["", "\ufeff", "\ufeff\ufeff"]),
        st.one_of(_value, st.just("0"), st.just("null")),
        st.sampled_from(["", "\ufeff"]),
    ).map(lambda t: t[0] + t[1] + t[2])

# Deeply nested with trailing garbage after closers.
def _deep_trailing_garbage():
    def build(t):
        depth, garbage = t
        return "[" * depth + "0" + "]" * depth + garbage
    return st.tuples(
        st.integers(min_value=1, max_value=1001),
        st.sampled_from(["", "x", " ", "]", "}", ",", "1", "[", "\x00"]),
    ).map(build)

# ---------- new: targeted additions for improved coverage ----------

# Numbers with huge digit counts (valid integers/floats) to stress big-number parsing.
def _huge_number():
    return st.one_of(
        st.integers(min_value=1, max_value=5000).map(lambda n: "1" * n),
        st.tuples(
            st.integers(min_value=1, max_value=2000),
            st.integers(min_value=1, max_value=2000),
        ).map(lambda t: "0." + "0" * t[0] + "1" * t[1]),
        st.tuples(
            st.integers(min_value=1, max_value=2000),
            st.integers(min_value=1, max_value=20),
        ).map(lambda t: "1" + "0" * t[0] + "e" + str(t[1])),
    )

# Strings that are extremely long (valid and with escapes) to stress buffer growth.
def _very_long_string():
    return st.tuples(
        st.sampled_from(['"', '"\x00', '"\\n']),
        st.integers(min_value=100, max_value=5000),
        st.sampled_from(['a', '\\n', '\\u00e9', '\x01']),
    ).map(lambda t: t[0] + t[2] * t[1] + '"')

# Arrays/objects with many duplicate keys and mixed types.
def _dup_key_mix():
    return st.tuples(
        st.integers(min_value=1, max_value=100),
        st.sampled_from(['"a"', '"a"', '"b"', '""']),
    ).map(lambda t: "{" + ",".join(t[1] + ":1" for _ in range(t[0])) + "}")

# Precision-boundary float literals.
def _float_precision():
    return st.sampled_from([
        "0.1", "0.2", "0.30000000000000004", "1.0000000000000002",
        "9007199254740993", "9007199254740992.0", "2.2250738585072014e-308",
        "4.9406564584124654e-324", "1.7976931348623157e308",
        "1.7976931348623159e308", "-1.7976931348623159e308",
        "2.2250738585072011e-308", "1e-323", "1e-324", "1e-325",
        "123456789012345678901234567890.123456789012345678901234567890",
    ])

# Documents mixing valid JSON with one embedded syntax error at random position.
def _one_error(t):
    prefix, bad, suffix = t
    return prefix + bad + suffix

def _single_error_doc():
    bad = st.sampled_from([
        ",", ":", "]", "}", '"', "\\", "x", "tru", "fals", "nul",
        "+", ".", "e", "0x", "//", "/*", "\x00", "\x1f", "'",
    ])
    return st.tuples(
        st.one_of(_value, st.just("0"), st.just("null"), st.just('"s"')),
        bad,
        st.one_of(_value, st.just("0"), st.just("null"), st.just('"s"')),
    ).map(_one_error)

# Empty / near-empty containers with odd whitespace.
def _empty_containers():
    ws = st.sampled_from(["", " ", "\t", "\n", "\r\n", "\x0b", "\x0c"])
    return st.tuples(
        st.sampled_from(["[", "{"]),
        st.lists(ws, min_size=0, max_size=6).map("".join),
        st.sampled_from(["]", "}"]),
    ).map(lambda t: t[0] + t[1] + t[2])

# Top-level scalars with surrounding whitespace and BOM.
def _scalar_top():
    return st.tuples(
        st.sampled_from(["", "\ufeff", " ", "\n"]),
        st.one_of(_number(), _string(), st.sampled_from(["true", "false", "null"])),
        st.sampled_from(["", " ", "\n", "\t"]),
    ).map(lambda t: t[0] + t[1] + t[2])

# Nested objects with values of every type at each level.
def _hetero_nest():
    def build(depth):
        s = "null"
        types = ['"s"', "0", "true", "false", "[]", "{}"]
        for i in range(depth):
            s = "[" + s + "," + types[i % len(types)] + "]"
        return s
    return st.integers(min_value=0, max_value=50).map(build)

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
    _deep_mixed(),
    _deep_truncated(),
    _wide_array(),
    _wide_object(),
    _ws_heavy(),
    _string_heavy(),
    _number_heavy(),
    _byte_soup(),
    _ws_only(),
    _ws_interleaved(),
    _deep_arrays_truncated(),
    _deep_stray_closer(),
    _long_escaped_string(),
    _deep_dup_keys(),
    _number_edge(),
    _string_escape_mix(),
    _bad_object(),
    _bad_array(),
    _surrogate_nested(),
    _multi_top(),
    _bom_placement(),
    _deep_trailing_garbage(),
    _huge_number(),
    _very_long_string(),
    _dup_key_mix(),
    _float_precision(),
    _single_error_doc(),
    _empty_containers(),
    _scalar_top(),
    _hetero_nest(),
)