from hypothesis import strategies as st
import json

# ---------- leaf strategies ----------

# Strings that exercise escapes, unicode, control chars (no raw NUL), etc.
_escapes = st.sampled_from([
    '\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
    '\\u0000', '\\u001F', '\\u007F', '\\u00e9', '\\u20ac',
    '\\uD800', '\\uDC00', '\\uD83D\\uDE00', '\\uFFFF', '\\uABCD',
    '\\u0000\\u0000', '\\uD834\\uDD1E',
])

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\\',
).filter(lambda c: ord(c) > 0x1F or c in "\t\n\r")

# A "string body" piece: either a safe char or an escape sequence
_str_piece = st.one_of(_safe_chars, _escapes)

_string_body = st.lists(_str_piece, min_size=0, max_size=12).map("".join)

_json_string = _string_body.map(lambda s: '"' + s + '"')


# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=400).map(str),
    ).map("".join),
    # extreme exponents including overflow
    st.sampled_from(["e309", "E309", "e-309", "e999", "e-999",
                     "e+308", "e-308", "e1000", "e-1000"]),
)

_number = st.tuples(_int_part, _frac, _exp).map("".join)

# malformed-ish numbers (leading +, .5, 1., 01, lone -)
_bad_number = st.sampled_from([
    "+1", "+0", "+1.5", ".5", "-.5", "1.", "01", "007", "-", "-.",
    "1e", "1e+", "1E-", "--1", "1..2", "0x1", "1_000", "Infinity", "NaN",
])


# ---------- recursive values ----------

_leaf = st.one_of(
    _json_string,
    _number,
    st.sampled_from(["true", "false", "null"]),
)

# depth near the parser cap (2048). Concentrate interesting depth near limit.
_deep_depth = st.one_of(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=2000, max_value=2048),
    st.integers(min_value=2049, max_value=2100),
)


def _wrap(value_strategy, depth):
    """Wrap a value in `depth` nested arrays (or objects)."""
    def build(s):
        return "[" * depth + s + "]" * depth
    return st.tuples(value_strategy, st.just(depth)).map(lambda t: build(t[0]))


# We'll use st.recursive for obj/arr productions.
def _obj_like(children):
    # children: strategy producing value strings
    pair = st.tuples(_json_string, children).map(lambda t: t[0] + ":" + t[1])
    pairs = st.lists(pair, min_size=0, max_size=5).map(lambda ps: ",".join(ps))
    return pairs.map(lambda body: "{" + body + "}")


def _arr_like(children):
    elems = st.lists(children, min_size=0, max_size=5).map(lambda es: ",".join(es))
    return elems.map(lambda body: "[" + body + "]")


def _make_value():
    return st.recursive(
        _leaf,
        lambda children: st.one_of(_obj_like(children), _arr_like(children)),
        max_leaves=40,
    )


_value = _make_value()


# Deep-but-legal nesting near the cap, wrapping a simple value.
_deep = st.builds(
    lambda d, inner: "[" * d + inner + "]" * d,
    _deep_depth,
    st.one_of(_leaf, st.just("{}"), st.just("[]")),
)

_deep_obj = st.builds(
    lambda d, inner: '{"k":' * d + inner + "}" * d,
    _deep_depth,
    st.one_of(_leaf, st.just("null")),
)


# ---------- malformed near-valid inputs ----------

_malformed = st.sampled_from([
    # double commas / trailing commas
    "[1,,2]", "[1,2,]", "[,]", "{,}", '{"a":1,,"b":2}', '{"a":1,}',
    # missing colons
    '{"a" 1}', '{"a" 1, "b":2}', '{"a"}', '{"a":}',
    # unterminated strings
    '"abc', '{"a":"b', '["x', '"\\', '"\\u12',
    # unterminated containers
    '[', '{', '[1,2', '{"a":1',
    # stray tokens
    ']', '}', ':', ',', '[,]', '{:}',
    # leading + / .5 / 01 style numbers in context
    '[+1]', '[.5]', '[1.]', '[01]', '[-]', '[-.]', '[+0]',
    # trailing content (accepted by target)
    '1abc', '1 garbage', '[]xyz', '{}extra', 'nullnull', 'truefalse',
    '1 2 3', '"a""b"', '[1] [2]',
    # duplicate keys (target rejects)
    '{"k":0,"k":1}', '{"a":1,"a":2,"b":3}', '{"x":{"y":1},"x":2}',
    # non-finite (target rejects)
    '1e309', '-1e309', '1e9999', '[1e309]', '{"a":1e309}',
    # control chars in strings (escaped)
    '"\\u0000"', '"a\\u0000b"', '"\\u001F"',
    # surrogate escapes
    '"\\uD800"', '"\\uDC00"', '"\\uD83D\\uDE00"', '"\\uD834\\uDD1E"',
    # whitespace variants
    '  {  "a"  :  1  }  ', '\t[\n1,\r2]\n', ' { } ', ' [ ] ',
    # empty
    '{}', '[]', '', ' ', '\n',
    # keys that are not strings (exercises key-parsing branches)
    '{1:2}', '{true:1}', '{null:0}', '{[]:1}', '{{}:1}', '{:1}',
    # unexpected value tokens in arrays/objects (exercises value dispatch)
    '[true,]', '{,}', '[:]', '[null null]', '{"a"::1}', '{"a":,}',
    # bare tokens / partial keywords (keyword-matching branches)
    't', 'tr', 'tru', 'truex', 'f', 'fa', 'fals', 'falsey',
    'n', 'nu', 'nul', 'nullx', 'TRUE', 'False', 'NULL',
    # unterminated escapes/keywords at EOF
    '"\\u', '"\\uD8', '"\\uD800', 'tru', 'fals', 'nul',
    # numbers with partial exponent/frac at EOF
    '1e', '1e+', '1e-', '1.', '-', '-0.', '0e', '0e+',
    # nested malformed
    '[[1,],2]', '{"a":{"b":}}', '[{"a":1},]', '{"a":[1,2,]}',
    # extra closing brackets
    ']', ']]', '}', '}}', '[1]]', '{"a":1}}',
    # deep-ish malformed
    '[[[[', '{"a":{"a":', '[1,[2,[3,',
    # whitespace/control characters between tokens (lexer whitespace branches)
    '[\x0b1]', '[\x0c1]', '{\x0b"a":1}', '{\x0c"a":1}',
    '[1\x0b,2]', '[1\x0c,2]', '{"a"\x0b:1}', '{"a"\x0c:1}',
    '{"a":\x0b1}', '{"a":\x0c1}', '[ \x0b\t\r\n1 ]',
    # bare control chars outside strings (invalid-token branches)
    '\x01', '\x1f', '[\x01]', '{\x01}', '\x7f', '[\x7f]',
    # raw (unescaped) control char inside a string
    '"\x01"', '"\x1f"', '"\x7f"', '["\x01"]', '{"a":"\x1f"}',
    # raw newline/tab inside string (unescaped-control branch)
    '"\n"', '"\t"', '"\r"', '["\n"]', '{"a":"\t"}',
    # invalid escape sequences (escape-dispatch fallthrough)
    '"\\x"', '"\\q"', '"\\\'"', '"\\ "', '"\\a"', '"\\z"',
    '"\\uZZZZ"', '"\\u12G4"', '"\\u"', '"\\u1"', '"\\u12"', '"\\u123"',
    '"\\uD800\\u0041"', '"\\uDC00x"', '"\\uD800\\uD800"',
    # lone high/low surrogates in escape pairs (surrogate-pair branches)
    '"\\uDBFF\\uDFFF"', '"\\uD800\\uDBFF"', '"\\uDC00\\uDFFF"',
    '"\\uD800\\n"', '"\\uD800a"',
    # numbers: leading zeros with fraction/exponent (strict-number branches)
    '[00]', '[01.5]', '[0e1]', '[-00]', '[00.0]', '[00e0]',
    '[1e]', '[1e+]', '[1e-]', '[1.]', '[.]', '[+.]', '[+.5]',
    '[1e1e1]', '[1.2.3]', '[1e+1.5]',
    # numbers in object values (number-value dispatch)
    '{"a":01}', '{"a":.5}', '{"a":+1}', '{"a":1.}',
    # keyword boundary at EOF inside containers
    '[tru', '[fals', '[nul', '{"a":tru', '{"a":fals', '{"a":nul',
    '[true', '[false', '[null', '{"a":true', '{"a":false', '{"a":null',
    # keyword followed by non-delimiter (keyword-termination branches)
    '[truex]', '[falsey]', '[nullz]', '{"a":truex}', '{"a":nullz}',
    # unterminated object key / string at various points
    '{"', '{"a', '{"a"', '{"a":', '{"a":1', '[1', '[[', '{"a":{"b"',
    # stray colon/comma at top level (top-level dispatch)
    ':', ',', '::', ',,', ':1', ',1',
    # BOM and other non-token leading bytes
    '\ufeff{}', '\ufeff1', '\ufeff[]', '\u00a0{}',
    # very long unterminated string / number at EOF
    '"' + 'a' * 100, '1' + '0' * 100, '1e' + '1' * 100,
    # mixed nesting with malformed inner
    '[{"a":[1,2,3,]}', '{"a":[{"b":},]}', '[[[{"a":1}]]]',
    # deeply nested with a single malformed char at the middle
    '[' * 100 + ']' * 99, '{"a":' * 100 + 'null' + '}' * 99,
    # trailing whitespace after complete values
    '{} ', '[]\n', 'true\t', 'null\r', '1 ', '"a"\n',
    # leading whitespace before values
    ' {}', '\n[]', '\ttrue', '\rnull', ' 1', '\n"a"',
    # multiple top-level values with whitespace
    '1\n2', 'true false', 'null\nnull', '{} []', '"a" "b"',
    # object with whitespace around colon/comma
    '{ "a" : 1 , "b" : 2 }', '{  }', '[  ]', '[ 1 , 2 ]',
    # ---- additional branches: multi-byte UTF-8 boundaries / invalid sequences
    '\xc3\xa9', '\xe2\x82\xac', '\xf0\x9f\x98\x80', '\x80', '\xbf',
    '\xc0\x80', '\xc1\xbf', '\xe0\x80\x80', '\xed\xa0\x80', '\xed\xbf\xbf',
    '\xf4\x90\x80\x80', '\xf5\x80\x80\x80', '\xfe', '\xff',
    '"\xc3\xa9"', '["\xe2\x82\xac"]', '{"\xf0\x9f\x98\x80":1}',
    '\xef\xbb\xbf{}', '\xef\xbb\xbf[]', '\xef\xbb\xbf1',
    # ---- additional branches: escape of every hex-digit position
    '"\\u0000"', '"\\u0001"', '"\\u000a"', '"\\u000d"', '"\\u0020"',
    '"\\u007e"', '"\\u0080"', '"\\u07ff"', '"\\u0800"', '"\\ud7ff"',
    '"\\ue000"', '"\\ufffd"', '"\\uffff"',
    '"\\ud800\\udc00"', '"\\udbff\\udfff"', '"\\ud800\\udfff"',
    '"\\udc00\\ud800"', '"\\ud800\\ud800"', '"\\udfff\\udfff"',
    # ---- additional branches: number state machine edges
    '[0]', '[-0]', '[0.0]', '[0.0e0]', '[0.0E0]', '[0.0e+0]', '[0.0e-0]',
    '[1e0]', '[1E0]', '[1e+0]', '[1e-0]', '[1.0e0]', '[1.0E+0]',
    '[9007199254740993]', '[18446744073709551616]',
    '[123456789012345678901234567890]',
    '[1e18446744073709551616]', '[1e-18446744073709551616]',
    '[0.000000000000000000001]',
    # ---- additional branches: literal whitespace set (space/tab/nl/cr)
    ' \t\r\n1 \t\r\n', '[\r\n]', '{\r\n}', '[\t]', '{ \t }',
    '{"a"\r\n:\r\n1}', '[1\r\n,\r\n2]',
    # ---- additional branches: object key must-be-string variants
    '{ "a" : 1 }', '{"" : 1}', '{"\\u0041":1}', '{"\\n":1}',
    # ---- additional branches: max-depth-adjacent exact boundaries
    '[' * 2047 + ']' * 2047, '[' * 2048 + ']' * 2048,
    '[' * 2049 + ']' * 2049, '[' * 2050 + ']' * 2050,
    '[' * 2048, '[' * 2049, '[' * 2050,
    ']' * 2048, ']' * 2049, ']' * 2050,
    # ---- additional branches: value dispatch after whitespace/colon
    '{"a":\t1}', '{"a":\n1}', '{"a":\r1}', '{"a": 1}',
    '[ \t1]', '[\n1]', '[\r1]',
    # ---- additional branches: top-level non-value token dispatch
    'x', 'X', '@', '#', '$', '%', '^', '&', '*', '(', ')',
    ';', '<', '=', '>', '?', '\\', '`', '~', '|',
    # ---- additional branches: string content high planes / noncharacters
    '"\ufffe"', '"\uffff"', '"\ufdd0"', '"\U0001fffe"', '"\U0010ffff"',
    # ---- additional branches: exponent overflow/underflow at exact limits
    '1e308', '1e-308', '1e309', '1e-309', '1e2147483647', '1e-2147483648',
    '[1e308]', '[1e-308]', '[1e309]', '[1e-309]',
    # ---- additional branches: multiple levels of nesting with whitespace
    '[ [ 1 ] ]', '{ "a" : { "b" : 1 } }', '[[[]]]', '{"a":{}}',
    '[ [ [ [ [ 1 ] ] ] ] ]',
    # ---- NEW: deep-nesting boundary variants exercising depth-increment/decrement
    #      and depth-check branches mid-structure (mixed [] and {} at the cap)
    '[' * 2047 + '{}' + ']' * 2047,
    '[' * 2048 + '1' + ']' * 2048,
    '{' + '"a":' * 2047 + '1' + '}' * 2047,
    '{' + '"a":' * 2048 + '1' + '}' * 2048,
    '{' + '"a":' * 2049 + '1' + '}' * 2049,
    # alternating array/object nesting across the cap boundary
    ('[{"a":' * 1024) + '1' + ('}]' * 1024),
    ('[{"a":' * 1025) + '1' + ('}]' * 1025),
    ('[{"a":' * 1026) + '1' + ('}]' * 1026),
    # depth boundaries with empty containers at the bottom
    '[' * 2047 + '[]' + ']' * 2047,
    '[' * 2048 + '[]' + ']' * 2048,
    '[' * 2049 + '[]' + ']' * 2049,
    '[' * 2048 + '{}' + ']' * 2048,
    '[' * 2049 + '{}' + ']' * 2049,
    # depth boundaries with malformed leaf at the bottom
    '[' * 2047 + ',' + ']' * 2047,
    '[' * 2048 + ',' + ']' * 2048,
    '[' * 2049 + ',' + ']' * 2049,
    # unclosed deep nesting (depth-check at EOF)
    '[' * 2047, '[' * 2048, '[' * 2049,
    '{' + '"a":' * 2047, '{' + '"a":' * 2048, '{' + '"a":' * 2049,
    ('[{"a":' * 1024), ('[{"a":' * 1025), ('[{"a":' * 1026),
    # extra closers deep (depth underflow branch)
    ']' * 2047, ']' * 2048, ']' * 2049, ']' * 2050,
    '}' * 2047, '}' * 2048, '}' * 2049, '}' * 2050,
    ']}]}' * 512, '}]}]' * 512,
    # ---- NEW: number lexing state-machine edges (sign/exponent transitions)
    '[1E+1]', '[1E-1]', '[1e+01]', '[1e-01]', '[1E+01]', '[1E-01]',
    '[-0.0e-0]', '[-0.0E+0]', '[+0.0e0]', '[0.0e+00]', '[0.0E-00]',
    '[1e01]', '[1E01]', '[1e-01]', '[1E+01]',
    '[0e0]', '[0E0]', '[0e+0]', '[0e-0]', '[-0e0]', '[-0E+0]',
    # partial number states at EOF (each transition boundary)
    '1.', '1.0', '1.0e', '1.0e+', '1.0e-', '1.0e0', '1.0e+0', '1.0e-0',
    '-0.', '-0.0', '-0.0e', '-0.0e+', '-0.0e-', '-0.0e0',
    '0.', '0.0', '0.0e', '0.0e+', '0.0e-', '0.0e0',
    '[1.]', '[1.e]', '[1.e+]', '[1.e-]', '[1.e0]', '[1.e+0]', '[1.e-0]',
    '[-.]', '[-.e]', '[-.e0]', '[+.]', '[+.e]', '[+.e0]',
    # ---- NEW: string state-machine edges (escape dispatch after backslash)
    '"\\', '"\\\\', '"\\\\\\', '"\\u', '"\\u0', '"\\u00', '"\\u000',
    '"\\u0000', '"\\u0000x', '"\\u0000\\', '"\\u0000\\u',
    # every simple escape char at EOF (escape-char dispatch)
    '"\\"', '"\\\\', '"\\/', '"\\b', '"\\f', '"\\n', '"\\r', '"\\t',
    '"\\"', '"\\a', '"\\e', '"\\v', '"\\0', '"\\1', '"\\9',
    # ---- NEW: object/array member parsing edges (colon/comma states)
    '{"a":1,"b":2,"c":3}', '{"a":1,"b":2,}', '{"a":1,,"b":2}',
    '{"a"::1}', '{"a"::}', '{"a":1:2}', '{"a":1,:"b":2}',
    '[1,2,3]', '[1,2,]', '[1,,2]', '[1,,,2]', '[,1]', '[,,1]',
    '{"a":}', '{"a":,}', '{"a":,"b":1}', '{"a":1,"b":}',
    '{"a":1,"b":,"c":2}',
    # ---- NEW: whitespace inside all structural positions
    '[\t1\t]', '[\n1\n]', '[\r1\r]', '[ 1 ]',
    '{\t"a"\t:\t1\t}', '{\n"a"\n:\n1\n}', '{\r"a"\r:\r1\r}',
    '{\t"a":1\t,\t"b":2\t}', '[\t1\t,\t2\t]',
    '{"a"\t:\t1}', '{"a"\n:\n1}', '{"a"\r:\r1}',
    # ---- NEW: keyword parsing edges (each char position at EOF)
    't', 'tr', 'tru', 'true',
    'f', 'fa', 'fal', 'fals', 'false',
    'n', 'nu', 'nul', 'null',
    '[t', '[tr', '[tru', '[true', '[f', '[fa', '[fal', '[fals', '[false',
    '[n', '[nu', '[nul', '[null',
    '{"a":t', '{"a":tr', '{"a":tru', '{"a":true',
    '{"a":f', '{"a":fa', '{"a":fal', '{"a":fals', '{"a":false',
    '{"a":n', '{"a":nu', '{"a":nul', '{"a":null',
    # ---- NEW: leading-zero and sign edge cases in value position
    '[0]', '[-0]', '[+0]', '[00]', '[-00]', '[+00]',
    '[0.0]', '[-0.0]', '[+0.0]', '[00.0]', '[000.0]',
    '[0e0]', '[-0e0]', '[+0e0]', '[00e0]', '[000e0]',
    '{"a":0}', '{"a":-0}', '{"a":+0}', '{"a":00}', '{"a":-00}',
    # ---- NEW: top-level dispatch after leading whitespace for all tokens
    ' \t\r\ntrue', ' \t\r\nfalse', ' \t\r\nnull', ' \t\r\n1',
    ' \t\r\n"a"', ' \t\r\n{}', ' \t\r\n[]',
    '\t{}', '\n{}', '\r{}', ' \t[]', '\n[]', '\r[]',
    # ---- NEW: invalid leading bytes / non-token starts
    '\x00', '[\x00]', '{\x00}', '"\x00"',
    '\x80', '\x81', '\x9f', '\xa0', '\xbf', '\xc0', '\xc1',
    '\xf8', '\xf9', '\xfa', '\xfb', '\xfc', '\xfd', '\xfe', '\xff',
    '[\x80]', '{\x80}', '"\x80"',
    # ---- NEW: unterminated at every structural position
    '[', '{', '["', '{"', '["a', '{"a', '["a"', '{"a"',
    '["a":', '{"a":', '["a":1', '{"a":1', '["a",', '{"a":,',
    '["a",1', '{"a":1,', '["a",1,', '{"a":1,"b"',
    # ---- NEW: extra tokens after complete value at every level
    '{}x', '[]x', 'truex', 'falsex', 'nullx', '1x', '"a"x',
    '[{}x]', '[[]x]', '[truex]', '[1x]', '["a"x]',
    '{"a":{}x}', '{"a":[]x}', '{"a":truex}', '{"a":1x}', '{"a":"b"x}',
    # ---- NEW: comma/colon immediately at EOF after key/value
    '{"a"', '{"a":', '{"a":1', '{"a":1,', '{"a":1,"b"',
    '[1', '[1,', '[1,2', '["a"', '["a",', '["a","b"',
    # ---- NEW: mixed-depth malformed with whitespace
    '[ \t{ "a" : \n1 \r} ]', '[\n[\r[\t1\t]\r]\n]',
    '{ "a" : [ 1 , 2 ] , "b" : { "c" : 3 } }',
])


# ---------- top-level combination ----------

_valid = st.one_of(
    _value,
    _deep,
    _deep_obj,
    st.sampled_from(["{}", "[]", "true", "false", "null", "0", "-0",
                     '""', '{"":""}', '[[],{}]', '[{},[]]']),
)

strategy = st.one_of(_valid, _malformed).map(lambda s: s if isinstance(s, str) else str(s))