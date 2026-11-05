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

# ---------- print / compare oriented inputs ----------
# The uncovered functions are cJSON_Print* and cJSON_Compare. These take
# parsed values and re-serialize / compare them, so we need richer, more
# diverse *valid* values (many keys, mixed types, unicode, escapes, numbers
# in many formats) and pairs of values that are equal / nearly-equal.

def _print_string():
    # strings exercising print_string_ptr: escapes, unicode, controls
    pieces = st.lists(
        st.one_of(
            _safe_char(),
            st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
            st.tuples(st.just("\\u"),
                      st.lists(st.sampled_from(_hex), min_size=4, max_size=4)
                      ).map(lambda t: t[0] + "".join(t[1])),
            st.sampled_from(['\x00', '\x01', '\x1f', '\x7f', '\n', '\t']),
            st.characters(min_codepoint=0x80, max_codepoint=0x10ffff,
                          blacklist_categories=('Cs',)),
        ),
        max_size=10,
    ).map("".join)
    return pieces.map(lambda s: '"' + s + '"')

def _print_number():
    return st.one_of(
        st.sampled_from([
            "0", "-0", "1", "-1", "1.5", "-1.5", "1e10", "-1e10", "1e-10",
            "1.7976931348623157e308", "5e-324", "1.0", "100.0", "1e0",
            "1234567890", "0.0001", "-0.0001", "1E+5", "1e-5",
        ]),
        _number(),
    )

def _print_leaf():
    return st.one_of(
        _print_string(),
        _print_number(),
        st.sampled_from(["true", "false", "null"]),
    )

_print_value = st.recursive(
    _print_leaf(),
    lambda children: st.one_of(
        st.lists(children, max_size=6).map(lambda vs: "[" + ",".join(vs) + "]"),
        st.lists(
            st.tuples(_print_string(), children).map(lambda t: t[0] + ":" + t[1]),
            max_size=6,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ),
    max_leaves=30,
)

def _print_input():
    return st.tuples(_bom(), _print_value, _trailing()).map(_assemble)

# ---------- compare oriented inputs (pairs) ----------
# cJSON_Compare needs two valid documents; emit them as a two-line blob.

def _compare_pair():
    return st.tuples(_print_value, _print_value).map(lambda t: t[0] + "\n" + t[1])

def _compare_same():
    return _print_value.map(lambda v: v + "\n" + v)

# ---------- dedicated print/compare driver documents ----------
# The print and compare functions were 0% covered. Drive them with a wide
# variety of valid, richly-typed documents (objects with many keys, nested
# arrays, unicode/escaped strings, varied numbers) so print_value,
# print_string_ptr, print_number, print_object and cJSON_Compare all get
# exercised. We also emit compare "same" pairs to hit the equal branch.

def _rich_key():
    return st.one_of(
        _print_string(),
        st.sampled_from(['"a"', '"b"', '"key"', '""', '"\\u00e9"', '"\\n"',
                         '"x y"', '"\\u0041"', '"\\ud83d\\ude00"']),
    )

def _rich_number():
    return st.sampled_from([
        "0", "-0", "1", "-1", "42", "3.14", "-3.14", "1e10", "1e-10",
        "1.5", "100.0", "1e0", "1234567890", "0.0001", "-0.0001",
        "1E+5", "1e-5", "1.7976931348623157e308", "5e-324",
        "2.2250738585072014e-308", "-1.5e300",
    ])

def _rich_leaf():
    return st.one_of(
        _print_string(),
        _rich_number(),
        st.sampled_from(["true", "false", "null"]),
    )

_rich_value = st.recursive(
    _rich_leaf(),
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=8).map(
            lambda vs: "[" + ",".join(vs) + "]"),
        st.lists(
            st.tuples(_rich_key(), children).map(lambda t: t[0] + ":" + t[1]),
            min_size=0, max_size=8,
        ).map(lambda ps: "{" + ",".join(ps) + "}"),
    ),
    max_leaves=40,
)

def _driver_doc():
    # a single valid document, plus optional trailing whitespace
    return st.tuples(_rich_value, st.sampled_from(["", "", "\n", " "])).map(
        lambda t: t[0] + t[1]
    )

def _driver_compare():
    # two documents separated by newline: same, near-equal, or different
    mode = st.sampled_from(["same", "diff", "shallow_same"])
    def build(t):
        m, a, b = t
        if m == "same":
            return a + "\n" + a
        if m == "shallow_same":
            # same keys/types but differing leaf where possible
            return a + "\n" + a
        return a + "\n" + b
    return st.tuples(mode, _rich_value, _rich_value).map(build)

# ---------- improved strategy ----------
# The previous run showed cJSON_Compare and the print_* functions at 0%.
# These are only reached if the driver actually parses and then invokes
# print/compare. Emit *valid* documents that are guaranteed to parse,
# plus explicit compare pairs, and reduce the noise (malformed / deep)
# that never reaches those code paths.

def _valid_doc():
    # always-valid document with optional surrounding whitespace
    return st.tuples(
        st.sampled_from(["", "", " ", "\n", "\t"]),
        _rich_value,
        st.sampled_from(["", "", " ", "\n"]),
    ).map(lambda t: t[0] + t[1] + t[2])

def _valid_compare_pair():
    # always-valid pair, newline-separated
    return st.tuples(_rich_value, _rich_value).map(lambda t: t[0] + "\n" + t[1])

def _valid_compare_same():
    return _rich_value.map(lambda v: v + "\n" + v)

strategy = st.one_of(
    # heavily weight valid print/compare drivers so the uncovered
    # print_* and cJSON_Compare branches are actually exercised
    _valid_doc(),
    _valid_doc(),
    _valid_doc(),
    _valid_doc(),
    _valid_compare_same(),
    _valid_compare_same(),
    _valid_compare_pair(),
    _valid_compare_pair(),
    _driver_doc(),
    _driver_compare(),
    # parser robustness inputs (lower weight)
    _top(),
    _print_input(),
    _compare_pair(),
    _compare_same(),
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
)