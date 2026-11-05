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
)
```