from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4().map(lambda h: "\\u" + h),
    _hex4().map(lambda h: "\\u" + h),
    st.sampled_from(["\\ud800", "\\udfff", "\\uD834", "\\uDD1E", "\\u0000"]),
    st.tuples(
        st.sampled_from(["\\ud800", "\\ud834", "\\udbff"]),
        st.sampled_from(["\\udc00", "\\udd1e", "\\udfff"]),
    ).map(lambda t: t[0] + t[1]),
    st.sampled_from(["\\ud800\\u0041", "\\udc00", "\\udfffx", "\\uD834\\uDD1E"]),
)

_safe = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x7E,
    blacklist_characters='"\\',
).map(lambda c: c)

_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

_unicode_char = st.characters(min_codepoint=0x80, max_codepoint=0x2FFF)

_str_piece = st.one_of(_safe, _escapes, _raw_control, _unicode_char)

_string_body = st.lists(_str_piece, min_size=0, max_size=8).map(lambda xs: "".join(xs))

def _quoted(body):
    return '"' + body + '"'

_valid_string = _string_body.map(_quoted)

# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.just("00"),
    st.just("01"),
    st.just("007"),
)

_frac = st.one_of(
    st.just(""),
    st.integers(min_value=0, max_value=10**12).map(lambda n: "." + str(n)),
    st.just("."),
)

_exp = st.one_of(
    st.just(""),
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        st.integers(min_value=0, max_value=10**4).map(str),
    ).map(lambda t: "".join(t)),
    st.sampled_from(["e309", "E309", "e-309", "e999", "e308", "e+00", "e01"]),
)

_sign = st.one_of(st.just(""), st.just("-"))

_valid_number = st.tuples(_sign, _int_part, _frac, _exp).map(lambda t: "".join(t))

_bad_number = st.sampled_from([
    "-", "+1", ".5", "-.5", "+", "1.2.3", "--1", "1e", "1e+", "0x", "1..2",
])

_number = st.one_of(_valid_number, _bad_number)

# ---------- literals ----------

_literal = st.one_of(
    st.just("true"),
    st.just("false"),
    st.just("null"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
)

# ---------- whitespace ----------

_ws = st.one_of(
    st.just(""),
    st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t ", "\x00"]),
).map(str)

# ---------- recursive structure ----------

_json_string = st.one_of(_valid_string, _literal, _number)

def _make_obj(pairs):
    if not pairs:
        return "{}"
    inner = ",".join(k + ":" + v for (k, v) in pairs)
    return "{" + inner + "}"

def _make_arr(items):
    if not items:
        return "[]"
    return "[" + ",".join(items) + "]"

_pair = st.tuples(_valid_string, _json_string).map(lambda t: (t[0], t[1]))

_obj = st.lists(_pair, min_size=0, max_size=6).map(_make_obj)

_arr = st.lists(_json_string, min_size=0, max_size=6).map(_make_arr)

_bad_obj = st.one_of(
    st.just("{"),
    st.just("}"),
    st.just('{"a"}'),
    st.just('{"a":}'),
    st.just('{"a":1,}'),
    st.just('{"a":1,,}'),
    st.just('{a:1}'),
    st.just("{'a':1}"),
    st.just('{"a":1'),
    st.just('{"a" : 1 , }'),
    st.just('{"a":1 "b":2}'),
    st.just('{"a"::1}'),
)

_bad_arr = st.one_of(
    st.just("["),
    st.just("]"),
    st.just("[1,]"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just("[1"),
    st.just("[1 2]"),
    st.just("[[1,]"),
    st.just("[1]]"),
)

# ---------- deep nesting near the ~1000 limit ----------

def _deep(depth, kind):
    if kind == "arr":
        return "[" * depth + "]" * depth
    else:
        return '{"a":' * depth + "1" + "}" * depth

_deep_nesting = st.one_of(
    st.integers(min_value=990, max_value=1002).map(lambda d: _deep(d, "arr")),
    st.integers(min_value=990, max_value=1002).map(lambda d: _deep(d, "obj")),
    st.integers(min_value=0, max_value=1000).map(lambda d: _deep(d, "arr")),
    st.integers(min_value=990, max_value=1002).map(lambda d: "[" * d),
    st.integers(min_value=990, max_value=1002).map(lambda d: "[" * d + "]" * (d - 1)),
    st.integers(min_value=990, max_value=1002).map(lambda d: '{"a":' * d),
    st.integers(min_value=990, max_value=1002).map(lambda d: "[" * d + "}" * d),
)

# ---------- top level ----------

_json_value = st.recursive(
    _json_string,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=6).map(_make_arr),
        st.lists(
            st.tuples(_valid_string, children), min_size=0, max_size=6
        ).map(_make_obj),
    ),
    max_leaves=20,
)

_bad_toplevel = st.one_of(
    _bad_number,
    _bad_obj,
    _bad_arr,
    st.just(""),
    st.just("   "),
    st.just('"unterminated'),
    st.just("'single'"),
    st.just("tru"),
    st.just("nul"),
    st.just("fals"),
    st.just('"\\x41"'),
    st.just('"\\u12"'),
    st.just('"\\uZZZZ"'),
    st.just("\x00"),
    st.just("\ufeff"),
    st.just("[]extra"),
    st.just("1abc"),
    st.just("truex"),
    st.just("nullnull"),
    st.just('"\\u"'),
    st.just('"a"b'),
)

_bom = st.one_of(st.just(""), st.just("\ufeff"))

_trailer = st.one_of(
    st.just(""),
    st.just(" \n\t "),
    st.just(" garbage"),
    st.just("\x00"),
    st.just("1 2"),
    st.just("abc"),
    st.just("{}[]"),
    st.just("\ufeff"),
)

def _wrap(v):
    return _bom + v + _trailer

_toplevel_valid = st.tuples(_bom, _json_value, _trailer).map(lambda t: t[0] + t[1] + t[2])
_toplevel_deep = st.tuples(_bom, _deep_nesting, _trailer).map(lambda t: t[0] + t[1] + t[2])
_toplevel_bad = st.tuples(_bom, _bad_toplevel, _trailer).map(lambda t: t[0] + t[1] + t[2])

_toplevel_string = st.tuples(_bom, _valid_string, _trailer).map(lambda t: "".join(t))

_ws_heavy = st.tuples(
    st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t ", ""]),
    _json_value,
    st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t ", ""]),
).map(lambda t: t[0] + t[1] + t[2])

_multi_value = st.lists(_json_value, min_size=2, max_size=4).map(
    lambda xs: " ".join(xs)
)

# ---------- targeted branch-coverage improvements ----------

_number_edges = st.one_of(
    st.sampled_from([
        "0", "-0", "0.0", "-0.0", "0e0", "0E0", "0e+0", "0e-0",
        "1e308", "1e309", "-1e309", "1e-308", "1e-324", "1e-325",
        "1E+308", "1E-308", "1.7976931348623157e308",
        "1.7976931348623159e308",
        "00", "-00", "01", "-01", "0.5e1", "123456789012345678901234567890",
        "1e999999999999999999999", "1e-999999999999999999999",
        "-", "-.", "-.0", ".0", ".e1", "1.", "1.e1", "1e", "1e+", "1e-",
        "+0", "+1", "++1", "-+1", "1_000", "0x1", "0b1", "0o1",
        "1.2.3", "1..2", "1e1e1", ".", "e1", "E1",
    ]),
    st.tuples(
        st.sampled_from(["", "-", "+", "--", "-+"]),
        st.sampled_from(["0", "1", "00", "01", "10", "007", "999"]),
        st.sampled_from(["", ".", ".0", ".5", ".999", ".000"]),
        st.sampled_from(["", "e", "E", "e+", "e-", "E+", "E-", "e0", "e-0", "e+0"]),
    ).map(lambda t: "".join(t)),
)

_string_edges = st.one_of(
    st.sampled_from([
        '""', '"a"', '"\\""', '"\\\\"', '"\\/"', '"\\b"', '"\\f"',
        '"\\n"', '"\\r"', '"\\t"', '"\\u0000"', '"\\u0041"', '"\\uFFFF"',
        '"\\uD834\\uDD1E"', '"\\uD834"', '"\\uDD1E"', '"\\uD834x"',
        '"\\uD834\\uD834"', '"\\uD834\\u0041"', '"\\u"', '"\\u1"',
        '"\\u12"', '"\\u123"', '"\\u12345"', '"\\uZZZZ"', '"\\x41"',
        '"\\U0041"', '"\\u{41}"', '"\\', '"abc', '"abc\\"',
        '"\\u0000\\u0000"', '"\\u0000x"', '"x\\u0000"',
        '"\x00"', '"\x01"', '"\x1f"', '"\x7f"', '"\t"', '"\n"', '"\r"',
        '"\\uD800"', '"\\uDBFF"', '"\\uDC00"', '"\\uDFFF"',
    ]),
    st.lists(
        st.one_of(
            _safe,
            st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n",
                             "\\r", "\\t", "\\u0041", "\\uD834\\uDD1E",
                             "\\uD834", "\\uDD1E", "\\u", "\\x"]),
            st.just("\\"),
        ),
        min_size=0, max_size=6,
    ).map(lambda xs: '"' + "".join(xs) + '"'),
)

_struct_edges = st.one_of(
    st.sampled_from([
        "{}", "[]", "[[]]", "[{}]", "{{}}", '{"a":{}}', '{"a":[]}',
        "[[[[]]]]", '{"a":{"b":{"c":{}}}}',
        '{"":""}', '{"":1}', '{"a":null}', '{"a":true}', '{"a":false}',
        "[null]", "[true,false]", "[1,2,3]", '{"a":1,"b":2}',
        '{"a" : 1}', '{ "a" : 1 }', '[ 1 , 2 ]',
        "[,]", "[1,]", "[,1]", "[1,,2]", "[1,2,]",
        '{"a":1,}', '{,}', '{"a":1,,"b":2}', '{"a"}', '{"a":}',
        '{"a":1 "b":2}', '{"a"::1}', '{:1}', '{"a":1}}',
        "[[1,]", "[1]]", "[1 2]", "[1;2]", '{"a";1}',
        "{}extra", "[]extra", "{{}}", "[[[]]]",
    ]),
    st.recursive(
        st.sampled_from(["{}", "[]", "null", "true", "false", "0", '""']),
        lambda c: st.one_of(
            st.tuples(st.just("["), c, st.just("]")).map(lambda t: t[0] + t[1] + t[2]),
            st.tuples(st.just('{"a":'), c, st.just("}")).map(lambda t: t[0] + t[1] + t[2]),
            st.tuples(st.just("["), c, st.just(","), c, st.just("]")).map(lambda t: "".join(t)),
            st.tuples(st.just('{"a":'), c, st.just(',"b":'), c, st.just("}")).map(lambda t: "".join(t)),
        ),
        max_leaves=6,
    ),
)

_literal_edges = st.one_of(
    st.sampled_from([
        "true", "false", "null", "True", "FALSE", "NULL",
        "tru", "fals", "nul", "t", "f", "n", "truex", "nullnull",
        "nan", "NaN", "NAN", "inf", "Infinity", "-Infinity", "+Infinity",
        "infinity", "Inf", "-Inf", "+Inf",
    ]),
)

_ws_edges = st.one_of(
    st.sampled_from(["", " ", "\t", "\n", "\r", "\x00", "\ufeff",
                     "  \t\n\r ", "\ufeff ", " \ufeff"]),
)

_targeted = st.one_of(
    _number_edges,
    _string_edges,
    _struct_edges,
    _literal_edges,
    _ws_edges,
    st.tuples(_bom, _number_edges, _trailer).map(lambda t: "".join(t)),
    st.tuples(_bom, _string_edges, _trailer).map(lambda t: "".join(t)),
    st.tuples(_bom, _struct_edges, _trailer).map(lambda t: "".join(t)),
    st.tuples(_bom, _literal_edges, _trailer).map(lambda t: "".join(t)),
    st.tuples(
        st.sampled_from(["", " ", "\t", "\n", "\r", "  "]),
        _struct_edges,
        st.sampled_from(["", " ", "\t", "\n", "\r", "  "]),
    ).map(lambda t: "".join(t)),
)

# ---------- improved structured near-miss generators ----------

_truncate = st.tuples(
    _json_value,
    st.integers(min_value=0, max_value=8),
).map(lambda t: t[0][: max(0, len(t[0]) - t[1])])

_stray_char = st.sampled_from(['"', "\\", ",", ":", "[", "]", "{", "}", "x", "\x00", "\x7f", "\ufeff"])

_mutate = st.tuples(
    _json_value,
    st.integers(min_value=0, max_value=10**6),
    _stray_char,
).map(lambda t: (lambda s, i, c: s[: i % (len(s) + 1)] + c + s[i % (len(s) + 1):])(t[0], t[1], t[2]))

_near_miss = st.one_of(
    _truncate,
    _mutate,
    _json_value.map(lambda s: s[:-1] if s and s[-1] in "]} " else s),
    st.tuples(_json_value, _stray_char).map(lambda t: t[0] + t[1]),
    st.tuples(_stray_char, _json_value).map(lambda t: t[0] + t[1]),
)

# ---------- NEW: deep structural near-misses and localized corruptions ----------
# The remaining branch gap is in deep nesting error paths and structural
# corruption at intermediate depths. Generate valid-looking nested structures
# with a single corruption injected at a random depth.

def _deep_corrupt(depth, kind, corruption):
    """Build a nested structure of `depth` levels with one corruption."""
    if kind == "arr":
        opens = ["["] * depth
        closes = ["]"] * depth
    else:
        opens = ['{"a":'] * depth
        closes = ["}"] * depth
    # choose a position to corrupt (0..depth-1)
    pos = corruption % depth
    if kind == "arr":
        # corrupt by removing a close or injecting a stray
        if pos % 3 == 0:
            closes = closes[:pos] + closes[pos + 1:]  # drop a close
        elif pos % 3 == 1:
            opens = opens[:pos] + ["[,"] + opens[pos:]  # stray comma
        else:
            closes = closes[:pos] + ["]x"] + closes[pos:]  # stray char
        return "".join(opens) + "".join(closes)
    else:
        if pos % 3 == 0:
            closes = closes[:pos] + closes[pos + 1:]
        elif pos % 3 == 1:
            opens = opens[:pos] + ['{"a":,'] + opens[pos:]
        else:
            closes = closes[:pos] + ["}x"] + closes[pos:]
        return "".join(opens) + "1" + "".join(closes)

_deep_corrupt_s = st.tuples(
    st.integers(min_value=2, max_value=50),
    st.sampled_from(["arr", "obj"]),
    st.integers(min_value=0, max_value=10**6),
).map(lambda t: _deep_corrupt(t[0], t[1], t[2]))

# Deep nested structures with mixed bracket types at random depths
_deep_mixed = st.tuples(
    st.integers(min_value=2, max_value=40),
    st.integers(min_value=0, max_value=10**6),
).map(lambda t: (
    lambda d, seed: (
        "".join(("[", '{"a":')[i % 2] for i in range(d))
        + "1"
        + "".join(("]", "}")[i % 2] for i in range(d - (seed % 2)))
    )
)(t[0], t[1]))

# Deep nesting with a truncation near the limit
_deep_trunc = st.tuples(
    st.integers(min_value=990, max_value=1002),
    st.integers(min_value=0, max_value=20),
    st.sampled_from(["arr", "obj"]),
).map(lambda t: _deep(t[0], t[2])[: max(0, len(_deep(t[0], t[2])) - t[1])])

_deep_edges = st.one_of(
    _deep_corrupt_s,
    _deep_mixed,
    _deep_trunc,
    # deep with stray char appended at various points
    st.tuples(
        st.integers(min_value=990, max_value=1002),
        st.integers(min_value=0, max_value=10**6),
        st.sampled_from(["arr", "obj"]),
    ).map(lambda t: (lambda s, seed: s[: seed % (len(s) + 1)] + "," + s[seed % (len(s) + 1):])(_deep(t[0], t[2]), t[1])),
)

# Localized corruption in otherwise-valid nested structures at moderate depth
_moderate_nested = st.recursive(
    st.sampled_from(["0", '""', "true", "null", "{}", "[]"]),
    lambda c: st.one_of(
        st.tuples(st.just("["), c, st.just("]")).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(st.just('{"k":'), c, st.just("}")).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(st.just("["), c, st.just(","), c, st.just("]")).map(lambda t: "".join(t)),
        st.tuples(st.just('{"k":'), c, st.just(',"j":'), c, st.just("}")).map(lambda t: "".join(t)),
    ),
    max_leaves=12,
)

_corrupt_nested = st.tuples(
    _moderate_nested,
    st.integers(min_value=0, max_value=10**6),
    _stray_char,
).map(lambda t: (lambda s, i, c: s[: i % (len(s) + 1)] + c + s[i % (len(s) + 1):])(t[0], t[1], t[2]))

_drop_nested = st.tuples(
    _moderate_nested,
    st.integers(min_value=0, max_value=10**6),
).map(lambda t: (lambda s, i: s[: i % (len(s) + 1)] + s[(i % (len(s) + 1)) + 1:])(t[0], t[1]))

_nested_edges = st.one_of(_corrupt_nested, _drop_nested)

# ---------- NEW: escape-sequence boundary and surrogate edge cases ----------
# Exercise the escape decoder's state machine at boundaries (truncated \u,
# invalid hex, surrogate pair boundaries, high/low surrogate ordering).

_escape_edges2 = st.one_of(
    st.sampled_from([
        '"\\u0"', '"\\u00"', '"\\u000"', '"\\u0000"', '"\\u00000"',
        '"\\uD7FF"', '"\\uD800"', '"\\uDBFF"', '"\\uDC00"', '"\\uDFFF"',
        '"\\uE000"', '"\\uFFFF"',
        '"\\uD800\\uDC00"', '"\\uDBFF\\uDFFF"', '"\\uDC00\\uD800"',
        '"\\uD800\\uD800"', '"\\uDC00\\uDC00"', '"\\uD800\\uDBFF"',
        '"\\uD800\\uE000"', '"\\uD800x"', '"x\\uD800"',
        '"\\uD800\\uD800\\uDC00"', '"\\uD800\\uDC00\\uDC00"',
        '"\\uD800\\n"', '"\\uD800\\u"', '"\\uD800\\"',
        '"\\u0000\\uD800"', '"\\uD800\\u0000"',
        '"\\uABCD"', '"\\uabcd"', '"\\uAbCd"',
        '"\\u00G0"', '"\\u0G00"', '"\\uG000"',
        '"\\u"', '"\\u\\u"', '"\\u\\"',
        '"\\u0041\\u0042"', '"\\u0041\\uD834\\uDD1E"',
        '"\\ud834\\udd1e"', '"\\uD834\\uDD1E\\uD834\\uDD1E"',
    ]),
    st.tuples(
        st.sampled_from(["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\u0041", "\\u0000"]),
        st.sampled_from(["\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF", "\\u0041", "\\u0000"]),
    ).map(lambda t: '"' + t[0] + t[1] + '"'),
)

# ---------- NEW: number/string boundary combinations at top level ----------
# Combine number edges with structural context to hit parse-then-reject paths.

_number_struct = st.tuples(
    st.sampled_from(["[", "[ ", '{"a":', '{"a": ', '{"a":[', '{"a":[']),
    _number_edges,
    st.sampled_from(["]", " ]", "}", " }", "]}", "] }", ",]", ", }"]),
).map(lambda t: "".join(t))

_string_struct = st.tuples(
    st.sampled_from(["[", "[ ", '{"a":', '{"a": ', '{"a":[', '{"a":[']),
    _string_edges,
    st.sampled_from(["]", " ]", "}", " }", "]}", "] }", ",]", ", }"]),
).map(lambda t: "".join(t))

_context_edges = st.one_of(_number_struct, _string_struct)

# ---------- final strategy ----------

strategy = st.one_of(
    _toplevel_valid,
    _toplevel_deep,
    _toplevel_bad,
    _toplevel_string,
    _ws_heavy,
    _multi_value,
    _targeted,
    _near_miss,
    _deep_edges,
    _nested_edges,
    _escape_edges2,
    _context_edges,
)