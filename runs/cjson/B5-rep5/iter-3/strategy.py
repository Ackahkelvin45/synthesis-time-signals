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
)

_bad_arr = st.one_of(
    st.just("["),
    st.just("]"),
    st.just("[1,]"),
    st.just("[,]"),
    st.just("[1,,2]"),
    st.just("[1"),
    st.just("[1 2]"),
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
)

def _wrap(v):
    return _bom + v + _trailer

_toplevel_valid = st.tuples(_bom, _json_value, _trailer).map(lambda t: t[0] + t[1] + t[2])
_toplevel_deep = st.tuples(_bom, _deep_nesting, _trailer).map(lambda t: t[0] + t[1] + t[2])
_toplevel_bad = st.tuples(_bom, _bad_toplevel, _trailer).map(lambda t: t[0] + t[1] + t[2])

# also a few raw string-only candidates (top-level strings)
_toplevel_string = st.tuples(_bom, _valid_string, _trailer).map(lambda t: "".join(t))

# whitespace-interleaved structured JSON (valid, with optional ws around tokens)
_ws_opt = st.one_of(st.just(""), st.just(" "), st.just("\n"), st.just("\t"), st.just("\r\n"))

def _ws_json(depth):
    # build a JSON value with random whitespace between tokens
    leaf = st.one_of(_json_string, _literal, _number)
    if depth <= 0:
        return leaf
    inner = _ws_json(depth - 1)
    arr = st.tuples(
        _ws_opt,
        st.lists(inner, min_size=0, max_size=4),
        _ws_opt,
    ).map(lambda t: "[" + t[0] + (("," + _ws_opt.sample() if False else ",")).join(t[1]) + t[2] + "]")
    # simpler: use hypothesis lists joined with commas
    arr2 = st.lists(inner, min_size=0, max_size=4).map(
        lambda xs: "[" + ",".join(xs) + "]"
    )
    obj = st.lists(
        st.tuples(_valid_string, inner), min_size=0, max_size=4
    ).map(lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}")
    return st.one_of(leaf, arr2, obj)

_ws_json_value = _ws_json(3)

_toplevel_ws_json = st.tuples(_bom, _ws_json_value, _trailer).map(
    lambda t: t[0] + t[1] + t[2]
)

# improved: whitespace-interleaved JSON with ws between every token
_ws_any = st.one_of(
    st.just(""), st.just(" "), st.just("\t"), st.just("\n"), st.just("\r"),
    st.just("  "), st.just("\r\n"), st.just(" \t\n "),
)

def _ws_token(s):
    return st.tuples(_ws_any, st.just(s), _ws_any).map(lambda t: t[0] + t[1] + t[2])

def _ws_json2(depth):
    leaf = st.one_of(
        _ws_token(_valid_string),
        _ws_token(_literal),
        _ws_token(_number),
    )
    if depth <= 0:
        return leaf
    inner = _ws_json2(depth - 1)
    arr = st.lists(inner, min_size=0, max_size=4).map(
        lambda xs: "[" + ",".join(xs) + "]"
    )
    obj = st.lists(
        st.tuples(_valid_string, inner), min_size=0, max_size=4
    ).map(lambda ps: "{" + ",".join(k + ":" + v for (k, v) in ps) + "}")
    return st.one_of(leaf, arr, obj)

_toplevel_ws_json2 = st.tuples(_bom, _ws_json2(3), _trailer).map(
    lambda t: t[0] + t[1] + t[2]
)

strategy = st.one_of(
    _toplevel_valid,
    _toplevel_deep,
    _toplevel_bad,
    _toplevel_string,
    _toplevel_ws_json,
    _toplevel_ws_json2,
)