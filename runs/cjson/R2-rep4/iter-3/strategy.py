from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_hex = st.sampled_from("0123456789abcdefABCDEF")

def _hex4():
    return st.tuples(_hex, _hex, _hex, _hex).map(lambda t: "".join(t))

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    _hex4().map(lambda h: "\\u" + h),
    # surrogate escapes (some lone -> rejected, some paired -> ok)
    _hex4().map(lambda h: "\\u" + h),  # includes D800-DFFF range via hex
    st.sampled_from(["\\ud800", "\\udfff", "\\uD834", "\\uDD1E", "\\u0000"]),
    # surrogate pairs (valid) and lone surrogates (invalid) for deeper coverage
    st.tuples(
        st.sampled_from(["\\ud800", "\\ud834", "\\udbff"]),
        st.sampled_from(["\\udc00", "\\udd1e", "\\udfff"]),
    ).map(lambda t: t[0] + t[1]),
    st.sampled_from(["\\ud800\\u0041", "\\udc00", "\\udfffx", "\\uD834\\uDD1E"]),
)

# safe codepoints: printable ASCII minus " and backslash
_safe = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x7E,
    blacklist_characters='"\\',
).map(lambda c: c)

# raw control bytes / NUL allowed inside strings by this parser
_raw_control = st.sampled_from(["\x00", "\x01", "\x09", "\x0a", "\x0d", "\x1f", "\x7f"])

# unicode printable non-ascii
_unicode_char = st.characters(min_codepoint=0x80, max_codepoint=0x2FFF)

_str_piece = st.one_of(_safe, _escapes, _raw_control, _unicode_char)

# a well-formed-ish string body (may include raw controls / escapes)
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

# malformed numbers the parser rejects
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
    # pairs: list of (key, val) strings
    if not pairs:
        return "{}"
    inner = ",".join(k + ":" + v for (k, v) in pairs)
    return "{" + inner + "}"

def _make_arr(items):
    if not items:
        return "[]"
    return "[" + ",".join(items) + "]"

# composite for objects: key string + value
_pair = st.tuples(_valid_string, _json_string).map(lambda t: (t[0], t[1]))

_obj = st.lists(_pair, min_size=0, max_size=6).map(_make_obj)

_arr = st.lists(_json_string, min_size=0, max_size=6).map(_make_arr)

# malformed object/array variants
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
    # mismatched / unbalanced deep nesting to hit error paths
    st.integers(min_value=990, max_value=1002).map(lambda d: "[" * d),
    st.integers(min_value=990, max_value=1002).map(lambda d: "[" * d + "]" * (d - 1)),
    st.integers(min_value=990, max_value=1002).map(lambda d: '{"a":' * d),
    st.integers(min_value=990, max_value=1002).map(lambda d: "[" * d + "}" * d),
)

# ---------- top level ----------

# recursive JSON value
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

# malformed top-level fragments
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

# BOM prefix
_bom = st.one_of(st.just(""), st.just("\ufeff"))

# trailing content (accepted, ignored)
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

# also a few raw string-only candidates (top-level strings)
_toplevel_string = st.tuples(_bom, _valid_string, _trailer).map(lambda t: "".join(t))

# whitespace-heavy wrappers to exercise skip_ws paths
_ws_heavy = st.tuples(
    st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t ", ""]),
    _json_value,
    st.sampled_from([" ", "\t", "\n", "\r", "  ", "\n\t ", ""]),
).map(lambda t: t[0] + t[1] + t[2])

# multi-value streams (parser may accept first and ignore rest)
_multi_value = st.lists(_json_value, min_size=2, max_size=4).map(
    lambda xs: " ".join(xs)
)

# ---------- targeted branch-coverage improvements ----------
# The branch coverage gap suggests error/edge branches in number, string,
# escape, and structural parsing are under-exercised. Add focused generators
# that hit specific decision points deterministically.

# number edge cases: leading zeros, lone minus, exponent boundaries, overflow
_number_edges = st.one_of(
    st.sampled_from([
        "0", "-0", "0.0", "-0.0", "0e0", "0E0", "0e+0", "0e-0",
        "1e308", "1e309", "-1e309", "1e-308", "1e-324", "1e-325",
        "1E+308", "1E-308", "1.7976931348623157e308",
        "1.7976931348623159e308",  # overflow
        "00", "-00", "01", "-01", "0.5e1", "123456789012345678901234567890",
        "1e999999999999999999999", "1e-999999999999999999999",
        "-", "-.", "-.0", ".0", ".e1", "1.", "1.e1", "1e", "1e+", "1e-",
        "+0", "+1", "++1", "-+1", "1_000", "0x1", "0b1", "0o1",
        "1.2.3", "1..2", "1e1e1", ".", "e1", "E1",
    ]),
    # random int with optional frac/exp in combinatorial ways
    st.tuples(
        st.sampled_from(["", "-", "+", "--", "-+"]),
        st.sampled_from(["0", "1", "00", "01", "10", "007", "999"]),
        st.sampled_from(["", ".", ".0", ".5", ".999", ".000"]),
        st.sampled_from(["", "e", "E", "e+", "e-", "E+", "E-", "e0", "e-0", "e+0"]),
    ).map(lambda t: "".join(t)),
)

# string/escape edges that exercise the escape decoder's branches
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
    # random escape soup
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

# structural edges: empty/nested/adjacent commas/brackets/colons
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
    # random nested combos
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

# literal edges: partial/case/whitespace-prefixed
_literal_edges = st.one_of(
    st.sampled_from([
        "true", "false", "null", "True", "FALSE", "NULL",
        "tru", "fals", "nul", "t", "f", "n", "truex", "nullnull",
        "nan", "NaN", "NAN", "inf", "Infinity", "-Infinity", "+Infinity",
        "infinity", "Inf", "-Inf", "+Inf",
    ]),
)

# whitespace-only and BOM-only edge cases
_ws_edges = st.one_of(
    st.sampled_from(["", " ", "\t", "\n", "\r", "\x00", "\ufeff",
                     "  \t\n\r ", "\ufeff ", " \ufeff"]),
)

# combine the new targeted generators
_targeted = st.one_of(
    _number_edges,
    _string_edges,
    _struct_edges,
    _literal_edges,
    _ws_edges,
    # wrap targeted pieces with BOM/trailer/whitespace
    st.tuples(_bom, _number_edges, _trailer).map(lambda t: "".join(t)),
    st.tuples(_bom, _string_edges, _trailer).map(lambda t: "".join(t)),
    st.tuples(_bom, _struct_edges, _trailer).map(lambda t: "".join(t)),
    st.tuples(_bom, _literal_edges, _trailer).map(lambda t: "".join(t)),
    # whitespace around structural edges
    st.tuples(
        st.sampled_from(["", " ", "\t", "\n", "\r", "  "]),
        _struct_edges,
        st.sampled_from(["", " ", "\t", "\n", "\r", "  "]),
    ).map(lambda t: "".join(t)),
)

strategy = st.one_of(
    _toplevel_valid,
    _toplevel_deep,
    _toplevel_bad,
    _toplevel_string,
    _ws_heavy,
    _multi_value,
    _targeted,
)