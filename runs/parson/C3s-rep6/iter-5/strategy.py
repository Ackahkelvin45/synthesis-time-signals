from hypothesis import strategies as st
import json

# ---------- primitives ----------

_json_ws = st.sampled_from(["", " ", "\t", "\n", "\r", "  ", "\n\t"])

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escapes = st.builds(
    lambda a, b, c, d: "\\u" + a + b + c + d,
    _hex, _hex, _hex, _hex,
)

# surrogate pairs and lone surrogates
_surrogate_escapes = st.sampled_from([
    "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
    "\\uD800\\uDC00",  # valid pair
    "\\uD83D\\uDE00",  # valid pair
    "\\u0000",         # NUL escape (six chars, fine)
    "\\u001f", "\\u007f", "\\uFFFD",
])

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) > 0x1F)

_string_body = st.one_of(
    st.text(_safe_chars, max_size=8),
    st.lists(
        st.one_of(
            st.text(_safe_chars, max_size=4),
            _simple_escapes,
            _unicode_escapes,
            _surrogate_escapes,
        ),
        max_size=6,
    ).map("".join),
)

# occasionally malformed string (unterminated, stray backslash, etc.)
_malformed_string = st.sampled_from([
    '"', '"abc', '"abc\\', '"\\u12', '"\\uZZZZ"', '"\\x"',
    '"\\uD800"', '"a\nb"', '"\\', '""extra',
])

json_string = st.one_of(
    _string_body.map(lambda s: '"' + s + '"'),
    _malformed_string,
)


# ---------- numbers ----------

_digits = st.text("0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.builds(lambda d: d, st.text("123456789", min_size=1, max_size=1).flatmap(
        lambda first: st.tuples(st.just(first), _digits).map(lambda t: t[0] + t[1])
    )),
)

_frac = st.builds(lambda d: "." + d, _digits)

_exp = st.builds(
    lambda e, s, d: e + s + d,
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    _digits,
)

_normal_number = st.builds(
    lambda sign, ip, fr, ex: sign + ip + fr + ex,
    st.sampled_from(["", "-"]),
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
)

_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e-309", "1e999999", "-1e999999",
    "0e0", "1E+308", "1e-308", "9" * 30, "-" + "9" * 30,
    "1e" + "9" * 20, "0." + "0" * 20 + "1",
    "1e2147483648", "-1e2147483647",
])

_malformed_number = st.sampled_from([
    "+1", ".5", "1.", "01", "00", "-", "-.", "1..2",
    "1e", "1e+", "--1", "1.e5", "0x1", "1_000",
])

json_number = st.one_of(_normal_number, _extreme_number, _malformed_number)


# ---------- recursive structures ----------

_json_simple_value = st.one_of(
    json_string,
    json_number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_key = st.one_of(
    _string_body.map(lambda s: '"' + s + '"'),
    st.sampled_from(['"a"', '"b"', '"key"', '"k"', '"dup"', '""']),
)


def _pair(value_strategy):
    return st.builds(
        lambda k, v: k + ":" + v,
        _key,
        value_strategy,
    )


# malformed object pieces
_bad_obj = st.sampled_from([
    "{}", "{,}", '{"a":}', '{"a" 1}', '{"a":1,}', '{"a":1,,}',
    '{a:1}', '{"a":1', '{"a":1}}', '{:1}', '{"a":1 "b":2}',
    '{"a":1,"a":2}',  # duplicate keys
    '{"a":1, "a":2, "a":3}',
])

_bad_arr = st.sampled_from([
    "[]", "[,]", "[1,]", "[1,,2]", "[1 2]", "[1", "[1]]", "[,1]",
])


def _make_json(depth):
    # depth controls how much recursion budget remains
    value = st.deferred(lambda: _value_strategy(depth))
    pair = _pair(value)
    obj = st.one_of(
        st.just("{}"),
        st.builds(
            lambda parts: "{" + ",".join(parts) + "}",
            st.lists(pair, min_size=1, max_size=4),
        ),
        _bad_obj,
    )
    arr = st.one_of(
        st.just("[]"),
        st.builds(
            lambda parts: "[" + ",".join(parts) + "]",
            st.lists(value, min_size=1, max_size=4),
        ),
        _bad_arr,
    )
    return st.one_of(_json_simple_value, obj, arr)


def _value_strategy(depth):
    if depth <= 0:
        return _json_simple_value
    return st.one_of(
        _json_simple_value,
        _make_json(depth - 1),
    )


# depth-limited recursive value (concentrate near 2048 but bounded for safety)
_deep_value = st.recursive(
    _json_simple_value,
    lambda children: st.one_of(
        st.builds(
            lambda parts: "[" + ",".join(parts) + "]",
            st.lists(children, min_size=1, max_size=3),
        ),
        st.builds(
            lambda parts: "{" + ",".join(parts) + "}",
            st.lists(
                st.builds(lambda k, v: k + ":" + v, _key, children),
                min_size=1,
                max_size=3,
            ),
        ),
    ),
    max_leaves=50,
)


# ---------- explicit deep nesting generators ----------

@st.composite
def _deep_nesting(draw):
    # target depth near 2048 cap (rejected beyond, accepted below)
    depth = draw(st.one_of(
        st.integers(min_value=0, max_value=16),
        st.integers(min_value=2040, max_value=2060),
        st.integers(min_value=1000, max_value=2050),
    ))
    open_c = draw(st.sampled_from(["[", "{"]))
    if open_c == "[":
        close_c = "]"
        inner = draw(st.one_of(st.just("0"), st.just('"x"'), st.just("null")))
    else:
        close_c = "}"
        inner = draw(st.one_of(
            st.just('"k":0'),
            st.just('"k":{"k":1}'),
            st.just('"a":1,"b":2'),
        ))
    return open_c * depth + inner + close_c * depth


# ---------- malformed / near-valid ----------

_malformed = st.sampled_from([
    "", " ", "\t", "\n",
    "{", "}", "[", "]", ",", ":", '"',
    "tru", "fals", "nul", "TRUE", "Null",
    '"unterminated', "'single'", "\\",
    "1abc", "1 garbage", "[]xyz", "{}trailing", "nullnull",
    "[]", "{}", "0", "-", "-.",
    '{"a":1,"a":1}', '{"x":[1,2,3],"x":[]}',
    "[1,2,3,]", '{"a":1,}',
    '\u0000',  # raw NUL - will be skipped by harness, but harmless here
])

# strip raw NUL from final outputs
def _no_raw_nul(s):
    return s.replace("\x00", "")


# ---------- combine ----------

_base_value = st.one_of(
    json_string,
    json_number,
    st.just("true"),
    st.just("false"),
    st.just("null"),
)

_recursive_value = st.recursive(
    _base_value,
    lambda children: st.one_of(
        st.builds(
            lambda parts: "[" + ",".join(parts) + "]",
            st.lists(children, min_size=1, max_size=4),
        ),
        st.builds(
            lambda parts: "{" + ",".join(parts) + "}",
            st.lists(
                st.builds(lambda k, v: k + ":" + v, _key, children),
                min_size=1, max_size=4,
            ),
        ),
    ),
    max_leaves=30,
)

# ---------- whitespace-padded / interleaved-token variants ----------
# The parser almost certainly has dedicated skip-whitespace branches that
# only execute when whitespace appears between tokens.  The original
# strategy only ever emits whitespace-free compact JSON (plus a few
# trailing-garbage cases), so those branches were never taken.

@st.composite
def _ws_padded(draw):
    ws = draw(_json_ws)
    ws2 = draw(_json_ws)
    ws3 = draw(_json_ws)
    ws4 = draw(_json_ws)

    kind = draw(st.sampled_from([
        "arr", "obj", "nested", "scalar", "mixed",
    ]))

    if kind == "arr":
        items = draw(st.lists(
            st.one_of(json_string, json_number,
                      st.just("true"), st.just("false"), st.just("null")),
            min_size=1, max_size=4,
        ))
        inner = (ws2 + "," + ws3).join(items)
        return "[" + ws + inner + ws4 + "]"

    if kind == "obj":
        pairs = draw(st.lists(
            st.builds(lambda k, v: k + ":" + v, _key,
                      st.one_of(json_string, json_number,
                                st.just("true"), st.just("false"), st.just("null"))),
            min_size=1, max_size=4,
        ))
        inner = (ws2 + "," + ws3).join(pairs)
        return "{" + ws + inner + ws4 + "}"

    if kind == "nested":
        return ("[" + ws + "{" + ws2 + '"k"' + ws3 + ":" + ws4 + "[" +
                ws + "1" + ws2 + "]" + ws3 + "}" + ws4 + "]")

    if kind == "scalar":
        return ws + draw(st.one_of(
            json_string, json_number,
            st.just("true"), st.just("false"), st.just("null"),
        )) + ws2

    # mixed: colon/comma surrounded by whitespace inside malformed shapes
    return draw(st.sampled_from([
        "{ " + ws + '"a"' + ws2 + ":" + ws3 + "1" + ws4 + " }",
        "[ " + ws + "1" + ws2 + "," + ws3 + "2" + ws4 + " ]",
        "{" + ws + '"a"' + ws2 + ":" + ws3 + "[" + ws4 + "1" + ws + "]" + ws2 + "}",
        "[" + ws + "]" + ws2,
        "{" + ws + "}" + ws2,
        "[" + ws + "1" + ws2 + "]" + ws3 + "garbage",
    ]))


# ---------- whitespace-between-every-token variants ----------
# Force the parser's skip-whitespace loop to run everywhere: before/after
# every structural token, between key and colon, colon and value, and
# before/after every comma.  The original only padded at the outer edges.

@st.composite
def _ws_everywhere(draw):
    ws = _json_ws

    def wrap(tok):
        return draw(ws) + tok + draw(ws)

    kind = draw(st.sampled_from(["arr", "obj", "deep", "colon", "comma"]))

    if kind == "arr":
        n = draw(st.integers(min_value=1, max_value=4))
        items = [
            draw(st.one_of(json_string, json_number,
                           st.just("true"), st.just("false"), st.just("null")))
            for _ in range(n)
        ]
        body = draw(ws).join(
            [draw(ws) + "," + draw(ws) for _ in range(n - 1)]
        ) if n > 1 else ""
        # rebuild with comma separators wrapped in whitespace
        parts = []
        for i, it in enumerate(items):
            parts.append(draw(ws) + it + draw(ws))
            if i < n - 1:
                parts.append(",")
        return "[" + "".join(parts) + "]"

    if kind == "obj":
        n = draw(st.integers(min_value=1, max_value=3))
        parts = []
        for i in range(n):
            k = draw(_key)
            v = draw(st.one_of(json_string, json_number,
                               st.just("true"), st.just("false"), st.just("null")))
            parts.append(draw(ws) + k + draw(ws) + ":" + draw(ws) + v + draw(ws))
            if i < n - 1:
                parts.append(",")
        return "{" + "".join(parts) + "}"

    if kind == "deep":
        return (draw(ws) + "[" + draw(ws) + "{" + draw(ws) + '"k"' + draw(ws) +
                ":" + draw(ws) + "[" + draw(ws) + "1" + draw(ws) + "]" +
                draw(ws) + "}" + draw(ws) + "]" + draw(ws))

    if kind == "colon":
        return "{" + draw(ws) + '"a"' + draw(ws) + ":" + draw(ws) + "1" + draw(ws) + "}"

    # comma: lots of whitespace around commas and trailing/leading
    return "[" + draw(ws) + "1" + draw(ws) + "," + draw(ws) + "2" + draw(ws) + "," + draw(ws) + "3" + draw(ws) + "]"


# ---------- token-boundary / truncation / control-char variants ----------
# Target parser branches that only fire on specific byte classes and on
# inputs truncated at every possible prefix length.  These reach the
# lexer's error and boundary handling branches that compact valid JSON
# never exercises.

# Every possible prefix of a handful of representative valid documents.
# Truncation mid-token forces distinct lexer error branches (unterminated
# string, incomplete number exponent, incomplete literal, EOF-in-object).
@st.composite
def _truncations(draw):
    doc = draw(st.sampled_from([
        '{"key": [1, 2.5e-3, true, false, null], "nested": {"a": "\\u0041"}}',
        '[true, false, null, 0, -0, 1e10, "\\n\\t\\\\"]',
        '{"a":1,"b":[{"c":[]},{"d":{}}],"e":"x"}',
        '[1,2,3,4,5,6,7,8,9,10]',
        '{"long":"' + "a" * 40 + '"}',
        'true',
        'false',
        'null',
        '12345.6789e+12',
        '"\\uD83D\\uDE00"',
    ]))
    cut = draw(st.integers(min_value=0, max_value=len(doc)))
    return doc[:cut]


# Raw control characters (0x00-0x1F) placed inside strings, between
# tokens, and as leading/trailing bytes.  A conforming parser must reject
# them; the rejection paths are separate branches.
_control_chars = "".join(chr(c) for c in range(0x20))

@st.composite
def _control_char_cases(draw):
    ctrl = draw(st.sampled_from(list(_control_chars)))
    kind = draw(st.sampled_from([
        "in_string", "between_tokens", "leading", "trailing",
        "in_number", "in_literal", "in_key",
    ]))
    if kind == "in_string":
        return '"ab' + ctrl + 'cd"'
    if kind == "between_tokens":
        return '{"a":1' + ctrl + ',"b":2}'
    if kind == "leading":
        return ctrl + '{"a":1}'
    if kind == "trailing":
        return '[1,2,3]' + ctrl
    if kind == "in_number":
        return '1' + ctrl + '2'
    if kind == "in_literal":
        return 'tr' + ctrl + 'ue'
    return '{"a' + ctrl + 'b":1}'


# Byte-level boundary cases: high-bit bytes, invalid UTF-8 lead bytes,
# overlong encodings, BOM, and lone continuation bytes.  These exercise
# the decoder / character-classification branches.
_raw_byte_cases = st.sampled_from([
    '\ufffd',           # replacement char
    '\ufeff',           # BOM
    '\x7f',             # DEL
    '\u0080', '\u009f', # C1 controls
    '\u2028', '\u2029', # line/paragraph separators
    '\u00a0',           # NBSP
    '\u200b',           # zero-width space
    '\ud800',           # lone high surrogate
    '\udfff',           # lone low surrogate
    '\uffff', '\ufffe',
    '"\u0080"', '"\u2028"', '"\ufeff"',
    '\u0080{"a":1}',
    '{"a":1}\u2028',
    '"\\uD800"',        # already covered but cheap
    '"\\uD800x"',
    '"\\uDC00\\uD800"', # reversed surrogate pair
    '"\\ud800\\udc00"', # lowercase valid pair
])


# Structural edge cases around the exact token boundaries the parser
# checks: empty containers with whitespace, deeply mixed, and the
# maximum/minimum numeric forms.
_structural_edges = st.sampled_from([
    '[ ]', '{ }', '[  ]', '{  }',
    '[\n]', '{\n}', '[\t]', '{\t}',
    '{"":""}', '{"":0}', '{"a":""}',
    '[[[[[[[[[[0]]]]]]]]]]',
    '{"a":{"b":{"c":{"d":{"e":0}}}}}',
    '[{},[],{},[]]',
    '{"a":[],"b":{},"c":[{}],"d":{"e":[]}}',
    '-0', '-0.0', '-0e0', '0.0', '0e-0', '0E+0',
    '1e0', '1E0', '1e+0', '1e-0',
    '0.1', '0.01', '0.001',
    '9007199254740993',   # 2^53+1
    '18446744073709551616',  # 2^64
    '-9223372036854775808',  # INT64_MIN
    '9223372036854775807',   # INT64_MAX
    '1.7976931348623157e308', # DBL_MAX
    '5e-324',                # DBL_MIN subnormal
    '"\\/\\"\\\\\\b\\f\\n\\r\\t"',
    '"' + '\\u0041' * 8 + '"',
    '"' + 'a' * 100 + '"',
    '[' + '1,' * 50 + '1]',
    '{' + ','.join('"k%d":%d' % (i, i) for i in range(20)) + '}',
])


# ---------- NEW: deep-nesting at every depth boundary ----------
# The parser's recursion-depth guard (if any) has a distinct accept/reject
# branch at each boundary.  The original only probed a few depths; sweep
# a wide, dense range of depths and both bracket kinds so the guard's
# comparison branches are all taken.  Also probe mixed open/close nesting
# and unbalanced deep prefixes to reach error-recovery branches.
@st.composite
def _deep_depth_sweep(draw):
    depth = draw(st.one_of(
        st.integers(min_value=0, max_value=8),
        st.integers(min_value=9, max_value=64),
        st.integers(min_value=65, max_value=256),
        st.integers(min_value=257, max_value=1024),
        st.integers(min_value=1025, max_value=2100),
    ))
    open_c = draw(st.sampled_from(["[", "{"]))
    close_c = "]" if open_c == "[" else "}"
    inner = draw(st.sampled_from([
        "0", '"x"', "null", "true", "false",
        '""', '{"k":0}', "[0]",
    ]))
    form = draw(st.sampled_from([
        "balanced", "unclosed", "extra_close", "mixed",
    ]))
    if form == "balanced":
        return open_c * depth + inner + close_c * depth
    if form == "unclosed":
        return open_c * depth + inner
    if form == "extra_close":
        return open_c * depth + inner + close_c * (depth + 1)
    # mixed: alternate bracket kinds at each level
    opens = "".join("[" if (i % 2 == 0) else "{" for i in range(depth))
    closes = "".join("]" if (i % 2 == 0) else "}" for i in reversed(range(depth)))
    return opens + inner + closes


# ---------- NEW: exhaustive short-token boundary cases ----------
# Single-byte and two-byte inputs hit the lexer's initial dispatch and
# lookahead branches that longer inputs skip past.  Enumerate all ASCII
# printable single chars, all whitespace-containing 2-char combos, and
# all partial literal/number prefixes so every first-token branch fires.
@st.composite
def _short_token_boundaries(draw):
    kind = draw(st.sampled_from([
        "single", "two", "literal_prefix", "number_prefix",
        "string_prefix", "bracket_pair", "colon_comma",
    ]))
    if kind == "single":
        return draw(st.sampled_from([chr(c) for c in range(0x20, 0x7f)]))
    if kind == "two":
        a = draw(st.sampled_from(list("{}[],:\"0123456789tfn-+.eE \t\n\r")))
        b = draw(st.sampled_from(list("{}[],:\"0123456789tfn-+.eE \t\n\r")))
        return a + b
    if kind == "literal_prefix":
        return draw(st.sampled_from([
            "t", "tr", "tru", "true", "truex", "true1",
            "f", "fa", "fal", "fals", "false", "falsex",
            "n", "nu", "nul", "null", "nullx", "nullnull",
        ]))
    if kind == "number_prefix":
        return draw(st.sampled_from([
            "0", "00", "01", "-", "-0", "-00", "-01",
            "1", "1.", "1.0", "1e", "1e+", "1e-", "1e0",
            "1E", "1E+", "1E-", ".", ".0", ".e", "+", "+0",
            "1e999999999999999999999", "0e", "0E", "0e+", "0e-",
        ]))
    if kind == "string_prefix":
        return draw(st.sampled_from([
            '"', '"a', '"ab', '"a\\', '"a\\"', '"a\\u', '"a\\u0',
            '"a\\u00', '"a\\u004', '"a\\u0041', '"a\\u0041"',
            '"\\', '"\\u', '"\\uD', '"\\uD8', '"\\uD80', '"\\uD800',
            '"\\uD800\\', '"\\uD800\\u', '"\\uD800\\uD', '"\\uD800\\uDC00"',
        ]))
    if kind == "bracket_pair":
        return draw(st.sampled_from([
            "[]", "[[]", "[]]", "[,]", "[:]", "[{}]", "[[]]",
            "{}", "{{}", "{}}", "{,}", "{:}", "{[]}", "{{}}",
        ]))
    return draw(st.sampled_from([
        ":", ",", ":,", ",:", "::", ",,",
        "[,]", "{,}", "[:1]", "{:1}", "{1:}", "[1:]",
    ]))


# ---------- NEW: string escape / unicode boundary sweep ----------
# The string lexer has a branch per escape class and per hex-digit
# validation step.  Systematically enumerate every valid escape and every
# truncated/invalid escape so all validation branches are entered.
@st.composite
def _escape_sweep(draw):
    kind = draw(st.sampled_from([
        "all_simple", "all_hex", "truncated_hex", "invalid_hex",
        "surrogate_forms", "mixed",
    ]))
    if kind == "all_simple":
        e = draw(st.sampled_from(
            ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
        ))
        return '"' + e + '"'
    if kind == "all_hex":
        d = draw(st.sampled_from(
            list("0123456789abcdefABCDEF")
        ))
        return '"\\u' + d + d + d + d + '"'
    if kind == "truncated_hex":
        return draw(st.sampled_from([
            '"\\u', '"\\u0', '"\\u00', '"\\u000',
            '"\\u0"', '"\\u00"', '"\\u000"',
        ]))
    if kind == "invalid_hex":
        return draw(st.sampled_from([
            '"\\uZZZZ"', '"\\u12G4"', '"\\u-123"', '"\\u 123"',
            '"\\u12 4"', '"\\u+123"', '"\\u0x12"',
        ]))
    if kind == "surrogate_forms":
        return draw(st.sampled_from([
            '"\\uD800"', '"\\uDBFF"', '"\\uDC00"', '"\\uDFFF"',
            '"\\uD800\\uDC00"', '"\\uD83D\\uDE00"',
            '"\\uDC00\\uD800"', '"\\uD800\\uD800"',
            '"\\uD800x"', '"\\uD800\\u0041"',
            '"\\ud800"', '"\\ud800\\udc00"',
        ]))
    # mixed: valid escape embedded among plain chars and other escapes
    parts = draw(st.lists(
        st.one_of(
            st.text(_safe_chars, max_size=3),
            st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
            _unicode_escapes,
        ),
        min_size=1, max_size=5,
    ))
    return '"' + "".join(parts) + '"'


# ---------- NEW: whitespace-class sweep ----------
# Enumerate every single whitespace byte and every (ws, token) combination
# so the parser's whitespace-skipping switch/loop has each branch taken.
@st.composite
def _ws_class_sweep(draw):
    ws_bytes = ["", " ", "\t", "\n", "\r", "\f", "\v",
                "  ", "\t\t", "\n\n", "\r\r", "\r\n", "\n\r",
                " \t\n\r", "\t \n\r"]
    ws = draw(st.sampled_from(ws_bytes))
    ws2 = draw(st.sampled_from(ws_bytes))
    kind = draw(st.sampled_from(["lead", "trail", "both", "inter"]))
    doc = draw(st.sampled_from([
        "0", "true", "false", "null", '"x"', "[]", "{}",
        "[1]", "[1,2]", '{"a":1}', '{"a":1,"b":2}',
    ]))
    if kind == "lead":
        return ws + doc
    if kind == "trail":
        return doc + ws
    if kind == "both":
        return ws + doc + ws2
    # inter: inject ws after every structural char
    out = []
    for ch in doc:
        out.append(ch)
        if ch in "{}[],:":
            out.append(ws)
    return "".join(out)


# ---------- combine ----------

_full = st.one_of(
    _recursive_value,
    _deep_value,
    _deep_nesting(),
    _deep_depth_sweep(),
    _short_token_boundaries(),
    _escape_sweep(),
    _ws_class_sweep(),
    _malformed,
    _ws_padded(),
    _ws_everywhere(),
    _truncations(),
    _control_char_cases(),
    _raw_byte_cases,
    _structural_edges,
    st.builds(
        lambda v, tail: v + tail,
        _recursive_value,
        st.sampled_from(["", " ", "garbage", "xyz", "\n", "[]extra"]),
    ),
)

strategy = _full.map(_no_raw_nul)